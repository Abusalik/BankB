"""AI Chatbot using Hugging Face Inference API with local fallback."""

import logging
import os
import httpx

logger = logging.getLogger("bankingai")

# Direct inference API - works with free tier tokens
HF_API_BASE = "https://api-inference.huggingface.co/models"

# Small models that are warm and available on free serverless inference
HF_MODELS = [
    "mistralai/Mistral-7B-Instruct-v0.2",
    "meta-llama/Llama-3.2-3B-Instruct",
    "meta-llama/Meta-Llama-3-8B-Instruct",
    "HuggingFaceH4/zephyr-7b-beta",
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


async def _try_direct_inference(
    model_name: str, prompt: str, hf_token: str
) -> str | None:
    """Try the direct /models/ inference endpoint for a single model."""
    url = f"{HF_API_BASE}/{model_name}"
    headers = {
        "Authorization": f"Bearer {hf_token}",
        "Content-Type": "application/json",
        "x-wait-for-model": "true",
    }
    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": 250, "temperature": 0.7, "return_full_text": False},
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(url, json=payload, headers=headers)
            logger.info("HF Direct API (%s) status=%s", model_name, res.status_code)
            if res.status_code == 200:
                result = res.json()
                if isinstance(result, list) and result:
                    text = result[0].get("generated_text", "")
                    # Strip prompt echo if present
                    if "[/INST]" in text:
                        text = text.split("[/INST]")[-1]
                    text = text.strip()
                    if text:
                        return text
            elif res.status_code == 503:
                logger.info("HF model %s is loading, trying next...", model_name)
            else:
                logger.warning("HF Direct API (%s) %s: %s", model_name, res.status_code, res.text[:200])
    except Exception as err:
        logger.warning("HF Direct API (%s) error: %s", model_name, err)

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

    # Build the prompt in Mistral/Llama instruction format
    prompt = f"<s>[INST] {system_prompt}{context_text}\n\nUser: {message} [/INST]"

    # Try each model until one succeeds
    for model_name in HF_MODELS:
        result = await _try_direct_inference(model_name, prompt, hf_token)
        if result:
            return result

    logger.info("All HF API calls failed. Falling back to local FAQ response.")
    return _local_response(message, context)
