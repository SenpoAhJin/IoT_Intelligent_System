"""Database verification script."""
import sys
sys.path.insert(0, '.')

from app.db import get_db
from app.models import Run, Hit
from datetime import datetime, timedelta, timezone

def verify_database():
    db = next(get_db())
    
    print("\n" + "="*60)
    print("DATABASE VERIFICATION REPORT")
    print("="*60)
    
    # 1. Run Status Distribution
    print("\n1. RUN STATUS DISTRIBUTION")
    total_runs = db.query(Run).count()
    started = db.query(Run).filter(Run.status == "started").count()
    finished = db.query(Run).filter(Run.status == "finished").count()
    abandoned = db.query(Run).filter(Run.status == "abandoned").count()
    cancelled = db.query(Run).filter(Run.status == "cancelled").count()
    
    print(f"  Total runs: {total_runs}")
    print(f"  Started: {started}")
    print(f"  Finished: {finished}")
    print(f"  Abandoned: {abandoned}")
    print(f"  Cancelled: {cancelled}")
    
    # 2. Active Runs (should match /api/health)
    print("\n2. ACTIVE RUNS (as /api/health counts)")
    active = db.query(Run).filter(
        Run.status == "started",
        Run.finished_at.is_(None)
    ).count()
    print(f"  Active runs: {active}")
    
    # 3. Stale Runs Check
    print("\n3. STALE RUNS CHECK")
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
    stale = db.query(Run).filter(
        Run.status == "started",
        Run.started_at < cutoff,
        Run.finished_at.is_(None)
    ).all()
    print(f"  Stale runs found: {len(stale)}")
    if stale:
        for run in stale:
            print(f"    - {run.run_uid}: started {run.started_at}")
    
    # 4. Hit Aggregation Verification
    print("\n4. HIT AGGREGATION VERIFICATION")
    finished_runs = db.query(Run).filter(Run.status == "finished").order_by(Run.finished_at.desc()).limit(5).all()
    
    for run in finished_runs:
        hit_records = db.query(Hit).filter(Hit.run_uid == run.run_uid).all()
        completed_hits = [h for h in hit_records if h.duration_ms > 0]
        
        db_hits = len(completed_hits)
        db_total_contact = sum(h.duration_ms for h in completed_hits)
        db_longest = max((h.duration_ms for h in completed_hits), default=0)
        
        match = (db_hits == run.hits and 
                db_total_contact == run.total_contact_ms and 
                db_longest == run.longest_hit_ms)
        
        status = "✓ MATCH" if match else "✗ MISMATCH"
        
        print(f"\n  Run: {run.run_uid}")
        print(f"    Status: {status}")
        print(f"    DB Hit count: {db_hits} | Run.hits: {run.hits}")
        print(f"    DB Total contact: {db_total_contact}ms | Run.total_contact_ms: {run.total_contact_ms}ms")
        print(f"    DB Longest hit: {db_longest}ms | Run.longest_hit_ms: {run.longest_hit_ms}ms")
    
    # 5. Incomplete Hits
    print("\n5. INCOMPLETE HITS (duration_ms = 0)")
    incomplete = db.query(Hit).filter(Hit.duration_ms == 0).count()
    total_hits = db.query(Hit).count()
    print(f"  Incomplete hits: {incomplete} / {total_hits}")
    
    print("\n" + "="*60)
    print("VERIFICATION COMPLETE")
    print("="*60 + "\n")
    
    db.close()

if __name__ == "__main__":
    verify_database()
