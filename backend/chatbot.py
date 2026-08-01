"""AI Chatbot using Hugging Face Inference API with local fallback."""

import logging
import os
import httpx

logger = logging.getLogger("bankingai")

HF_ROUTER_URL = "https://router.huggingface.co/hf-inference/v1/chat/completions"

HF_MODELS = [
    "Qwen/Qwen2.5-7B-Instruct",
    "meta-llama/Llama-3.2-3B-Instruct",
    "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
    "HuggingFaceH4/zephyr-7b-beta",
    "mistralai/Mistral-7B-Instruct-v0.3",
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


async def get_chat_response(message: str, context: dict | None = None) -> str:
    """Get chatbot response from Hugging Face API or local fallback."""
    hf_token = get_token()

    if not hf_token:
        logger.info("HF_TOKEN environment variable is not set. Using local FAQ fallback.")
        return _local_response(message, context)

    system_prompt = (
        "You are BankingAI, a helpful banking assistant. "
        "Explain loan and fraud predictions clearly. "
        "Answer banking FAQs concisely. "
        "Suggest practical ways to improve loan approval chances. "
        "Keep responses under 150 words."
    )

    context_text = f"\nUser Context: {context}" if context else ""

    headers = {
        "Authorization": f"Bearer {hf_token}",
        "Content-Type": "application/json",
        "x-wait-for-model": "true",
    }

    last_error_status = None
    last_error_text = ""

    # Attempt 1: Hugging Face Serverless Router Chat Completions API with fallback models
    for model_name in HF_MODELS:
        router_payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{message}{context_text}"},
            ],
            "max_tokens": 200,
            "temperature": 0.7,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(HF_ROUTER_URL, json=router_payload, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        content = data["choices"][0].get("message", {}).get("content", "").strip()
                        if content:
                            return content
                else:
                    last_error_status = res.status_code
                    last_error_text = res.text[:200]
                    logger.warning(
                        "HuggingFace Router API (%s) status %s: %s",
                        model_name,
                        res.status_code,
                        res.text[:200],
                    )
        except Exception as err:
            logger.warning("HuggingFace Router API (%s) error: %s", model_name, err)

    # Attempt 2: Direct Model Inference endpoints
    for model_name in HF_MODELS:
        direct_url = f"https://api-inference.huggingface.co/models/{model_name}"
        direct_payload = {
            "inputs": f"<s>[INST] {system_prompt}{context_text}\n\nUser Question: {message} [/INST]",
            "parameters": {"max_new_tokens": 200, "temperature": 0.7},
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(direct_url, json=direct_payload, headers=headers)
                if res.status_code == 200:
                    result = res.json()
                    if isinstance(result, list) and result:
                        text = result[0].get("generated_text", "")
                        if "[/INST]" in text:
                            text = text.split("[/INST]")[-1]
                        text = text.strip()
                        if text:
                            return text
                else:
                    last_error_status = res.status_code
                    last_error_text = res.text[:200]
                    logger.warning(
                        "HuggingFace Direct API (%s) status %s: %s",
                        model_name,
                        res.status_code,
                        res.text[:200],
                    )
        except Exception as err:
            logger.warning("HuggingFace Direct API (%s) error: %s", model_name, err)

    # Diagnostic feedback if token was supplied but rejected by HuggingFace
    if last_error_status == 401:
        return (
            "[HF Token Error]: The provided HF_TOKEN was rejected by Hugging Face (401 Unauthorized). "
            "Please verify that your token starts with 'hf_' and has read permissions. "
            "Fallback response: " + _local_response(message, context)
        )
    elif last_error_status == 403:
        return (
            "[HF Permission Error]: The provided HF_TOKEN lacks access to Hugging Face models (403 Forbidden). "
            "Fallback response: " + _local_response(message, context)
        )

    logger.info("HuggingFace API calls unfulfilled. Falling back to local FAQ response.")
    return _local_response(message, context)
