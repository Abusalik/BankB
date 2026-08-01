document.addEventListener("DOMContentLoaded", async () => {
    requireAuth();

    document.querySelectorAll(".tab-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
            document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
            btn.classList.add("active");
            document.getElementById(btn.dataset.tab).classList.add("active");
        });
    });

    try {
        const data = await API.get("/api/history");
        if (!data) return;

        renderLoanHistory(data.loans);
        renderFraudHistory(data.frauds);
        renderChatHistory(data.chats);
    } catch (err) {
        console.error("History load error:", err);
    }
});

function renderLoanHistory(loans) {
    const tbody = document.getElementById("loanHistoryBody");
    if (!loans.length) {
        tbody.innerHTML = '<tr><td colspan="4"><div class="empty-state"><p>No loan predictions yet</p></div></td></tr>';
        return;
    }
    tbody.innerHTML = loans.map((row) => `
        <tr>
            <td>${formatDate(row.created_at)}</td>
            <td><span class="badge ${row.prediction === "Approved" ? "badge-success" : "badge-danger"}">${row.prediction}</span></td>
            <td>${(row.probability * 100).toFixed(1)}%</td>
            <td>${formatLoanInput(row.input_data)}</td>
        </tr>
    `).join("");
}

function renderFraudHistory(frauds) {
    const tbody = document.getElementById("fraudHistoryBody");
    if (!frauds.length) {
        tbody.innerHTML = '<tr><td colspan="4"><div class="empty-state"><p>No fraud checks yet</p></div></td></tr>';
        return;
    }
    tbody.innerHTML = frauds.map((row) => {
        const input = JSON.parse(row.input_data);
        return `
        <tr>
            <td>${formatDate(row.created_at)}</td>
            <td><span class="badge ${row.prediction === "Fraud" ? "badge-danger" : "badge-success"}">${row.prediction}</span></td>
            <td>${(row.probability * 100).toFixed(1)}%</td>
            <td>Amount: $${input.amount?.toFixed(2) || "N/A"}</td>
        </tr>`;
    }).join("");
}

function renderChatHistory(chats) {
    const container = document.getElementById("chatHistoryList");
    if (!chats.length) {
        container.innerHTML = '<div class="empty-state"><p>No chat messages yet</p></div>';
        return;
    }
    container.innerHTML = chats.map((row) => `
        <div class="card" style="margin-bottom: 1rem;">
            <p style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.5rem;">${formatDate(row.created_at)}</p>
            <p><strong>You:</strong> ${row.message}</p>
            <p style="margin-top: 0.5rem;"><strong>AI:</strong> ${row.response}</p>
        </div>
    `).join("");
}

function formatLoanInput(inputStr) {
    const d = JSON.parse(inputStr);
    return `$${d.loan_amount || "N/A"} | Income: $${d.applicant_income || "N/A"}`;
}
