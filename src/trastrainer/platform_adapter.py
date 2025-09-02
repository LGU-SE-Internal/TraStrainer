"""TraStrainer algorithm adapter for the RCABench platform."""

from functools import partial
from pathlib import Path
from typing import List

from rcabench_platform.v2.algorithms.spec import (
    Algorithm,
    AlgorithmAnswer,
    AlgorithmArgs,
)
from rcabench_platform.v2.logging import logger

from .algorithm import TraStrainerAlgorithm
from .data_structures import SamplingConfig
from .polar_loader import PolarDataPreprocessor


class TraStrainerAdapter:
    """Adapter for TraStrainer to work with the new data format"""

    def __init__(self, sampling_rate: float = 0.1):
        """
        Initialize TraStrainer adapter

        Args:
            sampling_rate: Target sampling rate for trace sampling
        """
        self.sampling_rate = sampling_rate

    def __call__(self, input_folder: Path, inject_time: int | None = None) -> dict:
        """
        Run TraStrainer sampling on the given data

        Args:
            input_folder: Path to folder containing Parquet data files
            inject_time: Injection time (not used in current implementation)

        Returns:
            Dictionary with sampling results
        """
        try:
            logger.info(f"Running TraStrainer with sampling rate: {self.sampling_rate}")

            # Load data using Polars preprocessor
            preprocessor = PolarDataPreprocessor()
            traces, metrics = preprocessor.load_data(input_folder)

            if not traces:
                logger.warning("No traces found in data")
                return {
                    "sampled_trace_ids": [],
                    "total_traces": 0,
                    "sampling_rate_achieved": 0.0,
                    "execution_time": 0.0,
                }

            # Configure and run TraStrainer algorithm
            config = SamplingConfig(
                budget_sample_rate=self.sampling_rate,
                warm_up_size=min(10, len(traces) // 10),
                checkpoints_dir="./checkpoints",
            )

            algorithm = TraStrainerAlgorithm(config)
            result = algorithm.run(traces, metrics)

            # Save sampled results
            output_dir = preprocessor.save_sampled_results(result.sampled_trace_ids)

            logger.info(
                f"TraStrainer completed: sampled {result.actual_sample_count} out of {result.total_traces_processed} traces"
            )
            logger.info(f"Results saved to: {output_dir}")

            return {
                "sampled_trace_ids": result.sampled_trace_ids,
                "total_traces": result.total_traces_processed,
                "sampling_rate_achieved": result.sampling_rate_achieved,
                "execution_time": result.execution_time,
                "output_directory": str(output_dir),
                "traces": traces,  # Include trace data for further analysis if needed
                "metrics": metrics,  # Include metric data for further analysis if needed
            }

        except Exception as e:
            logger.error(f"TraStrainer failed: {e}")
            return {
                "sampled_trace_ids": [],
                "total_traces": 0,
                "sampling_rate_achieved": 0.0,
                "execution_time": 0.0,
                "error": str(e),
            }


def trastrainer_sampling(
    input_folder: Path, inject_time: int | None = None, sampling_rate: float = 0.1
) -> dict:
    """
    Standalone function for TraStrainer sampling

    Args:
        input_folder: Path to folder containing data
        inject_time: Injection time (optional)
        sampling_rate: Target sampling rate

    Returns:
        Dictionary with sampling results
    """
    adapter = TraStrainerAdapter(sampling_rate=sampling_rate)
    return adapter(input_folder, inject_time)


class TraStrainer(Algorithm):
    """TraStrainer algorithm implementation for RCABench platform"""

    def __init__(self, sampling_rate: float = 0.1):
        """
        Initialize TraStrainer algorithm

        Args:
            sampling_rate: Target sampling rate for trace sampling
        """
        self.sampling_rate = sampling_rate

    def needs_cpu_count(self) -> int | None:
        """Return required CPU count (None means no specific requirement)"""
        return 2  # TraStrainer can benefit from 2 CPUs for parallel processing

    def __call__(self, args: AlgorithmArgs) -> List[AlgorithmAnswer]:
        """
        Run TraStrainer algorithm

        Args:
            args: Algorithm arguments containing data path and configuration

        Returns:
            List of algorithm answers
        """
        try:
            # Extract input folder from args (use getattr for safety)
            input_folder = args.input_folder

            # Run TraStrainer
            adapter = TraStrainerAdapter(sampling_rate=self.sampling_rate)
            result = adapter(input_folder)

            # Log results but return empty list for now
            if "error" in result:
                logger.error(f"TraStrainer failed: {result['error']}")
                return []

            logger.info("TraStrainer completed successfully")
            logger.info(f"Total traces: {result.get('total_traces', 0)}")
            logger.info(f"Sampled traces: {len(result.get('sampled_trace_ids', []))}")
            logger.info(
                f"Achieved sampling rate: {result.get('sampling_rate_achieved', 0):.4f}"
            )

            # Return empty list for now
            return []

        except Exception as e:
            logger.error(f"TraStrainer algorithm failed: {e}")
            return []


# Create default instance with common sampling rates
TraStrainer01 = partial(TraStrainer, sampling_rate=0.1)
TraStrainer005 = partial(TraStrainer, sampling_rate=0.05)
TraStrainer001 = partial(TraStrainer, sampling_rate=0.01)
