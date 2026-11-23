"""Optional LLM-based coaching using Anthropic API."""

import os
from typing import Dict, Optional


def generate_llm_feedback(player_stats: Dict, recent_runs: List[Dict]) -> Optional[str]:
    """
    Generate personalized coaching feedback using Claude.
    
    Args:
        player_stats: Player statistics and skill level
        recent_runs: Recent run data
        
    Returns:
        Coaching message or None if disabled/failed
    """
    if not os.getenv("ENABLE_LLM_COACH", "false").lower() == "true":
        return None
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    
    try:
        from anthropic import Anthropic
        
        client = Anthropic(api_key=api_key)
        
        # Prepare context
        skill = player_stats.get("skill_level", "unknown")
        avg_score = player_stats.get("avg_score", 0)
        best_score = player_stats.get("best_score", 0)
        total_runs = len(recent_runs)
        
        last_run = recent_runs[-1] if recent_runs else {}
        last_hits = last_run.get("hits", 0)
        last_score = last_run.get("score", 0)
        
        prompt = f"""You are a friendly coach for a buzz-wire maze game. Give brief, encouraging feedback (2-3 sentences max) to this player:

Skill Level: {skill}
Recent Performance:
- Last run: {last_hits} hits, score {last_score}ms
- Average score: {avg_score:.0f}ms
- Best score: {best_score}ms
- Total runs: {total_runs}

Be specific, actionable, and motivating. Focus on what they can improve."""

        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text
        
    except Exception as e:
        print(f"LLM coaching failed: {e}")
        return None
