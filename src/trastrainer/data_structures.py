"""Data structures for TraStrainer algorithm."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class TraceSpan:
    """Represents a single span in a distributed trace."""

    trace_id: str
    span_id: str
    parent_id: str
    service_name: str
    operation_name: str
    start_time: str
    end_time: str
    duration: int
    status: str = "success"

    @property
    def is_root(self) -> bool:
        """Check if this span is the root of the trace."""
        return self.parent_id == "root" or self.parent_id == ""


@dataclass
class TraceData:
    """Container for trace information."""

    trace_id: str
    spans: List[TraceSpan]
    structure_vector: Optional[List[str]] = None
    feature_values: Optional[Dict[Tuple[str, str], float]] = None

    @property
    def root_span(self) -> Optional[TraceSpan]:
        """Get the root span of this trace."""
        for span in self.spans:
            if span.is_root:
                return span
        return None

    @property
    def start_time(self) -> str:
        """Get the start time of the earliest span."""
        if not self.spans:
            return ""
        return min(span.start_time for span in self.spans)

    @property
    def end_time(self) -> str:
        """Get the end time of the latest span."""
        if not self.spans:
            return ""
        return max(span.end_time for span in self.spans)


@dataclass
class MetricPoint:
    """Represents a single metric measurement point."""

    timestamp: str
    value: float


@dataclass
class MetricData:
    """Container for metric time series data."""

    service_name: str
    metric_name: str
    data_points: List[MetricPoint]

    @property
    def key(self) -> Tuple[str, str]:
        """Get the unique key for this metric."""
        return (self.service_name, self.metric_name)


@dataclass
class SamplingConfig:
    """Configuration for TraStrainer sampling algorithm with windowed sampling."""

    budget_sample_rate: float
    window_size: Optional[int] = None
    warm_up_size: int = 10
    checkpoints_dir: str = "./checkpoints"
    traces_per_window: Optional[int] = None  # Number of traces to process per window

    def __post_init__(self):
        """Set default window size based on sample rate if not provided."""
        if self.window_size is None:
            self.window_size = max(1, int(1 / self.budget_sample_rate))

        # Set default traces per window based on original TraStrainer logic
        if self.traces_per_window is None:
            self.traces_per_window = max(100, int(1 / self.budget_sample_rate))


@dataclass
class SamplingResult:
    """Result of trace sampling operation."""

    sampled_trace_ids: List[str]
    total_traces_processed: int
    sampling_rate_achieved: float
    execution_time: float

    @property
    def actual_sample_count(self) -> int:
        """Get the actual number of traces sampled."""
        return len(self.sampled_trace_ids)


@dataclass
class SystemMetrics:
    """System-level metrics extracted from trace data."""

    service_metrics: Dict[str, List[Dict[str, Any]]]
    resource_metrics: Dict[Tuple[str, str], List[Dict[str, Any]]]

    def get_service_spans(self, service_name: str) -> List[Dict[str, Any]]:
        """Get spans for a specific service."""
        return self.service_metrics.get(service_name, [])

    def get_resource_spans(
        self, service_name: str, resource: str
    ) -> List[Dict[str, Any]]:
        """Get resource-specific spans for a service."""
        key = (service_name, resource)
        return self.resource_metrics.get(key, [])
