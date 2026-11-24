#!/usr/bin/env python3
"""Test stale run detection"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from datetime import datetime, timedelta
from app.db import engine
from app.models import Run
from sqlalchemy.orm import sessionmaker

def detect_and_mark_stale_runs(db, timeout_minutes=30):
    """Detect and mark abandoned runs."""
    cutoff = datetime.utcnow() - timedelta(minutes=timeout_minutes)
    stale_runs = db.query(Run).filter(
        Run.status == "started",
        Run.started_at < cutoff,
        Run.finished_at.is_(None)
    ).all()
    
    for run in stale_runs:
        run.status = "abandoned"
        print(f"[Test] Marked stale run as abandoned: {run.run_uid}")
    
    if stale_runs:
        db.commit()
    
    return len(stale_runs)

Session = sessionmaker(bind=engine)
db = Session()

print("Before stale detection:")
print(f'  Started runs: {db.query(Run).filter(Run.status == "started").count()}')
print(f'  Abandoned runs: {db.query(Run).filter(Run.status == "abandoned").count()}')

stale_count = detect_and_mark_stale_runs(db, timeout_minutes=30)
print(f"\nMarked {stale_count} stale run(s) as abandoned")

print("\nAfter stale detection:")
print(f'  Started runs: {db.query(Run).filter(Run.status == "started").count()}')
print(f'  Abandoned runs: {db.query(Run).filter(Run.status == "abandoned").count()}')

db.close()
