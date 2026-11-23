"""Anomaly detection for runs and devices."""

from typing import Dict, List
from datetime import datetime, timedelta


def detect_run_anomalies(run: Dict) -> List[Dict]:
    """
    Detect anomalies in a single run.
    
    Args:
        run: Run dict with timing and hit data
        
    Returns:
        List of anomaly dicts with 'type', 'severity', 'message'
    """
    anomalies = []
    
    duration_ms = run.get("duration_ms", 0)
    hits = run.get("hits", 0)
    longest_hit = run.get("longest_hit_ms", 0)
    total_contact = run.get("total_contact_ms", 0)
    
    # Too fast - likely wiring error (finish connected to maze)
    if duration_ms < 500:
        anomalies.append({
            "type": "too_fast",
            "severity": "high",
            "message": f"Run completed in {duration_ms}ms. Finish pad may be wired to maze wire.",
            "value": duration_ms
        })
    
    # Stuck contact - single touch longer than 10s
    if longest_hit > 10000:
        anomalies.append({
            "type": "stuck_contact",
            "severity": "high",
            "message": f"Single contact lasted {longest_hit}ms. Check for short circuit or stuck ring.",
            "value": longest_hit
        })
    
    # Impossible hit rate
    if duration_ms > 0:
        hits_per_second = (hits / duration_ms) * 1000
        if hits_per_second > 10:
            anomalies.append({
                "type": "impossible_hit_rate",
                "severity": "medium",
                "message": f"Hit rate of {hits_per_second:.1f} hits/sec is unusually high.",
                "value": hits_per_second
            })
    
    # Total contact time exceeds run duration (shouldn't happen)
    if total_contact > duration_ms:
        anomalies.append({
            "type": "contact_exceeds_duration",
            "severity": "high",
            "message": "Total contact time exceeds run duration. Data corruption possible.",
            "value": total_contact - duration_ms
        })
    
    # Excessive hits
    if hits > 50:
        anomalies.append({
            "type": "excessive_hits",
            "severity": "low",
            "message": f"{hits} hits in one run is unusually high.",
            "value": hits
        })
    
    return anomalies


def detect_device_anomalies(device: Dict, last_heartbeat: datetime) -> List[Dict]:
    """
    Detect device-level anomalies.
    
    Args:
        device: Device dict
        last_heartbeat: Last heartbeat timestamp
        
    Returns:
        List of anomaly dicts
    """
    anomalies = []
    
    now = datetime.utcnow()
    
    # Device hasn't sent heartbeat in 60 seconds
    if last_heartbeat:
        silence_duration = (now - last_heartbeat).total_seconds()
        if silence_duration > 60:
            anomalies.append({
                "type": "device_offline",
                "severity": "medium",
                "message": f"Device hasn't sent heartbeat in {silence_duration:.0f} seconds.",
                "value": silence_duration
            })
    
    return anomalies


def detect_player_anomalies(player_runs: List[Dict]) -> List[Dict]:
    """
    Detect player-level anomalies across multiple runs.
    
    Args:
        player_runs: List of runs for a player
        
    Returns:
        List of anomaly dicts
    """
    anomalies = []
    
    if len(player_runs) < 5:
        return anomalies
    
    scores = [r.get("score", 0) for r in player_runs]
    
    # Sudden dramatic improvement (possible different player)
    if len(scores) >= 3:
        recent_avg = sum(scores[-3:]) / 3
        previous_avg = sum(scores[:-3]) / len(scores[:-3]) if len(scores) > 3 else recent_avg
        
        if previous_avg > 0:
            improvement_ratio = previous_avg / recent_avg
            if improvement_ratio > 3:
                anomalies.append({
                    "type": "sudden_improvement",
                    "severity": "low",
                    "message": f"Score improved by {improvement_ratio:.1f}x suddenly. Different player?",
                    "value": improvement_ratio
                })
    
    return anomalies


def get_anomaly_summary(anomalies: List[Dict]) -> str:
    """
    Generate summary message for anomalies.
    
    Args:
        anomalies: List of anomaly dicts
        
    Returns:
        Summary string
    """
    if not anomalies:
        return "No anomalies detected"
    
    high = [a for a in anomalies if a["severity"] == "high"]
    medium = [a for a in anomalies if a["severity"] == "medium"]
    low = [a for a in anomalies if a["severity"] == "low"]
    
    parts = []
    if high:
        parts.append(f"{len(high)} high severity")
    if medium:
        parts.append(f"{len(medium)} medium severity")
    if low:
        parts.append(f"{len(low)} low severity")
    
    return f"Found {len(anomalies)} anomalies: {', '.join(parts)}"
