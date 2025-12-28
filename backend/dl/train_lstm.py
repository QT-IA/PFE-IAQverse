import sys
import os
import numpy as np
import pandas as pd
from pathlib import Path
import logging

# Add project root to path to allow imports
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from backend.dl.lstm_model import IAQLSTMModel
from backend.utils import load_dataset_df
from backend.core.settings import Settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("train_lstm")

def prepare_sequences(data, time_steps=12):
    """
    Converts DataFrame into (samples, time_steps, features) for LSTM.
    """
    # Features used: co2, pm25, tvoc, temperature, humidity
    feature_cols = ["co2", "pm25", "tvoc", "temperature", "humidity"]
    target_cols = ["co2", "pm25", "tvoc"] # We predict these 3
    
    # Drop NaNs
    df = data[feature_cols].dropna()
    values = df.values
    
    X, y = [], []
    for i in range(len(values) - time_steps):
        X.append(values[i : i + time_steps])
        # Target is the NEXT value after the sequence (or N steps ahead)
        # Here we predict the immediate next step for simplicity
        # To predict 30 mins ahead (6 steps of 5 mins), use i + time_steps + 6
        target_idx = i + time_steps 
        if target_idx < len(values):
            # Extract only target columns indices
            target_indices = [df.columns.get_loc(c) for c in target_cols]
            y.append(values[target_idx, target_indices])
            
    return np.array(X), np.array(y)

def main():
    logger.info("🚀 Starting LSTM Training Pipeline")
    
    # 1. Load Data
    logger.info("Loading dataset...")
    df = load_dataset_df()
    if df is None or df.empty:
        logger.error("❌ No data found in dataset!")
        return

    logger.info(f"Loaded {len(df)} records.")

    # 2. Prepare Data
    TIME_STEPS = 12 # 1 hour context (assuming 5 min intervals)
    X, y = prepare_sequences(df, time_steps=TIME_STEPS)
    
    if len(X) == 0:
        logger.error("❌ Not enough data to create sequences.")
        return

    logger.info(f"Training data shape: X={X.shape}, y={y.shape}")

    # 3. Initialize Model
    # Input shape: (12, 5) -> 12 steps, 5 features
    # Output shape: 3 -> co2, pm25, tvoc
    model = IAQLSTMModel(input_shape=(TIME_STEPS, 5), output_shape=3)

    # 4. Train
    logger.info("Training model (this may take a while)...")
    model.train(X, y, epochs=5, batch_size=32) # Low epochs for quick test

    # 5. Save
    output_path = Settings.ML_MODELS_DIR / "lstm_model.h5"
    # Ensure directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    model.save(str(output_path))
    logger.info(f"✅ Model saved to {output_path}")

    # 6. Test Prediction
    logger.info("Testing prediction...")
    sample_input = X[-1].reshape(1, TIME_STEPS, 5)
    prediction = model.predict(sample_input)
    
    logger.info(f"Input (Last Step): {sample_input[0, -1]}")
    logger.info(f"Prediction: CO2={prediction[0][0]:.2f}, PM2.5={prediction[0][1]:.2f}, TVOC={prediction[0][2]:.2f}")
    logger.info(f"Actual Target: {y[-1]}")

if __name__ == "__main__":
    main()
