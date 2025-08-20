"""Backward compatibility module for legacy TraStrainer API."""

from typing import Dict, List

from .algorithm import run_trastrainer
from .data_structures import TraceData
from .preprocessor import MetricProcessor, TraceProcessor


# Legacy function aliases for backward compatibility
def tra_strainer(
    traces: Dict[str, List[Dict]], metrics: Dict, budget_sample_rate: float
) -> List[str]:
    """
    Legacy function to maintain compatibility with existing code.

    Args:
        traces: Dictionary of traces (legacy format)
        metrics: Dictionary of metrics
        budget_sample_rate: Target sampling rate

    Returns:
        List of sampled trace IDs
    """
    # Convert legacy trace format to new format if needed
    if traces and isinstance(next(iter(traces.values())), list):
        # Convert to TraceData format
        trace_data = {}
        for trace_id, spans in traces.items():
            if spans and isinstance(spans[0], dict):
                # Legacy format - convert dictionaries to TraceSpans
                from .data_structures import TraceSpan

                trace_spans = []
                for span_dict in spans:
                    span = TraceSpan(
                        trace_id=trace_id,
                        span_id=span_dict.get("SpanID", ""),
                        parent_id=span_dict.get("ParentID", "root"),
                        service_name=span_dict.get("PodName", ""),
                        operation_name=span_dict.get("OperationName", ""),
                        start_time=span_dict.get("StartTime", ""),
                        end_time=span_dict.get("EndTime", ""),
                        duration=int(span_dict.get("Duration", 0)),
                        status=span_dict.get("status", "success"),
                    )
                    trace_spans.append(span)
                trace_data[trace_id] = TraceData(trace_id=trace_id, spans=trace_spans)
        traces = trace_data

    return run_trastrainer(traces, metrics, budget_sample_rate)


# Legacy function aliases
process_metrics = MetricProcessor.process_metrics
read_traces = TraceProcessor.read_traces

# Legacy imports for existing code
from .algorithm import (
    FeatureExtractor,
    SamplingDecision,
    SamplingFilter,
    SimilarityCalculator,
)
from .algorithm import TraStrainerAlgorithm as TraStrainer
from .preprocessor import TimeUtils

# Make key functions available at package level
__all__ = [
    "tra_strainer",
    "process_metrics",
    "read_traces",
    "TraStrainer",
    "TimeUtils",
    "SimilarityCalculator",
    "FeatureExtractor",
    "SamplingFilter",
    "SamplingDecision",
]
