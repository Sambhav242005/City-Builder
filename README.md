# CityBuilder MVP

A stable micro-city simulation with one resource, `Food`, wrapped in a FastAPI backend and a React dashboard.

## Run Backend

```powershell
cd C:\Users\hp\Desktop\CityBuilder\backend
python -m venv ..\.venv
..\.venv\Scripts\python -m pip install -r requirements.txt
..\.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Run Frontend

```powershell
cd C:\Users\hp\Desktop\CityBuilder\frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

## Test

```powershell
cd C:\Users\hp\Desktop\CityBuilder\backend
..\.venv\Scripts\python -m pytest

cd C:\Users\hp\Desktop\CityBuilder\frontend
npm run build
```

