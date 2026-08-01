document.addEventListener("DOMContentLoaded", () => {
    requireAuth();

    const form = document.getElementById("chatForm");
    const input = document.getElementById("chatInput");
    const messages = document.getElementById("chatMessages");

    if (!form) return;

    addBotMessage(
        "Hello! I'm BankingAI Assistant. Ask me about loan predictions, " +
        "fraud detection, interest rates, or how to improve your loan approval chances."
    );

    document.querySelectorAll(".suggestion-chip").forEach((chip) => {
        chip.addEventListener("click", () => {
            input.value = chip.textContent;
            form.dispatchEvent(new Event("submit"));
        });
    });

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const message = input.value.trim();
        if (!message) return;

        addUserMessage(message);
        input.value = "";

        const context = {};
        const lastLoan = localStorage.getItem("lastLoanPrediction");
        const lastFraud = localStorage.getItem("lastFraudPrediction");
        if (lastLoan) context.loan_prediction = JSON.parse(lastLoan);
        if (lastFraud) context.fraud_prediction = JSON.parse(lastFraud);

        try {
            const result = await API.post("/chat", { message, context });
            addBotMessage(result.response);
        } catch (err) {
            addBotMessage("Sorry, I couldn't process your request. Please try again.");
        }
    });
});

function addUserMessage(text) {
    const messages = document.getElementById("chatMessages");
    const div = document.createElement("div");
    div.className = "chat-message user";
    div.textContent = text;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
}

function addBotMessage(text) {
    const messages = document.getElementById("chatMessages");
    const div = document.createElement("div");
    div.className = "chat-message bot";
    div.textContent = text;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
}
