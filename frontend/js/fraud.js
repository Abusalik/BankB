document.addEventListener("DOMContentLoaded", () => {
    requireAuth();

    const form = document.getElementById("fraudForm");
    if (!form) return;

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        hideAlert("alertBox");

        const payload = {
            time: parseFloat(document.getElementById("time").value),
            amount: parseFloat(document.getElementById("amount").value),
        };

        for (let i = 1; i <= 28; i++) {
            const el = document.getElementById(`v${i}`);
            payload[`v${i}`] = el ? parseFloat(el.value) || 0 : 0;
        }

        const btn = form.querySelector("button[type=submit]");
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Analyzing...';

        try {
            const result = await API.post("/predict-fraud", payload);
            showResult(result);
        } catch (err) {
            showAlert("alertBox", err.message);
        } finally {
            btn.disabled = false;
            btn.textContent = "Detect Fraud";
        }
    });
});

function showResult(result) {
    const box = document.getElementById("resultBox");
    const isFraud = result.prediction === "Fraud";

    box.className = `result-box show ${isFraud ? "fraud" : "legitimate"}`;
    box.innerHTML = `
        <h3>${isFraud ? "Fraud Detected" : "Legitimate Transaction"}</h3>
        <p><strong>Risk Score:</strong> ${(result.probability * 100).toFixed(1)}%</p>
        <p>${result.message}</p>
    `;

    localStorage.setItem("lastFraudPrediction", JSON.stringify(result));
}
