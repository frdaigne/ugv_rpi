"""
MCP System Tools — get_system_status, check_dependencies, install_missing_dependencies.
"""
import os
import platform
import time

import psutil

from services import dependency_service as _dep
from ugv_logger import get_logger

log = get_logger("mcp.system")

_HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_system_status() -> dict:
    """
    Return full system status: CPU, RAM, temperature, uptime, network interfaces.
    No secrets exposed.
    """
    try:
        cpu   = psutil.cpu_percent(interval=0.5)
        ram   = psutil.virtual_memory()
        boot  = psutil.boot_time()
        uptime_s = int(time.time() - boot)

        # Temperature (Linux /sys)
        temps = {}
        try:
            for name, entries in psutil.sensors_temperatures().items():
                temps[name] = [{"label": e.label, "current": e.current} for e in entries]
        except (AttributeError, Exception):
            temps = {}

        # Network interfaces (IP only, no secrets)
        ifaces = {}
        try:
            for iface, addrs in psutil.net_if_addrs().items():
                ips = [a.address for a in addrs
                       if a.family in (2, 10)]  # AF_INET, AF_INET6
                if ips:
                    ifaces[iface] = ips
        except Exception:
            pass

        # Disk usage for project path
        disk = psutil.disk_usage(_HERE)

        return {
            "cpu_percent":   cpu,
            "ram_total_mb":  ram.total // 1024 // 1024,
            "ram_used_mb":   ram.used  // 1024 // 1024,
            "ram_percent":   ram.percent,
            "uptime_s":      uptime_s,
            "uptime_human":  _fmt_uptime(uptime_s),
            "temperatures":  temps,
            "interfaces":    ifaces,
            "disk_used_gb":  round(disk.used  / 1e9, 2),
            "disk_free_gb":  round(disk.free  / 1e9, 2),
            "platform":      platform.platform(),
        }
    except Exception as exc:
        log.warning("get_system_status error: %s", exc)
        return {"error": str(exc)}


def _fmt_uptime(s: int) -> str:
    d, rem = divmod(s, 86400)
    h, rem = divmod(rem, 3600)
    m, sec = divmod(rem, 60)
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    parts.append(f"{sec}s")
    return " ".join(parts)


def check_dependencies() -> dict:
    """
    Check which system binaries and Python packages are installed.
    Returns structured status with OK/MISSING per item.
    """
    return _dep.check_dependencies()


def install_missing_dependencies(confirm: bool = False) -> dict:
    """
    Run the install script to install missing dependencies.
    DANGEROUS — requires confirm=true.
    """
    if not confirm:
        return {
            "ok":    False,
            "error": "confirm=true required. This will run apt-get and pip install on the system.",
        }
    return _dep.install_dependencies(confirm=True)
