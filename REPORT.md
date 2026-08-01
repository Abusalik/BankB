# BankingAI Deployment Audit Report

## Problems found
- The frontend and backend were deployed as separate Render services but the UI was still calling the API as if it were same-origin.
- API requests were using local-style paths and were not routed to the deployed backend URL.
- The backend did not return structured JSON errors for API failures, causing the frontend to receive HTML error pages.
- CORS was not explicitly configured for Render frontend domains.
- Database initialization depended on the runtime environment being fully configured for PostgreSQL.

## Files modified
- backend_repo/backend/main.py
- backend_repo/backend/database.py
- backend_repo/frontend/js/app.js
- backend_repo/frontend/js/auth.js
- backend_repo/frontend/js/register.js
- backend_repo/frontend/js/config.js
- backend_repo/templates/base.html
- backend_repo/templates/login.html
- backend_repo/templates/register.html

## Why each change was necessary
- The frontend now uses a single backend URL configuration so Render deployments can contact the backend service reliably.
- The backend now returns JSON error payloads instead of HTML pages for API calls.
- CORS now accepts the deployed frontend domain and local development origins.
- Database initialization is now guarded so startup can proceed more safely in Render environments.

## Remaining issues
- Render must set the FRONTEND_URL and DATABASE_URL environment variables on the backend service.
- The frontend service must also receive the deployed backend URL through the BACKEND_URL environment variable or the Render build config.
- If the ML models are missing at runtime, the prediction endpoints will return a 503 with a JSON message.
