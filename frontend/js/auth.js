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
            const data = await API.post("/login", { username, password });
            API.setAuth(data.access_token, data.username);
            window.location.href = "/dashboard";
        } catch (err) {
            showAlert("alertBox", err.message);
            btn.disabled = false;
            btn.textContent = "Sign In";
        }
    });
});
