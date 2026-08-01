"""AI Chatbot using Hugging Face InferenceClient with local fallback."""

import asyncio
import logging
import os
from functools import partial

logger = logging.getLogger("bankingai")

# Models to try in order (small models that work on free serverless inference)
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


def _sync_hf_call(model_name: str, messages: list, hf_token: str) -> str | None:
    """Synchronous call using huggingface_hub InferenceClient."""
    try:
        from huggingface_hub import InferenceClient

        client = InferenceClient(model=model_name, token=hf_token, timeout=30)
        response = client.chat_completion(
            messages=messages,
            max_tokens=250,
            temperature=0.7,
        )
        text = response.choices[0].message.content.strip()
        if text:
            logger.info("HF InferenceClient (%s) success", model_name)
            return text
    except Exception as err:
        err_str = str(err)
        logger.warning("HF InferenceClient (%s) error: %s", model_name, err_str[:200])
    return None


def _sync_hf_text_generation(model_name: str, prompt: str, hf_token: str) -> str | None:
    """Synchronous call using huggingface_hub text_generation (fallback)."""
    try:
        from huggingface_hub import InferenceClient

        client = InferenceClient(model=model_name, token=hf_token, timeout=30)
        response = client.text_generation(
            prompt,
            max_new_tokens=250,
            temperature=0.7,
        )
        text = response.strip()
        if text:
            logger.info("HF text_generation (%s) success", model_name)
            return text
    except Exception as err:
        err_str = str(err)
        logger.warning("HF text_generation (%s) error: %s", model_name, err_str[:200])
    return None


def _sync_requests_fallback(prompt: str, hf_token: str) -> str | None:
    """Last-resort fallback using requests library directly."""
    import requests

    for model_name in HF_MODELS:
        try:
            url = f"https://api-inference.huggingface.co/models/{model_name}"
            headers = {
                "Authorization": f"Bearer {hf_token}",
                "Content-Type": "application/json",
                "x-wait-for-model": "true",
            }
            payload = {
                "inputs": prompt,
                "parameters": {"max_new_tokens": 250, "temperature": 0.7, "return_full_text": False},
            }
            res = requests.post(url, json=payload, headers=headers, timeout=30)
            logger.info("requests fallback (%s) status=%s", model_name, res.status_code)
            if res.status_code == 200:
                result = res.json()
                if isinstance(result, list) and result:
                    text = result[0].get("generated_text", "").strip()
                    if text:
                        return text
        except Exception as err:
            logger.warning("requests fallback (%s) error: %s", model_name, str(err)[:200])
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

    # Strategy 1: Try chat_completion via InferenceClient (each model)
    for model_name in HF_MODELS:
        result = await loop.run_in_executor(
            None, partial(_sync_hf_call, model_name, messages, hf_token)
        )
        if result:
            return result

    # Strategy 2: Try text_generation via InferenceClient
    prompt = f"<s>[INST] {system_prompt}{context_text}\n\nUser: {message} [/INST]"
    for model_name in HF_MODELS[:2]:  # Try first 2 models
        result = await loop.run_in_executor(
            None, partial(_sync_hf_text_generation, model_name, prompt, hf_token)
        )
        if result:
            return result

    # Strategy 3: Try raw requests library (different HTTP stack from httpx)
    result = await loop.run_in_executor(
        None, partial(_sync_requests_fallback, prompt, hf_token)
    )
    if result:
        return result

    logger.info("All HF API strategies failed. Falling back to local FAQ response.")
    return _local_response(message, context)
