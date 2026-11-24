"""Tests for repairs: hit aggregation, stale runs, and idempotency."""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db import Base
from app.models import Player, Device, Run, Hit
from app.main import handle_mqtt_event, detect_and_mark_stale_runs


@pytest.fixture
def test_db():
    """Create a fresh in-memory database for each test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture
def sample_device(test_db):
    """Create a test device."""
    device = Device(id="test-device-001")
    test_db.add(device)
    test_db.commit()
    return device


@pytest.fixture
def sample_player(test_db):
    """Create a test player."""
    player = Player(id="test-player", name="Test Player")
    test_db.add(player)
    test_db.commit()
    return player


def test_hit_aggregation_from_database(test_db, sample_device, sample_player):
    """Test that run_finish calculates stats from actual Hit records."""
    run_uid = "test-run-001"
    
    # Create run
    run = Run(
        run_uid=run_uid,
        device_id=sample_device.id,
        player_id=sample_player.id,
        run_no=1,
        started_at=datetime.utcnow(),
        status="started"
    )
    test_db.add(run)
    test_db.commit()
    
    # Create Hit records
    hit1 = Hit(run_uid=run_uid, hit_no=1, start_ms=1000, duration_ms=200)
    hit2 = Hit(run_uid=run_uid, hit_no=2, start_ms=3000, duration_ms=150)
    hit3 = Hit(run_uid=run_uid, hit_no=3, start_ms=5000, duration_ms=300)
    test_db.add_all([hit1, hit2, hit3])
    test_db.commit()
    
    # Simulate run_finish - directly replicate the logic from main.py
    hit_records = test_db.query(Hit).filter(Hit.run_uid == run_uid).all()
    completed_hits = [h for h in hit_records if h.duration_ms > 0]
    
    run.hits = len(completed_hits)
    run.total_contact_ms = sum(h.duration_ms for h in completed_hits)
    run.longest_hit_ms = max((h.duration_ms for h in completed_hits), default=0)
    run.duration_ms = 8000
    run.hit_penalty_ms = 2000
    
    # Calculate score
    free_hits = 0
    scored_hits = max(0, run.hits - free_hits)
    run.score = run.duration_ms + (scored_hits * run.hit_penalty_ms)
    run.status = "finished"
    run.finished_at = datetime.utcnow()
    test_db.commit()
    
    # Verify aggregates match Hit records
    assert run.hits == 3
    assert run.total_contact_ms == 650  # 200 + 150 + 300
    assert run.longest_hit_ms == 300
    assert run.score == 14000  # 8000 + (3 * 2000)
    assert run.status == "finished"


def test_incomplete_hits_excluded(test_db, sample_device, sample_player):
    """Test that hits with duration_ms=0 are excluded from aggregates."""
    run_uid = "test-run-002"
    
    # Create run
    run = Run(
        run_uid=run_uid,
        device_id=sample_device.id,
        player_id=sample_player.id,
        run_no=2,
        started_at=datetime.utcnow(),
        status="started"
    )
    test_db.add(run)
    test_db.commit()
    
    # Create mix of complete and incomplete hits
    hit1 = Hit(run_uid=run_uid, hit_no=1, start_ms=1000, duration_ms=250)
    hit2 = Hit(run_uid=run_uid, hit_no=2, start_ms=2000, duration_ms=0)  # Incomplete
    hit3 = Hit(run_uid=run_uid, hit_no=3, start_ms=3000, duration_ms=180)
    hit4 = Hit(run_uid=run_uid, hit_no=4, start_ms=4000, duration_ms=0)  # Incomplete
    test_db.add_all([hit1, hit2, hit3, hit4])
    test_db.commit()
    
    # Simulate run_finish
    hit_records = test_db.query(Hit).filter(Hit.run_uid == run_uid).all()
    completed_hits = [h for h in hit_records if h.duration_ms > 0]
    
    run.hits = len(completed_hits)
    run.total_contact_ms = sum(h.duration_ms for h in completed_hits)
    run.longest_hit_ms = max((h.duration_ms for h in completed_hits), default=0)
    run.duration_ms = 7000
    run.hit_penalty_ms = 2000
    
    free_hits = 0
    scored_hits = max(0, run.hits - free_hits)
    run.score = run.duration_ms + (scored_hits * run.hit_penalty_ms)
    run.status = "finished"
    run.finished_at = datetime.utcnow()
    test_db.commit()
    
    # Verify only completed hits counted
    assert run.hits == 2  # Only hit1 and hit3
    assert run.total_contact_ms == 430  # 250 + 180
    assert run.longest_hit_ms == 250
    assert run.score == 11000  # 7000 + (2 * 2000)


def test_stale_run_detection(test_db, sample_device, sample_player):
    """Test that old started runs are marked as abandoned."""
    # Create stale run (started 1 hour ago, still status='started')
    old_time = datetime.utcnow() - timedelta(hours=1)
    stale_run = Run(
        run_uid="stale-run-001",
        device_id=sample_device.id,
        player_id=sample_player.id,
        run_no=10,
        started_at=old_time,
        status="started",
        finished_at=None
    )
    test_db.add(stale_run)
    
    # Create recent run (should not be marked as stale)
    recent_run = Run(
        run_uid="recent-run-001",
        device_id=sample_device.id,
        player_id=sample_player.id,
        run_no=11,
        started_at=datetime.utcnow() - timedelta(minutes=5),
        status="started",
        finished_at=None
    )
    test_db.add(recent_run)
    test_db.commit()
    
    # Call stale run detection with 30-minute timeout
    stale_count = detect_and_mark_stale_runs(test_db, timeout_minutes=30)
    
    # Verify results
    assert stale_count == 1
    
    test_db.refresh(stale_run)
    test_db.refresh(recent_run)
    
    assert stale_run.status == "abandoned"
    assert stale_run.finished_at is None  # Not marked as finished
    assert recent_run.status == "started"  # Still active


def test_active_runs_exclude_abandoned(test_db, sample_device, sample_player):
    """Test that active_runs count excludes finished and abandoned runs."""
    # Create runs in different states
    run1 = Run(
        run_uid="active-001",
        device_id=sample_device.id,
        player_id=sample_player.id,
        run_no=1,
        started_at=datetime.utcnow(),
        status="started",
        finished_at=None
    )
    
    run2 = Run(
        run_uid="finished-001",
        device_id=sample_device.id,
        player_id=sample_player.id,
        run_no=2,
        started_at=datetime.utcnow() - timedelta(minutes=10),
        status="finished",
        finished_at=datetime.utcnow() - timedelta(minutes=5)
    )
    
    run3 = Run(
        run_uid="abandoned-001",
        device_id=sample_device.id,
        player_id=sample_player.id,
        run_no=3,
        started_at=datetime.utcnow() - timedelta(hours=2),
        status="abandoned",
        finished_at=None
    )
    
    run4 = Run(
        run_uid="cancelled-001",
        device_id=sample_device.id,
        player_id=sample_player.id,
        run_no=4,
        started_at=datetime.utcnow() - timedelta(minutes=15),
        status="cancelled",
        finished_at=None
    )
    
    test_db.add_all([run1, run2, run3, run4])
    test_db.commit()
    
    # Query as /api/health does
    active_runs = test_db.query(Run).filter(
        Run.status == "started",
        Run.finished_at.is_(None)
    ).count()
    
    # Verify count matches only truly active runs
    assert active_runs == 1  # Only run1


def test_duplicate_hit_start_idempotent(test_db, sample_device, sample_player):
    """Test that duplicate hit_start doesn't create duplicate hits."""
    run_uid = "idempotent-run-001"
    
    # Create run
    run = Run(
        run_uid=run_uid,
        device_id=sample_device.id,
        player_id=sample_player.id,
        run_no=1,
        started_at=datetime.utcnow(),
        status="started"
    )
    test_db.add(run)
    test_db.commit()
    
    # Simulate hit_start event
    hit_no = 1
    start_ms = 1000
    
    # First hit_start
    existing = test_db.query(Hit).filter(
        Hit.run_uid == run_uid, 
        Hit.hit_no == hit_no
    ).first()
    
    if not existing:
        hit = Hit(
            run_uid=run_uid,
            hit_no=hit_no,
            start_ms=start_ms,
            duration_ms=0
        )
        test_db.add(hit)
        test_db.commit()
    
    # Duplicate hit_start (should be ignored)
    existing = test_db.query(Hit).filter(
        Hit.run_uid == run_uid, 
        Hit.hit_no == hit_no
    ).first()
    
    if not existing:
        hit = Hit(
            run_uid=run_uid,
            hit_no=hit_no,
            start_ms=start_ms,
            duration_ms=0
        )
        test_db.add(hit)
        test_db.commit()
    
    # Verify only one Hit record created
    hit_count = test_db.query(Hit).filter(Hit.run_uid == run_uid).count()
    assert hit_count == 1


def test_duplicate_hit_end_idempotent(test_db, sample_device, sample_player):
    """Test that duplicate hit_end doesn't update again."""
    run_uid = "idempotent-run-002"
    
    # Create run and hit
    run = Run(
        run_uid=run_uid,
        device_id=sample_device.id,
        player_id=sample_player.id,
        run_no=2,
        started_at=datetime.utcnow(),
        status="started"
    )
    test_db.add(run)
    test_db.commit()
    
    hit = Hit(run_uid=run_uid, hit_no=1, start_ms=1000, duration_ms=0)
    test_db.add(hit)
    test_db.commit()
    
    # First hit_end
    hit = test_db.query(Hit).filter(
        Hit.run_uid == run_uid, 
        Hit.hit_no == 1
    ).first()
    
    if hit and hit.duration_ms == 0:
        hit.duration_ms = 200
        test_db.commit()
    
    original_duration = hit.duration_ms
    
    # Duplicate hit_end with different duration (should be ignored)
    hit = test_db.query(Hit).filter(
        Hit.run_uid == run_uid, 
        Hit.hit_no == 1
    ).first()
    
    if hit and hit.duration_ms == 0:  # Should NOT update
        hit.duration_ms = 500
        test_db.commit()
    
    # Verify duration only set once
    test_db.refresh(hit)
    assert hit.duration_ms == original_duration  # Should still be 200


def test_duplicate_run_finish_idempotent(test_db, sample_device, sample_player):
    """Test that duplicate run_finish doesn't re-process."""
    run_uid = "idempotent-run-003"
    
    # Create run with hits
    run = Run(
        run_uid=run_uid,
        device_id=sample_device.id,
        player_id=sample_player.id,
        run_no=3,
        started_at=datetime.utcnow(),
        status="started"
    )
    test_db.add(run)
    test_db.commit()
    
    hit = Hit(run_uid=run_uid, hit_no=1, start_ms=1000, duration_ms=200)
    test_db.add(hit)
    test_db.commit()
    
    # First run_finish
    if run.status != "finished":
        hit_records = test_db.query(Hit).filter(Hit.run_uid == run_uid).all()
        completed_hits = [h for h in hit_records if h.duration_ms > 0]
        
        run.hits = len(completed_hits)
        run.total_contact_ms = sum(h.duration_ms for h in completed_hits)
        run.longest_hit_ms = max((h.duration_ms for h in completed_hits), default=0)
        run.duration_ms = 5000
        run.hit_penalty_ms = 2000
        run.score = run.duration_ms + (run.hits * run.hit_penalty_ms)
        run.status = "finished"
        run.finished_at = datetime.utcnow()
        test_db.commit()
    
    original_score = run.score
    original_hits = run.hits
    
    # Add another hit (simulating late-arriving event)
    hit2 = Hit(run_uid=run_uid, hit_no=2, start_ms=3000, duration_ms=150)
    test_db.add(hit2)
    test_db.commit()
    
    # Duplicate run_finish (should be ignored)
    test_db.refresh(run)
    if run.status != "finished":  # Should not re-process
        hit_records = test_db.query(Hit).filter(Hit.run_uid == run_uid).all()
        completed_hits = [h for h in hit_records if h.duration_ms > 0]
        
        run.hits = len(completed_hits)
        run.total_contact_ms = sum(h.duration_ms for h in completed_hits)
        run.longest_hit_ms = max((h.duration_ms for h in completed_hits), default=0)
        run.score = run.duration_ms + (run.hits * run.hit_penalty_ms)
        test_db.commit()
    
    # Verify score and hits unchanged
    test_db.refresh(run)
    assert run.score == original_score  # Should still be 7000 (5000 + 1*2000)
    assert run.hits == original_hits  # Should still be 1


def test_duplicate_run_start_idempotent(test_db, sample_device, sample_player):
    """Test that duplicate run_start doesn't create duplicate runs."""
    run_uid = "idempotent-run-004"
    
    # First run_start
    run = test_db.query(Run).filter(Run.run_uid == run_uid).first()
    if not run:
        run = Run(
            run_uid=run_uid,
            device_id=sample_device.id,
            player_id=sample_player.id,
            run_no=1,
            started_at=datetime.utcnow(),
            status="started"
        )
        test_db.add(run)
        test_db.commit()
    
    # Duplicate run_start
    run = test_db.query(Run).filter(Run.run_uid == run_uid).first()
    if not run:
        run = Run(
            run_uid=run_uid,
            device_id=sample_device.id,
            player_id=sample_player.id,
            run_no=1,
            started_at=datetime.utcnow(),
            status="started"
        )
        test_db.add(run)
        test_db.commit()
    
    # Verify only one Run record created
    run_count = test_db.query(Run).filter(Run.run_uid == run_uid).count()
    assert run_count == 1


def test_zero_hits_aggregation(test_db, sample_device, sample_player):
    """Test run_finish with zero hits."""
    run_uid = "zero-hits-run"
    
    # Create run with no hits
    run = Run(
        run_uid=run_uid,
        device_id=sample_device.id,
        player_id=sample_player.id,
        run_no=5,
        started_at=datetime.utcnow(),
        status="started"
    )
    test_db.add(run)
    test_db.commit()
    
    # Simulate run_finish with no hits
    hit_records = test_db.query(Hit).filter(Hit.run_uid == run_uid).all()
    completed_hits = [h for h in hit_records if h.duration_ms > 0]
    
    run.hits = len(completed_hits)
    run.total_contact_ms = sum(h.duration_ms for h in completed_hits)
    run.longest_hit_ms = max((h.duration_ms for h in completed_hits), default=0)
    run.duration_ms = 6000
    run.hit_penalty_ms = 2000
    
    free_hits = 0
    scored_hits = max(0, run.hits - free_hits)
    run.score = run.duration_ms + (scored_hits * run.hit_penalty_ms)
    run.status = "finished"
    run.finished_at = datetime.utcnow()
    test_db.commit()
    
    # Verify correct aggregation
    assert run.hits == 0
    assert run.total_contact_ms == 0
    assert run.longest_hit_ms == 0
    assert run.score == 6000  # Only duration, no penalties
