document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("loginForm");
    if (!form) return;

    if (API.isAuthenticated()) {
        window.location.href = "/dashboard";
        return;
    }

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        hideAlert("alertBox");

        const username = document.getElementById("username").value.trim();
        const password = document.getElementById("password").value;

        const btn = form.querySelector("button[type=submit]");
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Signing in...';

        try {
            const response = await fetch("/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, password }),
            });

            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || "Login failed");

            API.setAuth(data.access_token, data.username);
            window.location.href = "/dashboard";
        } catch (err) {
            showAlert("alertBox", err.message);
            btn.disabled = false;
            btn.textContent = "Sign In";
        }
    });
});
