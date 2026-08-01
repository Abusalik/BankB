/**
 * BankingAI - Shared JavaScript utilities
 */

const API = {
    token: localStorage.getItem("token"),
    username: localStorage.getItem("username"),

    setAuth(token, username) {
        this.token = token;
        this.username = username;
        localStorage.setItem("token", token);
        localStorage.setItem("username", username);
    },

    clearAuth() {
        this.token = null;
        this.username = null;
        localStorage.removeItem("token");
        localStorage.removeItem("username");
    },

    isAuthenticated() {
        return !!this.token;
    },

    headers() {
        return {
            "Content-Type": "application/json",
            Authorization: `Bearer ${this.token}`,
        };
    },

    async request(url, options = {}) {
        const response = await fetch(url, {
            ...options,
            headers: { ...this.headers(), ...options.headers },
        });

        if (response.status === 401) {
            this.clearAuth();
            window.location.href = "/";
            return null;
        }

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || "Request failed");
        }
        return data;
    },

    get(url) {
        return this.request(url);
    },

    post(url, body) {
        return this.request(url, {
            method: "POST",
            body: JSON.stringify(body),
        });
    },
};

function requireAuth() {
    if (!API.isAuthenticated()) {
        window.location.href = "/";
    }
}

function showAlert(elementId, message, type = "error") {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.className = `alert alert-${type}`;
    el.textContent = message;
    el.classList.remove("hidden");
}

function hideAlert(elementId) {
    const el = document.getElementById(elementId);
    if (el) el.classList.add("hidden");
}

function formatDate(dateStr) {
    const d = new Date(dateStr + "Z");
    return d.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function initSidebar() {
    const toggle = document.getElementById("menuToggle");
    const sidebar = document.getElementById("sidebar");

    if (toggle && sidebar) {
        toggle.addEventListener("click", () => sidebar.classList.toggle("open"));
    }

    const currentPath = window.location.pathname;
    document.querySelectorAll(".sidebar-nav a").forEach((link) => {
        if (link.getAttribute("href") === currentPath) {
            link.classList.add("active");
        }
    });

    const logoutBtn = document.getElementById("logoutBtn");
    if (logoutBtn) {
        logoutBtn.addEventListener("click", (e) => {
            e.preventDefault();
            API.clearAuth();
            window.location.href = "/";
        });
    }

    const userDisplay = document.getElementById("userDisplay");
    if (userDisplay) {
        userDisplay.textContent = API.username || "User";
    }
}

document.addEventListener("DOMContentLoaded", initSidebar);
