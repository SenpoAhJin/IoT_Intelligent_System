"""Check all database files in the project."""

import sqlite3
from pathlib import Path

project_root = Path(__file__).parent.parent

# Find all .db files
db_files = [
    project_root / "backend" / "aquabuzz.db",
    project_root / "aquabuzz.db",
    project_root / "scripts" / "aquabuzz.db",
]

for db_path in db_files:
    if db_path.exists():
        print(f"\n{'='*80}")
        print(f"Database: {db_path}")
        print(f"Size: {db_path.stat().st_size} bytes")
        print('='*80)
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get table list
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            print(f"Tables: {', '.join(t[0] for t in tables)}")
            
            # Count runs
            try:
                cursor.execute("SELECT COUNT(*) FROM runs")
                run_count = cursor.fetchone()[0]
                print(f"Total runs: {run_count}")
                
                if run_count > 0:
                    cursor.execute("SELECT status, COUNT(*) FROM runs GROUP BY status")
                    for row in cursor.fetchall():
                        print(f"  - {row[0]}: {row[1]}")
                    
                    # Check for test-run-001
                    cursor.execute("SELECT * FROM runs WHERE run_uid='test-run-001'")
                    test_run = cursor.fetchone()
                    if test_run:
                        print(f"\n⚠ Found test-run-001 in this database!")
            except sqlite3.OperationalError:
                print("No 'runs' table")
            
            # Count hits
            try:
                cursor.execute("SELECT COUNT(*) FROM hits")
                hit_count = cursor.fetchone()[0]
                print(f"Total hits: {hit_count}")
            except sqlite3.OperationalError:
                print("No 'hits' table")
            
            conn.close()
            
        except sqlite3.Error as e:
            print(f"Error reading database: {e}")
    else:
        print(f"\n❌ Not found: {db_path}")

print("\n" + "="*80)
