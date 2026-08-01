document.addEventListener("DOMContentLoaded", () => {
    requireAuth();

    const form = document.getElementById("loanForm");
    if (!form) return;

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        hideAlert("alertBox");

        const payload = {
            gender: document.getElementById("gender").value,
            married: document.getElementById("married").value,
            dependents: document.getElementById("dependents").value,
            education: document.getElementById("education").value,
            self_employed: document.getElementById("selfEmployed").value,
            applicant_income: parseFloat(document.getElementById("applicantIncome").value),
            coapplicant_income: parseFloat(document.getElementById("coapplicantIncome").value),
            loan_amount: parseFloat(document.getElementById("loanAmount").value),
            loan_amount_term: parseFloat(document.getElementById("loanTerm").value),
            credit_history: parseFloat(document.getElementById("creditHistory").value),
            property_area: document.getElementById("propertyArea").value,
        };

        const btn = form.querySelector("button[type=submit]");
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Predicting...';

        try {
            const result = await API.post("/predict-loan", payload);
            showResult(result);
        } catch (err) {
            showAlert("alertBox", err.message);
        } finally {
            btn.disabled = false;
            btn.textContent = "Predict Loan Approval";
        }
    });
});

function showResult(result) {
    const box = document.getElementById("resultBox");
    const isApproved = result.prediction === "Approved";

    box.className = `result-box show ${isApproved ? "approved" : "rejected"}`;
    box.innerHTML = `
        <h3>${isApproved ? "Loan Approved" : "Loan Rejected"}</h3>
        <p><strong>Confidence:</strong> ${(result.probability * 100).toFixed(1)}%</p>
        <p>${result.message}</p>
    `;

    localStorage.setItem("lastLoanPrediction", JSON.stringify(result));
}
