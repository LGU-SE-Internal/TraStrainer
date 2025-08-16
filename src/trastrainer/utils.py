"""Utility functions for TraStrainer."""

from typing import Any, Dict


def print_formatted_number(num: float, decimal_places: int = 2) -> str:
    """Format a number to specified decimal places."""
    return f"{round(num, decimal_places):.{decimal_places}f}"


def output_dict_as_strings(d: Dict[Any, Any]) -> Dict[str, str]:
    """Convert a dictionary to string key-value pairs."""
    return {str(k): str(v) for k, v in d.items()}


def output_metrics_counts(metrics: Dict[Any, Any]) -> Dict[str, int]:
    """Convert metrics dictionary to string keys with value counts."""
    return {str(k): len(v) if hasattr(v, "__len__") else 1 for k, v in metrics.items()}
