#!/usr/bin/env python3
"""
AquaBuzz Run Simulator

Generates realistic game runs and publishes them to MQTT for testing.
"""

import json
import time
import random
import argparse
from datetime import datetime
import paho.mqtt.client as mqtt


class PlayerProfile:
    """Player skill profile for realistic simulation."""
    
    def __init__(self, name, skill_level):
        self.name = name
        self.skill_level = skill_level
        
        # Skill-based parameters
        if skill_level == "expert":
            self.base_time = (4000, 7000)
            self.hit_prob = 0.1
            self.hit_duration = (50, 150)
            self.max_hits = 2
        elif skill_level == "intermediate":
            self.base_time = (8000, 15000)
            self.hit_prob = 0.3
            self.hit_duration = (100, 400)
            self.max_hits = 5
        else:  # beginner
            self.base_time = (12000, 25000)
            self.hit_prob = 0.5
            self.hit_duration = (200, 800)
            self.max_hits = 12
    
    def generate_run(self, run_no, device_id="aquabuzz-sim", boot_count=1):
        """Generate a realistic run."""
        duration_ms = random.randint(*self.base_time)
        
        # Determine hits
        num_hits = 0
        if random.random() < self.hit_prob:
            num_hits = random.randint(1, self.max_hits)
        
        # Generate hit timings
        hits = []
        if num_hits > 0:
            # Distribute hits across the run
            for i in range(num_hits):
                hit_start = random.randint(500, duration_ms - 500)
                hit_dur = random.randint(*self.hit_duration)
                hits.append({
                    "hit_no": i + 1,
                    "start_ms": hit_start,
                    "duration_ms": hit_dur
                })
            
            # Sort by start time
            hits.sort(key=lambda h: h["start_ms"])
            # Renumber
            for i, hit in enumerate(hits, 1):
                hit["hit_no"] = i
        
        # Calculate stats
        total_contact_ms = sum(h["duration_ms"] for h in hits)
        longest_hit_ms = max((h["duration_ms"] for h in hits), default=0)
        hit_penalty_ms = 2000
        score = duration_ms + (num_hits * hit_penalty_ms)
        
        run_uid = f"{device_id}-{boot_count}-{run_no}"
        
        return {
            "run_uid": run_uid,
            "run_no": run_no,
            "device_id": device_id,
            "player_id": self.name,
            "duration_ms": duration_ms,
            "hits": num_hits,
            "hit_records": hits,
            "total_contact_ms": total_contact_ms,
            "longest_hit_ms": longest_hit_ms,
            "hit_penalty_ms": hit_penalty_ms,
            "score": score
        }


def publish_run(client, run, delay=0.1):
    """Publish a simulated run as a sequence of events."""
    device_id = run["device_id"]
    run_uid = run["run_uid"]
    run_no = run["run_no"]
    player_id = run["player_id"]
    
    topic = f"aquabuzz/{device_id}/events"
    
    # run_start
    event = {
        "device_id": device_id,
        "run_uid": run_uid,
        "run_no": run_no,
        "player_id": player_id,
        "event": "run_start",
        "t_ms": 0,
        "ts": datetime.utcnow().isoformat() + "Z"
    }
    client.publish(topic, json.dumps(event))
    time.sleep(delay)
    
    # hits
    for hit in run["hit_records"]:
        # hit_start
        event = {
            "device_id": device_id,
            "run_uid": run_uid,
            "run_no": run_no,
            "player_id": player_id,
            "event": "hit_start",
            "hit": hit["hit_no"],
            "t_ms": hit["start_ms"],
            "ts": datetime.utcnow().isoformat() + "Z"
        }
        client.publish(topic, json.dumps(event))
        time.sleep(delay)
        
        # hit_end
        event = {
            "device_id": device_id,
            "run_uid": run_uid,
            "run_no": run_no,
            "player_id": player_id,
            "event": "hit_end",
            "hit": hit["hit_no"],
            "t_ms": hit["start_ms"] + hit["duration_ms"],
            "dur_ms": hit["duration_ms"],
            "ts": datetime.utcnow().isoformat() + "Z"
        }
        client.publish(topic, json.dumps(event))
        time.sleep(delay)
    
    # run_finish
    event = {
        "device_id": device_id,
        "run_uid": run_uid,
        "run_no": run_no,
        "player_id": player_id,
        "event": "run_finish",
        "t_ms": run["duration_ms"],
        "hits": run["hits"],
        "total_contact_ms": run["total_contact_ms"],
        "longest_hit_ms": run["longest_hit_ms"],
        "hit_penalty_ms": run["hit_penalty_ms"],
        "score": run["score"],
        "ts": datetime.utcnow().isoformat() + "Z"
    }
    client.publish(topic, json.dumps(event))
    time.sleep(delay)
    
    print(f"[SIM] Published run {run_no} for {player_id}: {run['hits']} hits, score {run['score']}")


def main():
    parser = argparse.ArgumentParser(description="AquaBuzz run simulator")
    parser.add_argument("--broker", default="localhost", help="MQTT broker host")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument("--runs", type=int, default=10, help="Number of runs to simulate")
    parser.add_argument("--players", type=int, default=1, help="Number of players")
    parser.add_argument("--delay", type=float, default=0.1, help="Delay between events (seconds)")
    parser.add_argument("--fast", action="store_true", help="Minimal delay for bulk generation")
    
    args = parser.parse_args()
    
    # Create player profiles
    profiles = [
        PlayerProfile("alice", "expert"),
        PlayerProfile("bob", "intermediate"),
        PlayerProfile("charlie", "beginner"),
    ][:args.players]
    
    # Connect to MQTT
    client = mqtt.Client(client_id="aquabuzz-simulator")
    print(f"[SIM] Connecting to {args.broker}:{args.port}")
    client.connect(args.broker, args.port, keepalive=60)
    client.loop_start()
    time.sleep(1)
    
    delay = 0.01 if args.fast else args.delay
    
    # Generate runs
    run_no = 1
    for i in range(args.runs):
        # Rotate through players
        profile = profiles[i % len(profiles)]
        
        # Generate and publish run
        run = profile.generate_run(run_no, device_id="aquabuzz-sim")
        publish_run(client, run, delay=delay)
        
        run_no += 1
        
        if not args.fast:
            time.sleep(0.5)  # Pause between runs
    
    # Send final heartbeat
    heartbeat_topic = f"aquabuzz/aquabuzz-sim/heartbeat"
    client.publish(heartbeat_topic, json.dumps({
        "device_id": "aquabuzz-sim",
        "ts": datetime.utcnow().isoformat() + "Z"
    }))
    
    time.sleep(1)
    client.loop_stop()
    client.disconnect()
    
    print(f"[SIM] Completed: {args.runs} runs from {len(profiles)} players")


if __name__ == "__main__":
    main()
