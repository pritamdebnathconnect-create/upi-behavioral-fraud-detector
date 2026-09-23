# Behavioral Anomaly Detector for UPI Fraud Detection

A real-time fraud detection system that scores UPI transactions based on behavioral anomalies and recommends user authentication steps.

## 🎯 Overview

This system detects fraudulent UPI transactions by analyzing deviations from a user's normal behavior patterns. Instead of trying to reverse transactions post-settlement (which is impossible in UPI), it raises the bar for authorization when something looks off.

**Architecture Philosophy:**
- Pre-transaction detection (while transaction is being authorized)
- Behavioral signals, not credential compromise
- Focus on Authorised Push Payment (APP) fraud
- Real-time scoring with <100ms latency

## 📊 How It Works

### The Problem

UPI settlements are **irrevocable**. Once money leaves the payer's account, it's gone. 98.5% of fraud value comes from social engineering (APP fraud), not account compromise. A user is coached on a call by a scammer to make the payment.

**Standard fraud signals don't work:**
- ✗ Device is the user's device
- ✗ Biometrics passed (it's the user)
- ✗ Credentials are correct (it's the user)
- ✗ Transaction looks syntactically valid

**So we detect behavioral context instead:**
- ✓ Is this payee new?
- ✓ Is the amount unusual?
- ✓ Is the transaction time weird for this user?
- ✓ Is the device their normal one?
- ✓ Are they transacting unusually fast?

### The Solution

Score a transaction on 5 behavioral features, combine them, and decide:
- **ALLOW** (score < 0.50): Silent, no friction
- **SHOW_CONFIRMATION** (0.50 - 0.65): "Confirm payee" dialog
- **REQUIRE_BIOMETRIC** (score > 0.65): Biometric re-auth required

## 🏗️ Project Structure

```
fraud-detector/
├── models.py                 # Database schema (SQLAlchemy)
├── feature_extractor.py      # Behavioral feature computation
├── scorer.py                 # Risk scoring and decision logic
├── main.py                   # FastAPI application
├── test_data.py              # Synthetic test data generation
├── test_fraud_detector.py    # Test cases (pytest)
├── demo.py                   # Interactive demo
└── requirements.txt          # Dependencies
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Demo

```bash
python demo.py
```

This generates test data and scores 7 different scenarios, showing how the system flags suspicious transactions.

### 3. Run Tests

```bash
pytest test_fraud_detector.py -v
```

Tests cover:
- Feature extraction (new payee, amount deviation, velocity, time, device)
- Scoring logic (normal, medium, high risk)
- End-to-end flows (normal user, suspicious user, new user)

### 4. Start the API Server

```bash
python main.py
```

The API runs on `http://localhost:8000`

#### Endpoints:

**Score a transaction:**
```bash
curl -X POST http://localhost:8000/score \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "payee_id": "payee_456",
    "amount": 5000,
    "device_id": "device_1"
  }'
```

**Response:**
```json
{
  "score": 0.35,
  "decision": "ALLOW",
  "reason": "Transaction looks normal",
  "features": {
    "new_payee": 0.0,
    "amount_deviation": 0.1,
    "velocity": 0.0,
    "time_anomaly": 0.0,
    "device_mismatch": 0.0
  },
  "transaction_id": 1
}
```

**Log a completed transaction:**
```bash
curl -X POST http://localhost:8000/transaction \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "payee_id": "payee_456",
    "amount": 5000,
    "device_id": "device_1"
  }'
```

**Get user profile:**
```bash
curl http://localhost:8000/user/user_123/profile
```

**Get recent decisions for a user:**
```bash
curl http://localhost:8000/user/user_123/decisions?limit=10
```

**System stats:**
```bash
curl http://localhost:8000/stats
```

## 🧠 Feature Engineering

### 1. New Payee Score (Weight: 0.30)

**Why it matters:** APP fraud almost always involves paying a new account (controlled by the scammer).

**How it works:**
- Query: Has user ever paid this payee before?
- Score: 1.0 if new, 0.0 if known

**Edge case:** New users have everything as "new payees" → default to 0.0 for first payment

### 2. Amount Deviation Score (Weight: 0.25)

**Why it matters:** Scammers often request specific amounts ("send ₹21,742").

**How it works:**
- Compute user's median amount (last 30 days)
- Compute z-score: `z = (current_amount - median) / std_dev`
- Score: `min(z / 3, 1.0)` → maps z=0→0, z=3→1.0

**Edge case:** User with low variance → any large amount flags it

### 3. Velocity Score (Weight: 0.20)

**Why it matters:** A quiet user suddenly making many payments is suspicious.

**How it works:**
- Count transactions in last 24 hours
- Compare to user's average rate
- If user does <1/week normally but does 5 today → flag

**Edge case:** Active users (>1/day) are given more slack

### 4. Time Anomaly Score (Weight: 0.15)

**Why it matters:** Scams happen when users are more confused (tired, night time).

**How it works:**
- Identify user's typical hours (hours with >5% of transactions)
- If transaction is outside typical hours:
  - Night (22:00 - 6:00): score = 0.9
  - Evening: score = 0.5
  - Otherwise: score = 0.0

**Edge case:** User with few transactions → default to 9-18 (business hours)

### 5. Device Mismatch Score (Weight: 0.10)

**Why it matters:** Attackers often use a different device to send money.

**How it works:**
- Count frequency of each device
- If device used >80% of time: score = 0.0 (normal)
- If device is new: score = 0.7 (suspicious)
- If device is occasional: score = 0.3 (minor concern)

**Edge case:** Low-end Android with many different devices → needs different logic

## 📈 Scoring Formula

```
final_score = 0.30 * new_payee 
            + 0.25 * amount_deviation 
            + 0.20 * velocity 
            + 0.15 * time_anomaly 
            + 0.10 * device_mismatch
```

Each feature is 0-1, so final score is 0-1.

## 🎚️ Decision Thresholds

| Score | Decision | User Experience |
|-------|----------|-----------------|
| < 0.50 | ALLOW | Silent, no friction |
| 0.50 - 0.65 | SHOW_CONFIRMATION | "Please confirm this new payee" |
| > 0.65 | REQUIRE_BIOMETRIC | "Verify with fingerprint" |

**How to tune thresholds:**
- Lower threshold → catch more fraud but more false positives
- Higher threshold → fewer false positives but miss more fraud
- Optimal depends on your cost function: `fraud_loss + friction_cost`

## 📊 Database Schema

### Transactions Table
Stores every completed UPI transaction for historical analysis.
```
- id (PK)
- user_id (indexed)
- payee_id (indexed)
- amount
- device_id
- timestamp (indexed)
- hour_of_day
- success (bool)
- is_fraud (bool, for labeling)
```

### User Profiles Table
Cached aggregates, recomputed hourly or on-demand.
```
- id (PK)
- user_id (unique, indexed)
- median_amount
- p90_amount, p10_amount
- std_dev_amount
- unique_payee_count
- avg_payee_count_per_week
- typical_hours (JSON)
- last_updated
```

### Scoring Decisions Table
Audit trail of every decision made by the scorer.
```
- id (PK)
- user_id (indexed)
- timestamp (indexed)
- amount, payee_id
- [feature scores for each of 5 features]
- final_score, decision, reason
- user_action (CONFIRMED, CANCELLED, ALLOWED_ANYWAY)
- is_actual_fraud (labeled later)
```

## 🧪 Testing

### Unit Tests
```bash
pytest test_fraud_detector.py::TestFeatureExtraction -v
pytest test_fraud_detector.py::TestFraudScorer -v
```

### Integration Tests
```bash
pytest test_fraud_detector.py::TestIntegration -v
```

### All Tests
```bash
pytest test_fraud_detector.py -v
```

## 📈 Phase 1 Scope (What we're Building)

✅ **Done:**
- Database schema for transactions, profiles, decisions
- Feature extraction (5 behavioral signals)
- Scoring logic (weighted sum)
- Decision logic (thresholds)
- FastAPI endpoints
- Synthetic test data
- Comprehensive tests
- Demo script

**Time:** 4-6 weeks for a solid MVP

## 🚀 Phase 2 Extensions (Future Enhancements)

- [ ] Real-time feature store with Redis caching
- [ ] User profile precomputation (hourly batch job)
- [ ] Drift monitoring (model performance degradation)
- [ ] A/B testing framework (threshold tuning)
- [ ] False positive analysis dashboard
- [ ] Beneficiary account risk scoring (cross-institutional)
- [ ] Machine learning model (gradient boosted trees) instead of rules

## 🎯 Key Decisions Made :

### Q: Why not try to reverse the transaction?
**A:** UPI is irrevocable. Money settles in 5 seconds. You can't reverse a SUCCESSFUL transaction; you can only file a chargeback, which is a weeks-long process. By then the money is in a mule account and gone. Prevention is the only option.

### Q: Why not just block high-risk transactions?
**A:** Blocking costs you more than fraud. A 1% fraud rate costs less than a 5% false-positive rate (users give up on your app). So we step-up (show confirmation) rather than hard-block.

### Q: How do you handle new users?
**A:** Conservatively. New users default to allowing their first payment (no profile to deviate from). After a few transactions, the profile kicks in.

### Q: What's the latency budget?
**A:** <100ms. Most PSP decisions happen in 50-300ms. Your scoring should be <50ms so the payment doesn't feel slow. That rules out expensive lookups or model inference at scale.
## ⚠️ Limitations

This is a learning/portfolio project, not a production fraud system. Being upfront about scope:

- **Synthetic data only.** All training and demo transactions are generated, not real UPI transaction history. Real fraud rates in India's UPI system are well under 1%; the training set uses an inflated 3% fraud rate to have enough positive examples to learn from at this scale.
- **Rule weights and model thresholds are not validated against real fraud losses.** In production these would be tuned against an actual cost function (fraud loss vs. friction cost) using real outcome data.
- **No retraining or drift-monitoring pipelie.** A real system needs continuous label ingestion and periodic retraining; this project trains once on a static dataset.
- **Single-node, not load-tested.** No claim is made about throughput at real UPI transaction volumes (tens of thousands of TPS).
- **No integration with real payment rails, KYC data, or device-attestation SDKs** — this scores a fixed set of 5 behavioral features computed from a toy schema.

## 📄 License

MIT License - see [LICENSE](LICENSE) file.

---

**Questions?** This is built as an internship project, so ask yourself: "Can I explain each line of this code in an interview?" If the answer is no, dig deeper.
