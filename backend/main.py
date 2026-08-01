"""FastAPI application entry point for BankingAI."""

import json
import logging
import os
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
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

allowed_origins = [
    os.getenv("FRONTEND_URL", "").rstrip("/"),
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
allowed_origins = [origin for origin in allowed_origins if origin]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.onrender\.com",
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
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bankingai")


@app.on_event("startup")
def startup():
    init_db()


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"success": False, "message": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s: %s", request.url.path, exc)
    err_msg = str(exc) or "Internal Server Error"
    return JSONResponse(status_code=500, content={"success": False, "detail": err_msg, "message": err_msg})


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info("%s %s", request.method, request.url.path)
    response = await call_next(request)
    return response


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


def _format_row(row) -> dict:
    if not row:
        return {}
    d = dict(row)
    if "created_at" in d and d["created_at"] is not None:
        d["created_at"] = str(d["created_at"])
    return d


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
        if _is_postgres():
            cursor.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) RETURNING id",
                (user.username, user.email, password_hash),
            )
            row = cursor.fetchone()
            user_id = row["id"] if isinstance(row, dict) else row[0]
        else:
            cursor.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                (user.username, user.email, password_hash),
            )
            user_id = cursor.lastrowid
        conn.commit()

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

    if row is None or not verify_password(user.password, row["password_hash"] if isinstance(row, dict) else row[1]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    user_id = row["id"] if isinstance(row, dict) else row[0]
    token = create_access_token({"sub": user.username, "user_id": user_id})
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
        loan_history = [_format_row(row) for row in cursor.fetchall()]

        cursor.execute(
            _prepare_query(
                "SELECT prediction, probability, created_at FROM fraud_history "
                "WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
                _is_postgres(),
            ),
            (user_id,),
        )
        fraud_history = [_format_row(row) for row in cursor.fetchall()]

        cursor.execute(
            _prepare_query(
                "SELECT message, response, created_at FROM chat_history "
                "WHERE user_id = ? ORDER BY created_at DESC LIMIT 5",
                _is_postgres(),
            ),
            (user_id,),
        )
        chat_history = [_format_row(row) for row in cursor.fetchall()]

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
        loans = [_format_row(row) for row in cursor.fetchall()]

        cursor.execute(
            _prepare_query(
                "SELECT id, input_data, prediction, probability, created_at FROM fraud_history "
                "WHERE user_id = ? ORDER BY created_at DESC",
                _is_postgres(),
            ),
            (user_id,),
        )
        frauds = [_format_row(row) for row in cursor.fetchall()]

        cursor.execute(
            _prepare_query(
                "SELECT id, message, response, created_at FROM chat_history "
                "WHERE user_id = ? ORDER BY created_at DESC",
                _is_postgres(),
            ),
            (user_id,),
        )
        chats = [_format_row(row) for row in cursor.fetchall()]

    return {"loans": loans, "frauds": frauds, "chats": chats}


@app.get("/api/health")
async def health_check():
    """Diagnostic endpoint to verify HF_TOKEN and API connectivity."""
    import httpx
    from backend.chatbot import get_token

    hf_token = get_token()
    result = {
        "status": "ok",
        "hf_token_set": bool(hf_token),
        "hf_token_prefix": hf_token[:8] + "..." if hf_token else "(empty)",
        "hf_token_length": len(hf_token),
        "database": "postgres" if _is_postgres() else "sqlite",
    }

    if hf_token:
        test_model = "mistralai/Mistral-7B-Instruct-v0.2"
        try:
            headers = {
                "Authorization": f"Bearer {hf_token}",
                "Content-Type": "application/json",
                "x-wait-for-model": "true",
            }
            payload = {
                "inputs": "<s>[INST] Say hello in one sentence. [/INST]",
                "parameters": {"max_new_tokens": 20, "return_full_text": False},
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(
                    f"https://api-inference.huggingface.co/models/{test_model}",
                    json=payload,
                    headers=headers,
                )
                result["hf_api_model"] = test_model
                result["hf_api_status"] = res.status_code
                result["hf_api_response"] = res.text[:300]
        except Exception as err:
            result["hf_api_status"] = "connection_error"
            result["hf_api_response"] = str(err)
    else:
        result["hf_api_status"] = "skipped"
        result["hf_api_response"] = "No HF_TOKEN configured"

    return result

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
