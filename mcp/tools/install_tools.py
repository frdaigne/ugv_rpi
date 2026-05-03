"""
MCP Install Tools — dependency management.
"""
from services import dependency_service as _dep


def check_dependencies() -> dict:
    """
    Check which system packages and Python packages are installed.
    Returns OK/MISSING status for each required component.
    """
    return _dep.check_dependencies()


def install_missing_dependencies(confirm: bool = False) -> dict:
    """
    Install all missing system and Python dependencies.
    DANGEROUS — runs apt-get and pip on the system.
    Requires confirm=true.
    """
    if not confirm:
        return {
            "ok":    False,
            "error": "confirm=true required. This will run apt-get update and pip install.",
            "what":  "Installs: wireguard, wireguard-tools, modemmanager, iproute2, "
                     "net-tools, sqlite3, python3-venv, and Python packages: "
                     "mcp, flask, requests, psutil, pyyaml, bcrypt, python-dotenv.",
        }
    return _dep.install_dependencies(confirm=True)
