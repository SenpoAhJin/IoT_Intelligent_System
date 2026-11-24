"""Database investigation script for AquaBuzz system."""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

# Database path - use the one in project root (the actual working database)
DB_PATH = Path(__file__).parent.parent / "aquabuzz.db"

def connect_db():
    """Connect to the database."""
    if not DB_PATH.exists():
        print(f"❌ Database not found at: {DB_PATH}")
        sys.exit(1)
    return sqlite3.connect(DB_PATH)

def print_section(title):
    """Print a section header."""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print('='*80)

def investigate():
    """Run all investigation queries."""
    conn = connect_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Count runs by status
    print_section("1. RUNS BY STATUS")
    cursor.execute("SELECT status, COUNT(*) as count FROM runs GROUP BY status")
    for row in cursor.fetchall():
        print(f"  Status '{row['status']}': {row['count']} runs")
    
    # 2. Find stale runs (started but never finished)
    print_section("2. STALE RUNS (status='started', finished_at IS NULL)")
    cursor.execute("""
        SELECT run_uid, device_id, player_id, started_at, finished_at, status
        FROM runs 
        WHERE status='started' AND finished_at IS NULL
    """)
    stale_runs = cursor.fetchall()
    if stale_runs:
        for row in stale_runs:
            print(f"  run_uid: {row['run_uid']}")
            print(f"    device_id: {row['device_id']}")
            print(f"    player_id: {row['player_id']}")
            print(f"    started_at: {row['started_at']}")
            print(f"    finished_at: {row['finished_at']}")
            print(f"    status: {row['status']}")
            print()
    else:
        print("  ✓ No stale runs found")
    
    # 3. Full record for test-run-001
    print_section("3. FULL RECORD FOR run_uid='test-run-001'")
    cursor.execute("SELECT * FROM runs WHERE run_uid='test-run-001'")
    row = cursor.fetchone()
    if row:
        for key in row.keys():
            print(f"  {key}: {row[key]}")
    else:
        print("  Record not found")
    
    # 4. Recent finished runs with statistics
    print_section("4. RECENT FINISHED RUNS (with statistics)")
    cursor.execute("""
        SELECT run_uid, player_id, hits, total_contact_ms, longest_hit_ms, score, finished_at
        FROM runs 
        WHERE status='finished'
        ORDER BY finished_at DESC
        LIMIT 10
    """)
    finished_runs = cursor.fetchall()
    if finished_runs:
        for row in finished_runs:
            print(f"\n  run_uid: {row['run_uid']}")
            print(f"    player: {row['player_id']}")
            print(f"    hits: {row['hits']}")
            print(f"    total_contact_ms: {row['total_contact_ms']}")
            print(f"    longest_hit_ms: {row['longest_hit_ms']}")
            print(f"    score: {row['score']}")
            print(f"    finished_at: {row['finished_at']}")
    else:
        print("  No finished runs found")
    
    # 5. Hit table analysis
    print_section("5. HIT TABLE ANALYSIS")
    cursor.execute("SELECT COUNT(*) as count FROM hits WHERE duration_ms = 0")
    zero_duration = cursor.fetchone()['count']
    cursor.execute("SELECT COUNT(*) as count FROM hits WHERE duration_ms > 0")
    nonzero_duration = cursor.fetchone()['count']
    cursor.execute("SELECT COUNT(*) as total FROM hits")
    total_hits = cursor.fetchone()['total']
    
    print(f"  Total hits: {total_hits}")
    print(f"  Hits with duration_ms = 0: {zero_duration}")
    print(f"  Hits with duration_ms > 0: {nonzero_duration}")
    
    # 6. Hit records for recent runs
    print_section("6. HIT RECORDS FOR RECENT FINISHED RUNS")
    if finished_runs:
        for run_row in finished_runs[:3]:  # Only show first 3 runs
            run_uid = run_row['run_uid']
            print(f"\n  Run: {run_uid} (declared hits: {run_row['hits']})")
            
            cursor.execute("""
                SELECT hit_no, start_ms, duration_ms 
                FROM hits 
                WHERE run_uid = ?
                ORDER BY hit_no
            """, (run_uid,))
            
            hit_records = cursor.fetchall()
            actual_hit_count = len(hit_records)
            
            if hit_records:
                for hit in hit_records:
                    print(f"    Hit #{hit['hit_no']}: start={hit['start_ms']}ms, duration={hit['duration_ms']}ms")
            else:
                print("    ⚠ NO HIT RECORDS FOUND IN DATABASE")
            
            # Check for discrepancy
            if run_row['hits'] != actual_hit_count:
                print(f"    ❌ DISCREPANCY: Run.hits={run_row['hits']} but actual Hit records={actual_hit_count}")
            else:
                print(f"    ✓ Match: Run.hits={run_row['hits']} equals actual Hit records={actual_hit_count}")
    
    # 7. Summary of issues
    print_section("7. DISCREPANCY SUMMARY")
    cursor.execute("""
        SELECT 
            r.run_uid,
            r.hits as declared_hits,
            COUNT(h.id) as actual_hits
        FROM runs r
        LEFT JOIN hits h ON r.run_uid = h.run_uid
        WHERE r.status = 'finished'
        GROUP BY r.run_uid
        HAVING r.hits != COUNT(h.id)
    """)
    discrepancies = cursor.fetchall()
    
    if discrepancies:
        print(f"  Found {len(discrepancies)} runs with hit count discrepancies:")
        for row in discrepancies:
            print(f"    {row['run_uid']}: declared={row['declared_hits']}, actual={row['actual_hits']}")
    else:
        print("  ✓ No discrepancies found between Run.hits and Hit record counts")
    
    conn.close()

if __name__ == "__main__":
    print(f"\n🔍 AquaBuzz Database Investigation")
    print(f"Database: {DB_PATH}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    investigate()
    
    print("\n" + "="*80)
    print("Investigation complete.")
    print("="*80 + "\n")
