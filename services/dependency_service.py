"""
Dependency Service — checks system packages and Python packages.
Used by MCP check_dependencies and install_missing_dependencies tools.
"""
import os
import shutil
import subprocess
import sys

from ugv_logger import get_logger

log = get_logger("dependency")

_HERE     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_VENV_DIR = os.path.join(_HERE, ".venv-mcp")
_SCRIPT   = os.path.join(_HERE, "scripts", "install_mcp_dependencies.sh")

# System binaries to check
SYSTEM_BINS = {
    "python3":         "python3",
    "pip3":            "pip3",
    "wg":              "wireguard-tools",
    "wg-quick":        "wireguard-tools",
    "ip":              "iproute2",
    "curl":            "curl",
    "jq":              "jq",
    "sqlite3":         "sqlite3",
    "zerotier-cli":    "zerotier-one",
    "mmcli":           "modemmanager",
}

# Python packages (importable name → pip name)
PYTHON_PACKAGES = {
    "mcp":       "mcp",
    "flask":     "flask",
    "requests":  "requests",
    "psutil":    "psutil",
    "yaml":      "pyyaml",
    "bcrypt":    "bcrypt",
    "dotenv":    "python-dotenv",
}


def _bin_present(binary: str) -> bool:
    return shutil.which(binary) is not None


def _pip_package_present(import_name: str, venv: bool = False) -> bool:
    python = os.path.join(_VENV_DIR, "bin", "python3") if venv else sys.executable
    if venv and not os.path.exists(python):
        return False
    try:
        subprocess.check_output(
            [python, "-c", f"import {import_name}"],
            stderr=subprocess.DEVNULL, timeout=5
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
            FileNotFoundError):
        return False


def check_dependencies() -> dict:
    """Return a full dependency status report."""
    system = {}
    for binary, pkg in SYSTEM_BINS.items():
        present = _bin_present(binary)
        system[binary] = {"present": present, "apt_pkg": pkg,
                          "status": "OK" if present else "MISSING"}

    python_pkgs = {}
    for imp_name, pip_name in PYTHON_PACKAGES.items():
        present = _pip_package_present(imp_name)
        python_pkgs[pip_name] = {"present": present,
                                  "status": "OK" if present else "MISSING"}

    venv_ok   = os.path.isdir(_VENV_DIR) and os.path.isfile(
        os.path.join(_VENV_DIR, "bin", "python3"))
    venv_pkgs = {}
    if venv_ok:
        for imp_name, pip_name in PYTHON_PACKAGES.items():
            present = _pip_package_present(imp_name, venv=True)
            venv_pkgs[pip_name] = {"present": present,
                                    "status": "OK" if present else "MISSING"}

    missing_sys = [k for k, v in system.items() if not v["present"]]
    missing_py  = [k for k, v in python_pkgs.items() if not v["present"]]

    return {
        "system_binaries": system,
        "python_packages": python_pkgs,
        "venv": {
            "path":      _VENV_DIR,
            "present":   venv_ok,
            "packages":  venv_pkgs,
        },
        "missing_system":  missing_sys,
        "missing_python":  missing_py,
        "all_ok":          not missing_sys and not missing_py,
    }


def install_dependencies(confirm: bool = False) -> dict:
    """
    Run the install script.
    confirm must be True — caller must explicitly pass it.
    """
    if not confirm:
        return {"ok": False, "error": "confirm=true required to install dependencies"}

    if not os.path.exists(_SCRIPT):
        return {"ok": False, "error": f"Install script not found: {_SCRIPT}"}

    try:
        result = subprocess.run(
            ["bash", _SCRIPT],
            capture_output=True, text=True, timeout=300
        )
        ok = result.returncode == 0
        log.info("Dependency install script exited with code %d", result.returncode)
        return {
            "ok":     ok,
            "stdout": result.stdout[-4000:],   # last 4000 chars
            "stderr": result.stderr[-2000:],
            "code":   result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Install script timed out (5 min limit)"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
