"""Data preprocessing module for TraStrainer."""

import csv
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from rcabench_platform.v2.logging import logger
from treelib import Tree

from .data_structures import SystemMetrics, TraceData, TraceSpan


class TimeUtils:
    """Utility class for timestamp and datetime conversions."""

    @staticmethod
    def timestamp_to_datetime(timestamp: str) -> str:
        """Convert Unix timestamp to formatted datetime string."""
        dt_object = datetime.fromtimestamp(int(timestamp))
        return dt_object.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def future_datetime(date_string: str, minutes: int) -> str:
        """Calculate a future datetime by adding minutes to a datetime string."""
        date_obj = datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S")
        new_date_obj = date_obj + timedelta(minutes=minutes)
        return new_date_obj.strftime("%Y-%m-%d %H:%M:%S")


class MetricProcessor:
    """Process and manage system metrics data from CSV files."""

    INCLUDED_METRICS = [
        "k8s.pod.cpu.usage",
        "k8s.pod.cpu_limit_utilization",
        "k8s.pod.memory.usage",
        "k8s.pod.memory_limit_utilization",
    ]

    EXCLUDED_METRIC_PATTERNS = ["Byte", "P95", "P99", "Syscall"]

    EXCLUDED_COLUMNS = [
        "PodName",
        "ServiceName",
        "Time",
        "time",
        "TimeStamp",
        "timestamp",
    ]

    @classmethod
    def process_metrics(cls, path: str) -> Dict[Tuple[str, str], List[Dict[str, str]]]:
        """
        Extract and process metrics from CSV files.

        Args:
            path: Path to directory with CSV files OR single CSV file

        Returns:
            Dictionary mapping (service, metric) to list of timestamp-value pairs
        """
        logger.info(f"Processing metrics from: {path}")

        if os.path.isfile(path) and path.endswith(".csv"):
            return cls._process_single_csv(path)
        elif os.path.isdir(path):
            return cls._process_directory(path)
        else:
            raise ValueError("Invalid path: must be directory or CSV file")

    @classmethod
    def _process_single_csv(
        cls, file_path: str
    ) -> Dict[Tuple[str, str], List[Dict[str, str]]]:
        """Process single CSV file with new format."""
        data_dict = {}

        with open(file_path, "r") as csv_file:
            csv_reader = csv.DictReader(csv_file)

            for row in csv_reader:
                metric = row.get("MetricName", "")
                if metric not in cls.INCLUDED_METRICS:
                    continue

                # Extract timestamp (first 19 characters)
                time_str = row.get("TimeUnix", "")[:19]
                value = 0.0 if not row.get("Value") else float(row.get("Value"))

                # Determine service name
                service = cls._extract_service_name(row)
                key = (service, metric)

                if key not in data_dict:
                    data_dict[key] = []

                data_dict[key].append({"date": time_str, "value": value})

        logger.info(f"Processed {len(data_dict)} metric series from single CSV")
        return data_dict

    @classmethod
    def _process_directory(
        cls, dir_path: str
    ) -> Dict[Tuple[str, str], List[Dict[str, str]]]:
        """Process directory with multiple CSV files (legacy format)."""
        data_dict = {}
        folder_path = os.path.join(dir_path, "metric")

        if not os.path.exists(folder_path):
            logger.warning(f"Metric folder not found: {folder_path}")
            return data_dict

        for filename in os.listdir(folder_path):
            if not filename.endswith(".csv"):
                continue

            file_path = os.path.join(folder_path, filename)
            cls._process_legacy_csv(file_path, data_dict)

        logger.info(f"Processed {len(data_dict)} metric series from directory")
        return data_dict

    @classmethod
    def _process_legacy_csv(cls, file_path: str, data_dict: Dict) -> None:
        """Process single CSV file in legacy format."""
        with open(file_path, "r") as csv_file:
            csv_reader = csv.DictReader(csv_file)

            for row in csv_reader:
                # Extract pod/service name and timestamp
                pod_name = row.get("PodName") or row.get("ServiceName")
                time_str = (row.get("Time") or row.get("time", ""))[:19]

                # Process each metric column
                for metric, value in row.items():
                    if cls._should_skip_metric(metric):
                        continue

                    key = (pod_name.split("-")[0], metric)
                    if key not in data_dict:
                        data_dict[key] = []

                    value = 0.0 if not value else float(value)
                    data_dict[key].append({"date": time_str, "value": value})

    @classmethod
    def _extract_service_name(cls, row: Dict[str, str]) -> str:
        """Extract service name from row data."""
        service = row.get("ServiceName", "").strip()
        if service:
            return service

        # Try to extract from ResourceAttributes
        try:
            resource_attrs = json.loads(row.get("ResourceAttributes", "{}"))
            service = resource_attrs.get(
                "k8s.deployment.name", ""
            ) or resource_attrs.get("k8s.pod.name", "")
        except json.JSONDecodeError:
            pass

        return service if service else "unknown"

    @classmethod
    def _should_skip_metric(cls, metric: str) -> bool:
        """Check if metric should be skipped."""
        if metric in cls.EXCLUDED_COLUMNS:
            return True
        return any(pattern in metric for pattern in cls.EXCLUDED_METRIC_PATTERNS)


class TraceProcessor:
    """Process and analyze distributed trace data."""

    @classmethod
    def read_traces(cls, path: str) -> Dict[str, TraceData]:
        """
        Read trace data from CSV files.

        Args:
            path: Path to directory or single CSV file

        Returns:
            Dictionary mapping trace IDs to TraceData objects
        """
        logger.info(f"Reading traces from: {path}")

        if os.path.isfile(path) and path.endswith(".csv"):
            traces = cls._read_single_trace_csv(path)
        elif os.path.isdir(path):
            traces = cls._read_trace_directory(path)
        else:
            raise ValueError("Invalid path: must be directory or CSV file")

        logger.info(f"Loaded {len(traces)} traces")
        return traces

    @classmethod
    def _read_single_trace_csv(cls, file_path: str) -> Dict[str, TraceData]:
        """Read traces from single CSV file (new format)."""
        raw_traces = {}

        with open(file_path, "r") as csv_file:
            csv_reader = csv.DictReader(csv_file)

            for row in csv_reader:
                trace_id = row.get("TraceId", "")
                if not trace_id:
                    continue

                span = cls._create_span_from_new_format(row)

                if trace_id not in raw_traces:
                    raw_traces[trace_id] = []
                raw_traces[trace_id].append(span)

        # Convert to TraceData objects
        return cls._convert_to_trace_data(raw_traces)

    @classmethod
    def _read_trace_directory(cls, dir_path: str) -> Dict[str, TraceData]:
        """Read traces from directory (legacy format)."""
        raw_traces = {}
        folder_path = os.path.join(dir_path, "trace")

        if not os.path.exists(folder_path):
            logger.warning(f"Trace folder not found: {folder_path}")
            return {}

        for filename in os.listdir(folder_path):
            if not filename.endswith(".csv"):
                continue

            file_path = os.path.join(folder_path, filename)
            cls._process_legacy_trace_csv(file_path, raw_traces)

        return cls._convert_to_trace_data(raw_traces)

    @classmethod
    def _create_span_from_new_format(cls, row: Dict[str, str]) -> TraceSpan:
        """Create TraceSpan from new CSV format row."""
        # Calculate start/end times
        end_time = row["Timestamp"][:19]
        duration_seconds = int(row["Duration"]) / 1e9
        start_time = (
            datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
            - timedelta(seconds=duration_seconds)
        ).strftime("%Y-%m-%d %H:%M:%S")

        return TraceSpan(
            trace_id=row.get("TraceId", ""),
            span_id=row.get("SpanId", ""),
            parent_id="root"
            if row.get("ParentSpanId") == ""
            else row.get("ParentSpanId", ""),
            service_name=row.get("ServiceName", ""),
            operation_name=row.get("SpanName", ""),
            start_time=start_time,
            end_time=end_time,
            duration=int(row["Duration"]),
            status="success",
        )

    @classmethod
    def _process_legacy_trace_csv(cls, file_path: str, raw_traces: Dict) -> None:
        """Process legacy trace CSV file."""
        try:
            with open(file_path, "r") as csv_file:
                csv_reader = csv.DictReader(csv_file)

                for row in csv_reader:
                    trace_id = row.get("TraceID", "")
                    if not trace_id:
                        continue

                    span = TraceSpan(
                        trace_id=trace_id,
                        span_id=row["SpanID"],
                        parent_id=row.get("ParentID", "root"),
                        service_name=row["PodName"].split("-")[0],
                        operation_name=row["OperationName"],
                        start_time=TimeUtils.timestamp_to_datetime(
                            row["StartTimeUnixNano"][:10]
                        ),
                        end_time=TimeUtils.timestamp_to_datetime(
                            row["EndTimeUnixNano"][:10]
                        ),
                        duration=int(row["Duration"]),
                        status="success",
                    )

                    if trace_id not in raw_traces:
                        raw_traces[trace_id] = []
                    raw_traces[trace_id].append(span)

        except FileNotFoundError:
            logger.warning(f"Trace file not found: {file_path}")

    @classmethod
    def _convert_to_trace_data(
        cls, raw_traces: Dict[str, List[TraceSpan]]
    ) -> Dict[str, TraceData]:
        """Convert raw trace data to TraceData objects."""
        traces = {}

        for trace_id, spans in raw_traces.items():
            # Sort spans by duration (descending) then by start time (descending)
            sorted_spans = sorted(
                spans, key=lambda x: (x.duration, x.start_time), reverse=True
            )
            traces[trace_id] = TraceData(trace_id=trace_id, spans=sorted_spans)

        return dict(sorted(traces.items(), key=lambda x: x[1].start_time, reverse=True))

    @classmethod
    def build_trace_tree(cls, spans: List[TraceSpan]) -> Tree:
        """
        Build tree representation of trace spans.

        Args:
            spans: List of spans from a trace

        Returns:
            Tree representation of the trace
        """
        # Sort spans by start time
        spans = sorted(spans, key=lambda x: x.start_time)

        # Build parent-child relationships
        parent_child = {}
        root_span = None

        for i, span in enumerate(spans):
            if span.is_root:
                root_span = span

            parent_id = span.parent_id
            if parent_id not in parent_child:
                parent_child[parent_id] = []
            parent_child[parent_id].append(i)

        # Create tree
        tree = Tree()
        if root_span:
            tree.create_node(
                tag=root_span.span_id, identifier=root_span.span_id, data=root_span
            )
            cls._build_tree_recursive(root_span.span_id, parent_child, tree, spans)

        return tree

    @classmethod
    def _build_tree_recursive(
        cls, node_id: str, parent_child: Dict, tree: Tree, spans: List[TraceSpan]
    ) -> None:
        """Recursively build the tree structure."""
        if node_id not in parent_child:
            return

        for child_index in parent_child[node_id]:
            child_span = spans[child_index]
            if tree.contains(child_span.span_id):
                continue

            tree.create_node(
                tag=child_span.span_id,
                identifier=child_span.span_id,
                parent=node_id,
                data=child_span,
            )

            cls._build_tree_recursive(child_span.span_id, parent_child, tree, spans)


class DataPreprocessor:
    """Main data preprocessing class combining metric and trace processing."""

    def __init__(self):
        """Initialize the data preprocessor."""
        self.metric_processor = MetricProcessor()
        self.trace_processor = TraceProcessor()

    def load_data(
        self, data_path: str
    ) -> Tuple[Dict[str, TraceData], Dict[Tuple[str, str], List[Dict]]]:
        """
        Load both trace and metric data from the given path.

        Args:
            data_path: Path to data directory or files

        Returns:
            Tuple of (traces, metrics)
        """
        logger.info(f"Loading data from: {data_path}")

        # Determine file paths
        if os.path.isdir(data_path):
            trace_path = os.path.join(data_path, "traces.csv")
            metric_path = os.path.join(data_path, "metrics.csv")

            # Fallback to directory structure if single files don't exist
            if not os.path.exists(trace_path):
                trace_path = data_path
            if not os.path.exists(metric_path):
                metric_path = data_path
        else:
            # Assume single file paths are provided
            trace_path = data_path.replace("metrics.csv", "traces.csv")
            metric_path = data_path.replace("traces.csv", "metrics.csv")

        # Load data
        traces = self.trace_processor.read_traces(trace_path)
        metrics = self.metric_processor.process_metrics(metric_path)

        logger.info(f"Loaded {len(traces)} traces and {len(metrics)} metric series")
        return traces, metrics

    def extract_system_metrics(self, trace: TraceData) -> SystemMetrics:
        """
        Extract system metrics from trace data.

        Args:
            trace: TraceData object

        Returns:
            SystemMetrics containing service and resource metrics
        """
        service_metrics = {}
        resource_metrics = {}
        resources = ["sql"]  # Define resources to track

        for span in trace.spans:
            service = span.service_name
            if not service:
                continue

            # Collect service-level metrics
            if service not in service_metrics:
                service_metrics[service] = []

            service_metrics[service].append(
                {
                    "span_id": span.span_id,
                    "duration": span.duration,
                    "status": span.status,
                }
            )

            # Collect resource-specific metrics
            for resource in resources:
                if resource in span.operation_name:
                    key = (service, resource)
                    if key not in resource_metrics:
                        resource_metrics[key] = []

                    resource_metrics[key].append(
                        {"span_id": span.span_id, "duration": span.duration}
                    )

        return SystemMetrics(
            service_metrics=service_metrics, resource_metrics=resource_metrics
        )
