from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .models import AdvanceRequest, BuildRequest, OptimizerTrainingReport, StateResponse
from .service import CitySimulationService


app = FastAPI(title="CityBuilder MVP API", version="0.1.0")
service = CitySimulationService(seed=42)
state_lock = asyncio.Lock()
DEFAULT_CORS_ORIGINS = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:5174",
    "http://localhost:5174",
)
OPTIMIZER_TRAINING_REPORT_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "optimizer_training_report.json"
)


def build_cors_origins(extra_origins: str | None = None) -> list[str]:
    raw_origins = (
        os.getenv("CITYBUILDER_CORS_ORIGINS", "")
        if extra_origins is None
        else extra_origins
    )
    origins = list(DEFAULT_CORS_ORIGINS)

    for origin in raw_origins.split(","):
        origin = origin.strip()
        if origin and origin not in origins:
            origins.append(origin)

    return origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=build_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/state", response_model=StateResponse)
async def get_state() -> StateResponse:
    async with state_lock:
        return service.snapshot()


@app.get("/optimizer/training-report", response_model=OptimizerTrainingReport)
async def get_optimizer_training_report() -> OptimizerTrainingReport:
    try:
        with OPTIMIZER_TRAINING_REPORT_PATH.open(encoding="utf-8") as report_file:
            report = json.load(report_file)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Optimizer training report is not available.",
        ) from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail="Optimizer training report contains invalid JSON.",
        ) from exc

    return OptimizerTrainingReport.model_validate(report)


@app.post("/tick", response_model=StateResponse)
async def tick() -> StateResponse:
    async with state_lock:
        return service.tick()


@app.post("/advance", response_model=StateResponse)
async def advance(request: AdvanceRequest | None = None) -> StateResponse:
    async with state_lock:
        return service.advance(request.ticks if request else None)


@app.post("/reset", response_model=StateResponse)
async def reset() -> StateResponse:
    async with state_lock:
        return service.reset()


@app.post("/government/approve", response_model=StateResponse)
async def approve_government_action() -> StateResponse:
    async with state_lock:
        return service.approve_government_action()


@app.post("/government/reject", response_model=StateResponse)
async def reject_government_action() -> StateResponse:
    async with state_lock:
        return service.reject_government_action()


@app.post("/build", response_model=StateResponse)
async def build_structure(request: BuildRequest) -> StateResponse:
    async with state_lock:
        return service.build_structure(request.building_type)


@app.post("/live/play", response_model=StateResponse)
async def play_live() -> StateResponse:
    async with state_lock:
        return service.play_live()


@app.post("/live/pause", response_model=StateResponse)
async def pause_live() -> StateResponse:
    async with state_lock:
        return service.pause_live()


@app.websocket("/live")
async def live(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            async with state_lock:
                if service.live_running:
                    snapshot = service.tick()
                    sleep_seconds = service.LIVE_TICK_INTERVAL_SECONDS
                else:
                    snapshot = service.snapshot()
                    sleep_seconds = 0.25
            await websocket.send_json(snapshot.model_dump(mode="json", by_alias=True))
            await asyncio.sleep(sleep_seconds)
    except WebSocketDisconnect:
        return
