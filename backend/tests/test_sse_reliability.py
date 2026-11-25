"""
PHASE 2B-1: SSE Reliability and Dashboard Synchronization Tests

Tests for Server-Sent Events connection reliability, event delivery,
active run synchronization, and browser refresh recovery.
"""

import pytest
import asyncio
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

from app.main import broadcast_event_async, sse_clients
from app.db import Base
from app.models import Run, Hit, Device, Player


@pytest.fixture
def test_db():
    """Create a fresh in-memory database for each test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    yield db
    db.close()


def test_active_run_query_no_active_run(test_db):
    """Test active run query logic when no game is active."""
    # Create a finished run
    player = Player(id="test_player", name="Test Player")
    test_db.add(player)
    
    run = Run(
        run_uid="test-run-finished",
        device_id="device-1",
        player_id="test_player",
        run_no=1,
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
        status="finished",
        duration_ms=10000,
        hits=2,
        score=14000
    )
    test_db.add(run)
    test_db.commit()
    
    # Query for active run (same logic as endpoint)
    active_run = test_db.query(Run).filter(
        Run.status == "started",
        Run.finished_at.is_(None)
    ).order_by(Run.started_at.desc()).first()
    
    # Should be None - no active runs
    assert active_run is None


def test_active_run_query_with_active_run(test_db):
    """Test active run query logic when a game is active."""
    # Create player and device
    player = Player(id="test_player", name="Test Player")
    device = Device(id="device-1")
    test_db.add(player)
    test_db.add(device)
    
    # Create active run
    run = Run(
        run_uid="test-run-active",
        device_id="device-1",
        player_id="test_player",
        run_no=1,
        started_at=datetime.utcnow(),
        finished_at=None,  # Not finished
        status="started",  # Active
        hits=0,
        score=0
    )
    test_db.add(run)
    test_db.commit()
    
    # Add some hits
    hit1 = Hit(run_uid="test-run-active", hit_no=1, start_ms=1000, duration_ms=100)
    hit2 = Hit(run_uid="test-run-active", hit_no=2, start_ms=2000, duration_ms=50)
    test_db.add_all([hit1, hit2])
    test_db.commit()
    
    # Query for active run (same logic as endpoint)
    active_run = test_db.query(Run).filter(
        Run.status == "started",
        Run.finished_at.is_(None)
    ).order_by(Run.started_at.desc()).first()
    
    # Should find the active run
    assert active_run is not None
    assert active_run.run_uid == "test-run-active"
    assert active_run.player_id == "test_player"
    
    # Count completed hits
    hit_count = test_db.query(Hit).filter(
        Hit.run_uid == active_run.run_uid,
        Hit.duration_ms > 0
    ).count()
    
    assert hit_count == 2  # Both hits completed


def test_active_run_ignores_abandoned_runs(test_db):
    """Test that abandoned runs are not returned as active."""
    player = Player(id="test_player", name="Test Player")
    test_db.add(player)
    
    # Create abandoned run
    run = Run(
        run_uid="test-run-abandoned",
        device_id="device-1",
        player_id="test_player",
        run_no=1,
        started_at=datetime.utcnow(),
        finished_at=None,
        status="abandoned",  # Stale/abandoned
        hits=0,
        score=0
    )
    test_db.add(run)
    test_db.commit()
    
    # Query for active run
    active_run = test_db.query(Run).filter(
        Run.status == "started",
        Run.finished_at.is_(None)
    ).order_by(Run.started_at.desc()).first()
    
    # Should be None - abandoned runs excluded
    assert active_run is None


def test_active_run_only_counts_completed_hits(test_db):
    """Test that only hits with duration_ms > 0 are counted."""
    player = Player(id="test_player", name="Test Player")
    device = Device(id="device-1")
    test_db.add(player)
    test_db.add(device)
    
    run = Run(
        run_uid="test-run-with-incomplete",
        device_id="device-1",
        player_id="test_player",
        run_no=1,
        started_at=datetime.utcnow(),
        finished_at=None,
        status="started",
        hits=0,
        score=0
    )
    test_db.add(run)
    test_db.commit()
    
    # Add completed and incomplete hits
    hit_complete = Hit(run_uid="test-run-with-incomplete", hit_no=1, start_ms=1000, duration_ms=100)
    hit_incomplete = Hit(run_uid="test-run-with-incomplete", hit_no=2, start_ms=2000, duration_ms=0)  # In progress
    test_db.add_all([hit_complete, hit_incomplete])
    test_db.commit()
    
    # Query for active run
    active_run = test_db.query(Run).filter(
        Run.status == "started",
        Run.finished_at.is_(None)
    ).order_by(Run.started_at.desc()).first()
    
    assert active_run is not None
    
    # Count completed hits only
    hit_count = test_db.query(Hit).filter(
        Hit.run_uid == active_run.run_uid,
        Hit.duration_ms > 0
    ).count()
    
    assert hit_count == 1  # Only completed hit counted


@pytest.mark.asyncio
async def test_sse_event_broadcasting():
    """Test that events are broadcast to all connected SSE clients."""
    # Clear any existing clients
    sse_clients.clear()
    
    # Create mock client queues
    queue1 = asyncio.Queue(maxsize=200)
    queue2 = asyncio.Queue(maxsize=200)
    
    sse_clients.append((1, queue1))
    sse_clients.append((2, queue2))
    
    # Broadcast an event
    test_event = {
        "event": "test_event",
        "run_uid": "test-123",
        "data": "test_data"
    }
    
    await broadcast_event_async(test_event)
    
    # Both queues should receive the event
    event1 = await asyncio.wait_for(queue1.get(), timeout=1.0)
    event2 = await asyncio.wait_for(queue2.get(), timeout=1.0)
    
    assert event1 == test_event
    assert event2 == test_event
    
    # Clean up
    sse_clients.clear()


@pytest.mark.asyncio
async def test_sse_full_queue_handling():
    """Test that full queue is handled gracefully (warning, not crash)."""
    sse_clients.clear()
    
    # Create a small queue and fill it
    small_queue = asyncio.Queue(maxsize=2)
    small_queue.put_nowait({"event": "filler1"})
    small_queue.put_nowait({"event": "filler2"})
    
    sse_clients.append((1, small_queue))
    
    # Try to broadcast when queue is full
    test_event = {"event": "test_overflow", "run_uid": "test-456"}
    
    # Should not raise exception, just log warning
    await broadcast_event_async(test_event)
    
    # Queue should still have original items
    assert small_queue.qsize() == 2
    
    sse_clients.clear()


@pytest.mark.asyncio
async def test_sse_multiple_events_in_sequence():
    """Test that multiple events are delivered in correct order."""
    sse_clients.clear()
    
    queue = asyncio.Queue(maxsize=200)
    sse_clients.append((1, queue))
    
    # Broadcast multiple events
    events = [
        {"event": "run_start", "run_uid": "test-seq-1", "sequence": 1},
        {"event": "hit_start", "run_uid": "test-seq-1", "sequence": 2},
        {"event": "hit_end", "run_uid": "test-seq-1", "sequence": 3},
        {"event": "run_finish", "run_uid": "test-seq-1", "sequence": 4},
    ]
    
    for event in events:
        await broadcast_event_async(event)
    
    # Retrieve and verify order
    received = []
    for _ in range(4):
        event = await asyncio.wait_for(queue.get(), timeout=1.0)
        received.append(event["sequence"])
    
    assert received == [1, 2, 3, 4]
    
    sse_clients.clear()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
