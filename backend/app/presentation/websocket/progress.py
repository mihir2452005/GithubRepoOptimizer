"""
WebSocket Progress — Real-time agent execution updates.
Clients connect to /ws/analysis/{job_id} and receive progress messages.
Also provides in-memory job result storage for polling.
"""

import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect


# Router for WebSocket endpoints
router = APIRouter(tags=["websocket"])

# Active WebSocket connections per job
_connections: dict[str, list[WebSocket]] = {}

# Completed job results (in-memory, for polling)
_job_results: dict[str, dict] = {}

# Active jobs tracker
_active_jobs: set[str] = set()


@router.websocket("/ws/analysis/{job_id}")
async def ws_progress_endpoint(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time analysis progress."""
    await websocket.accept()

    if job_id not in _connections:
        _connections[job_id] = []
    _connections[job_id].append(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if job_id in _connections:
            _connections[job_id] = [ws for ws in _connections[job_id] if ws is not websocket]
            if not _connections[job_id]:
                del _connections[job_id]


async def send_progress(job_id: str, message: dict):
    """Send a progress update to all WebSocket clients watching this job."""
    if job_id in _connections:
        dead = []
        for ws in _connections[job_id]:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        # Clean up dead connections
        for ws in dead:
            _connections[job_id].remove(ws)


def store_job_result(job_id: str, result: dict):
    """Store a completed job result for polling retrieval."""
    _job_results[job_id] = result
    _active_jobs.discard(job_id)


def get_job_result(job_id: str) -> dict | None:
    """Get a stored job result (returns None if not yet complete)."""
    return _job_results.get(job_id)


def mark_job_running(job_id: str):
    """Mark a job as currently running."""
    _active_jobs.add(job_id)


def is_job_running(job_id: str) -> bool:
    """Check if a job is currently running."""
    return job_id in _active_jobs
