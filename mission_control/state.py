"""
Mission Control — Robot state and trajectory management.

Thread-safe in-memory store.
Abstraction layer ready for SQLite / JSON file persistence.
"""

import threading
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional


class RobotPose:
    """Single pose snapshot."""
    __slots__ = ('x', 'y', 'theta', 'source', 'timestamp', 'confidence')

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        theta: float = 0.0,
        source: str = 'mock',
        confidence: float = 0.0,
    ):
        self.x = x
        self.y = y
        self.theta = theta
        self.source = source
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.confidence = confidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            'x': round(self.x, 4),
            'y': round(self.y, 4),
            'theta': round(self.theta, 4),
            'source': self.source,
            'timestamp': self.timestamp,
            'confidence': round(self.confidence, 3),
        }


class TrajectoryStore:
    """Thread-safe trajectory history store."""

    MAX_HISTORY = 2000   # max path points kept in memory
    MIN_INTERVAL = 0.2   # min seconds between path points

    def __init__(self):
        self._lock = threading.Lock()
        self._current: RobotPose = RobotPose()
        self._history: List[Dict] = []
        self._last_appended: float = 0.0

    def update(self, pose: RobotPose) -> None:
        now = time.monotonic()
        with self._lock:
            self._current = pose
            if now - self._last_appended >= self.MIN_INTERVAL:
                if len(self._history) >= self.MAX_HISTORY:
                    self._history.pop(0)
                self._history.append(pose.to_dict())
                self._last_appended = now

    def get_pose(self) -> Dict[str, Any]:
        with self._lock:
            return self._current.to_dict()

    def get_path(self) -> List[Dict]:
        with self._lock:
            return list(self._history)

    def reset(self) -> None:
        with self._lock:
            self._history.clear()
            self._current = RobotPose()


# Module-level singleton
_store: Optional[TrajectoryStore] = None


def get_store() -> TrajectoryStore:
    global _store
    if _store is None:
        _store = TrajectoryStore()
    return _store
