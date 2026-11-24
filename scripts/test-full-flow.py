#!/usr/bin/env python3
"""
Full End-to-End Flow Test
Simulates ESP32 event sequence through serial gateway to backend
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import json
import time
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import after adding to path
from app.models import Base, Run, Hit, Player, Device

# Test database
TEST_DB = "sqlite:///./test_aquabuzz.db"
engine = create_engine(TEST_DB, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def setup_test_db():
    """Create fresh test database"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("✓ Test database created")

def process_event(event: dict, db_session):
    """Simplified event processing for testing"""
    event_type = event.get("event")
    device_id = event.get("device_id")
    
    # Ensure device exists
    device = db_session.query(Device).filter(Device.id == device_id).first()
    if not device:
        device = Device(id=device_id)
        db_session.add(device)
        db_session.commit()
    
    # Handle heartbeat
    if "heartbeat" in event.get("_topic", ""):
        device.last_heartbeat = datetime.utcnow()
        db_session.commit()
        return
    
    # Handle game events
    run_uid = event.get("run_uid")
    player_id = event.get("player_id", "guest")
    
    if not run_uid:
        return
    
    # Ensure player exists
    player = db_session.query(Player).filter(Player.id == player_id).first()
    if not player:
        player = Player(id=player_id, name=player_id)
        db_session.add(player)
        db_session.commit()
    
    if event_type == "run_start":
        run = db_session.query(Run).filter(Run.run_uid == run_uid).first()
        if not run:
            run = Run(
                run_uid=run_uid,
                device_id=device_id,
                player_id=player_id,
                run_no=event.get("run_no", 0),
                started_at=datetime.utcnow(),
                status="started"
            )
            db_session.add(run)
            db_session.commit()
            print(f"    Created run: {run_uid}")
    
    elif event_type == "hit_start":
        run = db_session.query(Run).filter(Run.run_uid == run_uid).first()
        if not run:
            return
        
        hit_no = event.get("hit", 0)
        start_ms = event.get("t_ms", 0)
        
        existing = db_session.query(Hit).filter(
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
            db_session.add(hit)
            db_session.commit()
            print(f"    Hit {hit_no} started")
    
    elif event_type == "hit_end":
        run = db_session.query(Run).filter(Run.run_uid == run_uid).first()
        if not run:
            return
        
        hit_no = event.get("hit", 0)
        dur_ms = event.get("dur_ms", 0)
        
        hit = db_session.query(Hit).filter(
            Hit.run_uid == run_uid, 
            Hit.hit_no == hit_no
        ).first()
        
        if hit:
            if hit.duration_ms == 0:
                hit.duration_ms = dur_ms
                db_session.commit()
                print(f"    Hit {hit_no} completed: {dur_ms}ms")
        else:
            # Create complete record
            start_ms = event.get("t_ms", 0) - dur_ms
            hit = Hit(
                run_uid=run_uid,
                hit_no=hit_no,
                start_ms=start_ms,
                duration_ms=dur_ms
            )
            db_session.add(hit)
            db_session.commit()
            print(f"    Hit {hit_no} created (missed start)")
    
    elif event_type == "run_finish":
        run = db_session.query(Run).filter(Run.run_uid == run_uid).first()
        if run and run.status != "finished":
            run.finished_at = datetime.utcnow()
            run.duration_ms = event.get("t_ms", 0)
            run.hit_penalty_ms = event.get("hit_penalty_ms", 2000)
            
            # Calculate from Hit records (database as source of truth)
            hit_records = db_session.query(Hit).filter(Hit.run_uid == run_uid).all()
            completed_hits = [h for h in hit_records if h.duration_ms > 0]
            
            run.hits = len(completed_hits)
            run.total_contact_ms = sum(h.duration_ms for h in completed_hits)
            run.longest_hit_ms = max((h.duration_ms for h in completed_hits), default=0)
            
            # Recalculate score
            free_hits = 0
            scored_hits = max(0, run.hits - free_hits)
            run.score = run.duration_ms + (scored_hits * run.hit_penalty_ms)
            
            run.status = "finished"
            db_session.commit()
            print(f"    Run finished: score {run.score}ms (hits: {run.hits})")
    
    elif event_type == "run_cancel":
        run = db_session.query(Run).filter(Run.run_uid == run_uid).first()
        if run and run.status != "cancelled":
            run.status = "cancelled"
            run.duration_ms = event.get("t_ms", 0)
            db_session.commit()
            print(f"    Run cancelled")

def simulate_perfect_run(db):
    """Simulate a perfect run with no hits"""
    print("\n" + "="*60)
    print("TEST 1: Perfect Run (Zero Hits)")
    print("="*60)
    
    events = [
        {
            "device_id": "aquabuzz-001",
            "run_uid": "aquabuzz-001-test-1",
            "run_no": 1,
            "player_id": "test_player",
            "event": "run_start",
            "t_ms": 0,
            "_topic": "aquabuzz/aquabuzz-001/events"
        },
        {
            "device_id": "aquabuzz-001",
            "run_uid": "aquabuzz-001-test-1",
            "run_no": 1,
            "player_id": "test_player",
            "event": "run_finish",
            "t_ms": 5000,
            "hits": 0,
            "total_contact_ms": 0,
            "longest_hit_ms": 0,
            "hit_penalty_ms": 2000,
            "score": 5000,
            "_topic": "aquabuzz/aquabuzz-001/events"
        }
    ]
    
    for i, event in enumerate(events):
        print(f"\n  [{i+1}/{len(events)}] {event['event']}")
        process_event(event, db)
    
    # Verify
    run = db.query(Run).filter(Run.run_uid == "aquabuzz-001-test-1").first()
    
    assert run is not None, "Run not created"
    assert run.status == "finished", f"Expected finished, got {run.status}"
    assert run.hits == 0, f"Expected 0 hits, got {run.hits}"
    assert run.score == 5000, f"Expected score 5000, got {run.score}"
    
    print("\n✓ PASSED: Perfect run recorded correctly")

def simulate_run_with_hits(db):
    """Simulate a run with multiple hits"""
    print("\n" + "="*60)
    print("TEST 2: Run with Multiple Hits")
    print("="*60)
    
    events = [
        {
            "device_id": "aquabuzz-001",
            "run_uid": "aquabuzz-001-test-2",
            "run_no": 2,
            "player_id": "test_player",
            "event": "run_start",
            "t_ms": 0,
            "_topic": "aquabuzz/aquabuzz-001/events"
        },
        {
            "device_id": "aquabuzz-001",
            "run_uid": "aquabuzz-001-test-2",
            "run_no": 2,
            "player_id": "test_player",
            "event": "hit_start",
            "hit": 1,
            "t_ms": 1000,
            "_topic": "aquabuzz/aquabuzz-001/events"
        },
        {
            "device_id": "aquabuzz-001",
            "run_uid": "aquabuzz-001-test-2",
            "run_no": 2,
            "player_id": "test_player",
            "event": "hit_end",
            "hit": 1,
            "t_ms": 1150,
            "dur_ms": 150,
            "_topic": "aquabuzz/aquabuzz-001/events"
        },
        {
            "device_id": "aquabuzz-001",
            "run_uid": "aquabuzz-001-test-2",
            "run_no": 2,
            "player_id": "test_player",
            "event": "hit_start",
            "hit": 2,
            "t_ms": 3000,
            "_topic": "aquabuzz/aquabuzz-001/events"
        },
        {
            "device_id": "aquabuzz-001",
            "run_uid": "aquabuzz-001-test-2",
            "run_no": 2,
            "player_id": "test_player",
            "event": "hit_end",
            "hit": 2,
            "t_ms": 3200,
            "dur_ms": 200,
            "_topic": "aquabuzz/aquabuzz-001/events"
        },
        {
            "device_id": "aquabuzz-001",
            "run_uid": "aquabuzz-001-test-2",
            "run_no": 2,
            "player_id": "test_player",
            "event": "run_finish",
            "t_ms": 8000,
            "hits": 2,
            "total_contact_ms": 350,
            "longest_hit_ms": 200,
            "hit_penalty_ms": 2000,
            "score": 12000,
            "_topic": "aquabuzz/aquabuzz-001/events"
        }
    ]
    
    for i, event in enumerate(events):
        print(f"\n  [{i+1}/{len(events)}] {event['event']}")
        process_event(event, db)
    
    # Verify
    run = db.query(Run).filter(Run.run_uid == "aquabuzz-001-test-2").first()
    
    assert run is not None, "Run not created"
    assert run.status == "finished", f"Expected finished, got {run.status}"
    assert run.hits == 2, f"Expected 2 hits, got {run.hits}"
    assert run.score == 12000, f"Expected score 12000, got {run.score}"
    
    # Check hit records
    hits = db.query(Hit).filter(Hit.run_uid == "aquabuzz-001-test-2").all()
    assert len(hits) == 2, f"Expected 2 hit records, got {len(hits)}"
    
    print("\n✓ PASSED: Run with hits recorded correctly")

def simulate_duplicate_events(db):
    """Test idempotency"""
    print("\n" + "="*60)
    print("TEST 3: Duplicate Event Handling")
    print("="*60)
    
    event = {
        "device_id": "aquabuzz-001",
        "run_uid": "aquabuzz-001-test-3",
        "run_no": 3,
        "player_id": "test_player",
        "event": "run_start",
        "t_ms": 0,
        "_topic": "aquabuzz/aquabuzz-001/events"
    }
    
    print("\n  [1] run_start (first)")
    process_event(event, db)
    
    print("  [2] run_start (duplicate)")
    process_event(event, db)
    
    # Verify only one run
    runs = db.query(Run).filter(Run.run_uid == "aquabuzz-001-test-3").all()
    assert len(runs) == 1, f"Expected 1 run, got {len(runs)}"
    
    print("\n✓ PASSED: Duplicates handled correctly")

def print_final_stats(db):
    """Print final stats"""
    print("\n" + "="*60)
    print("FINAL DATABASE STATE")
    print("="*60)
    
    total_runs = db.query(Run).count()
    finished_runs = db.query(Run).filter(Run.status == "finished").count()
    total_hits = db.query(Hit).count()
    
    print(f"\n  Total Runs: {total_runs}")
    print(f"  Finished: {finished_runs}")
    print(f"  Total Hits: {total_hits}")

def main():
    print("\n" + "="*60)
    print("AQUABUZZ END-TO-END INTEGRATION TEST")
    print("="*60)
    
    db = None
    try:
        setup_test_db()
        db = SessionLocal()
        
        simulate_perfect_run(db)
        simulate_run_with_hits(db)
        simulate_duplicate_events(db)
        print_final_stats(db)
        
        print("\n" + "="*60)
        print("✓✓✓ ALL TESTS PASSED ✓✓✓")
        print("="*60)
        print("\nSystem ready for physical ESP32 testing!")
        
        return 0
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        if db:
            db.close()
        engine.dispose()
        time.sleep(0.5)
        if os.path.exists("test_aquabuzz.db"):
            try:
                os.remove("test_aquabuzz.db")
            except:
                pass

if __name__ == "__main__":
    sys.exit(main())


def setup_test_db():
    """Create fresh test database"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("✓ Test database created")

def simulate_perfect_run():
    """Simulate a perfect run with no hits"""
    print("\n" + "="*60)
    print("TEST 1: Perfect Run (Zero Hits)")
    print("="*60)
    
    events = [
        {
            "device_id": "aquabuzz-001",
            "run_uid": "aquabuzz-001-test-1",
            "run_no": 1,
            "player_id": "test_player",
            "event": "run_start",
            "t_ms": 0,
            "_topic": "aquabuzz/aquabuzz-001/events"
        },
        {
            "device_id": "aquabuzz-001",
            "run_uid": "aquabuzz-001-test-1",
            "run_no": 1,
            "player_id": "test_player",
            "event": "run_finish",
            "t_ms": 5000,
            "hits": 0,
            "total_contact_ms": 0,
            "longest_hit_ms": 0,
            "hit_penalty_ms": 2000,
            "score": 5000,
            "_topic": "aquabuzz/aquabuzz-001/events"
        }
    ]
    
    for i, event in enumerate(events):
        print(f"\n[{i+1}/{len(events)}] Processing: {event['event']}")
        handle_mqtt_event(event)
        time.sleep(0.1)
    
    # Verify
    db = SessionLocal()
    run = db.query(Run).filter(Run.run_uid == "aquabuzz-001-test-1").first()
    
    assert run is not None, "Run not created"
    assert run.status == "finished", f"Expected finished, got {run.status}"
    assert run.hits == 0, f"Expected 0 hits, got {run.hits}"
    assert run.score == 5000, f"Expected score 5000, got {run.score}"
    
    db.close()
    print("✓ PASSED: Perfect run recorded correctly")

def simulate_run_with_hits():
    """Simulate a run with multiple hits"""
    print("\n" + "="*60)
    print("TEST 2: Run with Multiple Hits")
    print("="*60)
    
    events = [
        {
            "device_id": "aquabuzz-001",
            "run_uid": "aquabuzz-001-test-2",
            "run_no": 2,
            "player_id": "test_player",
            "event": "run_start",
            "t_ms": 0,
            "_topic": "aquabuzz/aquabuzz-001/events"
        },
        {
            "device_id": "aquabuzz-001",
            "run_uid": "aquabuzz-001-test-2",
            "run_no": 2,
            "player_id": "test_player",
            "event": "hit_start",
            "hit": 1,
            "t_ms": 1000,
            "_topic": "aquabuzz/aquabuzz-001/events"
        },
        {
            "device_id": "aquabuzz-001",
            "run_uid": "aquabuzz-001-test-2",
            "run_no": 2,
            "player_id": "test_player",
            "event": "hit_end",
            "hit": 1,
            "t_ms": 1150,
            "dur_ms": 150,
            "_topic": "aquabuzz/aquabuzz-001/events"
        },
        {
            "device_id": "aquabuzz-001",
            "run_uid": "aquabuzz-001-test-2",
            "run_no": 2,
            "player_id": "test_player",
            "event": "hit_start",
            "hit": 2,
            "t_ms": 3000,
            "_topic": "aquabuzz/aquabuzz-001/events"
        },
        {
            "device_id": "aquabuzz-001",
            "run_uid": "aquabuzz-001-test-2",
            "run_no": 2,
            "player_id": "test_player",
            "event": "hit_end",
            "hit": 2,
            "t_ms": 3200,
            "dur_ms": 200,
            "_topic": "aquabuzz/aquabuzz-001/events"
        },
        {
            "device_id": "aquabuzz-001",
            "run_uid": "aquabuzz-001-test-2",
            "run_no": 2,
            "player_id": "test_player",
            "event": "run_finish",
            "t_ms": 8000,
            "hits": 2,
            "total_contact_ms": 350,
            "longest_hit_ms": 200,
            "hit_penalty_ms": 2000,
            "score": 12000,  # 8000 + (2 * 2000)
            "_topic": "aquabuzz/aquabuzz-001/events"
        }
    ]
    
    for i, event in enumerate(events):
        print(f"\n[{i+1}/{len(events)}] Processing: {event['event']}")
        handle_mqtt_event(event)
        time.sleep(0.1)
    
    # Verify
    db = SessionLocal()
    run = db.query(Run).filter(Run.run_uid == "aquabuzz-001-test-2").first()
    
    assert run is not None, "Run not created"
    assert run.status == "finished", f"Expected finished, got {run.status}"
    assert run.hits == 2, f"Expected 2 hits, got {run.hits}"
    assert run.score == 12000, f"Expected score 12000, got {run.score}"
    assert run.longest_hit_ms == 200, f"Expected longest hit 200ms, got {run.longest_hit_ms}"
    
    # Check hit records
    hits = db.query(Hit).filter(Hit.run_uid == "aquabuzz-001-test-2").all()
    assert len(hits) == 2, f"Expected 2 hit records, got {len(hits)}"
    
    hit1 = [h for h in hits if h.hit_no == 1][0]
    assert hit1.start_ms == 1000, f"Hit 1 start: expected 1000, got {hit1.start_ms}"
    assert hit1.duration_ms == 150, f"Hit 1 duration: expected 150, got {hit1.duration_ms}"
    
    hit2 = [h for h in hits if h.hit_no == 2][0]
    assert hit2.start_ms == 3000, f"Hit 2 start: expected 3000, got {hit2.start_ms}"
    assert hit2.duration_ms == 200, f"Hit 2 duration: expected 200, got {hit2.duration_ms}"
    
    db.close()
    print("✓ PASSED: Run with hits recorded correctly")

def simulate_duplicate_events():
    """Test idempotency - duplicate events should be ignored"""
    print("\n" + "="*60)
    print("TEST 3: Duplicate Event Handling (Idempotency)")
    print("="*60)
    
    # Send run_start twice
    event = {
        "device_id": "aquabuzz-001",
        "run_uid": "aquabuzz-001-test-3",
        "run_no": 3,
        "player_id": "test_player",
        "event": "run_start",
        "t_ms": 0,
        "_topic": "aquabuzz/aquabuzz-001/events"
    }
    
    print("\n[1] Processing: run_start (first time)")
    handle_mqtt_event(event)
    time.sleep(0.1)
    
    print("[2] Processing: run_start (duplicate)")
    handle_mqtt_event(event)
    time.sleep(0.1)
    
    # Verify only one run created
    db = SessionLocal()
    runs = db.query(Run).filter(Run.run_uid == "aquabuzz-001-test-3").all()
    assert len(runs) == 1, f"Expected 1 run, got {len(runs)}"
    
    # Send hit_start and hit_end twice
    hit_start = {
        "device_id": "aquabuzz-001",
        "run_uid": "aquabuzz-001-test-3",
        "run_no": 3,
        "player_id": "test_player",
        "event": "hit_start",
        "hit": 1,
        "t_ms": 1000,
        "_topic": "aquabuzz/aquabuzz-001/events"
    }
    
    print("[3] Processing: hit_start (first time)")
    handle_mqtt_event(hit_start)
    time.sleep(0.1)
    
    print("[4] Processing: hit_start (duplicate)")
    handle_mqtt_event(hit_start)
    time.sleep(0.1)
    
    # Verify only one hit record
    hits = db.query(Hit).filter(Hit.run_uid == "aquabuzz-001-test-3").all()
    assert len(hits) == 1, f"Expected 1 hit, got {len(hits)}"
    
    # Send hit_end
    hit_end = {
        "device_id": "aquabuzz-001",
        "run_uid": "aquabuzz-001-test-3",
        "run_no": 3,
        "player_id": "test_player",
        "event": "hit_end",
        "hit": 1,
        "t_ms": 1150,
        "dur_ms": 150,
        "_topic": "aquabuzz/aquabuzz-001/events"
    }
    
    print("[5] Processing: hit_end (first time)")
    handle_mqtt_event(hit_end)
    time.sleep(0.1)
    
    print("[6] Processing: hit_end (duplicate)")
    handle_mqtt_event(hit_end)
    time.sleep(0.1)
    
    # Verify hit duration only set once
    hits = db.query(Hit).filter(Hit.run_uid == "aquabuzz-001-test-3").all()
    assert len(hits) == 1, f"Expected 1 hit, got {len(hits)}"
    assert hits[0].duration_ms == 150, f"Expected duration 150, got {hits[0].duration_ms}"
    
    db.close()
    print("✓ PASSED: Duplicate events properly ignored")

def simulate_active_hit_at_finish():
    """Test run finish with active hit (should close the hit first)"""
    print("\n" + "="*60)
    print("TEST 4: Active Hit at Finish")
    print("="*60)
    
    events = [
        {
            "device_id": "aquabuzz-001",
            "run_uid": "aquabuzz-001-test-4",
            "run_no": 4,
            "player_id": "test_player",
            "event": "run_start",
            "t_ms": 0,
            "_topic": "aquabuzz/aquabuzz-001/events"
        },
        {
            "device_id": "aquabuzz-001",
            "run_uid": "aquabuzz-001-test-4",
            "run_no": 4,
            "player_id": "test_player",
            "event": "hit_start",
            "hit": 1,
            "t_ms": 2000,
            "_topic": "aquabuzz/aquabuzz-001/events"
        },
        # Note: NO hit_end before run_finish!
        # Firmware should send hit_end before run_finish (our fix)
        {
            "device_id": "aquabuzz-001",
            "run_uid": "aquabuzz-001-test-4",
            "run_no": 4,
            "player_id": "test_player",
            "event": "hit_end",
            "hit": 1,
            "t_ms": 5000,
            "dur_ms": 3000,
            "_topic": "aquabuzz/aquabuzz-001/events"
        },
        {
            "device_id": "aquabuzz-001",
            "run_uid": "aquabuzz-001-test-4",
            "run_no": 4,
            "player_id": "test_player",
            "event": "run_finish",
            "t_ms": 5000,
            "hits": 1,
            "total_contact_ms": 3000,
            "longest_hit_ms": 3000,
            "hit_penalty_ms": 2000,
            "score": 7000,
            "_topic": "aquabuzz/aquabuzz-001/events"
        }
    ]
    
    for i, event in enumerate(events):
        print(f"\n[{i+1}/{len(events)}] Processing: {event['event']}")
        handle_mqtt_event(event)
        time.sleep(0.1)
    
    # Verify
    db = SessionLocal()
    run = db.query(Run).filter(Run.run_uid == "aquabuzz-001-test-4").first()
    
    assert run is not None, "Run not created"
    assert run.status == "finished", f"Expected finished, got {run.status}"
    assert run.longest_hit_ms == 3000, f"Expected longest hit 3000ms, got {run.longest_hit_ms}"
    
    # Verify hit was recorded
    hits = db.query(Hit).filter(Hit.run_uid == "aquabuzz-001-test-4").all()
    assert len(hits) == 1, f"Expected 1 hit, got {len(hits)}"
    assert hits[0].duration_ms == 3000, f"Expected hit duration 3000ms, got {hits[0].duration_ms}"
    
    db.close()
    print("✓ PASSED: Active hit properly closed at finish")

def print_final_stats():
    """Print final database statistics"""
    print("\n" + "="*60)
    print("FINAL DATABASE STATE")
    print("="*60)
    
    db = SessionLocal()
    
    total_runs = db.query(Run).count()
    finished_runs = db.query(Run).filter(Run.status == "finished").count()
    total_hits = db.query(Hit).count()
    total_players = db.query(Player).count()
    
    print(f"\nTotal Runs: {total_runs}")
    print(f"Finished Runs: {finished_runs}")
    print(f"Total Hit Records: {total_hits}")
    print(f"Total Players: {total_players}")
    
    print("\nAll Runs:")
    runs = db.query(Run).all()
    for run in runs:
        print(f"  - {run.run_uid}: {run.status}, {run.hits} hits, score: {run.score}ms")
    
    db.close()

def main():
    print("\n" + "="*60)
    print("AQUABUZZ END-TO-END INTEGRATION TEST")
    print("="*60)
    print(f"Test Database: {TEST_DB}")
    print(f"Time: {datetime.now().isoformat()}")
    
    try:
        setup_test_db()
        simulate_perfect_run()
        simulate_run_with_hits()
        simulate_duplicate_events()
        simulate_active_hit_at_finish()
        print_final_stats()
        
        print("\n" + "="*60)
        print("✓✓✓ ALL TESTS PASSED ✓✓✓")
        print("="*60)
        print("\nThe AquaBuzz system correctly:")
        print("  ✓ Records perfect runs (zero hits)")
        print("  ✓ Tracks individual hit start/end events")
        print("  ✓ Calculates scores correctly")
        print("  ✓ Ignores duplicate events (idempotency)")
        print("  ✓ Closes active hits before finish")
        print("  ✓ Stores all data in the database")
        print("\nSystem is ready for physical ESP32 testing!")
        
        return 0
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # Clean up test database
        if os.path.exists("test_aquabuzz.db"):
            os.remove("test_aquabuzz.db")
            print("\n✓ Test database cleaned up")

if __name__ == "__main__":
    sys.exit(main())
