"""Metric prediction module for TraStrainer."""

import os
from typing import Dict, List, Tuple

import pandas as pd
from rcabench_platform.v2.logging import logger

from .preprocessor import TimeUtils

# Import prediction functionality - assume it's available
try:
    from .models.linear_predictor import Argument, metric_infer
except ImportError:
    logger.warning("Linear predictor models not available")
    Argument = None
    metric_infer = None


class MetricPredictor:
    """Predict and evaluate metrics using ML models."""

    def __init__(self, checkpoints_dir: str = "./checkpoints"):
        """
        Initialize metric predictor.

        Args:
            checkpoints_dir: Directory containing model checkpoints
        """
        self.checkpoints_dir = checkpoints_dir

    def compute_metrics_weights(
        self, metrics: Dict[Tuple[str, str], List[Dict]], start_time: str, end_time: str
    ) -> Dict[Tuple[str, str], float]:
        """
        Compute weights for metrics based on prediction accuracy.

        Args:
            metrics: Dictionary of metric data
            start_time: Start time for prediction window
            end_time: End time for prediction window

        Returns:
            Dictionary mapping metric keys to weights
        """
        metrics_weights = {}

        for key, value in metrics.items():
            try:
                weight = self._compute_single_metric_weight(
                    key, value, start_time, end_time
                )
                metrics_weights[key] = weight
            except Exception as e:
                logger.warning(f"Failed to compute weight for metric {key}: {e}")
                metrics_weights[key] = 1.0  # Default weight

        return metrics_weights

    def _compute_single_metric_weight(
        self, key: Tuple[str, str], value: List[Dict], start_time: str, end_time: str
    ) -> float:
        """Compute weight for a single metric."""
        if not value:
            return 1.0

        # Prepare input data
        input_df = pd.DataFrame(value)
        if input_df.empty or "date" not in input_df.columns:
            return 1.0

        # Find prediction window
        try:
            predict_idx = (input_df["date"] >= start_time).idxmax()
            predict_end = TimeUtils.future_datetime(end_time, 1)
            predict_len = len(
                input_df[
                    (input_df["date"] >= start_time) & (input_df["date"] < predict_end)
                ]
            )
            predict_len = max(predict_len, 1)
        except Exception:
            return 1.0

        # Create model ID from key
        model_id = "_".join(key)
        model_path = os.path.join(self.checkpoints_dir, f"{model_id}.pth")

        # Use default weight if model not found or prediction unavailable
        if not os.path.exists(model_path) or Argument is None or metric_infer is None:
            return 1.0

        try:
            # Ensure we have enough data
            start_idx = max(0, predict_idx - 96)
            end_idx = predict_idx + predict_len

            if end_idx > len(input_df) or start_idx >= end_idx:
                return 1.0

            data_slice = input_df.iloc[start_idx:end_idx]
            if len(data_slice) < 10:  # Minimum data requirement
                return 1.0

            # Run inference and calculate weight based on prediction error
            args = Argument(data_slice, model_id=model_id)
            preds, trues = metric_infer(args, model=None)

            if preds is None or trues is None:
                return 1.0

            # Calculate prediction error as weight
            error = abs(float(((trues - preds) / (preds + 1e-8)).mean()))
            return min(error, 10.0)  # Cap weight at 10

        except Exception as e:
            logger.debug(f"Prediction failed for {key}: {e}")
            return 1.0
