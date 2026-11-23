"""Skill level classification."""

from typing import Dict, List, Optional
import numpy as np
import os


def classify_skill_rules(features: Dict[str, float]) -> str:
    """
    Rule-based skill classification fallback.
    
    Args:
        features: Extracted features from a run
        
    Returns:
        Skill level: beginner, intermediate, expert
    """
    score = features.get("score", 999999)
    hits = features.get("hits", 999)
    duration_ms = features.get("duration_ms", 999999)
    
    # Expert: fast and clean
    if score < 8000 and hits <= 2:
        return "expert"
    
    # Intermediate: moderate performance
    if score < 15000 and hits <= 5:
        return "intermediate"
    
    # Beginner: still learning
    return "beginner"


def classify_skill_ml(features: Dict[str, float], model_path: str = "models/skill_classifier.joblib") -> Optional[str]:
    """
    ML-based skill classification using trained model.
    
    Args:
        features: Extracted features from a run
        model_path: Path to saved model
        
    Returns:
        Skill level or None if model not available
    """
    if not os.path.exists(model_path):
        return None
    
    try:
        import joblib
        model = joblib.load(model_path)
        
        # Feature vector (must match training order)
        X = np.array([[
            features.get("score", 0),
            features.get("hits", 0),
            features.get("duration_ms", 0),
            features.get("avg_hit_duration_ms", 0),
            features.get("hits_per_second", 0),
        ]])
        
        prediction = model.predict(X)[0]
        return prediction
    except Exception as e:
        print(f"ML classification failed: {e}")
        return None


def classify_skill(features: Dict[str, float]) -> str:
    """
    Classify skill level, trying ML first then falling back to rules.
    
    Args:
        features: Extracted features from a run
        
    Returns:
        Skill level: beginner, intermediate, expert
    """
    ml_result = classify_skill_ml(features)
    if ml_result:
        return ml_result
    
    return classify_skill_rules(features)


def train_classifier(runs_with_labels: List[Dict], output_path: str = "models/skill_classifier.joblib"):
    """
    Train a decision tree classifier on labeled run data.
    
    Args:
        runs_with_labels: List of dicts with 'features' and 'label' keys
        output_path: Where to save the trained model
    """
    if len(runs_with_labels) < 30:
        raise ValueError("Need at least 30 labeled runs to train classifier")
    
    from sklearn.tree import DecisionTreeClassifier
    import joblib
    
    # Prepare training data
    X = []
    y = []
    
    for run in runs_with_labels:
        features = run["features"]
        X.append([
            features.get("score", 0),
            features.get("hits", 0),
            features.get("duration_ms", 0),
            features.get("avg_hit_duration_ms", 0),
            features.get("hits_per_second", 0),
        ])
        y.append(run["label"])
    
    X = np.array(X)
    y = np.array(y)
    
    # Train model
    clf = DecisionTreeClassifier(max_depth=5, random_state=42)
    clf.fit(X, y)
    
    # Save model
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    joblib.save(clf, output_path)
    
    return clf


def auto_label_runs(runs: List[Dict]) -> List[Dict]:
    """
    Auto-label runs using rule-based classification for training data.
    
    Args:
        runs: List of run dicts with features
        
    Returns:
        List of dicts with 'features' and 'label' keys
    """
    labeled = []
    
    for run in runs:
        label = classify_skill_rules(run)
        labeled.append({
            "features": run,
            "label": label
        })
    
    return labeled
