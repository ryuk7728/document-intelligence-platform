# Deployment

The production layout uses two public services:

- Vercel hosts the static dashboard from `frontend/`.
- Render runs the Dockerized FastAPI/OCR backend and managed PostgreSQL database.

## Live deployment

- Frontend: `https://document-intelligence-platform-bice.vercel.app`
- Backend origin: `https://document-intelligence-platform-gn7s.onrender.com`
- Backend API base: `https://document-intelligence-platform-gn7s.onrender.com/api/v1`
- Health check: `https://document-intelligence-platform-gn7s.onrender.com/api/v1/health`
- Swagger UI: `https://document-intelligence-platform-gn7s.onrender.com/docs`

## Backend on Render

Create a Render Blueprint from the repository root. `render.yaml` provisions the web service, PostgreSQL database, environment configuration, and health check at `/api/v1/health`.

The free PostgreSQL plan currently expires after 30 days. It is suitable for the case-study evaluation window; upgrade or migrate it for longer-lived use.

## Frontend on Vercel

Import the repository and set the project root directory to `frontend`. Set `BACKEND_API_BASE_URL` to the deployed Render origin, without a trailing slash. Vercel runs `npm run build` and publishes `frontend/dist`.

The backend `CORS_ORIGINS` and `ALLOWED_HOSTS` values are restricted to the live Vercel and Render hostnames in `render.yaml`.

## Optional model enrichment

The verified baseline uses local OCR and deterministic extraction. Optional OpenAI-compatible enrichment uses deployment secrets:

- `LLM_PROVIDER=openai_compatible`
- `LLM_MODEL=<model name>`
- `LLM_API_KEY=<secret>`
- `LLM_BASE_URL=<compatible API base URL>`
