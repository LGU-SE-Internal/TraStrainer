"""TraStrainer sampler wrapper for RCABench platform."""

from typing import List

from rcabench_platform.v2.logging import logger
from rcabench_platform.v2.samplers.spec import (
    SamplerArgs,
    SampleResult,
    SamplingMode,
    TraceSampler,
)

from .algorithm import FeatureExtractor, SamplingFilter
from .data_structures import SamplingConfig, TraceData
from .polar_loader import PolarDataPreprocessor


class TraStrainerSampler(TraceSampler):
    """TraStrainer algorithm wrapper for RCABench platform."""

    def __init__(self, checkpoints_dir: str = "./checkpoints"):
        """
        Initialize TraStrainer sampler.

        Args:
            checkpoints_dir: Directory containing model checkpoints
        """
        self.checkpoints_dir = checkpoints_dir

    def needs_cpu_count(self) -> int | None:
        """Return number of CPU cores needed."""
        return 4  # TraStrainer can run on single core

    def __call__(self, args: SamplerArgs) -> List[SampleResult]:
        """
        Run TraStrainer sampling algorithm.

        Args:
            args: Sampling arguments from platform

        Returns:
            List of SampleResult with trace_id and sample_score
        """
        logger.info(f"Running TraStrainer sampler on {args.dataset}/{args.datapack}")

        try:
            # Load data using Polars preprocessor
            preprocessor = PolarDataPreprocessor()
            traces, metrics = preprocessor.load_data(args.input_folder)

            if not traces:
                logger.warning("No traces found in input data")
                return []

            # Calculate target sample count from sampling rate
            total_traces = len(traces)
            target_count = int(round(total_traces * args.sampling_rate))

            logger.info(
                f"TraStrainer: {total_traces} traces, target={target_count}, rate={args.sampling_rate:.3f}"
            )

            # Configure TraStrainer algorithm
            config = SamplingConfig(
                target_sample_count=target_count,
                budget_sample_rate=args.sampling_rate,
                checkpoints_dir=self.checkpoints_dir,
            )

            # Run TraStrainer algorithm to get scores
            trace_scores = self._compute_trace_scores(traces, metrics, config)

            # Convert to SampleResult format
            results = [
                SampleResult(trace_id=trace_id, sample_score=score)
                for trace_id, score in trace_scores.items()
            ]

            # Apply sampling mode
            if args.mode == SamplingMode.ONLINE:
                # Online mode: independent sampling based on score threshold
                # Use adaptive threshold based on sampling rate
                scores = [r.sample_score for r in results]
                if scores:
                    # Set threshold so that approximately sampling_rate fraction will be sampled
                    sorted_scores = sorted(scores, reverse=True)
                    threshold_idx = min(
                        int(len(sorted_scores) * args.sampling_rate),
                        len(sorted_scores) - 1,
                    )
                    threshold = sorted_scores[threshold_idx]

                    sampled_results = [
                        r for r in results if r.sample_score >= threshold
                    ]
                    logger.info(
                        f"TraStrainer Online: threshold={threshold:.3f}, sampled={len(sampled_results)}"
                    )
                    return sampled_results
                else:
                    return []

            elif args.mode == SamplingMode.OFFLINE:
                # Offline mode: sequential sampling with early exit when budget reached
                # Process traces in order and sample based on combined score threshold
                # This matches the original TraStrainer offline sampling logic

                # Sort results by trace processing order (not by score)
                # to maintain temporal sequence
                trace_order = list(traces.keys())
                ordered_results = []
                for trace_id in trace_order:
                    if trace_id in trace_scores:
                        ordered_results.append(
                            SampleResult(
                                trace_id=trace_id, sample_score=trace_scores[trace_id]
                            )
                        )

                # Calculate budget for total traces
                total_budget = int(round(args.sampling_rate * len(traces)))

                # Sequential sampling with score threshold
                sampled_results = []
                for result in ordered_results:
                    # Sample if combined score is above threshold (e.g., > 0.5)
                    if result.sample_score > 0.5:  # Combined score threshold
                        sampled_results.append(result)

                        # Check if budget is reached
                        if len(sampled_results) >= total_budget:
                            break

                logger.info(
                    f"TraStrainer Offline: processed={len(ordered_results)}, sampled={len(sampled_results)}, budget={total_budget}"
                )
                return sampled_results

            return results

        except Exception as e:
            logger.error(f"TraStrainer sampler failed: {e}")
            return []

    def _compute_trace_scores(
        self, traces: dict, metrics: dict, config: SamplingConfig
    ) -> dict:
        """
        Compute sampling scores for all traces using TraStrainer logic.

        Args:
            traces: Dictionary of trace data
            metrics: Dictionary of metrics
            config: Sampling configuration

        Returns:
            Dictionary mapping trace_id to sample_score
        """
        from collections import deque

        from .predictors import MetricPredictor
        from .preprocessor import TraceProcessor

        # Initialize TraStrainer components
        metric_predictor = MetricPredictor(config.checkpoints_dir)
        feature_extractor = FeatureExtractor()
        sampling_filter = SamplingFilter()

        # Initialize tracking variables
        trace_scores = {}
        processed_count = 0

        # Initialize history tracking
        history_metrics = {}
        for key in metrics:
            history_metrics[key] = deque(maxlen=config.window_size)

        history_structures = deque(maxlen=config.window_size)
        diversity_window = deque(maxlen=config.window_size)

        logger.info(f"Computing TraStrainer scores for {len(traces)} traces")

        # Process each trace to compute scores
        for trace_id, trace in traces.items():
            try:
                # Build trace tree and extract features
                tree = TraceProcessor.build_trace_tree(trace.spans)

                # Skip invalid traces
                if not tree.size() or tree.size() != len(trace.spans):
                    trace_scores[trace_id] = 0.0
                    continue

                # Extract trace features
                trace_structure = feature_extractor.get_trace_structure_vector(
                    trace, tree
                )

                # Extract system metrics (simplified for score computation)
                system_metrics = self._extract_system_metrics(trace)
                trace_feature_values = feature_extractor.compute_trace_feature_values(
                    system_metrics, metrics
                )

                # Get metric weights from predictor
                metrics_weights = metric_predictor.compute_metrics_weights(
                    metrics, trace.start_time, trace.end_time
                )

                # Compute sampling rates after warm-up
                if processed_count >= config.warm_up_size:
                    system_rate = sampling_filter.compute_system_bias_rate(
                        history_metrics, trace_feature_values, metrics_weights
                    )
                    diversity_rate = sampling_filter.compute_diversity_bias_rate(
                        history_structures, trace_structure, diversity_window
                    )

                    # Combine system and diversity rates as score (multiply probabilities)
                    # Higher rates indicate higher sampling priority
                    combined_score = system_rate * diversity_rate

                    # Normalize to [0, 1] range using tanh-like function
                    normalized_score = (
                        combined_score + 1
                    ) / 2  # Shift from [-1,1] to [0,1]

                else:
                    # During warm-up, use default score
                    normalized_score = 0.5

                trace_scores[trace_id] = normalized_score

                # Update history
                history_structures.append(trace_structure)
                for key in metrics:
                    if key in trace_feature_values:
                        history_metrics[key].append(trace_feature_values[key])

                processed_count += 1

                # Log progress
                if processed_count % 100 == 0:
                    logger.debug(f"Processed {processed_count}/{len(traces)} traces")

            except Exception as e:
                logger.debug(f"Error processing trace {trace_id}: {e}")
                trace_scores[trace_id] = 0.0
                continue

        logger.info(f"Computed scores for {len(trace_scores)} traces")
        return trace_scores

    def _extract_system_metrics(self, trace: TraceData):
        """Extract simplified system metrics from trace."""
        from .data_structures import SystemMetrics

        service_metrics = {}
        resource_metrics = {}
        resources = ["sql"]

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
                        {
                            "span_id": span.span_id,
                            "duration": span.duration,
                        }
                    )

        return SystemMetrics(
            service_metrics=service_metrics, resource_metrics=resource_metrics
        )
