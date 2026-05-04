"""
Mission Control — SLAM / positioning adapter.

Stable public interface (never break these signatures):
    get_current_pose()  -> dict
    get_path_history()  -> list[dict]
    reset_path()
    get_slam_status()   -> dict

Supported modes (auto-detected, priority order):
    'mock'        — simulated Lissajous trajectory, always available
    'lidar_basic' — raw YDLiDAR data present on base controller
    'slam'        — reserved for future ROS2 / SLAM integration

To plug in real SLAM later:
    1. Set self._mode = 'slam' from your ROS2 bridge
    2. Override _read_slam() to return a RobotPose from your topic
    3. Call slam_adapter.start() after init
"""

import math
import threading
import time
from datetime import datetime, timezone
from typing import Optional

from mission_control.state import RobotPose, get_store


class SlamAdapter:

    def __init__(self, base=None, mode: str = 'mock'):
        self._base = base
        self._preferred_mode = mode
        self._store = get_store()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._t0 = time.monotonic()

    # ── Public interface ──────────────────────────────────────────────────────

    def get_current_pose(self) -> dict:
        return self._store.get_pose()

    def get_path_history(self) -> list:
        return self._store.get_path()

    def reset_path(self) -> None:
        self._store.reset()
        self._t0 = time.monotonic()

    def get_slam_status(self) -> dict:
        active = self._active_mode()
        return {
            'mode': active,
            'running': self._running,
            'lidar_available': self._lidar_available(),
            'slam_available': False,   # set True when ROS2 bridge is wired
            'history_length': len(self._store.get_path()),
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name='mc_slam_adapter'
        )
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    # ── Internal update loop (10 Hz) ──────────────────────────────────────────

    def _loop(self) -> None:
        while self._running:
            try:
                mode = self._active_mode()
                if mode == 'slam':
                    pose = self._read_slam()
                elif mode == 'lidar_basic':
                    pose = self._read_lidar_basic()
                else:
                    pose = self._mock_pose()
                self._store.update(pose)
            except Exception:
                pass  # never crash the daemon thread
            time.sleep(0.1)

    # ── Mock mode: figure-8 Lissajous pattern ─────────────────────────────────

    def _mock_pose(self) -> RobotPose:
        t = time.monotonic() - self._t0
        x = 2.0 * math.sin(t * 0.3)
        y = 1.0 * math.sin(t * 0.6)
        # heading tangent to the curve
        dx = 2.0 * 0.3 * math.cos(t * 0.3)
        dy = 1.0 * 0.6 * math.cos(t * 0.6)
        theta = math.atan2(dy, dx)
        return RobotPose(x=x, y=y, theta=theta, source='mock', confidence=1.0)

    # ── LiDAR basic: raw scan presence, dead-reckoning placeholder ───────────

    def _read_lidar_basic(self) -> RobotPose:
        try:
            angles = getattr(self._base.rl, 'lidar_angles_show', None)
            dists = getattr(self._base.rl, 'lidar_distances_show', None)
            if angles and dists:
                avg_dist_m = sum(dists) / len(dists) / 1000.0  # mm → m
                confidence = min(1.0, avg_dist_m / 5.0)
                pose = self._mock_pose()  # dead-reckoning not yet implemented
                pose.source = 'lidar_basic'
                pose.confidence = confidence
                return pose
        except Exception:
            pass
        return self._mock_pose()

    # ── ROS2 / SLAM stub ─────────────────────────────────────────────────────

    def _read_slam(self) -> RobotPose:
        # Replace this with your ROS2 /amcl_pose or /odom subscriber output.
        # Expected: set self._last_slam_pose from your ROS2 callback thread,
        # then return it here.
        return self._mock_pose()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _lidar_available(self) -> bool:
        if self._base is None:
            return False
        try:
            return bool(getattr(self._base, 'use_lidar', False))
        except Exception:
            return False

    def _active_mode(self) -> str:
        # Future: check ROS2 connection first
        if self._lidar_available():
            return 'lidar_basic'
        return 'mock'


# Module-level singleton
_adapter: Optional[SlamAdapter] = None


def get_adapter() -> SlamAdapter:
    global _adapter
    if _adapter is None:
        _adapter = SlamAdapter(mode='mock')
        _adapter.start()
    return _adapter


def init_slam_adapter(base=None) -> SlamAdapter:
    """Called once from app.py after BaseController is ready."""
    global _adapter
    _adapter = SlamAdapter(base=base, mode='mock')
    _adapter.start()
    return _adapter
