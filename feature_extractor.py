from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from models import Transaction, UserProfile
from datetime import datetime, timedelta
import numpy as np
from typing import Dict, Tuple
import json


class FeatureExtractor:
    """Extract behavioral features from user transaction history"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_transactions_30d(self, user_id: str) -> list:
        """Get all transactions for a user in last 30 days"""
        cutoff = datetime.utcnow() - timedelta(days=30)
        return self.db.query(Transaction).filter(
            and_(
                Transaction.user_id == user_id,
                Transaction.timestamp >= cutoff,
                Transaction.success == True
            )
        ).all()
    
    def is_new_payee(self, user_id: str, payee_id: str) -> bool:
        """Check if user has ever paid this payee before"""
        count = self.db.query(Transaction).filter(
            and_(
                Transaction.user_id == user_id,
                Transaction.payee_id == payee_id
            )
        ).count()
        return count == 0
    
    def compute_amount_deviation(self, user_id: str, current_amount: float) -> float:
        """
        Compute how much current amount deviates from user's normal behavior.
        Return a 0-1 score where 1 = extreme deviation
        """
        transactions = self.get_user_transactions_30d(user_id)
        
        if len(transactions) < 2:
            # Not enough history, assume normal
            return 0.0
        
        amounts = [t.amount for t in transactions]
        median = np.median(amounts)
        std_dev = np.std(amounts)
        
        if std_dev == 0:
            # All transactions are same amount
            return 0.0 if current_amount == median else 1.0
        
        # Z-score: how many standard deviations away?
        z_score = abs((current_amount - median) / std_dev)
        
        # Convert z-score to 0-1 scale: z=0 -> 0, z=3 -> 1.0
        deviation_score = min(z_score / 3.0, 1.0)
        
        return float(deviation_score)
    
    def compute_velocity_score(self, user_id: str) -> float:
        """
        Compute velocity anomaly: is user transacting unusually fast?
        Return 0-1 score where 1 = unusual velocity
        """
        transactions = self.get_user_transactions_30d(user_id)
        
        if len(transactions) < 3:
            return 0.0
        
        # Count transactions in last 24 hours
        last_24h = datetime.utcnow() - timedelta(hours=24)
        recent = [t for t in transactions if t.timestamp >= last_24h]
        
        # Average transactions per day (30 days)
        avg_per_day = len(transactions) / 30.0
        
        # If user normally does 1 per week but does 5 today, flag it
        if avg_per_day < 0.1:
            # User is quiet, flag if they suddenly have 3+ today
            return min(len(recent) / 3.0, 1.0) if len(recent) >= 3 else 0.0
        elif avg_per_day < 1.0:
            # User does < 1 per day, flag if they do 5x more than average
            expected_24h = avg_per_day
            if len(recent) > 5 * expected_24h:
                return min(len(recent) / (5 * expected_24h), 1.0)
            return 0.0
        else:
            # User is active, less concern about velocity
            return 0.0
    
    def compute_time_anomaly_score(self, user_id: str, current_hour: int) -> float:
        """
        Compute if transaction happens at unusual time of day.
        Return 0-1 score where 1 = very unusual time
        """
        transactions = self.get_user_transactions_30d(user_id)
        
        if len(transactions) < 3:
            return 0.0
        
        # Count transactions per hour
        hours = [t.hour_of_day for t in transactions]
        hour_counts = {}
        for h in hours:
            hour_counts[h] = hour_counts.get(h, 0) + 1
        
        total = len(hours)
        typical_hours = [h for h, count in hour_counts.items() if count / total >= 0.05]
        
        if len(typical_hours) == 0:
            typical_hours = list(range(9, 18))  # Default: 9 AM - 6 PM
        
        if current_hour in typical_hours:
            return 0.0
        else:
            # Outside typical hours - how rare?
            # Night hours (22-6) are more suspicious than evening
            if current_hour >= 22 or current_hour < 6:
                return 0.9
            else:
                return 0.5
    
    def compute_device_mismatch_score(self, user_id: str, device_id: str) -> float:
        """
        Check if transaction is from a device user normally uses.
        Return 0-1 score where 1 = new/unusual device
        """
        transactions = self.get_user_transactions_30d(user_id)
        
        if len(transactions) == 0:
            return 0.0
        
        devices = [t.device_id for t in transactions]
        device_counts = {}
        for d in devices:
            device_counts[d] = device_counts.get(d, 0) + 1
        
        total = len(devices)
        device_frequency = device_counts.get(device_id, 0) / total if total > 0 else 0
        
        # If device is used >80% of the time, no anomaly
        if device_frequency >= 0.8:
            return 0.0
        # If device is new, score = 0.7
        elif device_frequency == 0:
            return 0.7
        # If device is used sometimes, score = 0.3
        else:
            return 0.3
    
    def extract_all_features(
        self, 
        user_id: str, 
        payee_id: str, 
        amount: float,
        device_id: str,
        current_hour: int
    ) -> Dict[str, float]:
        """
        Extract all features for a transaction.
        Returns dict with keys: new_payee, amount_deviation, velocity, time_anomaly, device_mismatch
        """
        
        return {
            "new_payee": 1.0 if self.is_new_payee(user_id, payee_id) else 0.0,
            "amount_deviation": self.compute_amount_deviation(user_id, amount),
            "velocity": self.compute_velocity_score(user_id),
            "time_anomaly": self.compute_time_anomaly_score(user_id, current_hour),
            "device_mismatch": self.compute_device_mismatch_score(user_id, device_id),
        }


def update_user_profile(db: Session, user_id: str) -> None:
    """
    Recompute and cache user profile based on recent transactions.
    This is called periodically or on-demand.
    """
    transactions = db.query(Transaction).filter(
        and_(
            Transaction.user_id == user_id,
            Transaction.timestamp >= datetime.utcnow() - timedelta(days=30),
            Transaction.success == True
        )
    ).all()
    
    if len(transactions) == 0:
        return
    
    amounts = [t.amount for t in transactions]
    hours = [t.hour_of_day for t in transactions]
    payee_ids = set(t.payee_id for t in transactions)
    
    # Compute statistics
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if profile is None:
        profile = UserProfile(user_id=user_id)
    
    profile.median_amount = float(np.median(amounts))
    profile.p90_amount = float(np.percentile(amounts, 90))
    profile.p10_amount = float(np.percentile(amounts, 10))
    profile.std_dev_amount = float(np.std(amounts))
    profile.unique_payee_count = len(payee_ids)
    profile.total_transactions = len(transactions)
    
    # Typical hours: hours with >5% of transactions
    hour_counts = {}
    for h in hours:
        hour_counts[h] = hour_counts.get(h, 0) + 1
    typical = [h for h, cnt in hour_counts.items() if cnt / len(hours) >= 0.05]
    profile.typical_hours = json.dumps(sorted(typical))
    
    # Payee count per week
    days_span = (transactions[-1].timestamp - transactions[0].timestamp).days + 1
    if days_span > 0:
        weeks = max(days_span / 7.0, 1)
        profile.avg_payee_count_per_week = len(payee_ids) / weeks
    
    profile.last_updated = datetime.utcnow()
    
    db.add(profile)
    db.commit()
