"""TraStrainer Diversity-only sampler wrapper for RCABench platform."""

from collections import deque
from typing import List

from rcabench_platform.v2.logging import logger
from rcabench_platform.v2.samplers.spec import (
    SamplerArgs,
    SampleResult,
    SamplingMode,
    TraceSampler,
)

from .algorithm import FeatureExtractor, SimilarityCalculator
from .data_structures import SamplingConfig
from .polar_loader import PolarDataPreprocessor


class TraStrainerDiversitySampler(TraceSampler):
    """TraStrainer diversity-only algorithm wrapper for RCABench platform."""

    def __init__(self):
        """Initialize TraStrainer diversity sampler."""
        pass

    def needs_cpu_count(self) -> int | None:
        """Return number of CPU cores needed."""
        return 2  # TraStrainer can run on single core

    def __call__(self, args: SamplerArgs) -> List[SampleResult]:
        """
        Run TraStrainer diversity-only sampling algorithm.

        Args:
            args: Sampling arguments from platform

        Returns:
            List of SampleResult with trace_id and diversity_score
        """
        logger.info(
            f"Running TraStrainer Diversity sampler on {args.dataset}/{args.datapack}"
        )

        try:
            # Load data using Polars preprocessor (we only need traces, not metrics)
            preprocessor = PolarDataPreprocessor()
            traces, _ = preprocessor.load_data(args.input_folder)  # Ignore metrics

            if not traces:
                logger.warning("No traces found in input data")
                return []

            # Calculate target sample count from sampling rate
            total_traces = len(traces)
            target_count = int(round(total_traces * args.sampling_rate))

            logger.info(
                f"TraStrainer Diversity: {total_traces} traces, target={target_count}, rate={args.sampling_rate:.3f}"
            )

            # Configure algorithm
            config = SamplingConfig(
                target_sample_count=target_count,
                budget_sample_rate=args.sampling_rate,
            )

            # Run diversity-only algorithm to get scores
            trace_scores = self._compute_diversity_scores(traces, config)

            # Convert to SampleResult format
            results = [
                SampleResult(trace_id=trace_id, sample_score=score)
                for trace_id, score in trace_scores.items()
            ]

            # Apply sampling mode
            if args.mode == SamplingMode.ONLINE:
                # Online mode: independent sampling based on score threshold
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
                        f"TraStrainer Diversity Online: threshold={threshold:.3f}, sampled={len(sampled_results)}"
                    )
                    return sampled_results
                else:
                    return []

            elif args.mode == SamplingMode.OFFLINE:
                # Offline mode: sequential sampling with early exit when budget reached
                # Process traces in temporal order and sample based on diversity score threshold
                # This matches the original TraStrainer offline sampling logic

                # Get preprocessor's inject time to separate normal/abnormal periods
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
                abnormal_budget = int(round(args.sampling_rate * len(abnormal_traces)))

                logger.info(
                    f"Normal period: {len(normal_traces)} traces, budget={normal_budget}"
                )
                logger.info(
                    f"Abnormal period: {len(abnormal_traces)} traces, budget={abnormal_budget}"
                )

                # Sequential sampling for normal period
                normal_sampled = []
                for result in normal_traces:
                    if result.sample_score > 0.5:  # Diversity threshold
                        normal_sampled.append(result)
                        if len(normal_sampled) >= normal_budget:
                            break

                # Sequential sampling for abnormal period
                abnormal_sampled = []
                for result in abnormal_traces:
                    if result.sample_score > 0.5:  # Diversity threshold
                        abnormal_sampled.append(result)
                        if len(abnormal_sampled) >= abnormal_budget:
                            break

                # Combine results
                sampled_results = normal_sampled + abnormal_sampled

                logger.info(
                    f"TraStrainer Diversity Offline: normal_sampled={len(normal_sampled)}/{normal_budget}, "
                    f"abnormal_sampled={len(abnormal_sampled)}/{abnormal_budget}, total={len(sampled_results)}"
                )
                return sampled_results

            return results

        except Exception as e:
            logger.error(f"TraStrainer Diversity sampler failed: {e}")
            return []

    def _compute_diversity_scores(self, traces: dict, config: SamplingConfig) -> dict:
        """
        Compute diversity scores for all traces using TraStrainer diversity logic only.

        Args:
            traces: Dictionary of trace data
            config: Sampling configuration

        Returns:
            Dictionary mapping trace_id to diversity_score
        """
        from collections import deque

        from .preprocessor import TraceProcessor

        # Initialize TraStrainer components
        feature_extractor = FeatureExtractor()

        # Initialize tracking variables for debugging
        trace_scores = {}
        processed_count = 0
        skipped_invalid_tree = 0
        skipped_tree_size_mismatch = 0
        skipped_extraction_error = 0

        # Initialize history tracking for diversity only
        history_structures = deque(maxlen=config.window_size)
        diversity_window = deque(maxlen=config.window_size)

        logger.info(f"Computing TraStrainer diversity scores for {len(traces)} traces")

        # Process each trace to compute diversity scores
        for trace_id, trace in traces.items():
            try:
                # Build trace tree and extract features
                tree = TraceProcessor.build_trace_tree(trace.spans)

                # Skip invalid traces
                if not tree.size():
                    trace_scores[trace_id] = 0.0
                    skipped_invalid_tree += 1
                    continue

                if tree.size() != len(trace.spans):
                    trace_scores[trace_id] = 0.0
                    skipped_tree_size_mismatch += 1
                    continue

                # Extract trace structure
                trace_structure = feature_extractor.get_trace_structure_vector(
                    trace, tree
                )

                # Compute diversity score after warm-up
                if processed_count >= max(
                    config.warm_up_size, 10
                ):  # Ensure at least 10 traces for comparison
                    diversity_score = self._compute_diversity_rate(
                        history_structures, trace_structure, diversity_window
                    )
                else:
                    # During warm-up, use high diversity score to encourage sampling
                    diversity_score = 0.8

                trace_scores[trace_id] = diversity_score

                # Update history
                history_structures.append(trace_structure)
                processed_count += 1

                # Log progress and diversity statistics
                if processed_count % 200 == 0:
                    logger.debug(f"Processed {processed_count}/{len(traces)} traces")
                    if diversity_window:
                        avg_diversity = sum(diversity_window) / len(diversity_window)
                        logger.debug(
                            f"Average diversity in window: {avg_diversity:.3f}"
                        )

            except Exception as e:
                logger.debug(f"Error processing trace {trace_id}: {e}")
                trace_scores[trace_id] = 0.0
                skipped_extraction_error += 1
                continue

        # Log final processing statistics
        logger.info(
            f"Processing completed - Total processed: {processed_count}/{len(traces)}"
        )
        logger.info(f"Successfully scored: {len(trace_scores)} traces")
        logger.info(f"Skipped - Invalid tree: {skipped_invalid_tree}")
        logger.info(f"Skipped - Tree size mismatch: {skipped_tree_size_mismatch}")
        logger.info(f"Skipped - Extraction error: {skipped_extraction_error}")

        # Log final diversity statistics
        if trace_scores:
            scores = list(trace_scores.values())
            non_zero_scores = [s for s in scores if s > 0]
            logger.info(
                f"Diversity scores - Min: {min(scores):.3f}, Max: {max(scores):.3f}, Avg: {sum(scores) / len(scores):.3f}"
            )
            logger.info(
                f"Non-zero scores: {len(non_zero_scores)}/{len(scores)} ({len(non_zero_scores) / len(scores) * 100:.1f}%)"
            )

        logger.info(f"Computed diversity scores for {len(trace_scores)} traces")
        return trace_scores

    def _compute_diversity_rate(
        self, history_structures: deque, trace_structure: list, diversity_window: deque
    ) -> float:
        """
        Calculate diversity rate based on trace structure similarity.
        Uses the same algorithm as the main TraStrainer implementation.

        Args:
            history_structures: Collection of historical trace structures
            trace_structure: Current trace structure
            diversity_window: Window of diversity values for normalization

        Returns:
            Diversity score [0-1]
        """
        if not history_structures:
            return 1.0

        # Count occurrences of each trace structure
        structure_counts = {}
        for structure in history_structures:
            key = "+".join(structure)
            structure_counts[key] = structure_counts.get(key, 0) + 1

        # Find most similar historical trace
        max_similarity = 0
        most_similar_key = ""

        for history_structure in history_structures:
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
