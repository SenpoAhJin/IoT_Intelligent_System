#!/usr/bin/env python3
"""Check database state"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.db import engine
from app.models import Run
from sqlalchemy.orm import sessionmaker

Session = sessionmaker(bind=engine)
db = Session()

runs = db.query(Run).all()
print(f'Total runs: {len(runs)}')
print(f'Started runs: {len([r for r in runs if r.status == "started"])}')
print(f'Finished runs: {len([r for r in runs if r.status == "finished"])}')
print(f'Abandoned runs: {len([r for r in runs if r.status == "abandoned"])}')

started_runs = [r for r in runs if r.status == 'started']
if started_runs:
    print('\nStarted runs:')
    for r in started_runs:
        print(f'  {r.run_uid} at {r.started_at}')

db.close()
