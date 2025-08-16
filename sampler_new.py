"""Updated sampler script using the restructured TraStrainer package with Polars support."""

import argparse
import sys
from pathlib import Path

from rcabench_platform.v2.logging import logger

# Use the new Polars-based approach
from src.trastrainer import PolarDataPreprocessor, SamplingConfig, TraStrainerAlgorithm


def main():
    """Main function for the sampler script."""
    parser = argparse.ArgumentParser(description="TraStrainer: Adaptive trace sampling")
    parser.add_argument("--path", type=str, required=True, help="Data directory path")
    parser.add_argument(
        "--rate", type=float, required=True, help="Target sampling rate"
    )

    args = parser.parse_args()

    # Validate inputs
    if not Path(args.path).exists():
        logger.error(f"Data path does not exist: {args.path}")
        sys.exit(1)

    if not (0 < args.rate <= 1):
        logger.error(f"Sampling rate must be between 0 and 1, got: {args.rate}")
        sys.exit(1)

    run_sampling(args.path, args.rate)


def run_sampling(data_path: str, sampling_rate: float):
    """Run TraStrainer sampling with the new Polars-based approach."""
    logger.info(f"Loading data from: {data_path}")

    # Data preprocessing using Polars
    preprocessor = PolarDataPreprocessor()
    traces, metrics = preprocessor.load_data(Path(data_path))

    logger.info(f"Loaded {len(traces)} traces and {len(metrics)} metric series")

    if not traces:
        logger.error("No traces found")
        return

    # Configure and run algorithm
    config = SamplingConfig(budget_sample_rate=sampling_rate)
    algorithm = TraStrainerAlgorithm(config)

    logger.info(f"Running TraStrainer with sampling rate: {sampling_rate}")
    result = algorithm.run(traces, metrics)

    # Output results
    logger.info("Sampling completed")
    logger.info(f"  Target rate: {sampling_rate}")
    logger.info(f"  Actual rate: {result.sampling_rate_achieved:.4f}")
    logger.info(f"  Traces processed: {result.total_traces_processed}")
    logger.info(f"  Traces sampled: {result.actual_sample_count}")
    logger.info(f"  Execution time: {result.execution_time:.2f}s")

    # Print results in original format for compatibility
    print(
        f"sampling_rate:{sampling_rate}, sampling trace_ids:{result.sampled_trace_ids}"
    )


if __name__ == "__main__":
    main()
