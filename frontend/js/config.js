window.BANKINGAI_CONFIG = window.BANKINGAI_CONFIG || {};
window.BANKINGAI_CONFIG.backendUrl =
    (window.BANKINGAI_CONFIG.backendUrl || "").trim() ||
    (window.__BACKEND_URL__ || "").trim() ||
    "";
