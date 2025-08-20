#!/usr/bin/env python3
"""测试基于论文理论的TraStrainer算法实现。

验证：
1. 算法处理所有traces，不提前退出
2. 不强制限制采样率，使用非严格模式
3. 基于目标采样数量而非固定采样率
4. 计算最终实际采样率
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from trastrainer.algorithm import TraStrainerAlgorithm
from trastrainer.data_structures import SamplingConfig
from trastrainer.polar_loader import PolarDataPreprocessor


def test_paper_algorithm():
    """测试基于论文理论的算法实现。"""
    # 数据路径
    data_path = Path("test/ts1-ts-route-plan-service-request-replace-method-qtbhzt")

    print(f"Loading data from: {data_path}")
    print("=" * 60)

    # 加载数据
    preprocessor = PolarDataPreprocessor()
    traces, metrics = preprocessor.load_data(str(data_path))

    total_traces = len(traces)
    print(f"Loaded {total_traces} traces")

    # 统计normal和abnormal traces - 基于时间而不是ID
    normal_count = 0
    abnormal_count = 0
    inject_time = preprocessor.inject_time

    print(f"Injection time: {inject_time}")

    for trace_id, trace in traces.items():
        trace_start = trace.start_time
        if trace_start < inject_time.isoformat():
            normal_count += 1
        else:
            abnormal_count += 1

    print(f"Normal traces (before injection): {normal_count}")
    print(f"Abnormal traces (after injection): {abnormal_count}")
    print()

    # 测试1: 基于目标采样数量（预期采样200个traces）
    print("Test 1: Target-based sampling (target=200 traces)")
    print("-" * 50)

    config1 = SamplingConfig(target_sample_count=200, checkpoints_dir="./checkpoints")

    algorithm1 = TraStrainerAlgorithm(config1)
    result1 = algorithm1.run(traces, metrics)

    print("Target samples: 200")
    print(f"Actual samples: {result1.actual_sample_count}")
    print(f"Total processed: {result1.total_traces_processed}")
    print(f"Achieved rate: {result1.sampling_rate_achieved:.3f}")
    print(f"Execution time: {result1.execution_time:.2f}s")
    print()

    # 分析采样结果中normal和abnormal的分布
    normal_sampled = 0
    abnormal_sampled = 0

    for trace_id in result1.sampled_trace_ids:
        if trace_id in traces:
            trace_start = traces[trace_id].start_time
            if trace_start < inject_time.isoformat():
                normal_sampled += 1
            else:
                abnormal_sampled += 1

    print(f"Sampled normal traces: {normal_sampled}")
    print(f"Sampled abnormal traces: {abnormal_sampled}")
    print(
        f"Normal sampling rate: {normal_sampled / normal_count:.3f}"
        if normal_count > 0
        else "Normal sampling rate: N/A"
    )
    print(
        f"Abnormal sampling rate: {abnormal_sampled / abnormal_count:.3f}"
        if abnormal_count > 0
        else "Abnormal sampling rate: N/A"
    )
    print()

    # 测试2: 基于预算采样率（用于对比，预期采样约5%）
    print("Test 2: Rate-based sampling (rate=0.05 for comparison)")
    print("-" * 50)

    config2 = SamplingConfig(budget_sample_rate=0.05, checkpoints_dir="./checkpoints")

    algorithm2 = TraStrainerAlgorithm(config2)
    result2 = algorithm2.run(traces, metrics)

    print("Target rate: 0.05")
    print(f"Expected samples: {int(0.05 * total_traces)}")
    print(f"Actual samples: {result2.actual_sample_count}")
    print(f"Total processed: {result2.total_traces_processed}")
    print(f"Achieved rate: {result2.sampling_rate_achieved:.3f}")
    print(f"Execution time: {result2.execution_time:.2f}s")
    print()

    # 分析采样结果
    normal_sampled2 = 0
    abnormal_sampled2 = 0

    for trace_id in result2.sampled_trace_ids:
        if trace_id in traces:
            trace_start = traces[trace_id].start_time
            if trace_start < inject_time.isoformat():
                normal_sampled2 += 1
            else:
                abnormal_sampled2 += 1

    print(f"Sampled normal traces: {normal_sampled2}")
    print(f"Sampled abnormal traces: {abnormal_sampled2}")
    print(
        f"Normal sampling rate: {normal_sampled2 / normal_count:.3f}"
        if normal_count > 0
        else "Normal sampling rate: N/A"
    )
    print(
        f"Abnormal sampling rate: {abnormal_sampled2 / abnormal_count:.3f}"
        if abnormal_count > 0
        else "Abnormal sampling rate: N/A"
    )
    print()

    # 验证算法确实处理了所有traces
    print("Algorithm Validation:")
    print("-" * 50)
    print(f"Total traces available: {total_traces}")
    print(f"Test 1 processed: {result1.total_traces_processed}")
    print(f"Test 2 processed: {result2.total_traces_processed}")
    print(
        f"Processed all traces: {result1.total_traces_processed == total_traces and result2.total_traces_processed == total_traces}"
    )
    print()

    # 验证非严格模式（应该有normal和abnormal都被采样）
    print("Sampling Bias Validation:")
    print("-" * 50)
    print(f"Test 1 has normal traces: {normal_sampled > 0}")
    print(f"Test 1 has abnormal traces: {abnormal_sampled > 0}")
    print(f"Test 2 has normal traces: {normal_sampled2 > 0}")
    print(f"Test 2 has abnormal traces: {abnormal_sampled2 > 0}")

    if normal_sampled > 0 and abnormal_sampled > 0:
        print("✅ Test 1: Successfully sampled both normal and abnormal traces")
    else:
        print("❌ Test 1: Failed to sample both normal and abnormal traces")

    if normal_sampled2 > 0 and abnormal_sampled2 > 0:
        print("✅ Test 2: Successfully sampled both normal and abnormal traces")
    else:
        print("❌ Test 2: Failed to sample both normal and abnormal traces")


if __name__ == "__main__":
    test_paper_algorithm()
