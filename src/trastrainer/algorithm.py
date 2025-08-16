"""Main TraStrainer algorithm implementation."""

import copy
import random
import time
from collections import deque
from typing import Deque, Dict, List, Tuple

import numpy as np
from rcabench_platform.v2.logging import logger
from treelib.tree import Tree

from .data_structures import SamplingConfig, SamplingResult, SystemMetrics, TraceData
from .predictors import MetricPredictor
from .preprocessor import DataPreprocessor, TraceProcessor


class SimilarityCalculator:
    """Calculate similarity between trace structures."""

    @staticmethod
    def compute_jaccard_similarity(
        spanline_1: List[str], spanline_2: List[str]
    ) -> float:
        """
        Compute Jaccard similarity between two span sequences.

        Args:
            spanline_1: First span sequence
            spanline_2: Second span sequence

        Returns:
            Jaccard similarity score [0-1]
        """
        cp_spanline_1 = copy.deepcopy(spanline_1)
        cp_spanline_2 = copy.deepcopy(spanline_2)

        # Count intersection elements
        intersection_cnt = 0
        for sl1 in spanline_1:
            if sl1 in cp_spanline_2:
                intersection_cnt += 1
                cp_spanline_2.pop(cp_spanline_2.index(sl1))
                cp_spanline_1.pop(cp_spanline_1.index(sl1))

        # Calculate union size and similarity
        union_cnt = intersection_cnt + len(cp_spanline_1) + len(cp_spanline_2)
        similarity = intersection_cnt / union_cnt if union_cnt else 0

        return similarity


class FeatureExtractor:
    """Extract features from trace data for sampling decisions."""

    @staticmethod
    def get_trace_structure_vector(trace: TraceData, tree: Tree) -> List[str]:
        """
        Create a sequence representation of spans in a trace.

        Args:
            trace: TraceData object
            tree: Tree representation of the trace

        Returns:
            List of span feature strings
        """
        basic_features = []

        for span in trace.spans:
            # Create feature string for each span
            feature_string = "-".join(
                [
                    str(tree.depth(span.span_id))
                    if tree.contains(span.span_id)
                    else "0",
                    span.service_name,
                    span.operation_name,
                    span.status,
                    str(int(span.duration / 1e4)),
                ]
            )
            basic_features.append(feature_string)

        basic_features.sort()
        return basic_features

    @staticmethod
    def compute_trace_feature_values(
        system_metrics: SystemMetrics, metrics: Dict[Tuple[str, str], List[Dict]]
    ) -> Dict[Tuple[str, str], float]:
        """
        Compute feature values based on trace data and metrics.

        Args:
            system_metrics: SystemMetrics extracted from trace
            metrics: Dictionary of metrics to compute features for

        Returns:
            Dictionary of computed feature values
        """
        feature_values = {}

        for key in metrics:
            service_name = key[0]
            spans = system_metrics.get_service_spans(service_name)

            if not spans:
                feature_values[key] = 0
                continue

            num_spans = len(spans)
            avg_duration = sum(span["duration"] for span in spans) / num_spans
            num_failures = sum(1 for span in spans if span["status"] == "fail")

            feature_value = num_spans * avg_duration * (1 + num_failures)
            feature_values[key] = feature_value

        return feature_values


class SamplingFilter:
    """Implements sampling filters for system bias and diversity bias."""

    @staticmethod
    def tanh(x: float) -> float:
        """Calculate hyperbolic tangent function."""
        return 2 / (1 + np.exp(-2 * x)) - 1

    @staticmethod
    def compute_system_bias_rate(
        history_trace_metrics: Dict[Tuple[str, str], Deque],
        trace_metric: Dict[Tuple[str, str], float],
        metrics_weights: Dict[Tuple[str, str], float],
    ) -> float:
        """
        Calculate system bias sampling rate based on metric anomalies.

        Args:
            history_trace_metrics: Historical metric values
            trace_metric: Current trace metrics
            metrics_weights: Weights for different metrics

        Returns:
            Sampling rate based on system metrics
        """
        sampling_rate = 0
        count = 0

        for key, weight in metrics_weights.items():
            value = trace_metric.get(key, 0)

            # Calculate mean and std deviation from history
            if not history_trace_metrics.get(key):
                mean, std = 0, 0
            else:
                values = list(history_trace_metrics[key])
                mean, std = np.mean(values), np.std(values)

            # Calculate normalized deviation (n_sigma)
            n_sigma = abs(value - mean) / (std + 1e-5)
            sampling_rate += weight * n_sigma
            count += weight

        # Normalize and transform sampling rate
        normalized_rate = sampling_rate / count if count else 0
        return SamplingFilter.tanh(normalized_rate)

    @staticmethod
    def compute_diversity_bias_rate(
        history_trace_structures: Deque[List[str]],
        trace_structure: List[str],
        diversity_window: Deque[float],
    ) -> float:
        """
        Calculate diversity bias sampling rate based on trace structure similarity.

        Args:
            history_trace_structures: Historical trace structures
            trace_structure: Current trace structure
            diversity_window: Window of diversity values for normalization

        Returns:
            Sampling rate based on trace diversity
        """
        if not history_trace_structures:
            return 1.0

        # Count occurrences of each trace structure
        structure_counts = {}
        for structure in history_trace_structures:
            key = "+".join(structure)
            structure_counts[key] = structure_counts.get(key, 0) + 1

        # Find most similar historical trace
        max_similarity = 0
        most_similar_key = ""

        for history_structure in history_trace_structures:
            similarity = SimilarityCalculator.compute_jaccard_similarity(
                history_structure, trace_structure
            )

            if similarity > max_similarity:
                max_similarity = similarity
                most_similar_key = "+".join(history_structure)

        # Calculate similarity-based rate
        count = structure_counts.get(most_similar_key, 0)
        similarity_rate = round(max_similarity * count, 2)

        if similarity_rate:
            diversity_rate = 1 / similarity_rate
            diversity_window.append(diversity_rate)
            return diversity_rate / sum(diversity_window) if diversity_window else 1.0
        else:
            return 1.0


class SamplingDecision:
    """Makes sampling decisions based on system and diversity rates."""

    @staticmethod
    def judge(
        system_rate: float, diversity_rate: float, strict: bool
    ) -> Tuple[bool, float, float]:
        """
        Decide whether to sample a trace.

        Args:
            system_rate: Sampling rate based on system metrics
            diversity_rate: Sampling rate based on trace diversity
            strict: Whether to use AND logic (True) or OR logic (False)

        Returns:
            Tuple of (sample decision, system random value, diversity random value)
        """
        system_random = random.random()
        diversity_random = random.random()

        is_system_sample = system_random <= system_rate
        is_diversity_sample = diversity_random <= diversity_rate

        if strict:
            return (
                is_system_sample and is_diversity_sample,
                system_random,
                diversity_random,
            )
        else:
            return (
                is_system_sample or is_diversity_sample,
                system_random,
                diversity_random,
            )


class TraStrainerAlgorithm:
    """Main TraStrainer algorithm for adaptive trace sampling."""

    def __init__(self, config: SamplingConfig):
        """
        Initialize TraStrainer algorithm.

        Args:
            config: Sampling configuration
        """
        self.config = config
        self.preprocessor = DataPreprocessor()
        self.metric_predictor = MetricPredictor(config.checkpoints_dir)
        self.feature_extractor = FeatureExtractor()
        self.sampling_filter = SamplingFilter()
        self.sampling_decision = SamplingDecision()

    def run(
        self, traces: Dict[str, TraceData], metrics: Dict[Tuple[str, str], List[Dict]]
    ) -> SamplingResult:
        """
        Run the TraStrainer sampling algorithm with windowed sampling.

        Args:
            traces: Dictionary of trace data
            metrics: Dictionary of metrics

        Returns:
            SamplingResult with sampling outcomes
        """
        start_time = time.time()
        logger.info(
            f"Starting TraStrainer with sample rate: {self.config.budget_sample_rate}"
        )

        return self._run_windowed_sampling(traces, metrics, start_time)

    def _run_windowed_sampling(
        self,
        traces: Dict[str, TraceData],
        metrics: Dict[Tuple[str, str], List[Dict]],
        start_time: float,
    ) -> SamplingResult:
        """Run sampling with sliding window approach"""
        traces_per_window = self.config.traces_per_window or 100
        logger.info(
            f"Using windowed sampling with {traces_per_window} traces per window"
        )

        sampled_trace_ids = []
        total_processed = 0
        total_skipped = 0

        # Initialize global history tracking (persistent across windows)
        global_history_metrics = self._init_history_metrics(metrics)
        global_history_structures = deque(maxlen=self.config.window_size)
        global_diversity_window = deque(maxlen=self.config.window_size)

        # Convert traces to list for windowing
        trace_items = list(traces.items())

        # Process traces in windows
        window_start = 0
        window_count = 0

        while window_start < len(trace_items):
            traces_per_window = self.config.traces_per_window or 100  # Provide default
            window_end = min(window_start + traces_per_window, len(trace_items))
            window_traces = dict(trace_items[window_start:window_end])

            window_count += 1
            logger.info(
                f"Processing window {window_count}: traces {window_start + 1}-{window_end} "
                f"({len(window_traces)} traces)"
            )

            # Process this window with persistent history
            window_result = self._process_window(
                window_traces,
                metrics,
                window_count,
                global_history_metrics,
                global_history_structures,
                global_diversity_window,
            )

            # Accumulate results
            sampled_trace_ids.extend(window_result.sampled_trace_ids)
            total_processed += window_result.total_traces_processed
            total_skipped += len(window_traces) - window_result.total_traces_processed

            # Move to next window
            window_start = window_end

        # Create final result
        end_time = time.time()
        execution_time = end_time - start_time
        actual_rate = (
            len(sampled_trace_ids) / total_processed if total_processed > 0 else 0
        )

        logger.info(
            f"Windowed TraStrainer completed: "
            f"processed={total_processed}, sampled={len(sampled_trace_ids)}, "
            f"skipped={total_skipped}, rate={actual_rate:.3f}, "
            f"windows={window_count}, time={execution_time:.2f}s"
        )

        return SamplingResult(
            sampled_trace_ids=sampled_trace_ids,
            total_traces_processed=total_processed,
            sampling_rate_achieved=actual_rate,
            execution_time=execution_time,
        )

    def _process_window(
        self,
        traces: Dict[str, TraceData],
        metrics: Dict[Tuple[str, str], List[Dict]],
        window_id: int,
        history_metrics: Dict[Tuple[str, str], Deque[float]],
        history_structures: Deque[List[str]],
        diversity_window: Deque[float],
    ) -> SamplingResult:
        """Process a single window of traces with persistent history"""
        window_start_time = time.time()

        # Initialize tracking variables for this window
        sampled_trace_ids = []
        processed_count = 0
        sample_count = 0
        skip_count = 0

        # Use the passed-in persistent history (NOT fresh for each window)
        # These queues maintain state across all windows

        # Calculate target samples for this window
        target_samples = max(1, int(len(traces) * self.config.budget_sample_rate))
        logger.debug(
            f"Window {window_id}: target {target_samples} samples from {len(traces)} traces"
        )

        # Get current global processed count (for warm-up logic)
        # This should be the total processed count across all previous windows
        current_global_processed = len(history_structures)

        # Process each trace in this window
        for trace_id, trace in traces.items():
            # Build trace tree and extract features
            tree = TraceProcessor.build_trace_tree(trace.spans)

            # Skip invalid traces
            if not tree.size() or tree.size() != len(trace.spans):
                skip_count += 1
                continue

            # Extract trace features
            trace_structure = self.feature_extractor.get_trace_structure_vector(
                trace, tree
            )
            system_metrics = self.preprocessor.extract_system_metrics(trace)
            trace_feature_values = self.feature_extractor.compute_trace_feature_values(
                system_metrics, metrics
            )

            # Get metric weights from predictor
            metrics_weights = self.metric_predictor.compute_metrics_weights(
                metrics, trace.start_time, trace.end_time
            )

            # Make sampling decision after warm-up period
            # Use global processed count (across all windows) for warm-up logic
            total_processed_so_far = len(history_structures) + processed_count
            if total_processed_so_far >= self.config.warm_up_size:
                system_rate = self.sampling_filter.compute_system_bias_rate(
                    history_metrics, trace_feature_values, metrics_weights
                )
                diversity_rate = self.sampling_filter.compute_diversity_bias_rate(
                    history_structures, trace_structure, diversity_window
                )

                # Use strict sampling if over budget for this window
                current_rate = (
                    sample_count / processed_count if processed_count > 0 else 0
                )
                strict = current_rate > self.config.budget_sample_rate

                is_sample, sys_random, div_random = self.sampling_decision.judge(
                    system_rate, diversity_rate, strict
                )

                # Add to sample if selected
                if is_sample:
                    sample_count += 1
                    sampled_trace_ids.append(trace_id)

                # Log sampling decision
                logger.debug(
                    f"Window {window_id} TraceID:{trace_id} "
                    f"SystemRate:{system_rate:.2f}/{sys_random:.2f} "
                    f"DiversityRate:{diversity_rate:.2f}/{div_random:.2f} "
                    f"IsAnd:{1 if strict else 0} "
                    f"Sample:{is_sample} "
                    f"CurSampleRate:{current_rate:.2f}"
                )

            else:
                # During warm-up, sample all traces
                sample_count += 1
                sampled_trace_ids.append(trace_id)

            # Update history
            history_structures.append(trace_structure)
            for key in metrics:
                if key in trace_feature_values:
                    history_metrics[key].append(trace_feature_values[key])

            processed_count += 1

            # Stop this window if we've reached the target
            if sample_count >= target_samples:
                logger.debug(
                    f"Window {window_id}: reached target {target_samples} samples, stopping window"
                )
                break

        # Create window result
        window_end_time = time.time()
        window_execution_time = window_end_time - window_start_time
        window_actual_rate = (
            sample_count / processed_count if processed_count > 0 else 0
        )

        logger.debug(
            f"Window {window_id} completed: "
            f"processed={processed_count}, sampled={sample_count}, "
            f"skipped={skip_count}, rate={window_actual_rate:.3f}, time={window_execution_time:.2f}s"
        )

        return SamplingResult(
            sampled_trace_ids=sampled_trace_ids,
            total_traces_processed=processed_count,
            sampling_rate_achieved=window_actual_rate,
            execution_time=window_execution_time,
        )

    def _run_legacy_sampling(
        self,
        traces: Dict[str, TraceData],
        metrics: Dict[Tuple[str, str], List[Dict]],
        start_time: float,
    ) -> SamplingResult:
        """Run the original non-windowed sampling algorithm"""
        logger.info("Using legacy (non-windowed) sampling")

        # Initialize tracking variables
        sampled_trace_ids = []
        processed_count = 0
        sample_count = 0
        skip_count = 0

        # Initialize history tracking
        history_metrics = self._init_history_metrics(metrics)
        history_structures = deque(maxlen=self.config.window_size)
        diversity_window = deque(maxlen=self.config.window_size)

        # Process each trace
        for trace_id, trace in traces.items():
            # Build trace tree and extract features
            tree = TraceProcessor.build_trace_tree(trace.spans)

            # Skip invalid traces
            if not tree.size() or tree.size() != len(trace.spans):
                skip_count += 1
                continue

            # Extract trace features
            trace_structure = self.feature_extractor.get_trace_structure_vector(
                trace, tree
            )
            system_metrics = self.preprocessor.extract_system_metrics(trace)
            trace_feature_values = self.feature_extractor.compute_trace_feature_values(
                system_metrics, metrics
            )

            # Get metric weights from predictor
            metrics_weights = self.metric_predictor.compute_metrics_weights(
                metrics, trace.start_time, trace.end_time
            )

            # Make sampling decision after warm-up period
            if processed_count >= self.config.warm_up_size:
                system_rate = self.sampling_filter.compute_system_bias_rate(
                    history_metrics, trace_feature_values, metrics_weights
                )
                diversity_rate = self.sampling_filter.compute_diversity_bias_rate(
                    history_structures, trace_structure, diversity_window
                )

                # Use strict sampling if over budget
                current_rate = sample_count / processed_count
                strict = current_rate > self.config.budget_sample_rate

                is_sample, sys_random, div_random = self.sampling_decision.judge(
                    system_rate, diversity_rate, strict
                )

                # Add to sample if selected
                if is_sample:
                    sample_count += 1
                    sampled_trace_ids.append(trace_id)

                # Log sampling decision
                logger.debug(
                    f"TraceID:{trace_id} "
                    f"SystemRate:{system_rate:.2f}/{sys_random:.2f} "
                    f"DiversityRate:{diversity_rate:.2f}/{div_random:.2f} "
                    f"IsAnd:{1 if strict else 0} "
                    f"Sample:{is_sample} "
                    f"CurSampleRate:{current_rate:.2f}"
                )

            else:
                # During warm-up, sample all traces
                sample_count += 1
                sampled_trace_ids.append(trace_id)

            # Update history
            history_structures.append(trace_structure)
            for key in metrics:
                if key in trace_feature_values:
                    history_metrics[key].append(trace_feature_values[key])

            processed_count += 1

            # Log progress periodically
            if processed_count % 100 == 0:
                current_rate = sample_count / processed_count
                logger.debug(
                    f"Processed {processed_count} traces, current sampling rate: {current_rate:.3f}"
                )

        # Create result
        end_time = time.time()
        execution_time = end_time - start_time
        actual_rate = sample_count / processed_count if processed_count > 0 else 0

        logger.info(
            f"Legacy TraStrainer completed: "
            f"processed={processed_count}, sampled={sample_count}, "
            f"skipped={skip_count}, rate={actual_rate:.3f}, time={execution_time:.2f}s"
        )

        return SamplingResult(
            sampled_trace_ids=sampled_trace_ids,
            total_traces_processed=processed_count,
            sampling_rate_achieved=actual_rate,
            execution_time=execution_time,
        )
        for trace_id, trace in traces.items():
            trace_start_time = time.time()

            # Build trace tree and extract features
            tree = TraceProcessor.build_trace_tree(trace.spans)

            # Skip invalid traces
            if not tree.size() or tree.size() != len(trace.spans):
                skip_count += 1
                continue

            # Extract trace features
            trace_structure = self.feature_extractor.get_trace_structure_vector(
                trace, tree
            )
            system_metrics = self.preprocessor.extract_system_metrics(trace)
            trace_feature_values = self.feature_extractor.compute_trace_feature_values(
                system_metrics, metrics
            )

            # Get metric weights from predictor
            metrics_weights = self.metric_predictor.compute_metrics_weights(
                metrics, trace.start_time, trace.end_time
            )

            # Make sampling decision after warm-up period
            if processed_count >= self.config.warm_up_size:
                system_rate = self.sampling_filter.compute_system_bias_rate(
                    history_metrics, trace_feature_values, metrics_weights
                )
                diversity_rate = self.sampling_filter.compute_diversity_bias_rate(
                    list(history_structures), trace_structure, diversity_window
                )

                # Use strict sampling if over budget
                current_rate = sample_count / processed_count
                strict = current_rate > self.config.budget_sample_rate

                is_sample, sys_random, div_random = self.sampling_decision.judge(
                    system_rate, diversity_rate, strict
                )

                # Log sampling decision
                logger.debug(
                    f"TraceID:{trace_id} "
                    f"SystemRate:{system_rate:.2f}/{sys_random:.2f} "
                    f"DiversityRate:{diversity_rate:.2f}/{div_random:.2f} "
                    f"IsAnd:{1 if strict else 0} "
                    f"Sample:{is_sample} "
                    f"CurSampleRate:{current_rate:.2f}"
                )

                # Add to sample if selected
                if is_sample:
                    sample_count += 1
                    sampled_trace_ids.append(trace_id)

            else:
                # During warm-up, sample all traces
                sample_count += 1
                sampled_trace_ids.append(trace_id)

            # Update history
            history_structures.append(trace_structure)
            for key in metrics:
                if key in trace_feature_values:
                    history_metrics[key].append(trace_feature_values[key])

            processed_count += 1

            # Log progress periodically
            if processed_count % 100 == 0:
                current_rate = sample_count / processed_count
                logger.debug(
                    f"Processed {processed_count} traces, current sampling rate: {current_rate:.3f}"
                )

        # 注释掉早期停止逻辑，让算法处理所有traces
        # # Stop if we've processed enough traces
        # target_processes = int(round(self.config.budget_sample_rate * len(traces)))
        # if processed_count >= target_processes:
        #     break

        # Create result
        end_time = time.time()
        execution_time = end_time - start_time
        actual_rate = sample_count / processed_count if processed_count > 0 else 0

        logger.info(
            f"TraStrainer completed: "
            f"processed={processed_count}, sampled={sample_count}, "
            f"skipped={skip_count}, rate={actual_rate:.3f}, time={execution_time:.2f}s"
        )

        return SamplingResult(
            sampled_trace_ids=sampled_trace_ids,
            total_traces_processed=processed_count,
            sampling_rate_achieved=actual_rate,
            execution_time=execution_time,
        )

    def _init_history_metrics(
        self, metrics: Dict[Tuple[str, str], List[Dict]]
    ) -> Dict[Tuple[str, str], Deque[float]]:
        """Initialize history tracking for metrics."""
        history_metrics = {}
        for key in metrics:
            history_metrics[key] = deque(maxlen=self.config.window_size)
        return history_metrics


def run_trastrainer(
    traces: Dict[str, TraceData],
    metrics: Dict[Tuple[str, str], List[Dict]],
    budget_sample_rate: float,
    checkpoints_dir: str = "./checkpoints",
) -> List[str]:
    """
    Legacy function to maintain compatibility with existing code.

    Args:
        traces: Dictionary of traces
        metrics: Dictionary of metrics
        budget_sample_rate: Target sampling rate
        checkpoints_dir: Directory containing model checkpoints

    Returns:
        List of sampled trace IDs
    """
    config = SamplingConfig(
        budget_sample_rate=budget_sample_rate, checkpoints_dir=checkpoints_dir
    )

    algorithm = TraStrainerAlgorithm(config)
    result = algorithm.run(traces, metrics)

    return result.sampled_trace_ids
