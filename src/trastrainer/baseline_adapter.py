"""Baseline algorithms adapter for the RCABench platform."""

import random
import time
from collections import deque
from pathlib import Path
from typing import Dict, List, Tuple

from rcabench_platform.v2.logging import logger

from .algorithm import FeatureExtractor
from .data_structures import TraceData, TraceSpan
from .polar_loader import PolarDataPreprocessor
from .preprocessor import TraceProcessor


class BaselineAdapter:
    """Adapter for baseline algorithms to work with the new data format"""

    def __init__(self, algorithm_name: str = "random", sampling_rate: float = 0.1):
        """
        Initialize baseline algorithm adapter

        Args:
            algorithm_name: Name of baseline algorithm ('random', 'sifter', 'sieve', 'wt')
            sampling_rate: Target sampling rate for trace sampling
        """
        self.algorithm_name = algorithm_name
        self.sampling_rate = sampling_rate

    def __call__(self, input_folder: Path, inject_time: int | None = None) -> dict:
        """
        Run baseline sampling on the given data

        Args:
            input_folder: Path to folder containing Parquet data files
            inject_time: Injection time (not used in current implementation)

        Returns:
            Dictionary with sampling results
        """
        try:
            logger.info(
                f"Running {self.algorithm_name} baseline with sampling rate: {self.sampling_rate}"
            )

            # Load data using Polars preprocessor
            preprocessor = PolarDataPreprocessor()
            traces, metrics = preprocessor.load_data(input_folder)

            # Convert traces to baseline format
            trace_list = self._convert_traces_to_baseline_format(traces)

            start_time = time.time()

            # Run appropriate sampling algorithm
            if self.algorithm_name == "random":
                sampled_trace_ids = self._random_sampling(
                    trace_list, self.sampling_rate
                )
            elif self.algorithm_name == "sifter":
                sampled_trace_ids = self._sifter_sampling(
                    trace_list, self.sampling_rate
                )
            elif self.algorithm_name == "sieve":
                sampled_trace_ids = self._sieve_sampling(trace_list, self.sampling_rate)
            elif self.algorithm_name == "wt":
                sampled_trace_ids = self._wt_sampling(trace_list, self.sampling_rate)
            else:
                raise ValueError(f"Unknown baseline algorithm: {self.algorithm_name}")

            execution_time = time.time() - start_time

            # Save results using the preprocessor
            output_dir = preprocessor.save_sampled_results(sampled_trace_ids)

            total_traces = len(traces)
            actual_sample_count = len(sampled_trace_ids)

            logger.info(
                f"{self.algorithm_name} completed: sampled {actual_sample_count} out of {total_traces} traces"
            )
            logger.info(f"Results saved to: {output_dir}")

            return {
                "sampled_trace_ids": sampled_trace_ids,
                "total_traces": total_traces,
                "sampling_rate_achieved": actual_sample_count / total_traces
                if total_traces > 0
                else 0,
                "execution_time": execution_time,
                "output_directory": str(output_dir),
                "algorithm": self.algorithm_name,
            }

        except Exception as e:
            logger.error(f"{self.algorithm_name} baseline failed: {e}")
            return {
                "sampled_trace_ids": [],
                "total_traces": 0,
                "sampling_rate_achieved": 0.0,
                "execution_time": 0.0,
                "error": str(e),
            }

    def _robust_process_trace(
        self, trace_spans: List[TraceSpan]
    ) -> Tuple[List[str], bool]:
        """
        Robustly process trace to handle incomplete traces

        Args:
            trace_spans: List of TraceSpan objects from a trace

        Returns:
            Tuple of (trace_structure, is_complete)
        """
        try:
            # Try the new processing using current module structure
            tree = TraceProcessor.build_trace_tree(trace_spans)

            # Use the new FeatureExtractor
            trace_data = TraceData(
                trace_id=trace_spans[0].trace_id if trace_spans else "",
                spans=trace_spans,
            )

            trace_structure = FeatureExtractor.get_trace_structure_vector(
                trace_data, tree
            )
            return trace_structure, True

        except Exception as e:
            # Handle incomplete traces by building a simpler structure
            logger.debug(f"New trace processing failed: {e}, using fallback method")

            # Create a simple feature representation without tree depth
            basic_features = []
            for span in trace_spans:
                try:
                    # Use a default depth of 0 for incomplete traces
                    feature = "-".join(
                        [
                            "0",  # default depth
                            span.service_name or "unknown",
                            span.operation_name or "unknown",
                            span.status or "unknown",
                            str(int(span.duration / 1e4)),
                        ]
                    )
                    basic_features.append(feature)
                except (ValueError, TypeError):
                    # Skip malformed spans
                    continue

            basic_features.sort()
            return basic_features, False

    def _convert_traces_to_baseline_format(
        self, traces: Dict[str, TraceData]
    ) -> List[List[Dict]]:
        """
        Convert TraStrainer trace format to baseline format

        Args:
            traces: Dictionary of TraceData objects

        Returns:
            List of trace lists in baseline format (each trace is a list of span dicts)
        """
        baseline_traces = []

        for trace_id, trace_data in traces.items():
            # Convert each trace to the format expected by baseline algorithms
            trace_spans = []
            for span in trace_data.spans:
                span_dict = {
                    "TraceID": span.trace_id,
                    "SpanID": span.span_id,
                    "ParentID": span.parent_id,
                    "ServiceName": span.service_name,
                    "OperationName": span.operation_name,
                    "StartTimeUnixNano": span.start_time,
                    "StartTime": span.start_time,  # Also add StartTime for sorting
                    "Duration": str(span.duration),
                    "PodName": span.service_name,  # Use service_name as PodName
                    "status": span.status,
                }
                trace_spans.append(span_dict)

            if trace_spans:  # Only add non-empty traces
                baseline_traces.append(trace_spans)

        return baseline_traces

    def _random_sampling(
        self, traces: List[List[Dict]], sampling_rate: float
    ) -> List[str]:
        """Random sampling baseline"""
        trace_ids = [trace[0]["TraceID"] for trace in traces if trace]
        sampling_number = int(round(len(trace_ids) * sampling_rate))

        if sampling_number >= len(trace_ids):
            return trace_ids

        return random.sample(trace_ids, sampling_number)

    def _sifter_sampling(
        self, traces: List[List[Dict]], sampling_rate: float
    ) -> List[str]:
        """
        Sifter sampling baseline - simplified implementation
        Based on diversity of trace structures
        """
        try:
            result = []
            history_trace_structures = deque(maxlen=100)

            for trace in traces:
                if not trace:
                    continue

                try:
                    # Convert baseline format to TraceSpan objects for robust processing
                    trace_spans = self._convert_baseline_to_tracespans(trace)
                    trace_structure, is_complete = self._robust_process_trace(
                        trace_spans
                    )

                    # Use simple diversity calculation
                    similarity = self._calculate_diversity_rate(
                        history_trace_structures, trace_structure
                    )

                    if similarity < sampling_rate:
                        result.append(trace)
                        history_trace_structures.append(trace_structure)
                        if len(result) >= int(round(sampling_rate * len(traces))):
                            break

                    history_trace_structures.append(trace_structure)

                except Exception as e:
                    # Handle any remaining errors gracefully
                    logger.debug(f"Skipping trace due to processing error: {e}")
                    # For problematic traces, fall back to simple sampling
                    if len(result) < int(round(sampling_rate * len(traces))):
                        if random.random() < sampling_rate:
                            result.append(trace)
                    continue

            # Extract trace IDs and apply correction
            sampled_ids = [trace[0]["TraceID"] for trace in result if trace]
            all_trace_ids = [trace[0]["TraceID"] for trace in traces if trace]

            return self._correction(all_trace_ids, sampling_rate, sampled_ids)

        except Exception as e:
            logger.warning(
                f"Sifter implementation failed: {e}, falling back to random sampling"
            )
            return self._random_sampling(traces, sampling_rate)

    def _convert_baseline_to_tracespans(self, trace: List[Dict]) -> List[TraceSpan]:
        """Convert baseline format to TraceSpan objects"""
        trace_spans = []
        for span_dict in trace:
            # Calculate end_time from start_time and duration
            try:
                duration_ns = int(span_dict.get("Duration", 0))
                start_time = span_dict.get(
                    "StartTime", span_dict.get("StartTimeUnixNano", "")
                )

                # Simple end time calculation (for this adapter, precise timing isn't critical)
                end_time = start_time  # Simplified

                span = TraceSpan(
                    trace_id=span_dict.get("TraceID", ""),
                    span_id=span_dict.get("SpanID", ""),
                    parent_id=span_dict.get("ParentID", ""),
                    service_name=span_dict.get(
                        "ServiceName", span_dict.get("PodName", "")
                    ),
                    operation_name=span_dict.get("OperationName", ""),
                    start_time=start_time,
                    end_time=end_time,
                    duration=duration_ns,
                    status=span_dict.get("status", "success"),
                )
                trace_spans.append(span)
            except (ValueError, TypeError) as e:
                logger.debug(f"Skipping malformed span: {e}")
                continue

        return trace_spans

    def _calculate_diversity_rate(
        self, history_structures: deque, current_structure: List[str]
    ) -> float:
        """Calculate diversity rate based on structure similarity"""
        if not history_structures:
            return 1.0

        # Simple Jaccard similarity calculation
        max_similarity = 0.0
        for hist_structure in history_structures:
            set1 = set(current_structure)
            set2 = set(hist_structure)

            if len(set1) == 0 and len(set2) == 0:
                similarity = 1.0
            else:
                intersection = len(set1.intersection(set2))
                union = len(set1.union(set2))
                similarity = intersection / union if union > 0 else 0.0

            max_similarity = max(max_similarity, similarity)

        # Return inverse of similarity (higher diversity = lower similarity)
        return 1.0 - max_similarity

    def _sieve_sampling(
        self, traces: List[List[Dict]], sampling_rate: float
    ) -> List[str]:
        """
        Sieve sampling baseline - uses random sampling as fallback
        """
        try:
            # Try to import the original Sieve components
            from Sieve.data_process import Span, Trace
            from Sieve.sieve import Sieve

            # Convert to Sieve format
            sieve_traces = []
            for trace in traces:
                if not trace:
                    continue

                spans = []
                for span_dict in trace:
                    try:
                        span = Span(
                            span_dict["TraceID"],
                            span_dict["SpanID"],
                            span_dict["ParentID"],
                            span_dict.get("StartTimeUnixNano", 0),
                            float(span_dict["Duration"]),
                            span_dict["ServiceName"],
                            span_dict["OperationName"],
                        )
                        spans.append(span)
                    except (KeyError, ValueError):
                        continue

                if spans:
                    sieve_traces.append(Trace(trace[0]["TraceID"], spans))

            # Run Sieve sampling
            result = []
            sieve = Sieve(tree_num=50, tree_size=128, k=50, threshold=0.3)

            for i, trace in enumerate(sieve_traces):
                if sieve.isSample(trace):
                    result.append(trace)

                if len(result) >= int(round(sampling_rate * len(sieve_traces))):
                    break

                # Compact every 128 traces
                if i % 128 == 0:
                    sieve.compact()

            sampled_ids = [trace.traceID for trace in result]
            all_trace_ids = [trace.traceID for trace in sieve_traces]

            return self._correction(all_trace_ids, sampling_rate, sampled_ids)

        except ImportError:
            logger.warning(
                "Sieve implementation not available, falling back to random sampling"
            )
            return self._random_sampling(traces, sampling_rate)

    def _wt_sampling(self, traces: List[List[Dict]], sampling_rate: float) -> List[str]:
        """
        WT (Workload-based) sampling baseline
        """
        try:
            # Simple workload-based sampling: prefer traces with more spans or longer duration
            trace_workloads = []

            for trace in traces:
                if not trace:
                    continue

                workload = len(trace)  # Number of spans
                total_duration = sum(int(span.get("Duration", 0)) for span in trace)

                trace_workloads.append(
                    {
                        "trace_id": trace[0]["TraceID"],
                        "workload": workload,
                        "total_duration": total_duration,
                        "score": workload * (total_duration / 1e9),  # Combined score
                    }
                )

            # Sort by workload score (descending) and sample top percentile
            trace_workloads.sort(key=lambda x: x["score"], reverse=True)
            target_count = int(round(len(trace_workloads) * sampling_rate))

            sampled_ids = [t["trace_id"] for t in trace_workloads[:target_count]]
            all_trace_ids = [t["trace_id"] for t in trace_workloads]

            return self._correction(all_trace_ids, sampling_rate, sampled_ids)

        except Exception as e:
            logger.warning(
                f"WT implementation failed: {e}, falling back to random sampling"
            )
            return self._random_sampling(traces, sampling_rate)

    def _correction(
        self, all_trace_ids: List[str], target_rate: float, sampled_ids: List[str]
    ) -> List[str]:
        """
        Apply correction to achieve target sampling rate
        """
        target_count = int(round(len(all_trace_ids) * target_rate))

        if len(sampled_ids) < target_count:
            # Need more samples
            remaining_ids = [tid for tid in all_trace_ids if tid not in sampled_ids]
            additional_needed = target_count - len(sampled_ids)
            if additional_needed <= len(remaining_ids):
                additional_samples = random.sample(remaining_ids, additional_needed)
                sampled_ids.extend(additional_samples)
        elif len(sampled_ids) > target_count:
            # Too many samples, randomly remove some
            sampled_ids = random.sample(sampled_ids, target_count)

        return sampled_ids
