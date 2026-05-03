#!/usr/bin/env bash
# check_ugv_mcp.sh — Quick health check for UGV MCP environment
# Usage: bash scripts/check_ugv_mcp.sh

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✓${NC}  $*"; PASS=$((PASS+1)); }
warn() { echo -e "  ${YELLOW}⚠${NC}  $*"; WARN=$((WARN+1)); }
fail() { echo -e "  ${RED}✗${NC}  $*"; FAIL=$((FAIL+1)); }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/.venv-mcp"
FLASK_URL="${FLASK_URL:-http://localhost:5000}"

PASS=0; WARN=0; FAIL=0

echo ""
echo -e "${CYAN}══════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  UGV MCP Environment Check${NC}"
echo -e "${CYAN}══════════════════════════════════════════════════════${NC}"
echo ""

# ── Python ────────────────────────────────────────────────────────────────────
echo "Python:"
if py=$(python3 --version 2>&1); then
    ok "python3: $py"
else
    fail "python3 not found"
fi

# ── Venv ──────────────────────────────────────────────────────────────────────
echo ""
echo "Virtual environment (.venv-mcp):"
if [ -f "$VENV_DIR/bin/python3" ]; then
    ok "venv present: $VENV_DIR"
else
    fail "venv missing — run: bash scripts/install_mcp_dependencies.sh"
fi

# ── Python packages ───────────────────────────────────────────────────────────
echo ""
echo "Python packages (venv):"
PYPKGS=(mcp flask requests psutil yaml bcrypt dotenv)
for pkg in "${PYPKGS[@]}"; do
    if [ -f "$VENV_DIR/bin/python3" ] && "$VENV_DIR/bin/python3" -c "import $pkg" &>/dev/null 2>&1; then
        ok "$pkg"
    elif python3 -c "import $pkg" &>/dev/null 2>&1; then
        warn "$pkg (system, not in venv)"
    else
        fail "$pkg — run install script"
    fi
done

# ── WireGuard ─────────────────────────────────────────────────────────────────
echo ""
echo "WireGuard:"
if command -v wg &>/dev/null; then
    ok "wg installed: $(wg --version 2>/dev/null || echo 'version unknown')"
else
    fail "wg not installed (sudo apt-get install wireguard-tools)"
fi
if command -v wg-quick &>/dev/null; then
    ok "wg-quick available"
else
    fail "wg-quick not found"
fi
WG_CONF="/etc/wireguard/wg0.conf"
if [ -f "$WG_CONF" ]; then
    perms=$(stat -c "%a" "$WG_CONF" 2>/dev/null)
    if [ "$perms" = "600" ]; then
        ok "wg0.conf exists (600)"
    else
        warn "wg0.conf exists but permissions=$perms (expected 600)"
    fi
    # Check if interface is up WITHOUT printing PrivateKey
    if sudo wg show wg0 &>/dev/null 2>&1; then
        ok "wg0 interface is UP"
    else
        warn "wg0 interface is DOWN"
    fi
else
    warn "wg0.conf does not exist (/etc/wireguard/wg0.conf)"
fi

# ── ZeroTier ──────────────────────────────────────────────────────────────────
echo ""
echo "ZeroTier:"
if command -v zerotier-cli &>/dev/null; then
    ok "zerotier-cli installed"
    if zt_info=$(sudo zerotier-cli info 2>/dev/null); then
        ok "daemon running: $zt_info"
    else
        warn "daemon not running (sudo systemctl start zerotier-one)"
    fi
else
    warn "zerotier-cli not installed"
fi

# ── Cellular ──────────────────────────────────────────────────────────────────
echo ""
echo "Cellular (MC8700):"
if lsusb 2>/dev/null | grep -q "1199:68a3"; then
    ok "Sierra Wireless MC8700 detected via USB"
else
    warn "MC8700 not detected (may not be connected)"
fi
if command -v mmcli &>/dev/null; then
    ok "mmcli available (ModemManager)"
else
    warn "mmcli not installed — limited cellular info"
fi

# ── Flask app ─────────────────────────────────────────────────────────────────
echo ""
echo "Flask app ($FLASK_URL):"
if command -v curl &>/dev/null; then
    if curl -sf --max-time 3 "$FLASK_URL/auth/me" &>/dev/null 2>&1; then
        ok "Flask app reachable at $FLASK_URL"
    elif curl -sf --max-time 3 "$FLASK_URL" &>/dev/null 2>&1; then
        ok "Flask app reachable (auth redirect)"
    else
        warn "Flask app not responding at $FLASK_URL"
    fi
else
    warn "curl not installed — cannot test Flask"
fi

# ── MCP config ────────────────────────────────────────────────────────────────
echo ""
echo "MCP config:"
MCP_CFG="$PROJECT_DIR/config/mcp_config.json"
if [ -f "$MCP_CFG" ]; then
    ok "mcp_config.json present"
    if command -v jq &>/dev/null; then
        enabled=$(jq -r '.mcp_enabled' "$MCP_CFG" 2>/dev/null)
        [ "$enabled" = "true" ] && ok "mcp_enabled = true" || warn "mcp_enabled = false (edit config/mcp_config.json to enable)"
    fi
else
    fail "mcp_config.json missing"
fi

MCP_TOKEN="$PROJECT_DIR/config/.mcp_token"
if [ -f "$MCP_TOKEN" ]; then
    tok_len=$(wc -c < "$MCP_TOKEN")
    ok "MCP token file exists ($tok_len bytes)"
    perms=$(stat -c "%a" "$MCP_TOKEN" 2>/dev/null)
    [ "$perms" = "600" ] && ok "Token file permissions: 600" || warn "Token file permissions: $perms (should be 600)"
else
    warn "MCP token not yet generated (starts on first server run)"
fi

# ── WireGuard permissions ─────────────────────────────────────────────────────
echo ""
echo "WireGuard directory permissions:"
if [ -d "/etc/wireguard" ]; then
    dir_perms=$(stat -c "%a %U:%G" /etc/wireguard 2>/dev/null)
    ok "/etc/wireguard exists: $dir_perms"
else
    warn "/etc/wireguard does not exist"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}══════════════════════════════════════════════════════${NC}"
echo -e "  Results: ${GREEN}$PASS OK${NC}  ${YELLOW}$WARN WARN${NC}  ${RED}$FAIL FAIL${NC}"
echo -e "${CYAN}══════════════════════════════════════════════════════${NC}"
echo ""
if [ "$FAIL" -gt 0 ]; then
    echo -e "  ${RED}Action needed — run: bash scripts/install_mcp_dependencies.sh${NC}"
elif [ "$WARN" -gt 0 ]; then
    echo -e "  ${YELLOW}Warnings present — review above for optional steps${NC}"
else
    echo -e "  ${GREEN}All checks passed!${NC}"
fi
echo ""
