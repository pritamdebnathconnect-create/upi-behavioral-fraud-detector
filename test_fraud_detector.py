"""
Test cases for fraud detection system.
Run with: pytest test_fraud_detector.py -v
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Transaction, ScoringDecision, UserProfile, SessionLocal
from feature_extractor import FeatureExtractor, update_user_profile
from scorer import FraudScorer
import os


# Use in-memory SQLite for testing
@pytest.fixture
def test_db():
    """Create a test database"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()


# Feature Extraction Tests

class TestFeatureExtraction:
    
    def test_is_new_payee(self, test_db):
        """Test detection of new payees"""
        extractor = FeatureExtractor(test_db)
        
        # Add a transaction for user_1 to payee_1
        transaction = Transaction(
            user_id="user_1",
            payee_id="payee_1",
            amount=5000,
            device_id="device_1",
            timestamp=datetime.utcnow(),
            hour_of_day=12,
            success=True
        )
        test_db.add(transaction)
        test_db.commit()
        
        # payee_1 should not be new
        assert extractor.is_new_payee("user_1", "payee_1") == False
        
        # payee_2 should be new
        assert extractor.is_new_payee("user_1", "payee_2") == True
    
    def test_amount_deviation(self, test_db):
        """Test amount deviation detection"""
        extractor = FeatureExtractor(test_db)
        
        # Add normal transactions: 5000, 5200, 5100
        for amount in [5000, 5200, 5100]:
            test_db.add(Transaction(
                user_id="user_1",
                payee_id="payee_1",
                amount=amount,
                device_id="device_1",
                timestamp=datetime.utcnow() - timedelta(days=5),
                hour_of_day=12,
                success=True
            ))
        test_db.commit()
        
        # Normal amount should have low deviation
        deviation_normal = extractor.compute_amount_deviation("user_1", 5100)
        assert deviation_normal < 0.3
        
        # Extreme amount should have high deviation
        deviation_extreme = extractor.compute_amount_deviation("user_1", 50000)
        assert deviation_extreme > 0.8
    
    def test_velocity_score(self, test_db):
        """Test velocity anomaly detection"""
        extractor = FeatureExtractor(test_db)
        
        # Add one transaction per day for 30 days
        for i in range(30):
            test_db.add(Transaction(
                user_id="user_quiet",
                payee_id=f"payee_{i % 5}",
                amount=5000,
                device_id="device_1",
                timestamp=datetime.utcnow() - timedelta(days=30-i),
                hour_of_day=12,
                success=True
            ))
        test_db.commit()
        
        # Normal velocity
        velocity_normal = extractor.compute_velocity_score("user_quiet")
        assert velocity_normal == 0.0  # Normal for this user
        
        # Add 5 transactions in last 24 hours
        for i in range(5):
            test_db.add(Transaction(
                user_id="user_quiet",
                payee_id=f"payee_{i}",
                amount=5000,
                device_id="device_1",
                timestamp=datetime.utcnow() - timedelta(hours=12),
                hour_of_day=12,
                success=True
            ))
        test_db.commit()
        
        velocity_high = extractor.compute_velocity_score("user_quiet")
        assert velocity_high > 0.5  # Should flag high velocity
    
    def test_time_anomaly_score(self, test_db):
        """Test unusual time detection"""
        extractor = FeatureExtractor(test_db)
        
        # User always transacts during 9-17
        for hour in range(9, 18):
            test_db.add(Transaction(
                user_id="user_daytime",
                payee_id="payee_1",
                amount=5000,
                device_id="device_1",
                timestamp=datetime.utcnow() - timedelta(days=10),
                hour_of_day=hour,
                success=True
            ))
        test_db.commit()
        
        # Daytime transaction should be normal
        time_score_day = extractor.compute_time_anomaly_score("user_daytime", 12)
        assert time_score_day < 0.2
        
        # Night transaction should be suspicious
        time_score_night = extractor.compute_time_anomaly_score("user_daytime", 2)
        assert time_score_night > 0.7
    
    def test_device_mismatch_score(self, test_db):
        """Test device anomaly detection"""
        extractor = FeatureExtractor(test_db)
        
        # User always uses device_1
        for i in range(10):
            test_db.add(Transaction(
                user_id="user_stable_device",
                payee_id="payee_1",
                amount=5000,
                device_id="device_1",
                timestamp=datetime.utcnow() - timedelta(days=10),
                hour_of_day=12,
                success=True
            ))
        test_db.commit()
        
        # Same device should have low score
        device_score_same = extractor.compute_device_mismatch_score("user_stable_device", "device_1")
        assert device_score_same < 0.3
        
        # New device should have high score
        device_score_new = extractor.compute_device_mismatch_score("user_stable_device", "device_new")
        assert device_score_new > 0.5


# Scoring Tests

class TestFraudScorer:
    
    def test_score_all_green(self):
        """Test scoring for normal transaction"""
        features = {
            "new_payee": 0.0,
            "amount_deviation": 0.1,
            "velocity": 0.0,
            "time_anomaly": 0.0,
            "device_mismatch": 0.0,
        }
        result = FraudScorer.score(features)
        
        assert result.score < 0.5
        assert result.decision == "ALLOW"
    
    def test_score_medium_risk(self):
        """Test scoring for slightly suspicious transaction"""
        features = {
            "new_payee": 1.0,  # New payee is suspicious
            "amount_deviation": 0.2,
            "velocity": 0.0,
            "time_anomaly": 0.1,
            "device_mismatch": 0.0,
        }
        result = FraudScorer.score(features)
        
        assert 0.5 < result.score < 0.8
        assert result.decision == "SHOW_CONFIRMATION"
    
    def test_score_high_risk(self):
        """Test scoring for highly suspicious transaction"""
        features = {
            "new_payee": 1.0,
            "amount_deviation": 0.9,
            "velocity": 0.8,
            "time_anomaly": 0.9,
            "device_mismatch": 0.7,
        }
        result = FraudScorer.score(features)
        
        assert result.score > 0.8
        assert result.decision == "REQUIRE_BIOMETRIC"


# Integration Tests

class TestIntegration:
    
    def test_end_to_end_normal_user(self, test_db):
        """Test complete flow for normal user"""
        # Add user history
        for i in range(20):
            test_db.add(Transaction(
                user_id="user_e2e",
                payee_id="payee_1",
                amount=5000,
                device_id="device_1",
                timestamp=datetime.utcnow() - timedelta(days=20-i),
                hour_of_day=12,
                success=True
            ))
        test_db.commit()
        
        # Extract features for a normal transaction
        extractor = FeatureExtractor(test_db)
        features = extractor.extract_all_features(
            user_id="user_e2e",
            payee_id="payee_1",
            amount=5100,
            device_id="device_1",
            current_hour=12
        )
        
        result = FraudScorer.score(features)
        
        assert result.score < 0.5
        assert result.decision == "ALLOW"
    
    def test_end_to_end_suspicious_transaction(self, test_db):
        """Test complete flow for suspicious transaction"""
        # Add user history
        for i in range(20):
            test_db.add(Transaction(
                user_id="user_suspicious",
                payee_id="payee_1",
                amount=5000,
                device_id="device_1",
                timestamp=datetime.utcnow() - timedelta(days=20-i),
                hour_of_day=12,
                success=True
            ))
        test_db.commit()
        
        # Extract features for suspicious transaction
        # - New payee (payee_2)
        # - High amount (50x normal)
        # - Night time
        # - New device
        extractor = FeatureExtractor(test_db)
        features = extractor.extract_all_features(
            user_id="user_suspicious",
            payee_id="payee_2",  # New payee
            amount=50000,  # 10x normal
            device_id="device_new",  # New device
            current_hour=2  # 2 AM
        )
        
        result = FraudScorer.score(features)
        
        assert result.score > 0.7
        assert result.decision in ["SHOW_CONFIRMATION", "REQUIRE_BIOMETRIC"]
    
    def test_new_user_scoring(self, test_db):
        """Test scoring for user with no history"""
        extractor = FeatureExtractor(test_db)
        features = extractor.extract_all_features(
            user_id="brand_new_user",
            payee_id="payee_1",
            amount=5000,
            device_id="device_1",
            current_hour=12
        )
        
        result = FraudScorer.score(features)
        
        # Should not crash, should return a reasonable score
        assert 0.0 <= result.score <= 1.0
        assert result.decision in ["ALLOW", "SHOW_CONFIRMATION", "REQUIRE_BIOMETRIC"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
