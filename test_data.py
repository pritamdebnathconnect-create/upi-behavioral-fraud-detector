"""
Generate synthetic test data for fraud detection testing.
Simulates realistic user behavior and various fraud scenarios.
"""

from sqlalchemy.orm import Session
from models import Transaction, init_db, SessionLocal
from datetime import datetime, timedelta
import random
import numpy as np


def generate_normal_user_history(
    db: Session,
    user_id: str,
    num_transactions: int = 50,
    start_date: datetime = None
):
    """
    Generate a realistic user with normal behavior patterns.
    """
    if start_date is None:
        start_date = datetime.utcnow() - timedelta(days=30)
    
    # User has 5 regular payees they send money to
    regular_payees = [f"payee_{i}" for i in range(1, 6)]
    
    # Normal amount: mean 5000, std 1000
    amounts = np.random.normal(5000, 1000, num_transactions)
    amounts = [max(500, amount) for amount in amounts]  # Min 500
    
    # Normal hours: 9 AM - 5 PM on weekdays
    normal_hours = list(range(9, 18))
    
    # Device: usually device_1, sometimes device_2
    devices = ["device_1"] * int(num_transactions * 0.85) + ["device_2"] * int(num_transactions * 0.15)
    random.shuffle(devices)
    
    for i in range(num_transactions):
        timestamp = start_date + timedelta(hours=random.randint(0, 30*24))
        
        transaction = Transaction(
            user_id=user_id,
            payee_id=random.choice(regular_payees),
            amount=amounts[i],
            device_id=devices[i],
            timestamp=timestamp,
            hour_of_day=random.choice(normal_hours),
            success=True,
            is_fraud=False
        )
        db.add(transaction)
    
    db.commit()
    print(f"✓ Generated normal user history: {user_id} ({num_transactions} transactions)")


def generate_suspicious_transaction(
    db: Session,
    user_id: str,
    anomaly_type: str = "new_payee"
):
    """
    Generate a suspicious transaction for testing.
    Types: new_payee, high_amount, unusual_time, new_device, high_velocity
    """
    timestamp = datetime.utcnow()
    
    transaction = Transaction(
        user_id=user_id,
        payee_id="unknown_payee" if anomaly_type == "new_payee" else "payee_1",
        amount=50000 if anomaly_type == "high_amount" else 5000,
        device_id="device_unknown" if anomaly_type == "new_device" else "device_1",
        timestamp=timestamp,
        hour_of_day=2 if anomaly_type == "unusual_time" else 12,  # 2 AM
        success=True,
        is_fraud=True
    )
    db.add(transaction)
    db.commit()
    print(f"✓ Generated suspicious transaction: {user_id} ({anomaly_type})")


def setup_test_scenarios():
    """Set up complete test scenarios"""
    init_db()
    db = SessionLocal()
    
    print("\n" + "="*60)
    print("Generating Test Data")
    print("="*60 + "\n")
    
    # Scenario 1: Normal user, normal transaction
    print("Scenario 1: Normal User")
    print("-" * 40)
    generate_normal_user_history(db, "user_normal", num_transactions=50)
    generate_suspicious_transaction(db, "user_normal", "new_payee")  # This should be flagged
    
    # Scenario 2: User with high variance
    print("\nScenario 2: High-Variance User")
    print("-" * 40)
    generate_normal_user_history(db, "user_varied", num_transactions=40)
    
    # Scenario 3: New user (no history)
    print("\nScenario 3: New User (No History)")
    print("-" * 40)
    new_user_transaction = Transaction(
        user_id="user_new",
        payee_id="payee_1",
        amount=5000,
        device_id="device_1",
        timestamp=datetime.utcnow(),
        hour_of_day=12,
        success=True,
        is_fraud=False
    )
    db.add(new_user_transaction)
    db.commit()
    print("✓ Generated new user (1 transaction)")
    
    # Scenario 4: Fraudster scenario
    print("\nScenario 5: Fraud Scenarios")
    print("-" * 40)
    generate_normal_user_history(db, "user_fraud_target", num_transactions=50)
    
    db.close()
    
    print("\n" + "="*60)
    print("Test data generated successfully!")
    print("="*60 + "\n")


if __name__ == "__main__":
    setup_test_scenarios()
