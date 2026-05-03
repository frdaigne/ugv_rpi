"""
Robot Adapter — thin wrapper over the existing Flask REST API.
MCP tools use this instead of calling hardware directly,
so there is no code duplication and all safety limits stay enforced.
"""
import requests
from ugv_logger import get_logger

log = get_logger("robot_adapter")

_BASE    = "http://localhost:5000"
_TIMEOUT = 5


def _get(path: str) -> dict:
    try:
        r = requests.get(_BASE + path, timeout=_TIMEOUT)
        return r.json()
    except Exception as exc:
        return {"error": str(exc)}


def _post(path: str, body: dict = None) -> dict:
    try:
        r = requests.post(_BASE + path, json=body or {}, timeout=_TIMEOUT)
        return r.json()
    except Exception as exc:
        return {"error": str(exc)}


def status() -> dict:
    """Full robot status from /api/ugv/status."""
    return _get("/api/ugv/status")


def stop() -> dict:
    """Emergency stop."""
    return _post("/api/ugv/stop")


def move(direction: str, speed: float = 0.3, duration: float = 1.0) -> dict:
    """
    Move robot. Direction: forward|backward|left|right|spin_left|spin_right.
    Speed 0.0–0.8, duration 0.1–5.0s.
    """
    return _post("/api/ugv/move", {
        "direction": direction,
        "speed":     max(0.0, min(0.8, float(speed))),
        "duration":  max(0.1, min(5.0, float(duration))),
    })


def camera(pan: float = 0.0, tilt: float = 0.0, speed: int = 200) -> dict:
    """Pan/tilt gimbal. pan: -180..180, tilt: -30..90."""
    return _post("/api/ugv/gimbal", {"x": pan, "y": tilt, "speed": speed})


def camera_center() -> dict:
    """Reset gimbal to forward position."""
    return _post("/api/ugv/gimbal/center")


def capture_photo() -> dict:
    return _post("/api/ugv/photo")


def start_recording() -> dict:
    return _post("/api/ugv/video/start")


def stop_recording() -> dict:
    return _post("/api/ugv/video/stop")


def set_lights(base: int = 0, head: int = 0) -> dict:
    return _post("/api/ugv/lights", {"base": base, "head": head})


def set_cv_mode(mode: str) -> dict:
    return _post("/api/ugv/cv/mode", {"mode": mode})


def routine_status() -> dict:
    return _get("/api/ugv/routine/status")


def start_routine(routine: str, params: dict = None) -> dict:
    body = dict(params or {})
    if routine in ("sentinel", "follow", "guard"):
        body["confirm"] = True
    return _post(f"/api/ugv/routine/{routine}", body)


def stop_routine() -> dict:
    return _post("/api/ugv/routine/stop")


def events(limit: int = 20) -> dict:
    return _get(f"/api/ugv/cv/events?limit={limit}")
