from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class PickResponse(BaseModel):
    id: int
    player_id: int
    match_id: int
    player_name: str
    match_info: str
    prop_type: str
    line: float
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
