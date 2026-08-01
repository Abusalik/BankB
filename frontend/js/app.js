/**
 * BankingAI - Shared JavaScript utilities
 */

const API_BASE_URL = (() => {
    const configured = (window.BANKINGAI_CONFIG?.backendUrl || "").trim();
    if (configured) return configured.replace(/\/$/, "");
    const fallback = (window.__BACKEND_URL__ || "").trim();
    return fallback ? fallback.replace(/\/$/, "") : window.location.origin;
})();

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
        const backendUrl = API_BASE_URL.replace(/\/$/, "");
        const requestUrl = url.match(/^https?:\/\//i)
            ? url
            : `${backendUrl}${url}`;

        let response;
        try {
            response = await fetch(requestUrl, {
                ...options,
                headers: { ...this.headers(), ...options.headers },
            });
        } catch (fetchErr) {
            if (window.location.hostname.includes("onrender.com") && (!API_BASE_URL || API_BASE_URL === window.location.origin)) {
                throw new Error("Backend connection failed: BACKEND_URL environment variable is missing or invalid on Render. Set BACKEND_URL to your Render backend URL.");
            }
            throw new Error(`Unable to connect to backend at ${requestUrl}. Check server status.`);
        }

        if (response.status === 401) {
            this.clearAuth();
            window.location.href = "/";
            throw new Error("Session expired. Please sign in again.");
        }

        if (!response.ok && window.location.hostname.includes("onrender.com") && (API_BASE_URL === window.location.origin)) {
            throw new Error(`Endpoint ${url} (${response.status}) not found on frontend service. Please configure BACKEND_URL in Render environment variables pointing to your Render backend service.`);
        }

        const contentType = response.headers.get("content-type") || "";
        let data;

        if (contentType.includes("application/json")) {
            data = await response.json();
        } else {
            const text = await response.text();
            try {
                data = JSON.parse(text);
            } catch {
                if (!response.ok) {
                    throw new Error(text || `Server Error (${response.status})`);
                }
                throw new Error("Unexpected response format from server");
            }
        }

        if (!response.ok) {
            throw new Error(data.detail || data.message || data.error || JSON.stringify(data));
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
