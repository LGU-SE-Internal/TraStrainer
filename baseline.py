import os
import csv
import time
from random import choice, sample
from Sieve.sieve import *
from Sieve.data_process import Span, Trace
from Sieve.wtSampling import WTSampling, traceEncoding
from TraStrainer import get_seq_span, diversity_biased_filter, process_trace


def read_traces(folder_path):
    """ 读取调用链数据 """
    original_traces = {}
    traces = {}
    # 遍历文件夹中的每个CSV文件
    for filename in os.listdir(folder_path):
        if filename.endswith('.csv'):
            file_path = os.path.join(folder_path, filename)
            try:
                with open(file_path, 'r') as csv_file:
                    csv_reader = csv.DictReader(csv_file)
                    for row in csv_reader:
                        row['status'] = 'success'
                        pod_name = row['PodName'] if 'PodName' in row.keys() else row.get('ServiceName')
                        span = Span(row['TraceID'], row['SpanID'], row['ParentID'], row['StartTimeUnixNano'],
                                    float(row['Duration']), pod_name, row['OperationName'])
                        if row['TraceID'] in traces.keys():
                            original_traces[row['TraceID']].append(row)
                            traces[row['TraceID']].append(span)
                        else:
                            original_traces[row['TraceID']] = [row]
                            traces[row['TraceID']] = [span]
            except FileNotFoundError:
                pass
    processed_traces = []
    for trace_id, spans in traces.items():
        processed_traces.append(Trace(trace_id, spans))
    return original_traces, processed_traces


def correction(trace_ids, sampling_rate, result):
    sampling_number = int(round(len(trace_ids) * sampling_rate))
    while len(result) < sampling_number:
        trace_id = choice(trace_ids)
        if trace_id not in result:
            result.append(trace_id)
    if len(result) > sampling_number:
        result = result[:sampling_number]
    return result


def random_sampling(traces, sampling_rate):
    """ 随机采样 """
    trace_ids = [i for i, j in traces.items()]
    sampling_number = int(round(len(traces) * sampling_rate))
    result = sample(trace_ids, sampling_number)
    return result


def sifter_sampling(traces, sampling_rate):
    """ Sifter: Scalable Sampling for Distributed Traces, without Feature Engineering """
    # 根据结构信息计算diversity，根据diversity采样
    result = []
    history_trace_structures = []
    diversity_window = []
    time_used = []
    for trace_id, trace in traces.items():
        start_time = time.time()
        _, _, tree = process_trace(trace)
        trace_structure = get_seq_span(trace, tree)
        similarity = diversity_biased_filter(history_trace_structures, trace_structure, diversity_window)
        if similarity < sampling_rate:
            result.append(trace)
            history_trace_structures.append(trace_structure)
            end_time = time.time()
            time_used.append(end_time-start_time)
            if len(result) >= int(round(sampling_rate * len(traces))):
                break
        history_trace_structures.append(trace_structure)
    result = [i[0]['TraceID'] for i in result]
    trace_ids = [i for i, j in traces.items()]
    result = correction(trace_ids, sampling_rate, result)
    return result


def sieve_sampling(traces, sampling_rate):
    """ Sieve: Attention-based Sampling of End-to-End Trace Data in Distributed Microservice Systems """
    result = []
    time_used = []
    sieve = Sieve(tree_num=50, tree_size=128, k=50, threshold=0.3)
    for i, trace in enumerate(traces):
        start_time = time.time()
        if sieve.isSample(trace):
            result.append(trace)
        end_time = time.time()
        time_used.append(end_time - start_time)
        if len(result) >= int(round(sampling_rate * len(traces))):
            break
        # 每处理128条trace降一次维
        if i % 128 == 0:
            sieve.compact()
    result = [i.traceID for i in result]
    trace_ids = [trace.traceID for trace in traces]
    result = correction(trace_ids, sampling_rate, result)
    return result


def wt_sampling(traces, sampling_rate):
    """ Weighted Sampling of Execution Traces: Capturing More Needles and Less Hay """
    encoding_traces = traceEncoding(traces)
    res = WTSampling(encoding_traces)
    res.build_sliding_tree(sampling_rate * len(traces))
    samples = res.sampling(sampling_rate * len(traces))
    result = [traces[s.pts[0][0][0]] for s in samples]
    result = [i.traceID for i in result]
    trace_ids = [trace.traceID for trace in traces]
    result = correction(trace_ids, sampling_rate, result)
    return result
