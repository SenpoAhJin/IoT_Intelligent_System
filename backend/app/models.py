"""SQLAlchemy database models."""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db import Base


class Player(Base):
    __tablename__ = "players"
    
    id = Column(String, primary_key=True)  # player_id
    name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    runs = relationship("Run", back_populates="player")


class Device(Base):
    __tablename__ = "devices"
    
    id = Column(String, primary_key=True)  # device_id
    name = Column(String, nullable=True)
    last_heartbeat = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    runs = relationship("Run", back_populates="device")


class Run(Base):
    __tablename__ = "runs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_uid = Column(String, unique=True, nullable=False, index=True)
    device_id = Column(String, ForeignKey("devices.id"), nullable=False)
    player_id = Column(String, ForeignKey("players.id"), nullable=False)
    run_no = Column(Integer, nullable=False)
    
    # Timing
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    
    # Performance
    hits = Column(Integer, default=0)
    total_contact_ms = Column(Integer, default=0)
    longest_hit_ms = Column(Integer, default=0)
    hit_penalty_ms = Column(Integer, default=2000)
    score = Column(Integer, nullable=True)
    
    # Status
    status = Column(String, default="started")  # started, finished, cancelled
    
    # Relationships
    device = relationship("Device", back_populates="runs")
    player = relationship("Player", back_populates="runs")
    hit_records = relationship("Hit", back_populates="run", cascade="all, delete-orphan")
    

class Hit(Base):
    __tablename__ = "hits"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_uid = Column(String, ForeignKey("runs.run_uid"), nullable=False)
    hit_no = Column(Integer, nullable=False)
    start_ms = Column(Integer, nullable=False)  # ms from run start
    duration_ms = Column(Integer, nullable=False)
    
    run = relationship("Run", back_populates="hit_records")


class Suggestion(Base):
    __tablename__ = "suggestions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(String, ForeignKey("players.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    suggestion_type = Column(String, nullable=False)  # behavior, skill, trend, difficulty
    message = Column(Text, nullable=False)
    reason = Column(Text, nullable=True)
    data = Column(Text, nullable=True)  # JSON string of supporting data
    
    priority = Column(String, default="normal")  # low, normal, high


class GameCommand(Base):
    """
    PHASE 2B-2: Track dashboard-initiated game commands.
    Commands flow: Dashboard → Backend → MQTT → Serial Gateway → ESP32
    """
    __tablename__ = "game_commands"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String, unique=True, nullable=False, index=True)
    device_id = Column(String, ForeignKey("devices.id"), nullable=False)
    command = Column(String, nullable=False)  # "start", "finish"
    
    # Command lifecycle timestamps
    requested_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    
    # Status: "pending", "sent", "acknowledged", "timeout", "rejected"
    status = Column(String, default="pending")
    
    # Metadata
    player_id = Column(String, nullable=True)
    run_uid = Column(String, nullable=True)  # Set after run_start event received
    error_reason = Column(String, nullable=True)
