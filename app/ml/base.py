from abc import ABC, abstractmethod
import pandas as pd
from typing import Any

class BaseModel(ABC):
    @abstractmethod
    def predict(self, features: pd.DataFrame) -> Any:
        """Make a prediction given features."""
        pass
    
    @abstractmethod
    def load(self, path: str) -> None:
        """Load model from path."""
        pass
