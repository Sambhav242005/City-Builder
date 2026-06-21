# CityBuilder MVP

A stable micro-city simulation with one resource, `Food`, wrapped in a FastAPI backend and a React dashboard.

## Prerequisites

- Python 3.13+
- Node.js 20+

## Run Backend

```powershell
cd backend
python -m venv ..\.venv
..\.venv\Scripts\python -m pip install -r requirements.txt
..\.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The backend serves the API on `http://127.0.0.1:8000`.

## Run Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

The Vite dev server proxies `/api/*` requests to the backend (port 8000 by default).
To use a different backend port, set `BACKEND_PORT`:

```powershell
$env:BACKEND_PORT="8010"; npm run dev
```

## Test

```powershell
cd backend
..\.venv\Scripts\python -m pytest

cd frontend
npm run build
```

## Train Optimizer

```powershell
cd backend
..\.venv\Scripts\python -m app.training_harness
```

This regenerates `backend\data\q_table.json` and
`backend\data\optimizer_training_report.json` from `CityTrainingEnv`.

## Deploy (Raspberry Pi)

Push to `main` — the GitHub Actions workflow in `.github/workflows/deploy-pi.yml`
runs tests on GitHub, then deploys to the Pi via a self-hosted runner.
See `deploy/docker-compose.yml` and `deploy/nginx/citybuilder.conf`.
