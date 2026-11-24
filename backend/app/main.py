"""FastAPI main application."""

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import asyncio
import json
import time
import queue
from datetime import datetime, timedelta

from app.db import get_db, init_db, engine
from app.models import Player, Device, Run, Hit, Suggestion
from app.schemas import (
    RunSchema, RunDetail, PlayerStats, DeviceSchema, 
    LeaderboardEntry, DifficultyConfig, InsightResponse, SuggestionSchema
)
from app.mqtt_client import MQTTEventIngester
from intelligence import features, behavior, classifier, trends, anomalies, suggestions, difficulty

# Initialize FastAPI app
app = FastAPI(title="AquaBuzz Intelligence API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global MQTT client
mqtt_client = None

# SSE clients for live updates
sse_clients = []


def detect_and_mark_stale_runs(db: Session, timeout_minutes: int = 30):
    """Detect and mark abandoned runs."""
    cutoff = datetime.utcnow() - timedelta(minutes=timeout_minutes)
    stale_runs = db.query(Run).filter(
        Run.status == "started",
        Run.started_at < cutoff,
        Run.finished_at.is_(None)
    ).all()
    
    for run in stale_runs:
        run.status = "abandoned"
        print(f"[Startup] Marked stale run as abandoned: {run.run_uid}")
    
    if stale_runs:
        db.commit()
    
    return len(stale_runs)


@app.on_event("startup")
async def startup():
    """Initialize database and MQTT client on startup."""
    init_db()
    print("[API] Database initialized")
    
    # Detect and mark stale runs
    db_session = next(get_db())
    try:
        stale_count = detect_and_mark_stale_runs(db_session, timeout_minutes=30)
        if stale_count > 0:
            print(f"[Startup] Marked {stale_count} stale run(s) as abandoned")
    finally:
        db_session.close()
    
    # Start MQTT client
    global mqtt_client
    mqtt_client = MQTTEventIngester(
        broker_host=os.getenv("MQTT_BROKER_HOST", "localhost"),
        broker_port=int(os.getenv("MQTT_BROKER_PORT", 1883)),
        username=os.getenv("MQTT_USERNAME"),
        password=os.getenv("MQTT_PASSWORD")
    )
    mqtt_client.set_event_handler(handle_mqtt_event)
    mqtt_client.start()
    print("[API] MQTT client started")


def handle_mqtt_event(event: dict):
    """Process incoming MQTT events with proper state tracking and deduplication."""
    # FEAT-003: Measure backend event processing timing
    backend_rx_ts = time.time()
    
    event_type = event.get("event")
    device_id = event.get("device_id")
    
    db = next(get_db())
    
    try:
        # Ensure device exists
        device = db.query(Device).filter(Device.id == device_id).first()
        if not device:
            device = Device(id=device_id)
            db.add(device)
            db.commit()
        
        # Handle heartbeat
        if "heartbeat" in event.get("_topic", ""):
            device.last_heartbeat = datetime.utcnow()
            db.commit()
            return
        
        # Handle game events
        run_uid = event.get("run_uid")
        player_id = event.get("player_id", "guest")
        
        if not run_uid:
            print(f"[MQTT] Event missing run_uid: {event_type}")
            return
        
        # Ensure player exists
        player = db.query(Player).filter(Player.id == player_id).first()
        if not player:
            player = Player(id=player_id, name=player_id)
            db.add(player)
            db.commit()
        
        if event_type == "run_start":
            # Create run (idempotent - only create if doesn't exist)
            run = db.query(Run).filter(Run.run_uid == run_uid).first()
            if not run:
                run = Run(
                    run_uid=run_uid,
                    device_id=device_id,
                    player_id=player_id,
                    run_no=event.get("run_no", 0),
                    started_at=datetime.utcnow(),
                    status="started"
                )
                db.add(run)
                
                # FEAT-003: Measure database write timing
                db_start = time.time()
                db.commit()
                db_end = time.time()
                
                print(f"[MQTT] Created run: {run_uid}")
                
                # FEAT-003: Latency logging
                if os.getenv("LOG_LEVEL") == "DEBUG":
                    db_write_ms = (db_end - db_start) * 1000
                    processing_ms = (db_end - backend_rx_ts) * 1000
                    print(f"[Latency] {event_type} run-{run_uid}: db_write={db_write_ms:.1f}ms, total={processing_ms:.1f}ms")
            else:
                print(f"[MQTT] Run already exists: {run_uid} (duplicate event ignored)")
        
        elif event_type == "hit_start":
            # Track hit start - store in Hit table immediately with duration=0
            run = db.query(Run).filter(Run.run_uid == run_uid).first()
            if not run:
                print(f"[MQTT] WARNING: hit_start for unknown run {run_uid}")
                return
            
            hit_no = event.get("hit", 0)
            start_ms = event.get("t_ms", 0)
            
            # Check if hit already exists (idempotency)
            existing = db.query(Hit).filter(
                Hit.run_uid == run_uid, 
                Hit.hit_no == hit_no
            ).first()
            
            if not existing:
                hit = Hit(
                    run_uid=run_uid,
                    hit_no=hit_no,
                    start_ms=start_ms,
                    duration_ms=0  # Will be updated on hit_end
                )
                db.add(hit)
                
                # FEAT-003: Measure database write timing
                db_start = time.time()
                db.commit()
                db_end = time.time()
                
                print(f"[MQTT] Hit {hit_no} started for run {run_uid}")
                
                # FEAT-003: Latency logging
                if os.getenv("LOG_LEVEL") == "DEBUG":
                    db_write_ms = (db_end - db_start) * 1000
                    processing_ms = (db_end - backend_rx_ts) * 1000
                    print(f"[Latency] {event_type} run-{run_uid} hit-{hit_no}: db_write={db_write_ms:.1f}ms, total={processing_ms:.1f}ms")
            else:
                print(f"[MQTT] Hit {hit_no} already exists (duplicate ignored)")
        
        elif event_type == "hit_end":
            # Complete hit record
            run = db.query(Run).filter(Run.run_uid == run_uid).first()
            if not run:
                print(f"[MQTT] WARNING: hit_end for unknown run {run_uid}")
                return
            
            hit_no = event.get("hit", 0)
            dur_ms = event.get("dur_ms", 0)
            
            # Find existing hit record
            hit = db.query(Hit).filter(
                Hit.run_uid == run_uid, 
                Hit.hit_no == hit_no
            ).first()
            
            if hit:
                # Update duration
                if hit.duration_ms == 0:  # Only update if not already set
                    hit.duration_ms = dur_ms
                    
                    # FEAT-003: Measure database write timing
                    db_start = time.time()
                    db.commit()
                    db_end = time.time()
                    
                    print(f"[MQTT] Hit {hit_no} completed: {dur_ms}ms")
                    
                    # FEAT-003: Latency logging
                    if os.getenv("LOG_LEVEL") == "DEBUG":
                        db_write_ms = (db_end - db_start) * 1000
                        processing_ms = (db_end - backend_rx_ts) * 1000
                        print(f"[Latency] {event_type} run-{run_uid} hit-{hit_no}: db_write={db_write_ms:.1f}ms, total={processing_ms:.1f}ms")
                else:
                    print(f"[MQTT] Hit {hit_no} already completed (duplicate ignored)")
            else:
                # Hit start was missed - create complete record
                print(f"[MQTT] WARNING: hit_end without hit_start, creating complete record")
                start_ms = event.get("t_ms", 0) - dur_ms
                hit = Hit(
                    run_uid=run_uid,
                    hit_no=hit_no,
                    start_ms=start_ms,
                    duration_ms=dur_ms
                )
                db.add(hit)
                db.commit()
        
        elif event_type == "run_finish":
            # Complete run with final statistics
            run = db.query(Run).filter(Run.run_uid == run_uid).first()
            if not run:
                print(f"[MQTT] WARNING: run_finish for unknown run {run_uid}")
                return
            
            # Idempotent - only update if not already finished
            if run.status != "finished":
                run.finished_at = datetime.utcnow()
                run.duration_ms = event.get("t_ms", 0)
                run.hit_penalty_ms = event.get("hit_penalty_ms", 2000)
                
                # CRITICAL FIX: Calculate aggregate stats from actual Hit records
                # Do NOT trust firmware's aggregate calculation - use database as source of truth
                print(f"[MQTT] Processing run_finish for {run_uid}")
                print(f"[MQTT] Querying Hit records for run_uid: {run_uid}")
                
                hit_records = db.query(Hit).filter(Hit.run_uid == run_uid).all()
                print(f"[MQTT] Found {len(hit_records)} Hit record(s) in database")
                
                # Count only completed hits (duration_ms > 0)
                completed_hits = [h for h in hit_records if h.duration_ms > 0]
                incomplete_hits = [h for h in hit_records if h.duration_ms == 0]
                
                print(f"[MQTT] Completed hits (duration > 0): {len(completed_hits)}")
                print(f"[MQTT] Incomplete hits (duration = 0): {len(incomplete_hits)}")
                
                run.hits = len(completed_hits)
                run.total_contact_ms = sum(h.duration_ms for h in completed_hits)
                run.longest_hit_ms = max((h.duration_ms for h in completed_hits), default=0)
                
                # Recalculate score using actual hit count
                free_hits = 0  # Can be made configurable
                scored_hits = max(0, run.hits - free_hits)
                run.score = run.duration_ms + (scored_hits * run.hit_penalty_ms)
                
                run.status = "finished"
                db.commit()
                
                print(f"[MQTT] Run finished: {run_uid}")
                print(f"  Duration: {run.duration_ms}ms")
                print(f"  Hits (from DB): {run.hits} (firmware sent: {event.get('hits', 'N/A')})")
                print(f"  Total Contact (from DB): {run.total_contact_ms}ms (firmware sent: {event.get('total_contact_ms', 'N/A')}ms)")
                print(f"  Longest Hit (from DB): {run.longest_hit_ms}ms (firmware sent: {event.get('longest_hit_ms', 'N/A')}ms)")
                print(f"  Score (recalculated): {run.score}ms (firmware sent: {event.get('score', 'N/A')}ms)")
                
                # Trigger intelligence analysis
                analyze_run(run, db)
            else:
                print(f"[MQTT] Run already finished: {run_uid} (duplicate ignored)")
        
        elif event_type == "run_cancel":
            run = db.query(Run).filter(Run.run_uid == run_uid).first()
            if run and run.status != "cancelled":
                run.status = "cancelled"
                run.duration_ms = event.get("t_ms", 0)
                db.commit()
                print(f"[MQTT] Run cancelled: {run_uid}")
            else:
                print(f"[MQTT] Run already cancelled or not found: {run_uid}")
        
        # Broadcast to SSE clients
        broadcast_event(event)
        
    except Exception as e:
        print(f"[MQTT] Error handling event {event_type}: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


def analyze_run(run: Run, db: Session):
    """Run intelligence analysis on completed run."""
    try:
        # Extract features - prepare hit_records as plain dicts
        hit_records = []
        for h in run.hit_records:
            hit_records.append({
                "start_ms": h.start_ms,
                "duration_ms": h.duration_ms
            })
        
        run_data = {
            "duration_ms": run.duration_ms or 0,
            "hits": run.hits or 0,
            "score": run.score or 0,
            "hit_records": hit_records,
            "total_contact_ms": run.total_contact_ms or 0,
            "longest_hit_ms": run.longest_hit_ms or 0,
            "status": run.status
        }
        
        # Only analyze if run was completed successfully
        if run.status != "finished":
            print(f"[Intelligence] Skipping analysis for {run.status} run {run.run_uid}")
            return
        
        feat = features.extract_features(run_data)
        
        # Behavior analysis
        tags = behavior.analyze_behavior(feat)
        
        # Skill classification
        skill = classifier.classify_skill(feat)
        
        # Store suggestions
        for tag in tags:
            advice = behavior.get_behavior_advice([tag])
            if advice:
                sugg = Suggestion(
                    player_id=run.player_id,
                    suggestion_type="behavior",
                    message=advice[0],
                    reason=f"Tag: {tag}",
                    priority="normal"
                )
                db.add(sugg)
        
        db.commit()
        print(f"[Intelligence] Analyzed run {run.run_uid}: {skill}, tags: {tags}")
        
    except Exception as e:
        print(f"[Intelligence] Analysis error: {e}")
        import traceback
        traceback.print_exc()


def broadcast_event(event: dict):
    """Broadcast event to all SSE clients."""
    for queue in sse_clients:
        try:
            queue.put_nowait(event)
        except:
            pass


@app.get("/")
async def root():
    return {"message": "AquaBuzz Intelligence API", "version": "1.0.0"}


@app.get("/api/health")
async def health(db: Session = Depends(get_db)):
    """Health check endpoint."""
    total_runs = db.query(Run).count()
    total_players = db.query(Player).count()
    
    # Active runs: status='started' AND finished_at is NULL (not stale)
    active_runs = db.query(Run).filter(
        Run.status == "started",
        Run.finished_at.is_(None)
    ).count()
    
    completed_runs = db.query(Run).filter(Run.status == "finished").count()
    abandoned_runs = db.query(Run).filter(Run.status == "abandoned").count()
    
    # Get device status
    devices = db.query(Device).all()
    device_status = []
    for device in devices:
        # Consider device online if heartbeat within last 30 seconds
        is_online = False
        if device.last_heartbeat:
            time_since = (datetime.utcnow() - device.last_heartbeat).total_seconds()
            is_online = time_since < 30
        
        device_status.append({
            "id": device.id,
            "online": is_online,
            "last_heartbeat": device.last_heartbeat.isoformat() if device.last_heartbeat else None
        })
    
    return {
        "status": "healthy",
        "mqtt_connected": mqtt_client.connected if mqtt_client else False,
        "total_runs": total_runs,
        "total_players": total_players,
        "active_runs": active_runs,
        "completed_runs": completed_runs,
        "abandoned_runs": abandoned_runs,
        "devices": device_status
    }


@app.get("/api/live")
async def live_events():
    """
    FEAT-009: Server-Sent Events endpoint for real-time dashboard updates.
    Stream live game events to dashboard without polling.
    """
    client_queue = queue.Queue(maxsize=100)
    sse_clients.append(client_queue)
    
    async def event_generator():
        try:
            while True:
                # Wait for event with timeout (30s keep-alive)
                try:
                    event = await asyncio.wait_for(
                        asyncio.to_thread(client_queue.get, timeout=30),
                        timeout=31.0
                    )
                    # Send event to client
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Send keep-alive comment
                    yield f": keep-alive\n\n"
        except asyncio.CancelledError:
            # Client disconnected
            print("[SSE] Client disconnected")
        finally:
            # Clean up
            if client_queue in sse_clients:
                sse_clients.remove(client_queue)
            print(f"[SSE] Client removed, {len(sse_clients)} clients remaining")
    
    print(f"[SSE] New client connected, {len(sse_clients)} total clients")
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/api/runs", response_model=List[RunSchema])
async def get_runs(
    limit: int = Query(50, ge=1, le=1000),
    player_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get recent runs."""
    query = db.query(Run)
    
    if player_id:
        query = query.filter(Run.player_id == player_id)
    
    runs = query.order_by(Run.started_at.desc()).limit(limit).all()
    return runs


@app.get("/api/runs/{run_id}", response_model=RunDetail)
async def get_run(run_id: int, db: Session = Depends(get_db)):
    """Get single run with hit details."""
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@app.get("/api/players", response_model=List[PlayerStats])
async def get_players(db: Session = Depends(get_db)):
    """Get all players with stats."""
    players = db.query(Player).all()
    result = []
    
    for player in players:
        runs = db.query(Run).filter(Run.player_id == player.id, Run.status == "finished").all()
        
        if runs:
            scores = [r.score for r in runs]
            best_score = min(scores)
            avg_score = sum(scores) / len(scores)
            total_hits = sum(r.hits for r in runs)
            
            # Get skill level from recent run
            feat = features.extract_features({
                "duration_ms": runs[-1].duration_ms,
                "hits": runs[-1].hits,
                "score": runs[-1].score,
                "hit_records": []
            })
            skill_level = classifier.classify_skill(feat)
        else:
            best_score = None
            avg_score = None
            total_hits = 0
            skill_level = None
        
        result.append(PlayerStats(
            id=player.id,
            name=player.name,
            total_runs=len(runs),
            best_score=best_score,
            avg_score=avg_score,
            total_hits=total_hits,
            skill_level=skill_level,
            created_at=player.created_at,
            last_seen=player.last_seen
        ))
    
    return result


@app.get("/api/leaderboard", response_model=List[LeaderboardEntry])
async def get_leaderboard(limit: int = Query(10, ge=1, le=100), db: Session = Depends(get_db)):
    """Get top scores."""
    runs = db.query(Run).filter(Run.status == "finished").order_by(Run.score.asc()).limit(limit).all()
    
    result = []
    for rank, run in enumerate(runs, 1):
        result.append(LeaderboardEntry(
            rank=rank,
            player_id=run.player_id,
            player_name=run.player.name,
            score=run.score,
            hits=run.hits,
            duration_ms=run.duration_ms,
            finished_at=run.finished_at
        ))
    
    return result


@app.get("/api/insights/{player_id}", response_model=InsightResponse)
async def get_insights(player_id: str, db: Session = Depends(get_db)):
    """Get intelligence insights for a player."""
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    
    # Get recent runs
    runs = db.query(Run).filter(
        Run.player_id == player_id,
        Run.status == "finished"
    ).order_by(Run.finished_at.desc()).limit(10).all()
    
    if not runs:
        raise HTTPException(status_code=404, detail="No completed runs")
    
    # Build feature dicts with proper hit_records
    run_dicts = []
    for run in runs:
        hit_records = []
        for h in run.hit_records:
            hit_records.append({
                "start_ms": h.start_ms,
                "duration_ms": h.duration_ms
            })
        
        run_dicts.append({
            "duration_ms": run.duration_ms or 0,
            "hits": run.hits or 0,
            "score": run.score or 0,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "hit_records": hit_records,
            "total_contact_ms": run.total_contact_ms or 0,
            "longest_hit_ms": run.longest_hit_ms or 0,
            "status": run.status
        })
    
    # Latest run analysis
    latest = run_dicts[0]
    feat = features.extract_features(latest)
    tags = behavior.analyze_behavior(feat)
    skill = classifier.classify_skill(feat)
    trend = trends.detect_trend(run_dicts)
    anoms = anomalies.detect_run_anomalies(latest)
    
    # Get stored suggestions
    suggestions_db = db.query(Suggestion).filter(
        Suggestion.player_id == player_id
    ).order_by(Suggestion.created_at.desc()).limit(5).all()
    
    # Difficulty recommendation
    diff_rec = difficulty.recommend_difficulty(run_dicts)
    
    return InsightResponse(
        player_id=player_id,
        skill_level=skill,
        behavior_tags=tags,
        trend=trend.get("type") if trend else None,
        anomalies=[a["message"] for a in anoms],
        suggestions=suggestions_db,
        recommended_difficulty=DifficultyConfig(**diff_rec) if diff_rec else None
    )


@app.post("/api/devices/{device_id}/config")
async def push_device_config(device_id: str, config: DifficultyConfig):
    """Push difficulty configuration to device via MQTT."""
    if not mqtt_client:
        raise HTTPException(status_code=503, detail="MQTT client not available")
    
    # Validate config
    validated = difficulty.validate_difficulty_config(config.dict())
    
    # Publish to device
    topic = f"aquabuzz/{device_id}/config"
    success = mqtt_client.publish(topic, validated)
    
    if success:
        return {"status": "sent", "config": validated}
    else:
        raise HTTPException(status_code=500, detail="Failed to publish config")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
