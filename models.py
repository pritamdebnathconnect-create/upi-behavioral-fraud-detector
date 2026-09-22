from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///fraud_detector.db")

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class Transaction(Base):
    """Store all user transactions for historical analysis"""
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    payee_id = Column(String, index=True, nullable=False)
    amount = Column(Float, nullable=False)
    device_id = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    hour_of_day = Column(Integer, nullable=False)  # 0-23
    success = Column(Boolean, default=True)  # Was transaction successful?
    is_fraud = Column(Boolean, default=False)  # Labeled as fraud (for training)
    
    __table_args__ = (
        Index('idx_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_user_payee', 'user_id', 'payee_id'),
    )


class UserProfile(Base):
    """Cached user behavior profiles (recomputed hourly)"""
    __tablename__ = "user_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True, nullable=False)
    median_amount = Column(Float, nullable=True)
    p90_amount = Column(Float, nullable=True)  # 90th percentile
    p10_amount = Column(Float, nullable=True)  # 10th percentile
    std_dev_amount = Column(Float, nullable=True)
    avg_payee_count_per_week = Column(Float, nullable=True)
    unique_payee_count = Column(Integer, nullable=True)
    total_transactions = Column(Integer, default=0)
    typical_hours = Column(String, nullable=True)  # JSON: [hour] when user normally transacts
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_user_profile', 'user_id'),
    )


class ScoringDecision(Base):
    """Log all scoring decisions for analysis and monitoring"""
    __tablename__ = "scoring_decisions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    payee_id = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Features
    new_payee_score = Column(Float, nullable=False)
    amount_deviation_score = Column(Float, nullable=False)
    velocity_score = Column(Float, nullable=False)
    time_anomaly_score = Column(Float, nullable=False)
    device_mismatch_score = Column(Float, nullable=False)
    
    # Final decision
    final_score = Column(Float, nullable=False)
    decision = Column(String, nullable=False)  # ALLOW, SHOW_CONFIRMATION, REQUIRE_BIOMETRIC
    reason = Column(String, nullable=True)
    
    # Feedback (filled later)
    user_action = Column(String, nullable=True)  # CONFIRMED, CANCELLED, ALLOWED_ANYWAY
    is_actual_fraud = Column(Boolean, nullable=True)  # Labeled as fraud later
    
    __table_args__ = (
        Index('idx_user_timestamp_decision', 'user_id', 'timestamp'),
    )


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully")


def get_db():
    """Dependency injection for database sessions"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
