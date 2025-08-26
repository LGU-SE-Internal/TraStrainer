"""Data loader for new Polars-based data format."""

import datetime
import json
import math
import shutil
import time
from functools import wraps
from pathlib import Path
from typing import Dict, List, Tuple

import polars as pl
from rcabench_platform.v2.logging import logger

from .data_structures import TraceData, TraceSpan


def timeit():
    """Simple timing decorator"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            end = time.time()
            logger.info(f"{func.__name__} took {end - start:.2f} seconds")
            return result

        return wrapper

    return decorator


def load_json(path: Path) -> dict:
    """Load JSON file"""
    with open(path, "r") as f:
        return json.load(f)


def tt_add_op_name(lf: pl.LazyFrame) -> pl.LazyFrame:
    """Add operation name for Train Ticket traces"""
    return lf.with_columns(pl.col("span_name").alias("operation_name"))


def replace_enum_values(column: str, enum_values: list, start: int = 0) -> pl.Expr:
    """Replace enum string values with integers"""
    mapping_expr = pl.col(column)
    for i, value in enumerate(enum_values):
        mapping_expr = mapping_expr.str.replace(value, str(start + i))
    return mapping_expr.cast(pl.Int32)


def load_inject_time(input_folder: Path) -> datetime.datetime:
    """Load injection time from environment configuration"""
    env = load_json(path=input_folder / "env.json")

    normal_start = int(env["NORMAL_START"])
    normal_end = int(env["NORMAL_END"])
    abnormal_start = int(env["ABNORMAL_START"])
    abnormal_end = int(env["ABNORMAL_END"])

    assert normal_start < normal_end <= abnormal_start < abnormal_end

    if normal_end < abnormal_start:
        inject_time = int(math.ceil(normal_end + abnormal_start) / 2)
    else:
        inject_time = abnormal_start

    inject_time = datetime.datetime.fromtimestamp(inject_time, tz=datetime.timezone.utc)
    logger.debug(f"inject_time={inject_time}")

    return inject_time


def merge_two_time_ranges(normal: pl.LazyFrame, anomal: pl.LazyFrame) -> pl.LazyFrame:
    """Merge normal and anomalous time ranges"""
    assert "anomal" not in normal.collect_schema().names()
    assert "anomal" not in anomal.collect_schema().names()
    normal = normal.with_columns(anomal=pl.lit(0, dtype=pl.UInt8))
    anomal = anomal.with_columns(anomal=pl.lit(1, dtype=pl.UInt8))
    merged = pl.concat([normal, anomal])
    return merged


@timeit()
def load_metrics(input_folder: Path) -> pl.LazyFrame:
    """Load metrics data from Parquet files"""
    normal_metrics = pl.scan_parquet(input_folder / "normal_metrics.parquet")
    anomal_metrics = pl.scan_parquet(input_folder / "abnormal_metrics.parquet")
    lf = merge_two_time_ranges(normal_metrics, anomal_metrics)

    # Apply unit conversions
    lf = process_metric_units(lf)

    # Select only the 4 core columns needed for metrics
    lf = lf.select(["time", "metric", "value", "service_name"])

    return lf


def is_special_constant_metric(metric: str) -> bool:
    """Check if metric is a special constant metric"""
    return metric in (
        "k8s.container.cpu_request",
        "k8s.container.memory_request",
        "k8s.container.cpu_limit",
        "k8s.container.memory_limit",
    )


def process_metric_units(lf: pl.LazyFrame) -> pl.LazyFrame:
    """Process metric units and convert to appropriate scales"""
    # Convert CPU utilization to percentage (multiply by 100)
    lf = lf.with_columns(
        pl.when(pl.col("metric") == "k8s.pod.cpu_limit_utilization")
        .then(pl.col("value") * 100)
        .when(pl.col("metric") == "k8s.pod.memory_limit_utilization")
        .then(pl.col("value") * 100)
        .when(pl.col("metric") == "k8s.pod.memory.usage")
        .then(pl.col("value") / 1024 / 1024)  # Convert bytes to MB
        .otherwise(pl.col("value"))
        .alias("value")
    )

    return lf


@timeit()
def load_metrics_histogram(input_folder: Path) -> pl.LazyFrame:
    """Load histogram metrics data from Parquet files"""
    normal_histogram = pl.scan_parquet(
        input_folder / "normal_metrics_histogram.parquet"
    )
    anomal_histogram = pl.scan_parquet(
        input_folder / "abnormal_metrics_histogram.parquet"
    )
    lf = merge_two_time_ranges(normal_histogram, anomal_histogram)

    lf = lf.with_columns(
        pl.when(pl.col("metric") == "jvm.gc.duration")
        .then(
            pl.concat_str("metric", "attr.jvm.gc.name", separator=":").alias("metric")
        )
        .otherwise(pl.col("metric"))
    )

    return lf


def ui_span_name_parser(df: pl.DataFrame) -> pl.DataFrame:
    """Parse UI dashboard span names by replacing with child span names"""
    # Create a mapping from parent span ID to child span name
    child_mapping = df.select(["parent_span_id", "span_name"]).rename(
        {"parent_span_id": "span_id", "span_name": "child_span_name"}
    )

    # Join with original dataframe
    merged_df = df.join(child_mapping, on="span_id", how="left")

    # Replace span names for ts-ui-dashboard service with child span names
    processed_df = merged_df.with_columns(
        pl.when(pl.col("service_name") == "ts-ui-dashboard")
        .then(pl.col("child_span_name"))
        .otherwise(pl.col("span_name"))
        .alias("span_name")
    ).drop("child_span_name")

    return processed_df


@timeit()
def load_traces(input_folder: Path) -> pl.LazyFrame:
    """Load trace data from Parquet files"""
    normal_traces = pl.scan_parquet(input_folder / "normal_traces.parquet")
    anomal_traces = pl.scan_parquet(input_folder / "abnormal_traces.parquet")
    lf = merge_two_time_ranges(normal_traces, anomal_traces)

    status_code_values = ["Unset", "Ok", "Error"]
    lf = lf.with_columns(
        replace_enum_values("attr.status_code", status_code_values, start=0),
    )

    lf = lf.with_columns(
        pl.col("duration").cast(pl.Float64),
        pl.col("attr.http.response.status_code").cast(pl.Float64),
        pl.col("attr.http.request.content_length").cast(pl.Float64),
        pl.col("attr.http.response.content_length").cast(pl.Float64),
    )

    # Apply UI span name parsing
    df = lf.collect()
    df = ui_span_name_parser(df)
    lf = df.lazy()
    lf = tt_add_op_name(lf)

    return lf


@timeit()
def load_logs(input_folder: Path) -> pl.LazyFrame:
    """Load log data from Parquet files"""
    normal_logs = pl.scan_parquet(input_folder / "normal_logs.parquet")
    anomal_logs = pl.scan_parquet(input_folder / "abnormal_logs.parquet")
    lf = merge_two_time_ranges(normal_logs, anomal_logs)

    level_values = ["", "TRACE", "DEBUG", "INFO", "WARN", "ERROR", "SEVERE"]
    lf = lf.with_columns(pl.col("level").str.replace("WARNING", "WARN", literal=True))
    lf = lf.with_columns(
        replace_enum_values("level", level_values, start=0).alias("level_number")
    )

    return lf


def compute_trace_duration_metrics(traces_lf: pl.LazyFrame) -> pl.LazyFrame:
    """Compute P90 duration metrics per service per minute from trace data"""
    # Convert time to minute-level buckets and compute trace duration P90
    duration_metrics = (
        traces_lf.with_columns(
            [
                # Extract minute timestamp from time column
                pl.col("time").dt.truncate("1m").alias("time_bucket"),
                # Use duration directly
                pl.col("duration").alias("duration_value"),
            ]
        )
        .group_by(["service_name", "time_bucket"])
        .agg(
            [
                # Calculate P90 duration per service per minute
                pl.col("duration_value").quantile(0.9).alias("value")
            ]
        )
        .with_columns(
            [
                # Add metric name
                pl.lit("trace_duration_p90").alias("metric"),
                # Rename time_bucket to time to match metrics format
                pl.col("time_bucket").alias("time"),
            ]
        )
        .select(["time", "metric", "value", "service_name"])
    )

    return duration_metrics


class PolarDataPreprocessor:
    """Data preprocessor for Polars-based data format"""

    def __init__(self):
        """Initialize the Polars data preprocessor"""
        self.inject_time: datetime.datetime | None = None
        self.original_input_folder: Path | None = None

    def load_data(
        self, input_folder: Path
    ) -> Tuple[Dict[str, TraceData], Dict[Tuple[str, str], List[Dict]]]:
        """
        Load trace and metric data from Parquet files

        Args:
            input_folder: Path to folder containing Parquet files

        Returns:
            Tuple of (traces, metrics) in TraStrainer format
        """
        logger.info(f"Loading data from: {input_folder}")

        # Load injection time - 确保input_folder是Path对象
        input_path = (
            Path(input_folder) if isinstance(input_folder, str) else input_folder
        )
        self.original_input_folder = input_path
        self.inject_time = load_inject_time(input_path)

        # Load raw data - 确保input_folder是Path对象
        traces_lf = load_traces(input_path)
        metrics_lf = load_metrics(input_path)

        # Compute trace duration metrics and combine with regular metrics
        trace_duration_metrics = compute_trace_duration_metrics(traces_lf)
        combined_metrics_lf = pl.concat([metrics_lf, trace_duration_metrics])

        # Convert to TraStrainer format
        traces = self._convert_traces(traces_lf)
        metrics = self._convert_metrics(combined_metrics_lf)

        logger.info(f"Loaded {len(traces)} traces and {len(metrics)} metric series")
        return traces, metrics

    def save_sampled_results(self, sampled_trace_ids: List[str]) -> Path:
        """
        Save sampled results to output directory with original files

        Args:
            sampled_trace_ids: List of sampled trace IDs

        Returns:
            Path to the output directory
        """
        if not self.original_input_folder:
            raise ValueError("No input folder loaded. Call load_data first.")

        # Create output directory
        output_dir = self.original_input_folder / "sampled" / "trastrainer"
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Saving sampled results to: {output_dir}")

        # Copy original files (env.json, injection.json, etc.)
        original_files = [
            "env.json",
            "injection.json",
            "notations.json",
            "conclusion.parquet",
            ".finished",
        ]

        for file_name in original_files:
            src_file = self.original_input_folder / file_name
            if src_file.exists():
                dst_file = output_dir / file_name
                shutil.copy2(src_file, dst_file)
                logger.debug(f"Copied {file_name}")

        # Load and filter original data
        sampled_trace_ids_set = set(sampled_trace_ids)

        # Filter and save traces
        self._save_filtered_traces(output_dir, sampled_trace_ids_set)

        # Copy metrics (unchanged)
        self._copy_metrics(output_dir)

        # Copy logs (unchanged)
        self._copy_logs(output_dir)

        logger.info(
            f"Successfully saved sampled data with {len(sampled_trace_ids)} traces"
        )
        return output_dir

    def _save_filtered_traces(self, output_dir: Path, sampled_trace_ids: set):
        """Filter and save traces based on sampled trace IDs"""
        logger.info("Filtering and saving traces...")

        if not self.original_input_folder:
            raise ValueError("Original input folder not set")

        # Load original traces
        normal_traces_lf = pl.scan_parquet(
            self.original_input_folder / "normal_traces.parquet"
        )
        abnormal_traces_lf = pl.scan_parquet(
            self.original_input_folder / "abnormal_traces.parquet"
        )

        # Filter by sampled trace IDs
        normal_filtered = normal_traces_lf.filter(
            pl.col("trace_id").is_in(sampled_trace_ids)
        )
        abnormal_filtered = abnormal_traces_lf.filter(
            pl.col("trace_id").is_in(sampled_trace_ids)
        )

        # Save filtered traces as Parquet files (same format as original)
        normal_output = output_dir / "normal_traces.parquet"
        abnormal_output = output_dir / "abnormal_traces.parquet"

        # Collect and write to parquet
        normal_df = normal_filtered.collect()
        abnormal_df = abnormal_filtered.collect()

        normal_df.write_parquet(normal_output)
        abnormal_df.write_parquet(abnormal_output)

        normal_count = normal_df.height
        abnormal_count = abnormal_df.height
        normal_unique = normal_df["trace_id"].n_unique() if normal_count > 0 else 0
        abnormal_unique = (
            abnormal_df["trace_id"].n_unique() if abnormal_count > 0 else 0
        )

        logger.info(
            f"Saved {normal_count} normal traces ({normal_unique} unique trace_ids) and {abnormal_count} abnormal traces ({abnormal_unique} unique trace_ids) to Parquet files"
        )

        # 提供数据分布信息
        if normal_count == 0:
            logger.info(
                "No normal traces found for sampled trace_ids - this is normal if sampling focused on abnormal period"
            )
        if abnormal_count == 0:
            logger.info(
                "No abnormal traces found for sampled trace_ids - this is normal if sampling focused on normal period"
            )

    def _copy_metrics(self, output_dir: Path):
        """Copy metric files (unchanged)"""
        logger.info("Copying metrics...")

        if not self.original_input_folder:
            raise ValueError("Original input folder not set")

        metric_files = [
            "normal_metrics.parquet",
            "abnormal_metrics.parquet",
            "normal_metrics_histogram.parquet",
            "abnormal_metrics_histogram.parquet",
            "normal_metrics_sum.parquet",
            "abnormal_metrics_sum.parquet",
        ]

        for file_name in metric_files:
            src_file = self.original_input_folder / file_name
            if src_file.exists():
                dst_file = output_dir / file_name
                shutil.copy2(src_file, dst_file)
                logger.debug(f"Copied {file_name}")

    def _copy_logs(self, output_dir: Path):
        """Copy log files (unchanged)"""
        logger.info("Copying logs...")

        if not self.original_input_folder:
            raise ValueError("Original input folder not set")

        log_files = ["normal_logs.parquet", "abnormal_logs.parquet"]

        for file_name in log_files:
            src_file = self.original_input_folder / file_name
            if src_file.exists():
                dst_file = output_dir / file_name
                shutil.copy2(src_file, dst_file)
                logger.debug(f"Copied {file_name}")

    def _convert_traces(self, lf: pl.LazyFrame) -> Dict[str, TraceData]:
        """Convert Polars LazyFrame to TraStrainer trace format"""
        logger.info("Converting traces to TraStrainer format...")

        # Collect the data
        df = lf.collect()

        traces = {}

        # Group by trace_id
        for trace_id_tuple, trace_group in df.group_by("trace_id"):
            trace_id = str(trace_id_tuple[0])  # Convert to string

            spans = []
            for row in trace_group.iter_rows(named=True):
                span = TraceSpan(
                    trace_id=trace_id,
                    span_id=row["span_id"],
                    parent_id=row.get("parent_span_id", "root") or "root",
                    service_name=row["service_name"] or "unknown-service",
                    operation_name=row.get("operation_name", row.get("span_name", ""))
                    or "unknown-operation",
                    start_time=row["time"].isoformat() if row["time"] else "",
                    end_time=(
                        row["time"]
                        + datetime.timedelta(microseconds=row["duration"] / 1000)
                    ).isoformat()
                    if row["time"] and row["duration"]
                    else "",
                    duration=int(row["duration"]) if row["duration"] else 0,
                    status="success"
                    if row.get("attr.status_code", 1) <= 1
                    else "error",
                )
                spans.append(span)

            # Sort spans by duration (descending) then by start time
            spans.sort(key=lambda x: (x.duration, x.start_time), reverse=True)

            traces[trace_id] = TraceData(trace_id=trace_id, spans=spans)

        # Sort traces by start time (ascending) to process normal period first
        traces = dict(
            sorted(traces.items(), key=lambda x: x[1].start_time, reverse=False)
        )

        logger.info(f"Converted {len(traces)} traces")
        return traces

    def _convert_metrics(self, lf: pl.LazyFrame) -> Dict[Tuple[str, str], List[Dict]]:
        """Convert Polars LazyFrame to TraStrainer metric format"""
        logger.info("Converting metrics to TraStrainer format...")

        # Collect the data
        df = lf.collect()

        metrics = {}

        # Group by service_name and metric
        for (service_name, metric), metric_group in df.group_by(
            ["service_name", "metric"]
        ):
            key = (service_name, metric)

            data_points = []
            for row in metric_group.iter_rows(named=True):
                data_points.append(
                    {
                        "date": row["time"].isoformat() if row["time"] else "",
                        "value": float(row["value"])
                        if row["value"] is not None
                        else 0.0,
                    }
                )

            # Sort by timestamp
            data_points.sort(key=lambda x: x["date"])
            metrics[key] = data_points

        logger.info(f"Converted {len(metrics)} metric series")
        return metrics
