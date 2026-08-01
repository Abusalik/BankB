document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("registerForm");
    if (!form) return;

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        hideAlert("alertBox");

        const username = document.getElementById("username").value.trim();
        const email = document.getElementById("email").value.trim();
        const password = document.getElementById("password").value;
        const confirm = document.getElementById("confirmPassword").value;

        if (password !== confirm) {
            showAlert("alertBox", "Passwords do not match");
            return;
        }

        const btn = form.querySelector("button[type=submit]");
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Creating account...';

        try {
            const response = await fetch("/register", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, email, password }),
            });

            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || "Registration failed");

            API.setAuth(data.access_token, data.username);
            window.location.href = "/dashboard";
        } catch (err) {
            showAlert("alertBox", err.message);
            btn.disabled = false;
            btn.textContent = "Create Account";
        }
    });
});
