"""Main entry point for TraStrainer application."""

import argparse
import sys
from pathlib import Path

from rcabench_platform.v2.logging import logger

from .algorithm import TraStrainerAlgorithm
from .data_structures import SamplingConfig
from .preprocessor import DataPreprocessor


def main():
    """Main function for TraStrainer CLI."""
    parser = argparse.ArgumentParser(
        description="TraStrainer: Adaptive trace sampling with system runtime state"
    )

    parser.add_argument(
        "--path",
        type=str,
        required=True,
        help="Path to data directory containing traces and metrics",
    )

    parser.add_argument(
        "--rate",
        type=float,
        required=True,
        help="Target sampling rate (e.g., 0.1 for 10%)",
    )

    parser.add_argument(
        "--checkpoints",
        type=str,
        default="./checkpoints",
        help="Directory containing model checkpoints",
    )

    parser.add_argument(
        "--window-size",
        type=int,
        help="Window size for history tracking (default: 1/rate)",
    )

    parser.add_argument(
        "--warm-up",
        type=int,
        default=10,
        help="Number of traces to process before applying sampling logic",
    )

    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Validate arguments
    if not Path(args.path).exists():
        logger.error(f"Data path does not exist: {args.path}")
        sys.exit(1)

    if not (0 < args.rate <= 1):
        logger.error(f"Sampling rate must be between 0 and 1, got: {args.rate}")
        sys.exit(1)

    # Configure logging
    if args.verbose:
        logger.setLevel("DEBUG")

    try:
        run_trastrainer_cli(args)
    except Exception as e:
        logger.error(f"TraStrainer failed: {e}")
        sys.exit(1)


def run_trastrainer_cli(args):
    """Run TraStrainer with CLI arguments."""
    logger.info(f"Starting TraStrainer with data path: {args.path}")
    logger.info(f"Target sampling rate: {args.rate}")

    # Create configuration
    config = SamplingConfig(
        budget_sample_rate=args.rate,
        window_size=args.window_size,
        warm_up_size=args.warm_up,
        checkpoints_dir=args.checkpoints,
    )

    # Load data
    logger.info("Loading data...")
    preprocessor = DataPreprocessor()
    traces, metrics = preprocessor.load_data(args.path)

    if not traces:
        logger.error("No traces found in data")
        return

    if not metrics:
        logger.warning("No metrics found in data")

    logger.info(f"Loaded {len(traces)} traces and {len(metrics)} metric series")

    # Run TraStrainer algorithm
    logger.info("Running TraStrainer algorithm...")
    algorithm = TraStrainerAlgorithm(config)
    result = algorithm.run(traces, metrics)

    # Output results
    logger.info("=== SAMPLING RESULTS ===")
    logger.info(f"Traces processed: {result.total_traces_processed}")
    logger.info(f"Traces sampled: {result.actual_sample_count}")
    logger.info(f"Actual sampling rate: {result.sampling_rate_achieved:.4f}")
    logger.info(f"Execution time: {result.execution_time:.2f}s")
    logger.info(f"Sampled trace IDs: {result.sampled_trace_ids}")

    print(f"sampling_rate:{args.rate}, sampling trace_ids:{result.sampled_trace_ids}")


if __name__ == "__main__":
    main()
