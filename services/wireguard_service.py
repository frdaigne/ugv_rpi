"""
WireGuard Service — V3.

SECURITY CONTRACT:
  PrivateKey values are NEVER returned in any dict, log, or string output.
  mask_secret() is applied to any value that might contain a private key.
  The word "private" in log messages refers only to the concept, not the value.
"""
import configparser
import io
import os
import re
import shutil
import subprocess
from datetime import datetime

from ugv_logger import get_logger

log = get_logger("wireguard")

WG_DIR  = "/etc/wireguard"
WG_BIN  = "wg"
WGQ_BIN = "wg-quick"

# Fields whose values must ALWAYS be masked in any output
_SECRET_FIELDS = {"privatekey", "presharedkey"}


# ─────────────────────────────────────────────────────────────────────────────
# Secret masking
# ─────────────────────────────────────────────────────────────────────────────

def mask_secret(value: str) -> str:
    """Return only first 4 + last 4 chars of a secret, replacing the middle with ***."""
    if not value or len(value) < 10:
        return "****MASKED****"
    return value[:4] + "****MASKED****" + value[-4:]


def _sanitize_config_text(text: str) -> str:
    """Return config text with all secret field values replaced. Never logs originals."""
    lines = []
    for line in text.splitlines():
        stripped = line.strip().lower()
        for field in _SECRET_FIELDS:
            if stripped.startswith(field + " ") or stripped.startswith(field + "="):
                eq = line.index("=")
                lines.append(line[: eq + 1] + " ****MASKED****")
                break
        else:
            lines.append(line)
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Config parsing / validation
# ─────────────────────────────────────────────────────────────────────────────

def parse_wireguard_config(path: str) -> dict:
    """
    Parse a WireGuard .conf file.
    Returns a dict with sections and fields — PrivateKey/PresharedKey are MASKED.
    Never logs or returns raw secret values.
    """
    if not os.path.exists(path):
        return {"ok": False, "error": f"File not found: {path}"}

    try:
        with open(path, "r") as f:
            raw = f.read()
    except PermissionError:
        return {"ok": False, "error": "Permission denied reading config (try sudo)"}

    # Use configparser with INTERFACE as default section trick
    parser = configparser.RawConfigParser(strict=False)
    # WireGuard uses repeated [Peer] sections; we flatten them
    try:
        parser.read_string(raw)
    except Exception as exc:
        return {"ok": False, "error": f"Parse error: {exc}"}

    result = {"ok": True, "sections": {}, "safe_text": _sanitize_config_text(raw)}

    for section in parser.sections():
        sec_key = section.lower()
        fields = {}
        for key, val in parser.items(section):
            if key.lower() in _SECRET_FIELDS:
                fields[key] = "****MASKED****"
            else:
                fields[key] = val
        result["sections"][sec_key] = fields

    return result


def validate_wireguard_config(path: str) -> tuple:
    """
    Validate a WireGuard config file.
    Returns (is_valid: bool, errors: list[str]).
    Never surfaces PrivateKey values.
    """
    errors = []

    if not os.path.exists(path):
        return False, [f"File not found: {path}"]

    try:
        with open(path, "r") as f:
            raw = f.read()
    except PermissionError:
        return False, ["Permission denied — cannot read file"]

    # Check for required sections
    has_interface = re.search(r"^\[Interface\]", raw, re.MULTILINE | re.IGNORECASE)
    has_peer      = re.search(r"^\[Peer\]",      raw, re.MULTILINE | re.IGNORECASE)

    if not has_interface:
        errors.append("Missing [Interface] section")
    if not has_peer:
        errors.append("Missing [Peer] section (required for tunnel)")

    # Required fields in Interface (check presence, NOT value)
    required_iface = {
        "address":    r"^\s*Address\s*=",
        "privatekey": r"^\s*PrivateKey\s*=",
    }
    for label, pattern in required_iface.items():
        if not re.search(pattern, raw, re.MULTILINE | re.IGNORECASE):
            if label == "privatekey":
                errors.append("Missing PrivateKey in [Interface] (value not shown)")
            else:
                errors.append(f"Missing {label.capitalize()} in [Interface]")

    # Required fields in Peer
    required_peer = {
        "publickey":  r"^\s*PublicKey\s*=",
        "allowedips": r"^\s*AllowedIPs\s*=",
        "endpoint":   r"^\s*Endpoint\s*=",
    }
    for label, pattern in required_peer.items():
        if not re.search(pattern, raw, re.MULTILINE | re.IGNORECASE):
            errors.append(f"Missing {label} in [Peer]")

    # Validate Address format lightly
    addr_match = re.search(r"^\s*Address\s*=\s*(.+)", raw, re.MULTILINE | re.IGNORECASE)
    if addr_match:
        addrs = [a.strip() for a in addr_match.group(1).split(",")]
        for addr in addrs:
            if "/" not in addr:
                errors.append(f"Address '{addr}' missing CIDR prefix (e.g. /24)")

    # Validate Endpoint format
    ep_match = re.search(r"^\s*Endpoint\s*=\s*(.+)", raw, re.MULTILINE | re.IGNORECASE)
    if ep_match:
        ep = ep_match.group(1).strip()
        if ":" not in ep:
            errors.append(f"Endpoint '{ep}' missing port (e.g. host:51820)")

    return len(errors) == 0, errors


# ─────────────────────────────────────────────────────────────────────────────
# Config installation
# ─────────────────────────────────────────────────────────────────────────────

def install_wireguard_config(source_path: str, target_name: str = "wg0") -> dict:
    """
    Safely install a WireGuard config:
      1. Validate source config
      2. Backup existing target if present
      3. Copy to /etc/wireguard/<target_name>.conf
      4. chmod 600, chown root:root
    PrivateKey is never logged.
    """
    target_conf = os.path.join(WG_DIR, f"{target_name}.conf")

    # Validate first
    valid, errors = validate_wireguard_config(source_path)
    if not valid:
        return {"ok": False, "error": "Config validation failed", "details": errors}

    # Backup existing
    backup_path = None
    if os.path.exists(target_conf):
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_path = target_conf + f".bak_{ts}"
        try:
            shutil.copy2(target_conf, backup_path)
            os.chmod(backup_path, 0o600)
            log.info("WireGuard config backed up to %s", backup_path)
        except Exception as exc:
            return {"ok": False, "error": f"Backup failed: {exc}"}

    # Copy source to target
    try:
        os.makedirs(WG_DIR, exist_ok=True)
        shutil.copy2(source_path, target_conf)
        os.chmod(target_conf, 0o600)
        # chown root:root via subprocess (may need sudo)
        _run(["chown", "root:root", target_conf], sudo=True)
        log.info("WireGuard config installed to %s (PrivateKey not logged)", target_conf)
        return {
            "ok":          True,
            "target":      target_conf,
            "backup":      backup_path,
            "permissions": "600 root:root",
        }
    except PermissionError:
        return {"ok": False, "error": "Permission denied — run as root or with sudo"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ─────────────────────────────────────────────────────────────────────────────
# Runtime helpers
# ─────────────────────────────────────────────────────────────────────────────

def _run(cmd, timeout=15, sudo=False):
    full = (["sudo"] + list(cmd)) if sudo else list(cmd)
    try:
        out = subprocess.check_output(full, text=True, timeout=timeout,
                                      stderr=subprocess.STDOUT)
        return True, out.strip()
    except FileNotFoundError:
        return False, f"Command not found: {full[0]}"
    except subprocess.CalledProcessError as exc:
        return False, exc.output.strip()
    except subprocess.TimeoutExpired:
        return False, "Command timed out"


def _wg_installed() -> bool:
    ok, _ = _run(["which", WG_BIN])
    return ok


def get_wireguard_status() -> dict:
    """
    Return WireGuard interface + peer info from `wg show all dump`.
    PrivateKey column from the dump is DISCARDED — never stored or returned.
    """
    if not _wg_installed():
        return {"installed": False}

    ok, out = _run([WG_BIN, "show", "all", "dump"], sudo=True)
    interfaces = {}

    if ok:
        for line in out.splitlines():
            cols = line.split("\t")
            if len(cols) == 5:
                # Interface line: iface  PRIVATE_KEY  public_key  listen_port  fwmark
                # col[1] = private key — DISCARD IMMEDIATELY, never store
                iface = cols[0]
                interfaces[iface] = {
                    "public_key":  cols[2],   # col[1] private key is skipped on purpose
                    "listen_port": cols[3],
                    "peers":       [],
                }
            elif len(cols) == 9:
                # Peer line: iface  pub  psk  endpoint  allowed  handshake  rx  tx  keepalive
                iface = cols[0]
                if iface not in interfaces:
                    interfaces[iface] = {"public_key": "", "listen_port": "", "peers": []}
                try:
                    rx, tx = int(cols[6]), int(cols[7])
                except ValueError:
                    rx = tx = 0
                hs_raw = cols[5]
                hs_str = (
                    datetime.utcfromtimestamp(int(hs_raw)).strftime("%Y-%m-%dT%H:%M:%SZ")
                    if hs_raw.isdigit() and hs_raw != "0"
                    else "never"
                )
                interfaces[iface]["peers"].append({
                    "public_key":       cols[1],
                    "endpoint":         cols[3],
                    "allowed_ips":      cols[4],
                    "latest_handshake": hs_str,
                    "transfer_rx_b":    rx,
                    "transfer_tx_b":    tx,
                })

    # List config files in /etc/wireguard (without reading their contents)
    conf_files = []
    if os.path.isdir(WG_DIR):
        try:
            conf_files = [
                f for f in os.listdir(WG_DIR) if f.endswith(".conf")
            ]
        except PermissionError:
            conf_files = ["(permission denied)"]

    return {
        "installed":    True,
        "interfaces":   interfaces,
        "config_files": conf_files,
        "wg_dir":       WG_DIR,
    }


def start_wireguard(interface: str = "wg0") -> dict:
    ok, out = _run([WGQ_BIN, "up", interface], sudo=True, timeout=20)
    log.info("WireGuard up %s: %s", interface, "OK" if ok else "FAILED")
    return {"ok": ok, "interface": interface, "output": out}


def stop_wireguard(interface: str = "wg0") -> dict:
    ok, out = _run([WGQ_BIN, "down", interface], sudo=True, timeout=20)
    log.info("WireGuard down %s: %s", interface, "OK" if ok else "FAILED")
    return {"ok": ok, "interface": interface, "output": out}


def restart_wireguard(interface: str = "wg0") -> dict:
    r1 = stop_wireguard(interface)
    r2 = start_wireguard(interface)
    return {"ok": r2["ok"], "stop": r1, "start": r2}


def enable_autostart(interface: str = "wg0") -> dict:
    ok, out = _run(["systemctl", "enable", f"wg-quick@{interface}"], sudo=True)
    log.info("WireGuard autostart %s: %s", interface, "enabled" if ok else "FAILED")
    return {"ok": ok, "output": out}


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point (for manual testing)
# python -m services.wireguard_service --validate /path/to/wg0.conf
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3 and sys.argv[1] == "--validate":
        path = sys.argv[2]
        valid, errs = validate_wireguard_config(path)
        parsed = parse_wireguard_config(path)
        print(f"\nFile: {path}")
        print(f"Valid: {valid}")
        if errs:
            for e in errs:
                print(f"  ERROR: {e}")
        print("\nSafe config preview:")
        print(parsed.get("safe_text", "(parse failed)"))
    else:
        print("Usage: python -m services.wireguard_service --validate /etc/wireguard/wg0.conf")
