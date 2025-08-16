#!/usr/bin/env python3
"""Test script for windowed sampling implementation."""

import logging
from pathlib import Path

from src.trastrainer.algorithm import TraStrainerAlgorithm
from src.trastrainer.data_structures import SamplingConfig
from src.trastrainer.polar_loader import PolarDataPreprocessor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_windowed_sampling():
    """Test the new windowed sampling implementation"""

    # Test parameters
    data_path = Path("test/ts1-ts-route-plan-service-request-replace-method-qtbhzt")
    budget_sample_rate = 0.05
    traces_per_window = 200  # Process 200 traces per window

    logger.info(f"Testing windowed sampling with {traces_per_window} traces per window")

    # Load data
    preprocessor = PolarDataPreprocessor()
    traces, metrics = preprocessor.load_data(data_path)

    logger.info(f"Loaded {len(traces)} traces and {len(metrics)} metrics")

    # Test windowed sampling
    config = SamplingConfig(
        budget_sample_rate=budget_sample_rate,
        traces_per_window=traces_per_window,
        warm_up_size=10,
    )

    algorithm = TraStrainerAlgorithm(config)
    result = algorithm.run(traces, metrics)

    logger.info("Windowed sampling results:")
    logger.info(f"  Total processed: {result.total_traces_processed}")
    logger.info(f"  Total sampled: {len(result.sampled_trace_ids)}")
    logger.info(f"  Sampling rate achieved: {result.sampling_rate_achieved:.3f}")
    logger.info(f"  Execution time: {result.execution_time:.2f}s")

    # Analyze trace distribution
    trace_list = list(traces.items())
    total_traces = len(trace_list)

    # Determine normal vs abnormal distribution in sampled traces
    normal_count = 0
    abnormal_count = 0

    for trace_id in result.sampled_trace_ids:
        # Find position in chronologically sorted list
        for i, (tid, trace) in enumerate(trace_list):
            if tid == trace_id:
                # Roughly estimate if it's normal (first half) or abnormal (second half)
                if i < total_traces * 0.8:  # Assuming 80% normal, 20% abnormal
                    normal_count += 1
                else:
                    abnormal_count += 1
                break

    logger.info("Sampled trace distribution (estimated):")
    logger.info(f"  Normal period traces: {normal_count}")
    logger.info(f"  Abnormal period traces: {abnormal_count}")

    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("SUMMARY:")
    logger.info(
        f"Windowed: {normal_count} normal + {abnormal_count} abnormal = {normal_count + abnormal_count} total"
    )

    if normal_count > 0 and abnormal_count > 0:
        logger.info("✅ Windowed sampling found traces from both periods!")
        ratio = normal_count / abnormal_count if abnormal_count > 0 else float("inf")
        logger.info(f"   Normal/Abnormal ratio: {ratio:.2f}")
    else:
        logger.info("❌ Windowed sampling still has bias toward one period")

    # Test saving functionality
    logger.info("\n" + "=" * 50)
    logger.info("Testing save functionality...")

    output_dir = preprocessor.save_sampled_results(result.sampled_trace_ids)
    logger.info(f"✅ Saved results to: {output_dir}")

    return result


if __name__ == "__main__":
    test_windowed_sampling()
