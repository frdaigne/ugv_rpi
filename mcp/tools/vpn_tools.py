"""
MCP VPN Tools — ZeroTier + WireGuard status and control.

SECURITY: PrivateKey is NEVER returned, logged, or passed through any function here.
          wireguard_service.py enforces masking at the source.
"""
import requests

from services import wireguard_service as _wg
from ugv_logger import get_logger

log = get_logger("mcp.vpn")

_BASE    = "http://localhost:5000"
_TIMEOUT = 5


def _get(path):
    try:
        return requests.get(_BASE + path, timeout=_TIMEOUT).json()
    except Exception as exc:
        return {"error": str(exc)}


def _post(path, body=None):
    try:
        return requests.post(_BASE + path, json=body or {}, timeout=_TIMEOUT).json()
    except Exception as exc:
        return {"error": str(exc)}


# ─── ZeroTier ─────────────────────────────────────────────────────────────────

def get_zerotier_status() -> dict:
    """ZeroTier daemon status, node ID, joined networks."""
    return _get("/api/remote/zerotier/status")


# ─── WireGuard ────────────────────────────────────────────────────────────────

def get_wireguard_status() -> dict:
    """
    WireGuard interface status: peers, endpoints, handshakes, transfer.
    PrivateKey is NEVER included in the response.
    """
    return _wg.get_wireguard_status()


def get_vpn_status() -> dict:
    """Combined ZeroTier + WireGuard status."""
    zt = get_zerotier_status()
    wg = get_wireguard_status()
    return {"zerotier": zt, "wireguard": wg}


def validate_wireguard_config(path: str) -> dict:
    """
    Validate a WireGuard config file at the given path.
    Returns validation result and a safe preview (PrivateKey masked).
    The actual PrivateKey value is NEVER returned.
    """
    valid, errors = _wg.validate_wireguard_config(path)
    parsed = _wg.parse_wireguard_config(path)
    return {
        "valid":       valid,
        "errors":      errors,
        "safe_preview": parsed.get("safe_text", ""),
        "sections":    parsed.get("sections", {}),
        "note":        "PrivateKey and PresharedKey are masked in all outputs",
    }


def load_wireguard_config(source_path: str, interface: str = "wg0",
                          confirm: bool = False) -> dict:
    """
    Install a WireGuard config file to /etc/wireguard/<interface>.conf.
    Validates first, creates backup of existing config, sets chmod 600.
    PrivateKey is NEVER logged or returned.
    DANGEROUS — requires confirm=true.
    """
    if not confirm:
        return {
            "ok":    False,
            "error": "confirm=true required. This will overwrite /etc/wireguard config.",
        }
    return _wg.install_wireguard_config(source_path, interface)


def start_wireguard(interface: str = "wg0", confirm: bool = False) -> dict:
    """Start WireGuard tunnel (wg-quick up). DANGEROUS — requires confirm=true."""
    if not confirm:
        return {"ok": False, "error": "confirm=true required to start WireGuard"}
    return _wg.start_wireguard(interface)


def stop_wireguard(interface: str = "wg0", confirm: bool = False) -> dict:
    """Stop WireGuard tunnel (wg-quick down). DANGEROUS — requires confirm=true."""
    if not confirm:
        return {"ok": False, "error": "confirm=true required to stop WireGuard"}
    return _wg.stop_wireguard(interface)


def restart_wireguard(interface: str = "wg0", confirm: bool = False) -> dict:
    """Restart WireGuard tunnel. DANGEROUS — requires confirm=true."""
    if not confirm:
        return {"ok": False, "error": "confirm=true required to restart WireGuard"}
    return _wg.restart_wireguard(interface)


def enable_wireguard_autostart(interface: str = "wg0", confirm: bool = False) -> dict:
    """Enable wg-quick@<interface> via systemctl. DANGEROUS — requires confirm=true."""
    if not confirm:
        return {"ok": False, "error": "confirm=true required to enable autostart"}
    return _wg.enable_autostart(interface)
