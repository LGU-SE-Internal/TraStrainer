"""Example usage of TraStrainer package."""

from rcabench_platform.v2.logging import logger

from trastrainer import DataPreprocessor, SamplingConfig, TraStrainerAlgorithm


def run_trastrainer_example(data_path: str, sampling_rate: float = 0.1):
    """
    Example function demonstrating TraStrainer usage.

    Args:
        data_path: Path to directory containing trace and metric data
        sampling_rate: Target sampling rate (e.g., 0.1 for 10%)
    """
    logger.info("=== TraStrainer Example ===")

    # Step 1: Data Preprocessing
    logger.info("Step 1: Loading and preprocessing data...")
    preprocessor = DataPreprocessor()
    traces, metrics = preprocessor.load_data(data_path)

    logger.info(f"Loaded {len(traces)} traces and {len(metrics)} metric series")

    # Step 2: Algorithm Configuration
    logger.info("Step 2: Configuring TraStrainer algorithm...")
    config = SamplingConfig(
        budget_sample_rate=sampling_rate,
        warm_up_size=10,
        checkpoints_dir="./checkpoints",
    )

    # Step 3: Run TraStrainer Algorithm
    logger.info("Step 3: Running adaptive sampling...")
    algorithm = TraStrainerAlgorithm(config)
    result = algorithm.run(traces, metrics)

    # Step 4: Display Results
    logger.info("Step 4: Results summary")
    logger.info(f"  Target sampling rate: {sampling_rate}")
    logger.info(f"  Actual sampling rate: {result.sampling_rate_achieved:.4f}")
    logger.info(f"  Traces processed: {result.total_traces_processed}")
    logger.info(f"  Traces sampled: {result.actual_sample_count}")
    logger.info(f"  Execution time: {result.execution_time:.2f}s")
    logger.info(f"  Sampled trace IDs: {len(result.sampled_trace_ids)} traces")

    return result


def demonstrate_data_structures():
    """Demonstrate the data structures used in TraStrainer."""
    from trastrainer.data_structures import SamplingConfig, TraceData, TraceSpan

    logger.info("=== Data Structures Demo ===")

    # Create a sample trace span
    span = TraceSpan(
        trace_id="trace-123",
        span_id="span-456",
        parent_id="root",
        service_name="user-service",
        operation_name="get_user",
        start_time="2024-01-01 10:00:00",
        end_time="2024-01-01 10:00:01",
        duration=1000000,  # nanoseconds
        status="success",
    )

    logger.info(f"Created span: {span.service_name}.{span.operation_name}")
    logger.info(f"  Is root span: {span.is_root}")

    # Create a trace with multiple spans
    trace = TraceData(trace_id="trace-123", spans=[span])

    logger.info(f"Created trace: {trace.trace_id}")
    logger.info(f"  Start time: {trace.start_time}")
    logger.info(
        f"  Root span: {trace.root_span.operation_name if trace.root_span else 'None'}"
    )

    # Create sampling configuration
    config = SamplingConfig(budget_sample_rate=0.1, warm_up_size=5)

    logger.info(
        f"Created config: rate={config.budget_sample_rate}, window={config.window_size}"
    )


if __name__ == "__main__":
    # Run demonstrations
    demonstrate_data_structures()

    # To run with actual data:
    # result = run_trastrainer_example("./data/test/", 0.1)
