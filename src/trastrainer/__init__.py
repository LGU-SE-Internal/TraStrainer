"""
TraStrainer: An adaptive sampler for distributed traces with system runtime state.

This package provides tools for:
- Processing metrics and trace data
- Adaptive trace sampling using system bias and diversity bias
- Machine learning-based metric prediction
"""

from .algorithm import TraStrainerAlgorithm
from .data_structures import MetricData, SamplingConfig, TraceData

# Legacy compatibility
from .legacy import process_metrics, read_traces, tra_strainer
from .platform_adapter import TraStrainer, TraStrainerAdapter, trastrainer_sampling

# New Polars-based components
from .polar_loader import PolarDataPreprocessor
from .preprocessor import DataPreprocessor

__version__ = "1.0.0"
__author__ = "TraStrainer Team"

__all__ = [
    # Core components
    "TraceData",
    "MetricData",
    "SamplingConfig",
    "DataPreprocessor",
    "TraStrainerAlgorithm",
    # New Polars components
    "PolarDataPreprocessor",
    "TraStrainer",
    "TraStrainerAdapter",
    "trastrainer_sampling",
    # Legacy API
    "tra_strainer",
    "process_metrics",
    "read_traces",
]
