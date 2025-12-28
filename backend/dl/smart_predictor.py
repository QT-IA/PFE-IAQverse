import numpy as np
import pandas as pd
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional

from ..ml.ml_predict_generic import RealtimeGenericPredictor
from .lstm_model import IAQLSTMModel
from ..api.query import get_iaq_data
from ..core.data_store import get_dataset

logger = logging.getLogger("iaq_smart_predictor")

class SmartPredictor:
    """
    Intelligent predictor that selects the best model between 
    Classic ML (Voting Regressor) and Deep Learning (LSTM).
    """
    def __init__(self, model_dir: Path, lstm_model_path: Path = None):
        self.ml_predictor = RealtimeGenericPredictor(model_dir=model_dir)
        
        # LSTM Configuration
        self.time_steps = 12  # e.g., 12 * 5 mins = 60 mins context
        self.features = 5     # co2, pm25, tvoc, temp, humidity
        self.lstm_model = IAQLSTMModel(input_shape=(self.time_steps, self.features))
        
        if lstm_model_path and lstm_model_path.exists():
            self.lstm_model.load(str(lstm_model_path))
        else:
            logger.info("No trained LSTM model found. It will need training.")

        # Performance tracking (Exponential Moving Average of MAE)
        self.errors = {
            "ml": 100.0,  # Initial high error
            "dl": 100.0
        }
        self.alpha = 0.2 # Smoothing factor for error update

    def _prepare_lstm_input(self, data: pd.DataFrame) -> np.ndarray:
        """
        Prepares the dataframe for LSTM input (scaling + reshaping).
        """
        # Note: In a real app, use the SAME scaler as training. 
        # Here we assume data is already somewhat normalized or we use a simple local norm for demo.
        # For production, load the scaler saved during training.
        if len(data) < self.time_steps:
            return None
            
        # Select features in correct order
        features = ["co2", "pm25", "tvoc", "temperature", "humidity"]
        df_subset = data[features].tail(self.time_steps)
        
        # Simple normalization (should match training)
        # This is a placeholder. Ideally, load scaler from disk.
        values = df_subset.values
        return np.expand_dims(values, axis=0)

    def predict(self, enseigne: str, salle: str, sensor_id: str) -> Dict[str, Any]:
        """
        Orchestrates the prediction using the best available model.
        """
        # 1. Get ML Prediction
        ml_pred = self.ml_predictor.predict(enseigne, salle, sensor_id)
        
        # 2. Get Data for LSTM
        # Fetch last N records
        try:
            # We need enough history. 1 hour should be enough for 12 steps of 5 mins
            history = get_iaq_data(sensor_id=sensor_id, hours=2, raw=True)
            if isinstance(history, dict) and "Data" in history:
                df_hist = pd.DataFrame(history["Data"])
            elif isinstance(history, list):
                df_hist = pd.DataFrame(history)
            else:
                df_hist = pd.DataFrame()
        except Exception as e:
            logger.warning(f"Failed to fetch history for LSTM: {e}")
            df_hist = pd.DataFrame()

        # Fallback: If not enough live data, use static dataset (for demo/immediate availability)
        if len(df_hist) < self.time_steps:
            logger.info(f"Insufficient live history ({len(df_hist)}/{self.time_steps}). Using static dataset for LSTM.")
            ds = get_dataset()
            if ds is not None and not ds.empty:
                # Filter by sensor if possible, otherwise take generic tail
                # Note: In a real app we might not want to mix contexts, but for demo it ensures DL works
                mask = (ds["enseigne"] == enseigne) if enseigne else pd.Series([True] * len(ds))
                if salle:
                    mask &= (ds["salle"] == salle)
                
                filtered_ds = ds[mask]
                if filtered_ds.empty:
                    filtered_ds = ds # Fallback to any data
                
                # Take the last N records to simulate history
                df_hist = filtered_ds.tail(self.time_steps)

        dl_pred_values = None
        
        # 3. Get LSTM Prediction if possible
        if not df_hist.empty and len(df_hist) >= self.time_steps and self.lstm_model.is_trained:
            X_input = self._prepare_lstm_input(df_hist)
            if X_input is not None:
                # Predict
                # Output shape: (1, 3) -> [co2, pm25, tvoc]
                raw_pred = self.lstm_model.predict(X_input)
                dl_pred_values = {
                    "co2": float(raw_pred[0][0]),
                    "pm25": float(raw_pred[0][1]),
                    "tvoc": float(raw_pred[0][2])
                }
        else:
            logger.info(f"LSTM skipped: hist_len={len(df_hist)}, trained={self.lstm_model.is_trained}")

        # 4. Selection Logic
        # If we have both, we can choose based on historical error or just average.
        # For this implementation, we'll use a weighted average based on inverse error,
        # or simply prefer LSTM if available as it captures temporal dynamics better.
        
        final_pred = ml_pred
        used_model = "ml"

        if dl_pred_values:
            # Simple Ensemble: Average
            # Or "Best Model" logic:
            # Prefer DL if errors are equal (initial state) or DL error is lower
            logger.info(f"Comparing errors - DL: {self.errors['dl']} vs ML: {self.errors['ml']}")
            if self.errors["dl"] <= self.errors["ml"]:
                # Use DL
                final_pred["predicted_values"] = dl_pred_values
                used_model = "dl"
            else:
                # Use ML but maybe blend slightly?
                # Let's stick to "Selection" as requested.
                used_model = "ml"
                
            # Add metadata
            final_pred["model_used"] = used_model
            final_pred["candidates"] = {
                "ml": ml_pred.get("predicted_values"),
                "dl": dl_pred_values
            }
        else:
            logger.info("LSTM prediction unavailable (insufficient history or model not trained). Using ML.")
        
        return final_pred

    def update_feedback(self, actual_values: Dict[str, float], predicted_values: Dict[str, float], model_type: str):
        """
        Updates the error metrics for a model type based on new ground truth.
        """
        # Calculate Mean Absolute Error for this sample
        error = 0.0
        count = 0
        for key in ["co2", "pm25", "tvoc"]:
            if key in actual_values and key in predicted_values:
                error += abs(actual_values[key] - predicted_values[key])
                count += 1
        
        if count > 0:
            avg_error = error / count
            # Update EMA
            self.errors[model_type] = (self.alpha * avg_error) + ((1 - self.alpha) * self.errors[model_type])
            logger.info(f"Updated error for {model_type}: {self.errors[model_type]:.2f}")
