#!/usr/bin/env bash
# install_mcp_dependencies.sh — Idempotent dependency installer for UGV MCP
# Run as: sudo bash scripts/install_mcp_dependencies.sh
# Or:      bash scripts/install_mcp_dependencies.sh  (will use sudo internally)
set -e

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC}      $*"; }
miss() { echo -e "${YELLOW}[INSTALLING]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC}   $*"; }
info() { echo -e "          $*"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/.venv-mcp"

echo ""
echo "══════════════════════════════════════════════════════"
echo "  UGV MCP Dependency Installer"
echo "══════════════════════════════════════════════════════"
echo ""

# ── Detect OS ────────────────────────────────────────────────────────────────
if [ -f /etc/os-release ]; then
    . /etc/os-release
    info "OS: $PRETTY_NAME"
else
    info "OS: $(uname -a)"
fi

# ── Helper: check binary ─────────────────────────────────────────────────────
check_bin() {
    local bin="$1"
    if command -v "$bin" &>/dev/null; then
        ok "$bin"
        return 0
    else
        return 1
    fi
}

# ── APT packages ─────────────────────────────────────────────────────────────
APT_PACKAGES=(
    python3
    python3-venv
    python3-pip
    wireguard
    wireguard-tools
    iproute2
    net-tools
    curl
    jq
    sqlite3
)

echo "── System packages ──────────────────────────────────"
APT_NEEDED=()
for pkg in "${APT_PACKAGES[@]}"; do
    if dpkg -s "$pkg" &>/dev/null 2>&1; then
        ok "$pkg"
    else
        miss "$pkg"
        APT_NEEDED+=("$pkg")
    fi
done

if [ "${#APT_NEEDED[@]}" -gt 0 ]; then
    echo ""
    info "Running: sudo apt-get update && apt-get install -y ${APT_NEEDED[*]}"
    sudo apt-get update -qq
    sudo apt-get install -y -qq "${APT_NEEDED[@]}"
    ok "APT packages installed"
else
    ok "All APT packages already present"
fi

# ── Optional: ModemManager for cellular ─────────────────────────────────────
echo ""
echo "── Optional packages ────────────────────────────────"
if dpkg -s modemmanager &>/dev/null 2>&1; then
    ok "modemmanager (mmcli available)"
else
    echo -e "${YELLOW}[SKIP]${NC}    modemmanager — install manually if needed for MC8700:"
    echo "           sudo apt-get install modemmanager"
fi

# ── Python venv ──────────────────────────────────────────────────────────────
echo ""
echo "── Python venv ($VENV_DIR) ──────────────────────────"
if [ -d "$VENV_DIR" ] && [ -f "$VENV_DIR/bin/python3" ]; then
    ok "venv already exists"
else
    miss "Creating .venv-mcp"
    python3 -m venv "$VENV_DIR"
    ok "venv created"
fi

# ── Python packages ──────────────────────────────────────────────────────────
echo ""
echo "── Python packages (venv) ───────────────────────────"
PY_PACKAGES=(
    mcp
    flask
    requests
    psutil
    pyyaml
    bcrypt
    python-dotenv
)

PIP="$VENV_DIR/bin/pip"
for pkg in "${PY_PACKAGES[@]}"; do
    imp="${pkg//-/_}"
    imp="${imp//pyyaml/yaml}"
    if "$VENV_DIR/bin/python3" -c "import $imp" &>/dev/null 2>&1; then
        ok "$pkg"
    else
        miss "$pkg"
        "$PIP" install -q "$pkg"
        ok "$pkg installed"
    fi
done

# ── System bin check ─────────────────────────────────────────────────────────
echo ""
echo "── Binary checks ────────────────────────────────────"
for bin in python3 pip3 wg wg-quick ip curl sqlite3; do
    check_bin "$bin" || err "$bin not found after install"
done

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════"
ok "Installation complete"
info "Activate venv: source $VENV_DIR/bin/activate"
info "Run MCP:       python mcp/server.py"
info "Check status:  bash scripts/check_ugv_mcp.sh"
echo "══════════════════════════════════════════════════════"
echo ""
