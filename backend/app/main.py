from __future__ import annotations

import asyncio

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .models import BuildRequest, StateResponse
from .service import CitySimulationService


app = FastAPI(title="CityBuilder MVP API", version="0.1.0")
service = CitySimulationService(seed=42)
state_lock = asyncio.Lock()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/state", response_model=StateResponse)
async def get_state() -> StateResponse:
    async with state_lock:
        return service.snapshot()


@app.post("/tick", response_model=StateResponse)
async def tick() -> StateResponse:
    async with state_lock:
        return service.tick()


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


@app.websocket("/live")
async def live(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            async with state_lock:
                snapshot = service.tick()
            await websocket.send_json(snapshot.model_dump(mode="json", by_alias=True))
            await asyncio.sleep(1.25)
    except WebSocketDisconnect:
        return
