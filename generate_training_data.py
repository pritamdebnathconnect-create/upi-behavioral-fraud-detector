"""
Generate a labeled dataset for training the ML fraud model.

Unlike test_data.py (which populates the live transactions table for demo purposes),
this script generates a standalone (features -> label) dataset for model training.

We simulate two populations:
  1. NORMAL transactions: consistent with the user's own history (low anomaly scores)
  2. FRAUD transactions: APP-fraud-style (new payee, high amount, odd time, new device)

Each transaction is converted into the same 5 features your rule engine already
computes, so the ML model is a drop-in replacement for FraudScorer.
"""

import numpy as np
import pandas as pd

np.random.seed(42)

FEATURE_NAMES = ["new_payee", "amount_deviation", "velocity", "time_anomaly", "device_mismatch"]


def generate_normal_sample(n: int) -> pd.DataFrame:
    """
    Normal transactions: mostly low anomaly scores, with realistic noise.
    Real users occasionally DO pay a new payee, or transact at odd hours,
    without it being fraud -- that noise is what makes this a hard problem.
    """
    data = {
        "new_payee": np.random.choice([0, 1], size=n, p=[0.85, 0.15]),           # 15% legit new-payee payments
        "amount_deviation": np.clip(np.random.exponential(0.15, size=n), 0, 1),   # mostly small deviations
        "velocity": np.clip(np.random.exponential(0.08, size=n), 0, 1),           # rarely bursts
        "time_anomaly": np.random.choice([0, 0.5, 0.9], size=n, p=[0.88, 0.09, 0.03]),
        "device_mismatch": np.random.choice([0, 0.3, 0.7], size=n, p=[0.80, 0.15, 0.05]),
    }
    df = pd.DataFrame(data)
    df["is_fraud"] = 0
    return df


def generate_fraud_sample(n: int) -> pd.DataFrame:
    """
    APP-fraud-style transactions: near-always a new payee, usually a large/odd
    amount, often at odd hours, sometimes a new device. Not every signal fires
    every time -- that's realistic and is what makes a pure rule threshold noisy.
    """
    data = {
        "new_payee": np.random.choice([0, 1], size=n, p=[0.05, 0.95]),            # almost always new payee
        "amount_deviation": np.clip(np.random.beta(4, 2, size=n), 0, 1),          # skewed high
        "velocity": np.clip(np.random.beta(2, 4, size=n), 0, 1),                  # moderate, not always
        "time_anomaly": np.random.choice([0, 0.5, 0.9], size=n, p=[0.35, 0.25, 0.40]),
        "device_mismatch": np.random.choice([0, 0.3, 0.7], size=n, p=[0.45, 0.25, 0.30]),
    }
    df = pd.DataFrame(data)
    df["is_fraud"] = 1
    return df


def generate_dataset(total_n: int = 20000, fraud_rate: float = 0.03) -> pd.DataFrame:
    """
    Build the full labeled dataset at a realistic fraud rate.
    Default 3% is deliberately higher than real-world UPI fraud rates
    (which are well under 1%) so the model has enough positive examples
    to learn from in a small student-project dataset. Document this
    choice explicitly in your write-up -- it's a real limitation.
    """
    n_fraud = int(total_n * fraud_rate)
    n_normal = total_n - n_fraud

    normal_df = generate_normal_sample(n_normal)
    fraud_df = generate_fraud_sample(n_fraud)

    df = pd.concat([normal_df, fraud_df], ignore_index=True)

    # Assign a synthetic day index 0-59 so we can do a time-based split later,
    # mirroring how you'd split real transaction data by date, not randomly.
    df["day"] = np.random.randint(0, 60, size=len(df))

    # Shuffle row order (but day column preserves the time signal for splitting)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)

    return df


if __name__ == "__main__":
    df = generate_dataset()
    df.to_csv("training_data.csv", index=False)

    print(f"Generated {len(df)} labeled transactions")
    print(f"Fraud: {df['is_fraud'].sum()} ({df['is_fraud'].mean()*100:.2f}%)")
    print(f"Normal: {(df['is_fraud']==0).sum()} ({(1-df['is_fraud'].mean())*100:.2f}%)")
    print(f"\nSaved to training_data.csv")
    print(f"\nFeature ranges:")
    print(df[FEATURE_NAMES].describe())
