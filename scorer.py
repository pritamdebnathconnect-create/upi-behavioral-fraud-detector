from typing import Dict, Tuple
from dataclasses import dataclass


@dataclass
class ScoringResult:
    """Result of fraud scoring"""
    score: float  # 0-1 score
    decision: str  # ALLOW, SHOW_CONFIRMATION, REQUIRE_BIOMETRIC
    reason: str
    feature_scores: Dict[str, float]


class FraudScorer:
    """Score transactions for fraud risk and make decisions"""
    
    # Feature weights (must sum to 1.0)
    WEIGHTS = {
        "new_payee": 0.30,
        "amount_deviation": 0.25,
        "velocity": 0.20,
        "time_anomaly": 0.15,
        "device_mismatch": 0.10,
    }
    
    # Decision thresholds
    ALLOW_THRESHOLD = 0.50  # Below this: allow silently
    CONFIRM_THRESHOLD = 0.65  # Between this and allow: show confirmation
    BIOMETRIC_THRESHOLD = 0.80  # Above this: require biometric
    
    @classmethod
    def score(cls, features: Dict[str, float]) -> ScoringResult:
        """
        Score a transaction based on extracted features.
        
        Args:
            features: Dict with keys: new_payee, amount_deviation, velocity, 
                     time_anomaly, device_mismatch
        
        Returns:
            ScoringResult with score, decision, reason
        """
        
        # Compute weighted score
        score = 0.0
        for feature_name, weight in cls.WEIGHTS.items():
            feature_value = features.get(feature_name, 0.0)
            score += weight * feature_value
        
        # Clamp to 0-1
        score = min(max(score, 0.0), 1.0)
        
        # Make decision
        if score >= cls.BIOMETRIC_THRESHOLD:
            decision = "REQUIRE_BIOMETRIC"
            reason = cls._get_reason(features, "high")
        elif score >= cls.CONFIRM_THRESHOLD:
            decision = "SHOW_CONFIRMATION"
            reason = cls._get_reason(features, "medium")
        else:
            decision = "ALLOW"
            reason = "Transaction looks normal"
        
        return ScoringResult(
            score=round(score, 3),
            decision=decision,
            reason=reason,
            feature_scores=features
        )
    
    @classmethod
    def _get_reason(cls, features: Dict[str, float], level: str) -> str:
        """Generate a human-readable reason for the decision"""
        reasons = []
        
        if features.get("new_payee", 0) >= 0.5:
            reasons.append("new payee")
        if features.get("amount_deviation", 0) >= 0.5:
            reasons.append("unusual amount")
        if features.get("velocity", 0) >= 0.5:
            reasons.append("high velocity")
        if features.get("time_anomaly", 0) >= 0.7:
            reasons.append("unusual time")
        if features.get("device_mismatch", 0) >= 0.5:
            reasons.append("new device")
        
        if not reasons:
            reasons = ["multiple small anomalies"]
        
        reason_text = ", ".join(reasons)
        
        if level == "high":
            return f"Suspicious activity detected: {reason_text}"
        else:
            return f"Please confirm: {reason_text}"
    
    @classmethod
    def print_explanation(cls, result: ScoringResult) -> str:
        """Print detailed explanation of the score"""
        output = []
        output.append(f"\n{'='*60}")
        output.append(f"Fraud Score: {result.score} ({result.decision})")
        output.append(f"Reason: {result.reason}")
        output.append(f"{'='*60}")
        output.append("\nFeature breakdown:")
        for feature, weight in cls.WEIGHTS.items():
            feature_value = result.feature_scores.get(feature, 0.0)
            contribution = weight * feature_value
            output.append(f"  {feature:20s}: {feature_value:.2f} * {weight:.2f} = {contribution:.3f}")
        output.append(f"\n{'='*60}\n")
        return "\n".join(output)
