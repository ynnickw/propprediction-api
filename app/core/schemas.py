from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class PickResponse(BaseModel):
    id: int
    player_id: Optional[int] = None
    match_id: int
    player_name: Optional[str] = None
    match_info: str
    prediction_type: str = 'player_prop'
    prop_type: str
    line: Optional[float] = None
    recommendation: str
    model_expected: float
    bookmaker_prob: float
    model_prob: float
    edge_percent: float
    confidence: str
    created_at: datetime

    class Config:
        from_attributes = True

class LeagueResponse(BaseModel):
    id: int
    name: str

class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
