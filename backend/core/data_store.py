import pandas as pd
from typing import Optional
from ..utils import load_dataset_df
import logging

logger = logging.getLogger("iaq_data_store")

class DataStore:
    _instance = None
    _df: Optional[pd.DataFrame] = None

    @classmethod
    def get_data(cls) -> Optional[pd.DataFrame]:
        if cls._df is None:
            logger.info("Loading dataset into DataStore...")
            cls._df = load_dataset_df()
            if cls._df is not None:
                logger.info(f"Dataset loaded: {len(cls._df)} rows")
            else:
                logger.warning("Failed to load dataset")
        return cls._df

# Global accessor
def get_dataset():
    return DataStore.get_data()
