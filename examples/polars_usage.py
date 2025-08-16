"""Example usage of TraStrainer with new Polars-based data loading."""

from pathlib import Path

from rcabench_platform.v2.logging import logger

# Import the new components
from src.trastrainer import (
    PolarDataPreprocessor,
    SamplingConfig,
    TraStrainer,
    TraStrainerAlgorithm,
    trastrainer_sampling,
)


def example_basic_usage():
    """Basic example of using TraStrainer with Polars data."""
    logger.info("=== TraStrainer Polars Example ===")

    # Example data path (adjust to your actual data location)
    data_path = Path("./data/example_data")

    if not data_path.exists():
        logger.warning(f"Example data path does not exist: {data_path}")
        logger.info(
            "This example requires data in Parquet format with the following files:"
        )
        logger.info("  - normal_traces.parquet")
        logger.info("  - abnormal_traces.parquet")
        logger.info("  - normal_metrics.parquet")
        logger.info("  - abnormal_metrics.parquet")
        logger.info("  - env.json")
        return

    # Method 1: Using the high-level function
    logger.info("Method 1: Using trastrainer_sampling function")
    result = trastrainer_sampling(input_folder=data_path, sampling_rate=0.1)

    if "error" not in result:
        logger.info(f"Sampled {len(result['sampled_trace_ids'])} traces")
        logger.info(f"Sampling rate achieved: {result['sampling_rate_achieved']:.4f}")

    # Method 2: Using the components directly
    logger.info("Method 2: Using components directly")

    # Load data
    preprocessor = PolarDataPreprocessor()
    traces, metrics = preprocessor.load_data(data_path)

    logger.info(f"Loaded {len(traces)} traces and {len(metrics)} metric series")

    # Configure algorithm
    config = SamplingConfig(
        budget_sample_rate=0.1,
        warm_up_size=min(10, len(traces) // 10),
        checkpoints_dir="./checkpoints",
    )

    # Run algorithm
    algorithm = TraStrainerAlgorithm(config)
    result = algorithm.run(traces, metrics)

    logger.info("TraStrainer Results:")
    logger.info(f"  Traces processed: {result.total_traces_processed}")
    logger.info(f"  Traces sampled: {result.actual_sample_count}")
    logger.info(f"  Target rate: {config.budget_sample_rate}")
    logger.info(f"  Achieved rate: {result.sampling_rate_achieved:.4f}")
    logger.info(f"  Execution time: {result.execution_time:.2f}s")

    return result


def example_platform_integration():
    """Example of using TraStrainer as an Algorithm for platform integration."""
    logger.info("=== Platform Integration Example ===")

    # Create TraStrainer algorithm instance
    trastrainer_algo = TraStrainer(sampling_rate=0.1)

    logger.info("TraStrainer algorithm created")
    logger.info(f"CPU requirements: {trastrainer_algo.needs_cpu_count()}")

    # In a real scenario, this would be called by the platform with AlgorithmArgs
    # For demonstration, we show the structure
    class MockArgs:
        def __init__(self, data_path: str):
            self.data_path = data_path

    # Example call (would need actual data)
    # args = MockArgs("./data/example_data")
    # answers = trastrainer_algo(args)

    logger.info("TraStrainer is ready for platform integration")


def example_cli_usage():
    """Example of CLI usage patterns."""
    logger.info("=== CLI Usage Examples ===")

    examples = [
        # Basic sampling
        "python -m trastrainer.cli sample ./data/example_data --rate 0.1",
        # Verbose output with custom format
        "python -m trastrainer.cli sample ./data/example_data --rate 0.05 --verbose --format json",
        # CSV output for processing
        "python -m trastrainer.cli sample ./data/example_data --rate 0.01 --format csv > sampled_traces.csv",
        # Validate data structure
        "python -m trastrainer.cli validate ./data/example_data",
        # Get algorithm information
        "python -m trastrainer.cli info",
    ]

    logger.info("CLI usage examples:")
    for i, example in enumerate(examples, 1):
        logger.info(f"  {i}. {example}")


def example_data_format():
    """Example showing the expected data format."""
    logger.info("=== Expected Data Format ===")

    logger.info("Required files in data directory:")
    required_files = [
        "env.json - Environment configuration with time ranges",
        "normal_traces.parquet - Traces from normal period",
        "abnormal_traces.parquet - Traces from anomalous period",
        "normal_metrics.parquet - Metrics from normal period",
        "abnormal_metrics.parquet - Metrics from anomalous period",
    ]

    for file_desc in required_files:
        logger.info(f"  - {file_desc}")

    logger.info("\nTrace columns (Parquet format):")
    trace_cols = [
        "time (datetime) - Start time of span in UTC",
        "trace_id (string) - Unique identifier of trace",
        "span_id (string) - Unique identifier of span",
        "parent_span_id (string) - Parent span identifier",
        "service_name (string) - Service that generated the span",
        "span_name (string) - Operation name",
        "duration (uint64) - Duration in nanoseconds",
        "attr.* - Additional span attributes",
    ]

    for col_desc in trace_cols:
        logger.info(f"    {col_desc}")

    logger.info("\nMetric columns (Parquet format):")
    metric_cols = [
        "time (datetime) - UTC timestamp of metric",
        "metric (string) - Name of the metric",
        "value (float64) - Metric value",
        "service_name (string) - Service that generated metric",
        "attr.* - Additional metric attributes",
    ]

    for col_desc in metric_cols:
        logger.info(f"    {col_desc}")


if __name__ == "__main__":
    # Run all examples
    example_data_format()
    example_cli_usage()
    example_platform_integration()

    # Try basic usage if data exists
    try:
        example_basic_usage()
    except Exception as e:
        logger.info(f"Basic usage example skipped: {e}")
        logger.info("Provide actual data files to run the full example")
