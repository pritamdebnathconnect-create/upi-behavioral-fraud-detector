"""
Demo script showing the fraud detector in action.
Run with: python demo.py
"""

from models import init_db, SessionLocal
from test_data import setup_test_scenarios
from feature_extractor import FeatureExtractor, update_user_profile
from scorer import FraudScorer
from datetime import datetime


def demo_score_transaction(user_id, payee_id, amount, device_id, hour):
    """Demo scoring a transaction"""
    db = SessionLocal()
    
    print(f"\n{'='*70}")
    print(f"Scoring Transaction")
    print(f"{'='*70}")
    print(f"User: {user_id}")
    print(f"Payee: {payee_id}")
    print(f"Amount: ₹{amount:,.0f}")
    print(f"Device: {device_id}")
    print(f"Hour: {hour}:00")
    print(f"{'='*70}\n")
    
    # Extract features
    extractor = FeatureExtractor(db)
    features = extractor.extract_all_features(
        user_id=user_id,
        payee_id=payee_id,
        amount=amount,
        device_id=device_id,
        current_hour=hour
    )
    
    # Score
    result = FraudScorer.score(features)
    
    # Print results
    print(f"Final Score: {result.score} / 1.0")
    print(f"Decision: {result.decision}")
    print(f"Reason: {result.reason}\n")
    
    print("Feature Breakdown:")
    print("-" * 70)
    for feature_name, weight in FraudScorer.WEIGHTS.items():
        feature_value = result.feature_scores[feature_name]
        contribution = weight * feature_value
        bar_length = int(contribution * 20)
        bar = "█" * bar_length + "░" * (20 - bar_length)
        print(f"{feature_name:20s} {feature_value:4.2f} [{bar}] {contribution:5.3f}")
    
    print("-" * 70)
    print(f"Total Score: {result.score}")
    print(f"\nDecision Thresholds:")
    print(f"  ALLOW (< 0.50):          [{'█' * 10}░░░░░░░░░░]")
    print(f"  CONFIRM (0.50 - 0.65):   [██████████{'█' * 3}░░░░░░]")
    print(f"  BIOMETRIC (> 0.65):      [██████████████░░░░░░]")
    print(f"\n  Your score: {result.score:5.2f}  ", end="")
    
    score_bar = int(result.score * 20)
    print(f"[{'█' * score_bar}{'░' * (20 - score_bar)}]")
    
    db.close()


def main():
    """Run the demo"""
    
    print("\n" + "="*70)
    print("FRAUD DETECTION SYSTEM - DEMO")
    print("="*70 + "\n")
    
    # Setup test data
    print("Setting up test data...")
    setup_test_scenarios()
    
    print("\n" + "="*70)
    print("SCENARIO 1: Normal User, Normal Transaction")
    print("="*70)
    demo_score_transaction(
        user_id="user_normal",
        payee_id="payee_1",  # Regular payee
        amount=5000,  # Normal amount
        device_id="device_1",  # Known device
        hour=12  # Daytime
    )
    
    print("\n" + "="*70)
    print("SCENARIO 2: Normal User, New Payee (SUSPICIOUS)")
    print("="*70)
    demo_score_transaction(
        user_id="user_normal",
        payee_id="unknown_payee",  # NEW PAYEE
        amount=5000,  # Normal amount
        device_id="device_1",  # Known device
        hour=12  # Daytime
    )
    
    print("\n" + "="*70)
    print("SCENARIO 3: Normal User, High Amount (SUSPICIOUS)")
    print("="*70)
    demo_score_transaction(
        user_id="user_normal",
        payee_id="payee_1",  # Regular payee
        amount=50000,  # 10x NORMAL AMOUNT
        device_id="device_1",  # Known device
        hour=12  # Daytime
    )
    
    print("\n" + "="*70)
    print("SCENARIO 4: Normal User, Night Payment (SUSPICIOUS)")
    print("="*70)
    demo_score_transaction(
        user_id="user_normal",
        payee_id="payee_1",  # Regular payee
        amount=5000,  # Normal amount
        device_id="device_1",  # Known device
        hour=2  # 2 AM - UNUSUAL TIME
    )
    
    print("\n" + "="*70)
    print("SCENARIO 5: Normal User, New Device (SUSPICIOUS)")
    print("="*70)
    demo_score_transaction(
        user_id="user_normal",
        payee_id="payee_1",  # Regular payee
        amount=5000,  # Normal amount
        device_id="device_unknown",  # NEW DEVICE
        hour=12  # Daytime
    )
    
    print("\n" + "="*70)
    print("SCENARIO 6: CLASSIC APP FRAUD - Multiple Anomalies")
    print("="*70)
    print("(New payee + High amount + Night time + New device)\n")
    demo_score_transaction(
        user_id="user_normal",
        payee_id="mule_account_123",  # NEW PAYEE
        amount=100000,  # 20x NORMAL
        device_id="device_attacker",  # NEW DEVICE
        hour=3  # 3 AM - NIGHT
    )
    
    print("\n" + "="*70)
    print("SCENARIO 7: New User (No History)")
    print("="*70)
    demo_score_transaction(
        user_id="user_new",
        payee_id="payee_1",
        amount=5000,
        device_id="device_1",
        hour=12
    )
    
    print("\n" + "="*70)
    print("DEMO COMPLETE")
    print("="*70)
    print("\nKey Takeaways:")
    print("✓ Normal transactions are allowed silently")
    print("✓ Single anomalies trigger confirmation dialog")
    print("✓ Multiple anomalies require biometric auth")
    print("✓ No history users default to allowing first transaction")
    print("\n")


if __name__ == "__main__":
    main()
