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
from datetime import datetime

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


@app.on_event("startup")
async def startup():
    """Initialize database and MQTT client on startup."""
    init_db()
    print("[API] Database initialized")
    
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
    """Process incoming MQTT events."""
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
        
        # Ensure player exists
        player = db.query(Player).filter(Player.id == player_id).first()
        if not player:
            player = Player(id=player_id, name=player_id)
            db.add(player)
            db.commit()
        
        if event_type == "run_start":
            # Create or update run
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
                db.commit()
        
        elif event_type == "hit_start":
            # Record hit start
            run = db.query(Run).filter(Run.run_uid == run_uid).first()
            if run:
                # Will be completed on hit_end
                pass
        
        elif event_type == "hit_end":
            # Complete hit record
            run = db.query(Run).filter(Run.run_uid == run_uid).first()
            if run:
                hit_no = event.get("hit", 0)
                # Check if hit already exists (idempotency)
                existing = db.query(Hit).filter(
                    Hit.run_uid == run_uid, 
                    Hit.hit_no == hit_no
                ).first()
                
                if not existing:
                    hit = Hit(
                        run_uid=run_uid,
                        hit_no=hit_no,
                        start_ms=event.get("t_ms", 0) - event.get("dur_ms", 0),
                        duration_ms=event.get("dur_ms", 0)
                    )
                    db.add(hit)
                    run.hits += 1
                    db.commit()
        
        elif event_type == "run_finish":
            # Complete run
            run = db.query(Run).filter(Run.run_uid == run_uid).first()
            if run:
                run.finished_at = datetime.utcnow()
                run.duration_ms = event.get("t_ms", 0)
                run.hits = event.get("hits", 0)
                run.total_contact_ms = event.get("total_contact_ms", 0)
                run.longest_hit_ms = event.get("longest_hit_ms", 0)
                run.hit_penalty_ms = event.get("hit_penalty_ms", 2000)
                run.score = event.get("score", 0)
                run.status = "finished"
                db.commit()
                
                # Trigger intelligence analysis
                analyze_run(run, db)
        
        elif event_type == "run_cancel":
            run = db.query(Run).filter(Run.run_uid == run_uid).first()
            if run:
                run.status = "cancelled"
                db.commit()
        
        # Broadcast to SSE clients
        broadcast_event(event)
        
    except Exception as e:
        print(f"[MQTT] Error handling event: {e}")
        db.rollback()
    finally:
        db.close()


def analyze_run(run: Run, db: Session):
    """Run intelligence analysis on completed run."""
    try:
        # Extract features
        hit_records = [{"duration_ms": h.duration_ms} for h in run.hit_records]
        run_data = {
            "duration_ms": run.duration_ms,
            "hits": run.hits,
            "score": run.score,
            "hit_records": hit_records,
            "total_contact_ms": run.total_contact_ms,
            "longest_hit_ms": run.longest_hit_ms
        }
        
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
    
    return {
        "status": "healthy",
        "mqtt_connected": mqtt_client.connected if mqtt_client else False,
        "total_runs": total_runs,
        "total_players": total_players
    }


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
    
    # Build feature dicts
    run_dicts = []
    for run in runs:
        run_dicts.append({
            "duration_ms": run.duration_ms,
            "hits": run.hits,
            "score": run.score,
            "finished_at": run.finished_at.isoformat(),
            "hit_records": [{"duration_ms": h.duration_ms} for h in run.hit_records]
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
