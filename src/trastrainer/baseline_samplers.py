"""Baseline samplers wrapper for RCABench platform."""

import random
from collections import deque
from typing import List

from rcabench_platform.v2.logging import logger
from rcabench_platform.v2.samplers.spec import (
    SamplerArgs,
    SampleResult,
    SamplingMode,
    TraceSampler,
)

from .polar_loader import PolarDataPreprocessor


class BaselineSampler(TraceSampler):
    """Base class for baseline algorithm samplers."""

    def __init__(self, algorithm_name: str):
        """
        Initialize baseline sampler.

        Args:
            algorithm_name: Name of baseline algorithm ('random', 'sifter', 'sieve', 'wt')
        """
        self.algorithm_name = algorithm_name

    def needs_cpu_count(self) -> int | None:
        """Return number of CPU cores needed."""
        return 2

    def __call__(self, args: SamplerArgs) -> List[SampleResult]:
        """
        Run baseline sampling algorithm.

        Args:
            args: Sampling arguments from platform

        Returns:
            List of SampleResult with trace_id and sample_score
        """
        logger.info(
            f"Running {self.algorithm_name} baseline sampler on {args.dataset}/{args.datapack}"
        )

        try:
            # Load data using Polars preprocessor
            preprocessor = PolarDataPreprocessor()
            traces, metrics = preprocessor.load_data(args.input_folder)

            if not traces:
                logger.warning("No traces found in input data")
                return []

            total_traces = len(traces)
            target_count = int(round(total_traces * args.sampling_rate))

            logger.info(
                f"{self.algorithm_name}: {total_traces} traces, target={target_count}, rate={args.sampling_rate:.3f}"
            )

            # Compute trace scores using baseline algorithm
            trace_scores = self._compute_trace_scores(traces, args.sampling_rate)

            # Convert to SampleResult format
            results = [
                SampleResult(trace_id=trace_id, sample_score=score)
                for trace_id, score in trace_scores.items()
            ]

            # Apply sampling mode
            if args.mode == SamplingMode.ONLINE:
                # Online mode: use score as sampling probability
                sampled_results = []
                for result in results:
                    # For baseline algorithms, treat score as sampling probability
                    if random.random() < result.sample_score:
                        sampled_results.append(result)

                # If too few samples, add more based on highest scores
                if len(sampled_results) < target_count:
                    remaining = [r for r in results if r not in sampled_results]
                    remaining.sort(key=lambda x: x.sample_score, reverse=True)
                    additional_needed = min(
                        target_count - len(sampled_results), len(remaining)
                    )
                    sampled_results.extend(remaining[:additional_needed])

                logger.info(
                    f"{self.algorithm_name} Online: sampled={len(sampled_results)}"
                )
                return sampled_results

            elif args.mode == SamplingMode.OFFLINE:
                # Offline mode: sequential sampling with early exit when budget reached
                # Handle TracePicker (normal-only) vs regular datasets

                # Check if this is TracePicker data (normal-only)
                is_tracepicker = self._is_tracepicker_data(args)

                if is_tracepicker:
                    # TracePicker: all traces are normal, no separation needed
                    logger.info(
                        "Detected TracePicker data - treating all traces as normal period"
                    )

                    all_results = [
                        SampleResult(trace_id=trace_id, sample_score=score)
                        for trace_id, score in trace_scores.items()
                    ]

                    # Sequential sampling until budget is reached
                    sampled_results = []
                    for result in all_results:
                        if random.random() < result.sample_score:
                            sampled_results.append(result)
                            if len(sampled_results) >= target_count:
                                break

                    logger.info(
                        f"{self.algorithm_name} TracePicker Offline: sampled={len(sampled_results)}/{target_count}"
                    )
                    return sampled_results

                else:
                    # Regular datasets: separate normal and abnormal periods
                    inject_time = preprocessor.inject_time
                    if not inject_time:
                        logger.warning(
                            "No inject time found, treating all traces as normal period"
                        )
                        inject_time_str = "9999-12-31T23:59:59+00:00"  # Far future
                    else:
                        inject_time_str = inject_time.isoformat()

                    # Separate traces into normal and abnormal periods
                    normal_traces = []
                    abnormal_traces = []

                    for trace_id, trace in traces.items():
                        if trace_id in trace_scores:
                            result = SampleResult(
                                trace_id=trace_id, sample_score=trace_scores[trace_id]
                            )
                            if trace.start_time < inject_time_str:
                                normal_traces.append(result)
                            else:
                                abnormal_traces.append(result)

                    # Calculate separate budgets for normal and abnormal periods
                    normal_budget = int(round(args.sampling_rate * len(normal_traces)))
                    abnormal_budget = int(
                        round(args.sampling_rate * len(abnormal_traces))
                    )

                    logger.info(
                        f"Normal period: {len(normal_traces)} traces, budget={normal_budget}"
                    )
                    logger.info(
                        f"Abnormal period: {len(abnormal_traces)} traces, budget={abnormal_budget}"
                    )

                    # Sequential sampling for normal period
                    normal_sampled = []
                    for result in normal_traces:
                        if random.random() < result.sample_score:
                            normal_sampled.append(result)
                            if len(normal_sampled) >= normal_budget:
                                break

                    # Sequential sampling for abnormal period
                    abnormal_sampled = []
                    for result in abnormal_traces:
                        if random.random() < result.sample_score:
                            abnormal_sampled.append(result)
                            if len(abnormal_sampled) >= abnormal_budget:
                                break

                    # Combine results
                    sampled_results = normal_sampled + abnormal_sampled

                    logger.info(
                        f"{self.algorithm_name} Offline: normal_sampled={len(normal_sampled)}/{normal_budget}, "
                        f"abnormal_sampled={len(abnormal_sampled)}/{abnormal_budget}, total={len(sampled_results)}"
                    )
                    return sampled_results

            return results

        except Exception as e:
            logger.error(f"{self.algorithm_name} sampler failed: {e}")
            return []

    def _is_tracepicker_data(self, args: SamplerArgs) -> bool:
        """Check if data is from TracePicker dataset"""
        # Check dataset name or presence of TracePicker-specific files
        if args.dataset == "tracepicker":
            return True

        # Check for TracePicker-specific files
        if (args.input_folder / "normal_traces.parquet").exists():
            return True

        # Check metadata
        metadata_path = args.input_folder / "metadata.json"
        if metadata_path.exists():
            try:
                import json

                with open(metadata_path, "r") as f:
                    metadata = json.load(f)
                return metadata.get("source") == "tracepicker"
            except Exception:
                pass

        return False

    def _extract_simple_structure(self, trace_data) -> List[str]:
        """Extract simple trace structure for TracePicker data"""
        try:
            # Use service call sequence as structure
            services = []
            for span in sorted(trace_data.spans, key=lambda x: x.start_time):
                services.append(span.service_name)

            # Remove consecutive duplicates to get call path
            structure = []
            prev_service = None
            for service in services:
                if service != prev_service:
                    structure.append(service)
                    prev_service = service

            return structure if structure else ["unknown"]

        except Exception as e:
            logger.debug(f"Error extracting structure: {e}")
            return ["unknown"]

    def _compute_trace_scores(self, traces: dict, sampling_rate: float) -> dict:
        """
        Compute sampling scores for traces using baseline algorithm.

        Args:
            traces: Dictionary of trace data
            sampling_rate: Target sampling rate

        Returns:
            Dictionary mapping trace_id to sample_score
        """
        if self.algorithm_name == "random":
            return self._random_scores(traces)
        elif self.algorithm_name == "sifter":
            return self._sifter_scores(traces, sampling_rate)
        elif self.algorithm_name == "sieve":
            return self._sieve_scores(traces, sampling_rate)
        elif self.algorithm_name == "wt":
            return self._wt_scores(traces, sampling_rate)
        else:
            logger.warning(f"Unknown algorithm {self.algorithm_name}, using random")
            return self._random_scores(traces)

    def _random_scores(self, traces: dict) -> dict:
        """Random baseline: assign random scores."""
        return {trace_id: random.random() for trace_id in traces.keys()}

    def _sifter_scores(self, traces: dict, sampling_rate: float) -> dict:
        """Sifter baseline: diversity-based scores."""
        from collections import deque

        trace_scores = {}
        history_structures = deque(maxlen=100)

        for trace_id, trace_data in traces.items():
            try:
                # For TracePicker data, use simplified structure extraction
                # since tree building can be complex and error-prone
                trace_structure = self._extract_simple_structure(trace_data)

                # Calculate diversity score
                diversity_score = self._calculate_diversity_score(
                    history_structures, trace_structure
                )

                # Normalize to [0, 1] and use as sampling probability
                normalized_score = min(1.0, max(0.0, diversity_score))
                trace_scores[trace_id] = normalized_score

                # Update history
                history_structures.append(trace_structure)

            except Exception as e:
                logger.debug(f"Error processing trace {trace_id}: {e}")
                trace_scores[trace_id] = random.random()  # Fallback to random

        return trace_scores

    def _calculate_diversity_score(
        self, history_structures: deque, current_structure: List[str]
    ) -> float:
        """Calculate diversity-based score."""
        if not history_structures:
            return 1.0

        # Simple diversity calculation: higher score for more unique structures
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

        # Return diversity score (inverse of similarity)
        return 1.0 - max_similarity

    def _sieve_scores(self, traces: dict, sampling_rate: float) -> dict:
        """Sieve baseline: reservoir sampling-like scores."""
        # For Sieve, we'll use a simplified scoring approach
        # since the original Sieve algorithm is complex
        trace_scores = {}
        trace_list = list(traces.items())

        for i, (trace_id, trace_data) in enumerate(trace_list):
            try:
                # Simple Sieve-like scoring: prefer traces with more diverse structures
                # and higher workloads
                num_spans = len(trace_data.spans)
                span_diversity = len(
                    set(span.operation_name for span in trace_data.spans)
                )

                # Combine span count and diversity
                workload_score = num_spans / 100.0  # Normalize by typical span count
                diversity_score = span_diversity / max(1, num_spans)  # Diversity ratio

                # Add reservoir sampling component
                reservoir_score = (i + 1) ** (-0.5)  # Decay with position

                combined_score = (
                    workload_score + diversity_score + reservoir_score
                ) / 3.0
                trace_scores[trace_id] = min(1.0, combined_score)

            except Exception as e:
                logger.debug(f"Error processing trace {trace_id}: {e}")
                trace_scores[trace_id] = random.random()

        return trace_scores

    def _wt_scores(self, traces: dict, sampling_rate: float) -> dict:
        """WT (Workload-based) baseline: workload-based scores."""
        trace_scores = {}
        workloads = []

        # First pass: calculate workloads
        for trace_id, trace_data in traces.items():
            try:
                # Calculate workload metrics
                num_spans = len(trace_data.spans)
                total_duration = sum(span.duration for span in trace_data.spans)
                avg_duration = total_duration / num_spans if num_spans > 0 else 0

                # Number of unique services
                unique_services = len(
                    set(span.service_name for span in trace_data.spans)
                )

                # Combined workload score
                workload = (
                    num_spans * (avg_duration / 1e6) * unique_services
                )  # Normalize duration
                workloads.append((trace_id, workload))

            except Exception as e:
                logger.debug(f"Error processing trace {trace_id}: {e}")
                workloads.append((trace_id, 0.0))

        # Normalize workloads to [0, 1] range
        if workloads:
            max_workload = max(w[1] for w in workloads)
            min_workload = min(w[1] for w in workloads)
            workload_range = max_workload - min_workload

            for trace_id, workload in workloads:
                if workload_range > 0:
                    normalized_score = (workload - min_workload) / workload_range
                else:
                    normalized_score = 0.5  # All workloads are the same

                trace_scores[trace_id] = normalized_score

        return trace_scores


class SifterSampler(BaselineSampler):
    """Sifter sampling baseline."""

    def __init__(self):
        super().__init__("sifter")


class SieveSampler(BaselineSampler):
    """Sieve sampling baseline."""

    def __init__(self):
        super().__init__("sieve")


class WTSampler(BaselineSampler):
    """WT (Workload-based) sampling baseline."""

    def __init__(self):
        super().__init__("wt")


class RandomSampler(BaselineSampler):
    """Random sampling baseline."""

    def __init__(self):
        super().__init__("random")
