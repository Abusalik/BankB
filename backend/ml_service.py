"""Machine learning inference service for loan and fraud models."""

import os
import pickle

import joblib
import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOAN_MODEL_PATH = os.path.join(BASE_DIR, "models", "loan_model.pkl")
FRAUD_MODEL_PATH = os.path.join(BASE_DIR, "models", "fraud_model.pkl")

_loan_artifacts = None
_fraud_artifacts = None


def _load_loan_model():
    global _loan_artifacts
    if _loan_artifacts is None:
        if not os.path.exists(LOAN_MODEL_PATH):
            raise FileNotFoundError(
                f"Loan model not found at {LOAN_MODEL_PATH}. "
                "Run notebooks/loan_prediction.ipynb first."
            )
        _loan_artifacts = joblib.load(LOAN_MODEL_PATH)
    return _loan_artifacts


def _load_fraud_model():
    global _fraud_artifacts
    if _fraud_artifacts is None:
        if not os.path.exists(FRAUD_MODEL_PATH):
            raise FileNotFoundError(
                f"Fraud model not found at {FRAUD_MODEL_PATH}. "
                "Run notebooks/fraud_detection.ipynb first."
            )
        _fraud_artifacts = joblib.load(FRAUD_MODEL_PATH)
    return _fraud_artifacts


def predict_loan(data: dict) -> tuple[str, float]:
    """Predict loan approval status."""
    artifacts = _load_loan_model()
    model = artifacts["model"]
    encoders = artifacts["encoders"]
    feature_columns = artifacts["feature_columns"]

    row = {
        "Gender": data["gender"],
        "Married": data["married"],
        "Dependents": data["dependents"],
        "Education": data["education"],
        "Self_Employed": data["self_employed"],
        "ApplicantIncome": data["applicant_income"],
        "CoapplicantIncome": data["coapplicant_income"],
        "LoanAmount": data["loan_amount"],
        "Loan_Amount_Term": data["loan_amount_term"],
        "Credit_History": data["credit_history"],
        "Property_Area": data["property_area"],
    }

    df = pd.DataFrame([row])

    for col, encoder in encoders.items():
        if col in df.columns:
            df[col] = encoder.transform(df[col].astype(str))

    df = df[feature_columns]
    proba = model.predict_proba(df)[0]
    pred_idx = int(np.argmax(proba))
    label = artifacts["target_encoder"].inverse_transform([pred_idx])[0]
    probability = float(proba[pred_idx])

    return label, probability


def predict_fraud(data: dict) -> tuple[str, float]:
    """Predict credit card fraud."""
    artifacts = _load_fraud_model()
    model = artifacts["model"]
    scaler = artifacts["scaler"]
    feature_columns = artifacts["feature_columns"]

    row = {"Time": data["time"], "Amount": data["amount"]}
    for i in range(1, 29):
        row[f"V{i}"] = data.get(f"v{i}", 0.0)

    df = pd.DataFrame([row])[feature_columns]
    df_scaled = scaler.transform(df)
    proba = model.predict_proba(df_scaled)[0]
    fraud_prob = float(proba[1])
    prediction = "Fraud" if fraud_prob >= 0.5 else "Legitimate"

    return prediction, fraud_prob


def get_loan_explanation(label: str, probability: float, data: dict) -> str:
    """Generate a human-readable loan prediction explanation."""
    status = "Approved" if label == "Y" else "Rejected"
    tips = []

    if data.get("credit_history", 1) == 0:
        tips.append("Improve your credit history before reapplying.")
    if data.get("applicant_income", 0) < 3000:
        tips.append("Higher applicant income strengthens your application.")
    if data.get("loan_amount", 0) > 200:
        tips.append("Consider requesting a smaller loan amount.")

    tip_text = " ".join(tips) if tips else "Your profile looks balanced overall."

    return (
        f"Loan prediction: {status} (confidence: {probability:.1%}). "
        f"{tip_text}"
    )


def get_fraud_explanation(prediction: str, probability: float) -> str:
    """Generate a human-readable fraud prediction explanation."""
    if prediction == "Fraud":
        return (
            f"This transaction is flagged as potentially fraudulent "
            f"(risk score: {probability:.1%}). "
            "We recommend verifying the transaction with the cardholder."
        )
    return (
        f"This transaction appears legitimate "
        f"(fraud risk: {probability:.1%})."
    )
