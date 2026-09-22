from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
import uvicorn

from models import init_db, get_db, Transaction, ScoringDecision
from feature_extractor import FeatureExtractor, update_user_profile
from scorer import FraudScorer
from pydantic import BaseModel


# Initialize database
init_db()

app = FastAPI(
    title="Fraud Detection API",
    description="Real-time behavioral anomaly detection for UPI payments",
    version="1.0.0"
)


# Request/Response models
class ScoreTransactionRequest(BaseModel):
    user_id: str
    payee_id: str
    amount: float
    device_id: str
    timestamp: Optional[datetime] = None


class ScoreTransactionResponse(BaseModel):
    score: float
    decision: str
    reason: str
    features: dict
    transaction_id: Optional[int] = None


class HealthResponse(BaseModel):
    status: str
    message: str


# Endpoints

@app.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        message="Fraud detection service is running"
    )


@app.post("/score", response_model=ScoreTransactionResponse)
def score_transaction(
    request: ScoreTransactionRequest,
    db: Session = Depends(get_db)
) -> ScoreTransactionResponse:
    """
    Score a transaction for fraud risk.
    
    Returns a decision: ALLOW, SHOW_CONFIRMATION, or REQUIRE_BIOMETRIC
    """
    
    # Use provided timestamp or current time
    timestamp = request.timestamp or datetime.utcnow()
    hour_of_day = timestamp.hour
    
    # Extract features
    extractor = FeatureExtractor(db)
    features = extractor.extract_all_features(
        user_id=request.user_id,
        payee_id=request.payee_id,
        amount=request.amount,
        device_id=request.device_id,
        current_hour=hour_of_day
    )
    
    # Score
    result = FraudScorer.score(features)
    
    # Log the decision
    decision_log = ScoringDecision(
        user_id=request.user_id,
        payee_id=request.payee_id,
        amount=request.amount,
        timestamp=timestamp,
        new_payee_score=features["new_payee"],
        amount_deviation_score=features["amount_deviation"],
        velocity_score=features["velocity"],
        time_anomaly_score=features["time_anomaly"],
        device_mismatch_score=features["device_mismatch"],
        final_score=result.score,
        decision=result.decision,
        reason=result.reason
    )
    db.add(decision_log)
    db.commit()
    db.refresh(decision_log)
    
    return ScoreTransactionResponse(
        score=result.score,
        decision=result.decision,
        reason=result.reason,
        features=result.feature_scores,
        transaction_id=decision_log.id
    )


@app.post("/transaction")
def log_transaction(
    request: ScoreTransactionRequest,
    db: Session = Depends(get_db)
):
    """
    Log a transaction to user's history.
    This is called after a payment succeeds.
    """
    
    timestamp = request.timestamp or datetime.utcnow()
    hour_of_day = timestamp.hour
    
    transaction = Transaction(
        user_id=request.user_id,
        payee_id=request.payee_id,
        amount=request.amount,
        device_id=request.device_id,
        timestamp=timestamp,
        hour_of_day=hour_of_day,
        success=True
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    
    # Update user profile
    update_user_profile(db, request.user_id)
    
    return {
        "status": "logged",
        "transaction_id": transaction.id,
        "user_id": request.user_id
    }


@app.get("/user/{user_id}/profile")
def get_user_profile(user_id: str, db: Session = Depends(get_db)):
    """Get cached user profile"""
    from models import UserProfile
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    
    if profile is None:
        return {
            "user_id": user_id,
            "status": "no_profile",
            "message": "User has no transaction history yet"
        }
    
    return {
        "user_id": user_id,
        "median_amount": profile.median_amount,
        "p90_amount": profile.p90_amount,
        "p10_amount": profile.p10_amount,
        "std_dev_amount": profile.std_dev_amount,
        "unique_payee_count": profile.unique_payee_count,
        "total_transactions": profile.total_transactions,
        "avg_payee_count_per_week": profile.avg_payee_count_per_week,
        "typical_hours": profile.typical_hours,
        "last_updated": profile.last_updated
    }


@app.get("/user/{user_id}/decisions")
def get_user_decisions(user_id: str, limit: int = 10, db: Session = Depends(get_db)):
    """Get recent scoring decisions for a user"""
    decisions = db.query(ScoringDecision).filter(
        ScoringDecision.user_id == user_id
    ).order_by(ScoringDecision.timestamp.desc()).limit(limit).all()
    
    return {
        "user_id": user_id,
        "count": len(decisions),
        "decisions": [
            {
                "id": d.id,
                "timestamp": d.timestamp,
                "payee_id": d.payee_id,
                "amount": d.amount,
                "final_score": d.final_score,
                "decision": d.decision,
                "reason": d.reason
            }
            for d in decisions
        ]
    }


@app.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """Get system statistics"""
    from models import Transaction, ScoringDecision
    
    total_transactions = db.query(Transaction).count()
    total_decisions = db.query(ScoringDecision).count()
    
    # Count decisions by type
    from sqlalchemy import func
    decisions_by_type = db.query(
        ScoringDecision.decision,
        func.count(ScoringDecision.id)
    ).group_by(ScoringDecision.decision).all()
    
    decision_stats = {d[0]: d[1] for d in decisions_by_type}
    
    return {
        "total_transactions_logged": total_transactions,
        "total_decisions_scored": total_decisions,
        "decisions_by_type": decision_stats
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
