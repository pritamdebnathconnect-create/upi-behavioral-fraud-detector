# Quick Start Guide

## Prerequisites
- Python 3.8+
- pip

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 2: Run the Demo (Recommended First)

```bash
python demo.py
```

This will:
1. Create a fresh database
2. Generate synthetic test data for 3 test users
3. Score 7 different scenarios showing how the system works
4. Show you how each feature contributes to the final score

**Expected output:** Shows decisions for normal transactions, new payee fraud, high amount fraud, night payments, etc.

## Step 3: Run the Test Suite

```bash
pytest test_fraud_detector.py -v
```

This runs ~15 tests covering:
- Feature extraction for each of the 5 signals
- Scoring logic (normal, medium, high risk)
- End-to-end flows

**Expected result:** All tests pass ✓

## Step 4: Start the API Server

```bash
python main.py
```

Server runs on `http://localhost:8000`

### Test the API

In another terminal:

```bash
# Score a normal transaction
curl -X POST http://localhost:8000/score \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "payee_id": "known_payee",
    "amount": 5000,
    "device_id": "device_1"
  }'

# Should return score ~0.2-0.3 with decision "ALLOW"
```

```bash
# Score a suspicious transaction (new payee, high amount, night time)
curl -X POST http://localhost:8000/score \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "payee_id": "unknown_payee",
    "amount": 50000,
    "device_id": "device_1"
  }'

# Should return score ~0.7+ with decision "SHOW_CONFIRMATION" or "REQUIRE_BIOMETRIC"
```

## File Guide

| File | What it does | Read if... |
|------|-------------|-----------|
| `models.py` | Database schema | You want to understand the data model |
| `feature_extractor.py` | Computes behavioral signals | You want to see how features are extracted |
| `scorer.py` | Combines features into a score | You want to understand the scoring logic |
| `main.py` | FastAPI app and endpoints | You want to integrate this into a backend |
| `test_data.py` | Generates synthetic test data | You need more test users |
| `test_fraud_detector.py` | Test cases | You want to verify correctness |
| `demo.py` | Interactive walkthrough | You want to see the system in action |

## Database

By default, the system uses SQLite (`fraud_detector.db`).

To use PostgreSQL instead:
1. Create a database: `createdb fraud_detector`
2. Set environment variable: `export DATABASE_URL="postgresql://user:password@localhost/fraud_detector"`
3. Run the app

## Next Steps

### Phase 1 (What you just built):
✅ Single-service, MVP fraud detection

### Phase 2 (Coming weeks 5-6):
- [ ] Add Redis caching for user profiles
- [ ] Implement hourly batch job to recompute profiles
- [ ] Add Prometheus metrics for monitoring
- [ ] Set up production threshold tuning

### Phase 3 (Weeks 7-8):
- [ ] Dashboard to view recent decisions
- [ ] False positive analysis
- [ ] User feedback loop (did the user confirm/cancel?)

## Troubleshooting

**"ModuleNotFoundError: No module named 'fastapi'"**
→ Run `pip install -r requirements.txt`

**"SQLAlchemy import error"**
→ Make sure you're in the fraud-detector directory and have a virtual environment

**"Tests fail with sqlite error"**
→ Delete `fraud_detector.db` and try again: `rm fraud_detector.db && pytest test_fraud_detector.py -v`

**"Port 8000 already in use"**
→ Change the port in `main.py`: `uvicorn.run(app, host="0.0.0.0", port=8001)`

## Key Concepts to Understand

**Before moving on, make sure you can answer:**

1. Why can't we reverse a UPI transaction?
2. What's the difference between APP fraud and account compromise fraud?
3. Why does a "new payee" feature matter more than credentials?
4. How would you detect a mule account cluster?
5. What's a better metric than accuracy for imbalanced fraud detection?

If you can't answer these, re-read the README and ask questions.

---

**Good luck! 🚀**
