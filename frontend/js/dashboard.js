document.addEventListener("DOMContentLoaded", async () => {
    requireAuth();

    try {
        const data = await API.get("/api/dashboard");
        if (!data) return;

        document.getElementById("totalLoans").textContent = data.stats.total_loans;
        document.getElementById("totalFraud").textContent = data.stats.total_fraud_checks;
        document.getElementById("approvedLoans").textContent = data.stats.approved_loans;
        document.getElementById("fraudDetected").textContent = data.stats.fraud_detected;

        renderLoanTable(data.loan_history);
        renderFraudTable(data.fraud_history);
        renderCharts(data);
    } catch (err) {
        console.error("Dashboard load error:", err);
    }
});

function renderLoanTable(history) {
    const tbody = document.getElementById("loanTableBody");
    if (!history.length) {
        tbody.innerHTML = '<tr><td colspan="3" class="empty-state">No loan predictions yet</td></tr>';
        return;
    }
    tbody.innerHTML = history.map((row) => `
        <tr>
            <td>${formatDate(row.created_at)}</td>
            <td><span class="badge ${row.prediction === "Approved" ? "badge-success" : "badge-danger"}">${row.prediction}</span></td>
            <td>${(row.probability * 100).toFixed(1)}%</td>
        </tr>
    `).join("");
}

function renderFraudTable(history) {
    const tbody = document.getElementById("fraudTableBody");
    if (!history.length) {
        tbody.innerHTML = '<tr><td colspan="3" class="empty-state">No fraud checks yet</td></tr>';
        return;
    }
    tbody.innerHTML = history.map((row) => `
        <tr>
            <td>${formatDate(row.created_at)}</td>
            <td><span class="badge ${row.prediction === "Fraud" ? "badge-danger" : "badge-success"}">${row.prediction}</span></td>
            <td>${(row.probability * 100).toFixed(1)}%</td>
        </tr>
    `).join("");
}

function renderCharts(data) {
    const loanCtx = document.getElementById("loanChart");
    const fraudCtx = document.getElementById("fraudChart");

    if (loanCtx) {
        new Chart(loanCtx, {
            type: "doughnut",
            data: {
                labels: ["Approved", "Rejected"],
                datasets: [{
                    data: [
                        data.stats.approved_loans,
                        data.stats.total_loans - data.stats.approved_loans,
                    ],
                    backgroundColor: ["#27ae60", "#e74c3c"],
                    borderWidth: 0,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: "bottom" } },
            },
        });
    }

    if (fraudCtx) {
        new Chart(fraudCtx, {
            type: "doughnut",
            data: {
                labels: ["Legitimate", "Fraud"],
                datasets: [{
                    data: [
                        data.stats.total_fraud_checks - data.stats.fraud_detected,
                        data.stats.fraud_detected,
                    ],
                    backgroundColor: ["#3498db", "#e74c3c"],
                    borderWidth: 0,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: "bottom" } },
            },
        });
    }
}
