"""AI Chatbot using Hugging Face Inference API with local fallback."""

import os

import httpx

HF_API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2"
HF_TOKEN = os.getenv("HF_TOKEN", "")

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


async def get_chat_response(message: str, context: dict | None = None) -> str:
    """Get chatbot response from Hugging Face or local fallback."""
    if not HF_TOKEN:
        return _local_response(message, context)

    system_prompt = (
        "You are BankingAI, a helpful banking assistant. "
        "Explain loan and fraud predictions clearly. "
        "Answer banking FAQs concisely. "
        "Suggest practical ways to improve loan approval chances. "
        "Keep responses under 150 words."
    )

    context_text = ""
    if context:
        context_text = f"\nUser context: {context}"

    payload = {
        "inputs": (
            f"<s>[INST] {system_prompt}{context_text}\n\n"
            f"User: {message} [/INST]"
        ),
        "parameters": {"max_new_tokens": 200, "temperature": 0.7},
    }

    headers = {"Authorization": f"Bearer {HF_TOKEN}"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(HF_API_URL, json=payload, headers=headers)
            if response.status_code == 200:
                result = response.json()
                if isinstance(result, list) and result:
                    text = result[0].get("generated_text", "")
                    if "[/INST]" in text:
                        return text.split("[/INST]")[-1].strip()
                    return text.strip()
            return _local_response(message, context)
    except Exception:
        return _local_response(message, context)
