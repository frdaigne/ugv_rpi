"""
MCP Security Service — V3.
Token validation, tool allowlist, audit logging.
Dangerous tools require explicit confirmation parameter.
"""
import json
import os
import secrets
import sqlite3
from datetime import datetime
from functools import wraps

from ugv_logger import get_logger

log = get_logger("mcp_security")

_HERE      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH   = os.path.join(_HERE, "config", "mcp_audit.db")
_CFG_PATH  = os.path.join(_HERE, "config", "mcp_config.json")

# Tools that require confirm=true in params before executing
DANGEROUS_TOOLS = {
    "install_missing_dependencies",
    "start_wireguard",
    "stop_wireguard",
    "restart_wireguard",
    "load_wireguard_config",
    "enable_wireguard_autostart",
    "move_robot",
    "start_routine",
}


# ─────────────────────────────────────────────────────────────────────────────
# Config loading
# ─────────────────────────────────────────────────────────────────────────────

def _load_cfg() -> dict:
    try:
        with open(_CFG_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def is_mcp_enabled() -> bool:
    return _load_cfg().get("mcp_enabled", False)


def token_required() -> bool:
    return _load_cfg().get("require_token", True)


def allowed_tools() -> list:
    return _load_cfg().get("allowed_tools", [])


def dangerous_confirm_required() -> bool:
    return _load_cfg().get("dangerous_tools_require_confirmation", True)


# ─────────────────────────────────────────────────────────────────────────────
# Token management
# ─────────────────────────────────────────────────────────────────────────────

_TOKEN_FILE = os.path.join(_HERE, "config", ".mcp_token")


def get_or_create_token() -> str:
    """Return existing MCP token or generate and save a new one."""
    if os.path.exists(_TOKEN_FILE):
        with open(_TOKEN_FILE) as f:
            tok = f.read().strip()
        if tok:
            return tok
    tok = secrets.token_urlsafe(32)
    os.makedirs(os.path.dirname(_TOKEN_FILE), exist_ok=True)
    with open(_TOKEN_FILE, "w") as f:
        f.write(tok)
    os.chmod(_TOKEN_FILE, 0o600)
    log.info("New MCP token generated and saved to config/.mcp_token")
    return tok


def verify_token(provided: str) -> bool:
    if not token_required():
        return True
    expected = get_or_create_token()
    return secrets.compare_digest(provided or "", expected)


# ─────────────────────────────────────────────────────────────────────────────
# Audit log (SQLite)
# ─────────────────────────────────────────────────────────────────────────────

def _audit_conn():
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mcp_audit (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            ts        TEXT NOT NULL,
            tool      TEXT NOT NULL,
            caller    TEXT,
            allowed   INTEGER NOT NULL,
            result_ok INTEGER,
            note      TEXT
        )
    """)
    conn.commit()
    return conn


def audit_log(tool: str, caller: str = None, allowed: bool = True,
              result_ok: bool = None, note: str = None):
    """Write an audit entry. Never include secret values in any field."""
    try:
        with _audit_conn() as c:
            c.execute(
                "INSERT INTO mcp_audit (ts, tool, caller, allowed, result_ok, note) "
                "VALUES (?,?,?,?,?,?)",
                (datetime.utcnow().isoformat(), tool, caller,
                 int(allowed), int(result_ok) if result_ok is not None else None, note)
            )
    except Exception as exc:
        log.warning("Audit log write failed: %s", exc)


def get_audit_log(limit: int = 50) -> list:
    try:
        with _audit_conn() as c:
            rows = c.execute(
                "SELECT ts, tool, caller, allowed, result_ok, note "
                "FROM mcp_audit ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [
            {"ts": r[0], "tool": r[1], "caller": r[2],
             "allowed": bool(r[3]), "result_ok": r[4], "note": r[5]}
            for r in rows
        ]
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Tool gate — call this before executing any MCP tool
# ─────────────────────────────────────────────────────────────────────────────

def check_tool_access(tool_name: str, params: dict,
                      token: str = None, caller: str = None) -> tuple:
    """
    Returns (allowed: bool, reason: str).
    Checks: MCP enabled, token valid, tool in allowlist, dangerous confirm.
    """
    if not is_mcp_enabled():
        audit_log(tool_name, caller, allowed=False, note="MCP disabled")
        return False, "MCP is disabled in config/mcp_config.json"

    if token_required() and not verify_token(token):
        audit_log(tool_name, caller, allowed=False, note="bad token")
        return False, "Invalid or missing MCP token"

    allowed = allowed_tools()
    if allowed and tool_name not in allowed:
        audit_log(tool_name, caller, allowed=False, note="not in allowlist")
        return False, f"Tool '{tool_name}' not in allowed_tools list"

    if dangerous_confirm_required() and tool_name in DANGEROUS_TOOLS:
        if not params.get("confirm"):
            audit_log(tool_name, caller, allowed=False, note="confirm missing")
            return False, (
                f"Tool '{tool_name}' is dangerous and requires confirm=true in params. "
                "Add 'confirm': true to your call after reviewing the action."
            )

    audit_log(tool_name, caller, allowed=True)
    return True, "ok"
