"""AI Chatbot using Hugging Face Inference Providers with local fallback."""

import asyncio
import logging
import os
from functools import partial

logger = logging.getLogger("bankingai")

# Models to try - these work with featherless-ai provider
HF_MODELS = [
    "mistralai/Mistral-7B-Instruct-v0.2",
    "HuggingFaceH4/zephyr-7b-beta",
    "meta-llama/Llama-3.2-3B-Instruct",
    "meta-llama/Meta-Llama-3-8B-Instruct",
]

BANKING_FAQ = {
    "interest rate": (
        "Our standard personal loan interest rates range from 8.5% to 14% APR, "
        "depending on credit score, income, and loan tenure."
    ),
    "minimum income": (
        "The minimum monthly income requirement for a personal loan is "
        "approximately $2,500 for salaried applicants."
    ),
    "credit score": (
        "A credit score above 700 significantly improves loan approval chances. "
        "Scores below 650 may require a co-applicant or collateral."
    ),
    "fraud": (
        "If you suspect fraud, contact our 24/7 helpline immediately and "
        "freeze your card through the mobile app."
    ),
    "documents": (
        "Required documents: valid ID, proof of income (last 3 payslips), "
        "bank statements (6 months), and address proof."
    ),
}


def _local_response(message: str, context: dict | None = None) -> str:
    """Rule-based fallback when Hugging Face API is unavailable."""
    msg = message.lower()

    for keyword, answer in BANKING_FAQ.items():
        if keyword in msg:
            return answer

    if any(w in msg for w in ["loan", "approve", "approval", "reject"]):
        if context and "loan_prediction" in context:
            lp = context["loan_prediction"]
            return (
                f"Based on your recent loan prediction ({lp.get('prediction', 'N/A')}), "
                f"I recommend maintaining a strong credit history, keeping debt-to-income "
                f"ratio below 40%, and ensuring stable employment for 6+ months."
            )
        return (
            "To improve loan approval chances: maintain good credit history, "
            "keep loan amount reasonable relative to income, add a co-applicant "
            "if possible, and choose shorter loan terms."
        )

    if any(w in msg for w in ["fraud", "suspicious", "transaction"]):
        if context and "fraud_prediction" in context:
            fp = context["fraud_prediction"]
            return (
                f"Your recent transaction was classified as {fp.get('prediction', 'N/A')} "
                f"with risk score {fp.get('probability', 0):.1%}. "
                "Monitor your account and enable transaction alerts."
            )
        return (
            "For fraud protection: enable SMS alerts, use two-factor authentication, "
            "never share OTPs, and report unrecognized transactions within 24 hours."
        )

    if any(w in msg for w in ["hello", "hi", "hey"]):
        return (
            "Hello! I'm BankingAI Assistant. I can explain loan and fraud predictions, "
            "answer banking FAQs, and suggest ways to improve your loan approval chances."
        )

    return (
        "I'm BankingAI Assistant. Ask me about loan predictions, fraud detection, "
        "interest rates, credit scores, required documents, or how to improve "
        "your loan approval chances."
    )


def get_token() -> str:
    """Check common environment variable keys for HuggingFace token."""
    for key in ["HF_TOKEN", "HB_TOKEN", "HUGGINGFACE_TOKEN", "HUGGING_FACE_TOKEN"]:
        val = os.getenv(key, "").strip().strip("'\"")
        if val:
            return val
    return ""


def _sync_featherless_call(model_name: str, messages: list, hf_token: str) -> str | None:
    """Use InferenceClient with provider='featherless-ai' (confirmed working)."""
    try:
        from huggingface_hub import InferenceClient

        client = InferenceClient(provider="featherless-ai", api_key=hf_token, timeout=30)
        response = client.chat_completion(
            model=model_name,
            messages=messages,
            max_tokens=250,
            temperature=0.7,
        )
        text = response.choices[0].message.content.strip()
        if text:
            logger.info("featherless-ai (%s) success", model_name)
            return text
    except Exception as err:
        logger.warning("featherless-ai (%s) error: %s", model_name, str(err)[:200])
    return None


def _sync_raw_router_call(model_name: str, messages: list, hf_token: str) -> str | None:
    """Direct HTTP to router.huggingface.co/featherless-ai (confirmed working)."""
    import requests

    url = "https://router.huggingface.co/featherless-ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {hf_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_name,
        "messages": messages,
        "max_tokens": 250,
        "temperature": 0.7,
        "stream": False,
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=30)
        logger.info("raw-router (%s) status=%s", model_name, res.status_code)
        if res.status_code == 200:
            data = res.json()
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            if text:
                return text
    except Exception as err:
        logger.warning("raw-router (%s) error: %s", model_name, str(err)[:200])
    return None


async def get_chat_response(message: str, context: dict | None = None) -> str:
    """Get chatbot response from Hugging Face API or local fallback."""
    hf_token = get_token()

    if not hf_token:
        logger.info("HF_TOKEN not set. Using local FAQ fallback.")
        return _local_response(message, context)

    system_prompt = (
        "You are BankingAI, a helpful banking assistant. "
        "Explain loan and fraud predictions clearly. "
        "Answer banking FAQs concisely. "
        "Suggest practical ways to improve loan approval chances. "
        "Keep responses under 150 words."
    )

    context_text = f"\nUser context: {context}" if context else ""

    messages = [
        {"role": "system", "content": system_prompt + context_text},
        {"role": "user", "content": message},
    ]

    loop = asyncio.get_event_loop()

    # Strategy 1: featherless-ai provider via InferenceClient (confirmed working)
    for model_name in HF_MODELS:
        result = await loop.run_in_executor(
            None, partial(_sync_featherless_call, model_name, messages, hf_token)
        )
        if result:
            return result

    # Strategy 2: Raw HTTP to router.huggingface.co/featherless-ai (confirmed working)
    for model_name in HF_MODELS:
        result = await loop.run_in_executor(
            None, partial(_sync_raw_router_call, model_name, messages, hf_token)
        )
        if result:
            return result

    logger.info("All HF API strategies failed. Falling back to local FAQ response.")
    return _local_response(message, context)
