import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.optimizers import Adam
import logging
import os

logger = logging.getLogger("iaq_dl")

class IAQLSTMModel:
    def __init__(self, input_shape, output_shape=3):
        """
        Initializes the LSTM model.
        :param input_shape: Tuple (time_steps, features)
        :param output_shape: Number of output features (e.g., CO2, PM2.5, TVOC)
        """
        self.input_shape = input_shape
        self.output_shape = output_shape
        self.model = self._build_model()
        self.is_trained = False

    def _build_model(self):
        """
        Builds a concise LSTM architecture.
        """
        model = Sequential([
            LSTM(64, activation='relu', return_sequences=True, input_shape=self.input_shape),
            Dropout(0.2),
            LSTM(32, activation='relu'),
            Dropout(0.2),
            Dense(16, activation='relu'),
            Dense(self.output_shape)
        ])
        
        model.compile(optimizer=Adam(learning_rate=0.001), loss='mse', metrics=['mae'])
        return model

    def train(self, X_train, y_train, epochs=10, batch_size=32, validation_split=0.2):
        """
        Trains the model.
        """
        logger.info("Training LSTM model...")
        history = self.model.fit(
            X_train, y_train,
            epochs=epochs,
            batch_size=batch_size,
            validation_split=validation_split,
            verbose=0
        )
        self.is_trained = True
        logger.info("LSTM training completed.")
        return history

    def predict(self, X_input):
        """
        Predicts future values.
        :param X_input: Numpy array of shape (1, time_steps, features)
        """
        if not self.is_trained:
            logger.warning("LSTM model is not trained. Returning zeros.")
            return np.zeros((X_input.shape[0], self.output_shape))
            
        return self.model.predict(X_input, verbose=0)

    def save(self, filepath):
        self.model.save(filepath)
        logger.info(f"LSTM model saved to {filepath}")

    def load(self, filepath):
        if os.path.exists(filepath):
            self.model = tf.keras.models.load_model(filepath)
            self.is_trained = True
            logger.info(f"LSTM model loaded from {filepath}")
        else:
            logger.warning(f"Model file not found: {filepath}")
