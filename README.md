# BankingAI

An intelligent banking platform with **Loan Approval Prediction**, **Credit Card Fraud Detection**, **AI Chatbot**, and a premium web dashboard.

## Features

- **Loan Approval Prediction** — ML models (Logistic Regression, Random Forest, XGBoost)
- **Fraud Detection** — Random Forest & XGBoost on credit card transactions
- **AI Chatbot** — Hugging Face Inference API with local FAQ fallback
- **Authentication** — JWT-based register/login with SQLite
- **Dashboard** — Stats, charts, and prediction history

## Project Structure

```
BankingAI/
├── datasets/           # loan_prediction.csv, creditcard.csv
├── notebooks/          # Jupyter notebooks for model training
├── backend/            # FastAPI application
├── frontend/           # CSS & JavaScript
├── models/             # Saved ML models (.pkl)
├── database/           # SQLite database
├── static/             # Static assets
├── templates/          # HTML templates
├── scripts/            # Utility scripts
├── requirements.txt
└── README.md
```

## Setup

### 1. Create virtual environment

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Generate datasets (if not present)

```bash
python scripts/generate_datasets.py
```

### 4. Train models

Option A — Run notebooks:
```bash
jupyter notebook notebooks/
```

Option B — Run training script:
```bash
python scripts/train_models.py
```

This saves:
- `models/loan_model.pkl`
- `models/fraud_model.pkl`

### 5. (Optional) Hugging Face API

Set your Hugging Face token for the AI chatbot:

```bash
set HF_TOKEN=your_huggingface_token    # Windows
# export HF_TOKEN=your_huggingface_token  # macOS/Linux
```

Without a token, the chatbot uses a built-in FAQ fallback.

### 6. Start the server

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000** in your browser.

## API Endpoints

| Method | Endpoint        | Description              |
|--------|-----------------|--------------------------|
| POST   | `/register`     | Create new account       |
| POST   | `/login`        | Sign in                  |
| POST   | `/predict-loan` | Loan approval prediction |
| POST   | `/predict-fraud`| Fraud detection          |
| POST   | `/chat`         | AI chatbot               |
| GET    | `/api/dashboard`| Dashboard data           |
| GET    | `/api/history`  | Full activity history    |

All prediction and chat endpoints require a Bearer token from login/register.

## Pages

| Route         | Description          |
|---------------|----------------------|
| `/`           | Login                |
| `/register`   | Registration         |
| `/dashboard`  | Overview & charts    |
| `/loan`       | Loan prediction form |
| `/fraud`      | Fraud detection form |
| `/chat`       | AI chatbot           |
| `/history`    | Activity history     |

## Tech Stack

- **Backend:** Python, FastAPI, SQLite
- **ML:** scikit-learn, XGBoost, pandas
- **Frontend:** HTML, CSS, JavaScript, Chart.js
- **AI Chat:** Hugging Face Inference API
- **Notebooks:** Jupyter

## License

MIT
