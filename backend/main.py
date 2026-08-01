"""FastAPI application entry point for BankingAI."""

import json
import os
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from backend.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from backend.chatbot import get_chat_response
from backend.database import _is_postgres, _prepare_query, get_connection, init_db
from backend.ml_service import (
    get_fraud_explanation,
    get_loan_explanation,
    predict_fraud,
    predict_loan,
)
from backend.schemas import (
    ChatRequest,
    ChatResponse,
    FraudPredictionRequest,
    LoanPredictionRequest,
    PredictionResponse,
    TokenResponse,
    UserLogin,
    UserRegister,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = FastAPI(
    title="BankingAI",
    description="Loan prediction, fraud detection, and AI chatbot",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.path.join(BASE_DIR, "static")
frontend_dir = os.path.join(BASE_DIR, "frontend")
templates_dir = os.path.join(BASE_DIR, "templates")

if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
if os.path.isdir(frontend_dir):
    app.mount("/frontend", StaticFiles(directory=frontend_dir), name="frontend")

templates = Jinja2Templates(directory=templates_dir)

security = HTTPBearer(auto_error=False)


@app.on_event("startup")
def startup():
    init_db()


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return payload


def get_user_id(payload: dict) -> int:
    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return int(user_id)


# --- Page Routes ---

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/loan", response_class=HTMLResponse)
async def loan_page(request: Request):
    return templates.TemplateResponse("loan.html", {"request": request})


@app.get("/fraud", response_class=HTMLResponse)
async def fraud_page(request: Request):
    return templates.TemplateResponse("fraud.html", {"request": request})


@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})


@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    return templates.TemplateResponse("history.html", {"request": request})


# --- API Routes ---

@app.post("/register", response_model=TokenResponse)
async def register(user: UserRegister):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            _prepare_query("SELECT id FROM users WHERE username = ? OR email = ?", _is_postgres()),
            (user.username, user.email),
        )
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Username or email already exists")

        password_hash = hash_password(user.password)
        cursor.execute(
            _prepare_query(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                _is_postgres(),
            ),
            (user.username, user.email, password_hash),
        )
        conn.commit()
        user_id = cursor.lastrowid

    token = create_access_token({"sub": user.username, "user_id": user_id})
    return TokenResponse(access_token=token, username=user.username)


@app.post("/login", response_model=TokenResponse)
async def login(user: UserLogin):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            _prepare_query("SELECT id, password_hash FROM users WHERE username = ?", _is_postgres()),
            (user.username,),
        )
        row = cursor.fetchone()

    if row is None or not verify_password(user.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token({"sub": user.username, "user_id": row["id"]})
    return TokenResponse(access_token=token, username=user.username)


@app.post("/predict-loan", response_model=PredictionResponse)
async def predict_loan_endpoint(
    data: LoanPredictionRequest,
    payload: Annotated[dict, Depends(get_current_user)],
):
    user_id = get_user_id(payload)
    input_dict = data.model_dump()

    try:
        label, probability = predict_loan(input_dict)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    status_text = "Approved" if label == "Y" else "Rejected"
    message = get_loan_explanation(label, probability, input_dict)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            _prepare_query(
                "INSERT INTO loan_history (user_id, input_data, prediction, probability) VALUES (?, ?, ?, ?)",
                _is_postgres(),
            ),
            (user_id, json.dumps(input_dict), status_text, probability),
        )
        conn.commit()

    return PredictionResponse(
        prediction=status_text,
        probability=probability,
        message=message,
    )


@app.post("/predict-fraud", response_model=PredictionResponse)
async def predict_fraud_endpoint(
    data: FraudPredictionRequest,
    payload: Annotated[dict, Depends(get_current_user)],
):
    user_id = get_user_id(payload)
    input_dict = data.model_dump()

    try:
        prediction, probability = predict_fraud(input_dict)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    message = get_fraud_explanation(prediction, probability)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            _prepare_query(
                "INSERT INTO fraud_history (user_id, input_data, prediction, probability) VALUES (?, ?, ?, ?)",
                _is_postgres(),
            ),
            (user_id, json.dumps(input_dict), prediction, probability),
        )
        conn.commit()

    return PredictionResponse(
        prediction=prediction,
        probability=probability,
        message=message,
    )


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    data: ChatRequest,
    payload: Annotated[dict, Depends(get_current_user)],
):
    user_id = get_user_id(payload)
    response_text = await get_chat_response(data.message, data.context)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            _prepare_query(
                "INSERT INTO chat_history (user_id, message, response) VALUES (?, ?, ?)",
                _is_postgres(),
            ),
            (user_id, data.message, response_text),
        )
        conn.commit()

    return ChatResponse(response=response_text)


@app.get("/api/dashboard")
async def dashboard_data(payload: Annotated[dict, Depends(get_current_user)]):
    user_id = get_user_id(payload)

    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            _prepare_query(
                "SELECT prediction, probability, created_at FROM loan_history "
                "WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
                _is_postgres(),
            ),
            (user_id,),
        )
        loan_history = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            _prepare_query(
                "SELECT prediction, probability, created_at FROM fraud_history "
                "WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
                _is_postgres(),
            ),
            (user_id,),
        )
        fraud_history = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            _prepare_query(
                "SELECT message, response, created_at FROM chat_history "
                "WHERE user_id = ? ORDER BY created_at DESC LIMIT 5",
                _is_postgres(),
            ),
            (user_id,),
        )
        chat_history = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            _prepare_query("SELECT COUNT(*) as count FROM loan_history WHERE user_id = ?", _is_postgres()),
            (user_id,),
        )
        total_loans = cursor.fetchone()["count"]

        cursor.execute(
            _prepare_query("SELECT COUNT(*) as count FROM fraud_history WHERE user_id = ?", _is_postgres()),
            (user_id,),
        )
        total_fraud = cursor.fetchone()["count"]

        cursor.execute(
            _prepare_query(
                "SELECT COUNT(*) as count FROM loan_history WHERE user_id = ? AND prediction = 'Approved'",
                _is_postgres(),
            ),
            (user_id,),
        )
        approved_loans = cursor.fetchone()["count"]

        cursor.execute(
            _prepare_query(
                "SELECT COUNT(*) as count FROM fraud_history WHERE user_id = ? AND prediction = 'Fraud'",
                _is_postgres(),
            ),
            (user_id,),
        )
        fraud_detected = cursor.fetchone()["count"]

    return {
        "stats": {
            "total_loans": total_loans,
            "total_fraud_checks": total_fraud,
            "approved_loans": approved_loans,
            "fraud_detected": fraud_detected,
        },
        "loan_history": loan_history,
        "fraud_history": fraud_history,
        "chat_history": chat_history,
    }


@app.get("/api/history")
async def full_history(payload: Annotated[dict, Depends(get_current_user)]):
    user_id = get_user_id(payload)

    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            _prepare_query(
                "SELECT id, input_data, prediction, probability, created_at FROM loan_history "
                "WHERE user_id = ? ORDER BY created_at DESC",
                _is_postgres(),
            ),
            (user_id,),
        )
        loans = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            _prepare_query(
                "SELECT id, input_data, prediction, probability, created_at FROM fraud_history "
                "WHERE user_id = ? ORDER BY created_at DESC",
                _is_postgres(),
            ),
            (user_id,),
        )
        frauds = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            _prepare_query(
                "SELECT id, message, response, created_at FROM chat_history "
                "WHERE user_id = ? ORDER BY created_at DESC",
                _is_postgres(),
            ),
            (user_id,),
        )
        chats = [dict(row) for row in cursor.fetchall()]

    return {"loans": loans, "frauds": frauds, "chats": chats}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
