#!/usr/bin/env python3
"""
Test Hit Aggregation Logic
Simulates the exact scenario where individual hits exist but aggregate stats are zero
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
TEST_DB = "sqlite:///./test_hit_aggregation.db"
engine = create_engine(TEST_DB, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def setup_test_db():
    """Create fresh test database"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("✓ Test database created\n")

def process_event(event: dict, db_session):
    """Simulate backend event processing with the NEW logic"""
    event_type = event.get("event")
    device_id = event.get("device_id")
    
    # Ensure device exists
    device = db_session.query(Device).filter(Device.id == device_id).first()
    if not device:
        device = Device(id=device_id)
        db_session.add(device)
        db_session.commit()
    
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
            print(f"  ✓ Created run: {run_uid}")
    
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
            print(f"  ✓ Hit #{hit_no} started at {start_ms}ms")
    
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
                print(f"  ✓ Hit #{hit_no} completed: {dur_ms}ms duration")
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
            print(f"  ⚠ Hit #{hit_no} created (missed start): {dur_ms}ms")
    
    elif event_type == "run_finish":
        run = db_session.query(Run).filter(Run.run_uid == run_uid).first()
        if run and run.status != "finished":
            run.finished_at = datetime.utcnow()
            run.duration_ms = event.get("t_ms", 0)
            run.hit_penalty_ms = event.get("hit_penalty_ms", 2000)
            
            # NEW LOGIC: Calculate from Hit records, not firmware stats
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
            
            print(f"  ✓ Run finished: {run_uid}")
            print(f"    Duration: {run.duration_ms}ms")
            print(f"    Hits (from DB): {run.hits}")
            print(f"    Total Contact (from DB): {run.total_contact_ms}ms")
            print(f"    Longest Hit (from DB): {run.longest_hit_ms}ms")
            print(f"    Score: {run.score}ms")
            print()
            print(f"    Firmware sent: hits={event.get('hits')}, total_contact={event.get('total_contact_ms')}, longest={event.get('longest_hit_ms')}")

def test_scenario_buggy_firmware():
    """Test: Firmware sends hits=0 but backend has individual hits"""
    print("="*70)
    print("TEST: Buggy Firmware Scenario")
    print("Firmware incorrectly sends hits=0 in run_finish")
    print("Backend should use Hit table as source of truth")
    print("="*70)
    print()
    
    db = SessionLocal()
    
    # Events simulating buggy firmware
    events = [
        {
            "device_id": "aquabuzz-001",
            "run_uid": "test-buggy-1",
            "run_no": 1,
            "player_id": "test_player",
            "event": "run_start",
            "t_ms": 0
        },
        {
            "device_id": "aquabuzz-001",
            "run_uid": "test-buggy-1",
            "run_no": 1,
            "player_id": "test_player",
            "event": "hit_start",
            "hit": 1,
            "t_ms": 1000
        },
        {
            "device_id": "aquabuzz-001",
            "run_uid": "test-buggy-1",
            "run_no": 1,
            "player_id": "test_player",
            "event": "hit_end",
            "hit": 1,
            "t_ms": 1289,
            "dur_ms": 289  # Valid 289ms contact
        },
        {
            "device_id": "aquabuzz-001",
            "run_uid": "test-buggy-1",
            "run_no": 1,
            "player_id": "test_player",
            "event": "run_finish",
            "t_ms": 4850,
            "hits": 0,  # BUGGY: Firmware says 0 hits
            "total_contact_ms": 0,  # BUGGY: Firmware says 0ms
            "longest_hit_ms": 0,  # BUGGY: Firmware says 0ms
            "hit_penalty_ms": 2000,
            "score": 4850  # BUGGY: Score ignores hit
        }
    ]
    
    for event in events:
        print(f"Processing: {event['event']}")
        process_event(event, db)
        print()
    
    # Verify results
    print("="*70)
    print("VERIFICATION")
    print("="*70)
    
    run = db.query(Run).filter(Run.run_uid == "test-buggy-1").first()
    hits = db.query(Hit).filter(Hit.run_uid == "test-buggy-1").all()
    
    print(f"\nIndividual Hits in Database: {len(hits)}")
    for h in hits:
        print(f"  Hit #{h.hit_no}: start={h.start_ms}ms, duration={h.duration_ms}ms")
    
    print(f"\nAggregate Statistics:")
    print(f"  Total Hits: {run.hits}")
    print(f"  Total Contact: {run.total_contact_ms}ms")
    print(f"  Longest Hit: {run.longest_hit_ms}ms")
    print(f"  Score: {run.score}ms")
    
    # Assertions
    assert len(hits) == 1, f"Expected 1 hit, got {len(hits)}"
    assert hits[0].duration_ms == 289, f"Expected duration 289ms, got {hits[0].duration_ms}"
    assert run.hits == 1, f"Expected run.hits=1, got {run.hits}"
    assert run.total_contact_ms == 289, f"Expected total_contact=289ms, got {run.total_contact_ms}"
    assert run.longest_hit_ms == 289, f"Expected longest=289ms, got {run.longest_hit_ms}"
    
    expected_score = 4850 + (1 * 2000)  # duration + (hits * penalty)
    assert run.score == expected_score, f"Expected score={expected_score}, got {run.score}"
    
    print(f"\n✓✓✓ TEST PASSED ✓✓✓")
    print("Backend correctly calculated stats from Hit records")
    print("Firmware's incorrect values were ignored")
    
    db.close()

def test_scenario_correct_firmware():
    """Test: Firmware sends correct stats"""
    print("\n" + "="*70)
    print("TEST: Correct Firmware Scenario")
    print("Firmware sends correct aggregate stats")
    print("Backend should still use Hit table as authoritative source")
    print("="*70)
    print()
    
    db = SessionLocal()
    
    events = [
        {
            "device_id": "aquabuzz-001",
            "run_uid": "test-correct-1",
            "run_no": 2,
            "player_id": "test_player",
            "event": "run_start",
            "t_ms": 0
        },
        {
            "device_id": "aquabuzz-001",
            "run_uid": "test-correct-1",
            "run_no": 2,
            "player_id": "test_player",
            "event": "hit_start",
            "hit": 1,
            "t_ms": 500
        },
        {
            "device_id": "aquabuzz-001",
            "run_uid": "test-correct-1",
            "run_no": 2,
            "player_id": "test_player",
            "event": "hit_end",
            "hit": 1,
            "t_ms": 650,
            "dur_ms": 150
        },
        {
            "device_id": "aquabuzz-001",
            "run_uid": "test-correct-1",
            "run_no": 2,
            "player_id": "test_player",
            "event": "hit_start",
            "hit": 2,
            "t_ms": 2000
        },
        {
            "device_id": "aquabuzz-001",
            "run_uid": "test-correct-1",
            "run_no": 2,
            "player_id": "test_player",
            "event": "hit_end",
            "hit": 2,
            "t_ms": 2200,
            "dur_ms": 200
        },
        {
            "device_id": "aquabuzz-001",
            "run_uid": "test-correct-1",
            "run_no": 2,
            "player_id": "test_player",
            "event": "run_finish",
            "t_ms": 5000,
            "hits": 2,  # Correct
            "total_contact_ms": 350,  # Correct
            "longest_hit_ms": 200,  # Correct
            "hit_penalty_ms": 2000,
            "score": 9000  # Correct: 5000 + (2 * 2000)
        }
    ]
    
    for event in events:
        print(f"Processing: {event['event']}")
        process_event(event, db)
        print()
    
    # Verify
    run = db.query(Run).filter(Run.run_uid == "test-correct-1").first()
    hits = db.query(Hit).filter(Hit.run_uid == "test-correct-1").all()
    
    print("="*70)
    print("VERIFICATION")
    print("="*70)
    print(f"\nIndividual Hits: {len(hits)}")
    print(f"Aggregate Hits: {run.hits}")
    print(f"Total Contact: {run.total_contact_ms}ms")
    print(f"Score: {run.score}ms")
    
    assert len(hits) == 2
    assert run.hits == 2
    assert run.total_contact_ms == 350
    assert run.score == 9000
    
    print(f"\n✓✓✓ TEST PASSED ✓✓✓")
    
    db.close()

def main():
    print("\n" + "="*70)
    print("HIT AGGREGATION LOGIC TEST SUITE")
    print("Testing database as source of truth for aggregate stats")
    print("="*70)
    print()
    
    try:
        setup_test_db()
        test_scenario_buggy_firmware()
        test_scenario_correct_firmware()
        
        print("\n" + "="*70)
        print("✓✓✓ ALL TESTS PASSED ✓✓✓")
        print("="*70)
        print("\nConclusion:")
        print("  ✓ Backend ignores firmware's aggregate stats")
        print("  ✓ Backend calculates from Hit table (source of truth)")
        print("  ✓ Dashboard will now show consistent data")
        
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
        engine.dispose()
        time.sleep(0.5)
        if os.path.exists("test_hit_aggregation.db"):
            try:
                os.remove("test_hit_aggregation.db")
            except:
                pass

if __name__ == "__main__":
    sys.exit(main())
