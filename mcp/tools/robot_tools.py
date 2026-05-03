"""
MCP Robot Tools — all robot control goes through robot_adapter
which calls the Flask REST API. No direct hardware access.
"""
from services import robot_adapter as _robot
from ugv_logger import get_logger

log = get_logger("mcp.robot")


def get_robot_status() -> dict:
    """Full robot status: battery, CPU, temperature, gimbal angles, CV mode, lights."""
    return _robot.status()


def stop_robot() -> dict:
    """Emergency stop — immediately halts motors and any running routine."""
    return _robot.stop()


def move_robot(direction: str, speed: float = 0.3, duration: float = 1.0,
               confirm: bool = False) -> dict:
    """
    Move robot. DANGEROUS — requires confirm=true.
    direction: forward | backward | left | right | spin_left | spin_right
    speed: 0.0–0.8 (default 0.3, max safe 0.8)
    duration: 0.1–5.0 seconds (auto-stops after duration)
    """
    if not confirm:
        return {
            "ok":    False,
            "error": "confirm=true required to move the robot. "
                     "Ensure the area around the robot is clear.",
        }
    return _robot.move(direction, speed, duration)


def move_camera(pan: float = 0.0, tilt: float = 0.0, speed: int = 200) -> dict:
    """
    Move camera gimbal.
    pan: -180 to 180 (negative=left, positive=right)
    tilt: -30 to 90  (negative=down, positive=up)
    speed: 1–1000
    """
    return _robot.camera(pan, tilt, speed)


def center_gimbal() -> dict:
    """Reset gimbal to center — looks straight ahead."""
    return _robot.camera_center()


def capture_photo() -> dict:
    """Capture a photo with the current camera view."""
    return _robot.capture_photo()


def start_recording() -> dict:
    """Start video recording."""
    return _robot.start_recording()


def stop_recording() -> dict:
    """Stop video recording."""
    return _robot.stop_recording()


def set_lights(base: int = 0, head: int = 0) -> dict:
    """Control lights. base/head: 0=off, 255=max brightness."""
    return _robot.set_lights(base, head)


def set_autonomous_mode(mode: str, confirm: bool = False) -> dict:
    """
    Start an autonomous routine. DANGEROUS — requires confirm=true.
    mode: patrol | watch | search | sentinel | follow
    """
    if not confirm:
        return {"ok": False, "error": "confirm=true required to start an autonomous mode"}
    return _robot.start_routine(mode, {"confirm": True})


def stop_autonomous_mode() -> dict:
    """Stop the currently running autonomous routine."""
    return _robot.stop_routine()


def get_routine_status() -> dict:
    """Current routine state (idle/running), name, parameters."""
    return _robot.routine_status()


def get_events(limit: int = 20) -> dict:
    """Get last N robot events (CV detections, routine changes, errors)."""
    return _robot.events(limit)
