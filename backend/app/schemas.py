"""Pydantic schemas for API requests and responses."""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


class PlayerBase(BaseModel):
    id: str
    name: Optional[str] = None


class PlayerStats(PlayerBase):
    total_runs: int
    best_score: Optional[int]
    avg_score: Optional[float]
    total_hits: int
    skill_level: Optional[str]
    created_at: datetime
    last_seen: datetime


class HitSchema(BaseModel):
    hit_no: int
    start_ms: int
    duration_ms: int
    
    class Config:
        from_attributes = True


class RunSchema(BaseModel):
    id: int
    run_uid: str
    device_id: str
    player_id: str
    run_no: int
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    duration_ms: Optional[int]
    hits: int
    total_contact_ms: int
    longest_hit_ms: int
    hit_penalty_ms: int
    score: Optional[int]
    status: str
    
    class Config:
        from_attributes = True


class RunDetail(RunSchema):
    hit_records: List[HitSchema] = []


class DeviceSchema(BaseModel):
    id: str
    name: Optional[str]
    last_heartbeat: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class SuggestionSchema(BaseModel):
    id: int
    player_id: str
    created_at: datetime
    suggestion_type: str
    message: str
    reason: Optional[str]
    priority: str
    
    class Config:
        from_attributes = True


class LeaderboardEntry(BaseModel):
    rank: int
    player_id: str
    player_name: Optional[str]
    score: int
    hits: int
    duration_ms: int
    finished_at: datetime


class DifficultyConfig(BaseModel):
    hit_penalty_ms: int = Field(ge=0, le=10000)
    free_hits: int = Field(ge=0, le=10)
    time_limit_ms: Optional[int] = Field(None, ge=1000, le=300000)
    fast_time_ms: Optional[int] = Field(None, ge=1000, le=60000)


class InsightResponse(BaseModel):
    player_id: str
    skill_level: Optional[str]
    behavior_tags: List[str]
    trend: Optional[str]
    anomalies: List[str]
    suggestions: List[SuggestionSchema]
    recommended_difficulty: Optional[DifficultyConfig]
