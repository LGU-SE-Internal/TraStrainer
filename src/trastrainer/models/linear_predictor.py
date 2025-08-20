"""Linear predictor implementation for metric forecasting."""

import os
import random
import warnings
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import torch
from rcabench_platform.v2.logging import logger

warnings.filterwarnings("ignore")

# Set random seed for reproducibility
FIX_SEED = 2021
random.seed(FIX_SEED)
torch.manual_seed(FIX_SEED)
np.random.seed(FIX_SEED)


class Argument:
    """Configuration arguments for the linear predictor."""

    def __init__(self, input_data: pd.DataFrame, model_id: str = "weather"):
        # Basic config
        self.model_id = model_id
        self.model = "DLinear"
        self.input = input_data

        # Data loader
        self.data = "custom"
        self.features = "M"  # multivariate predict multivariate
        self.target = "OT"
        self.freq = "h"  # hourly
        self.checkpoints = "./checkpoints/"

        # Forecasting task
        self.seq_len = 96  # input sequence length
        self.label_len = 0  # start token length
        self.pred_len = 1  # prediction sequence length

        # DLinear
        self.individual = False

        # Model parameters
        self.embed_type = 0
        self.enc_in = 7
        self.dec_in = 7
        self.c_out = 7
        self.d_model = 512
        self.n_heads = 8
        self.e_layers = 2
        self.d_layers = 1
        self.d_ff = 2048
        self.moving_avg = 25
        self.factor = 1
        self.distil = True
        self.dropout = 0.05
        self.embed = "timeF"
        self.activation = "gelu"
        self.output_attention = True
        self.do_predict = True

        # Optimization
        self.num_workers = 0
        self.itr = 1
        self.train_epochs = 100
        self.batch_size = 4
        self.patience = 3
        self.learning_rate = 0.0001
        self.des = "Exp"
        self.loss = "mse"
        self.lradj = "type1"
        self.use_amp = False


class MockDLinearModel:
    """Mock implementation of DLinear model for prediction."""

    def __init__(self, args: Argument):
        self.args = args
        self.device = torch.device("cpu")

    def predict(self, data: np.ndarray) -> np.ndarray:
        """Mock prediction - returns simple trend continuation."""
        if len(data) < 2:
            return np.array([data[-1] if len(data) > 0 else 0.0])

        # Simple linear extrapolation
        trend = data[-1] - data[-2]
        prediction = data[-1] + trend
        return np.array([prediction])

    def save(self, path: str) -> None:
        """Mock save method."""
        pass

    @classmethod
    def load(cls, path: str, args: Argument) -> "MockDLinearModel":
        """Mock load method."""
        return cls(args)


class ExpMain:
    """Main experiment class for training and inference."""

    def __init__(self, args: Argument):
        self.args = args
        self.device = torch.device("cpu")
        self.model = self._build_model()

    def _build_model(self) -> MockDLinearModel:
        """Build the prediction model."""
        return MockDLinearModel(self.args)

    def train(self) -> MockDLinearModel:
        """Train the model (mock implementation)."""
        logger.info(f"Training model for {self.args.model_id}")

        # In a real implementation, this would train the model
        # For now, we just return the model

        # Save model checkpoint
        checkpoint_path = os.path.join(
            self.args.checkpoints, f"{self.args.model_id}.pth"
        )
        if not os.path.exists(self.args.checkpoints):
            os.makedirs(self.args.checkpoints)

        self.model.save(checkpoint_path)
        logger.info(f"Model saved to {checkpoint_path}")

        return self.model

    def test(
        self, model: Optional[MockDLinearModel] = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Test the model and return predictions and ground truth."""
        if model is None:
            model = self.model

        try:
            # Extract values from input data
            if "value" in self.args.input.columns:
                values = self.args.input["value"].values
            else:
                # Use the second column if 'value' not found
                values = self.args.input.iloc[:, 1].values

            # Ensure we have enough data
            if len(values) < self.args.seq_len + self.args.pred_len:
                logger.warning(f"Insufficient data for prediction: {len(values)}")
                return np.array([0.0]), np.array([0.0])

            # Split data for prediction
            input_data = values[: -self.args.pred_len]
            true_values = values[-self.args.pred_len :]

            # Make prediction
            predictions = model.predict(input_data)

            return predictions, true_values

        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return np.array([0.0]), np.array([0.0])


def metric_learner(args: Argument) -> MockDLinearModel:
    """
    Train a metric prediction model.

    Args:
        args: Training configuration

    Returns:
        Trained model
    """
    exp = ExpMain(args)
    model = exp.train()
    return model


def metric_infer(
    args: Argument, model: Optional[MockDLinearModel] = None
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """
    Perform metric inference.

    Args:
        args: Inference configuration
        model: Optional pre-trained model

    Returns:
        Tuple of (predictions, ground_truth)
    """
    try:
        exp = ExpMain(args)
        preds, trues = exp.test(model=model)
        return preds, trues
    except Exception as e:
        logger.error(f"Metric inference failed: {e}")
        return None, None
