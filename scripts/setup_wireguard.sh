#!/usr/bin/env bash
# setup_wireguard.sh — WireGuard setup helper for UGV
# Usage:
#   bash scripts/setup_wireguard.sh --validate /path/to/wg0.conf
#   bash scripts/setup_wireguard.sh --install  /path/to/wg0.conf
#   bash scripts/setup_wireguard.sh --status
#   bash scripts/setup_wireguard.sh --start
#   bash scripts/setup_wireguard.sh --stop
#
# SECURITY: This script NEVER prints PrivateKey values.

set -e

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC}    $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*"; }
info() { echo -e "        $*"; }

IFACE="${WG_IFACE:-wg0}"
WG_DIR="/etc/wireguard"
WG_CONF="$WG_DIR/$IFACE.conf"

# ── Mask secrets in config display ───────────────────────────────────────────
mask_config() {
    # Replace PrivateKey and PresharedKey values with MASKED
    # NEVER print the actual key — sed matches and replaces only the value
    sed -E 's/^(PrivateKey\s*=\s*).+/\1****MASKED****/I;
            s/^(PresharedKey\s*=\s*).+/\1****MASKED****/I'
}

# ── Validate config file ──────────────────────────────────────────────────────
cmd_validate() {
    local conf="$1"
    echo ""
    echo "── Validating: $conf ────────────────────────────────"
    if [ ! -f "$conf" ]; then
        err "File not found: $conf"
        exit 1
    fi

    # Show safe preview — PrivateKey is masked
    echo ""
    info "Config preview (secrets masked):"
    mask_config < "$conf" | while IFS= read -r line; do
        info "  $line"
    done
    echo ""

    local errs=0
    grep -qi '^\[Interface\]' "$conf" && ok "[Interface] section found" \
        || { err "Missing [Interface] section"; errs=$((errs+1)); }
    grep -qi '^\[Peer\]' "$conf" && ok "[Peer] section found" \
        || { err "Missing [Peer] section"; errs=$((errs+1)); }
    grep -qi '^Address\s*=' "$conf" && ok "Address field found" \
        || { err "Missing Address in [Interface]"; errs=$((errs+1)); }
    grep -qi '^PrivateKey\s*=' "$conf" && ok "PrivateKey field found (value not shown)" \
        || { err "Missing PrivateKey in [Interface]"; errs=$((errs+1)); }
    grep -qi '^PublicKey\s*=' "$conf" && ok "PublicKey field found" \
        || { err "Missing PublicKey in [Peer]"; errs=$((errs+1)); }
    grep -qi '^Endpoint\s*=' "$conf" && ok "Endpoint field found" \
        || { err "Missing Endpoint in [Peer]"; errs=$((errs+1)); }
    grep -qi '^AllowedIPs\s*=' "$conf" && ok "AllowedIPs field found" \
        || { err "Missing AllowedIPs in [Peer]"; errs=$((errs+1)); }

    echo ""
    if [ "$errs" -eq 0 ]; then
        ok "Config valid ($conf)"
    else
        err "$errs error(s) found"
        exit 1
    fi
}

# ── Install config ────────────────────────────────────────────────────────────
cmd_install() {
    local src="$1"
    cmd_validate "$src"

    echo ""
    echo "── Installing config ────────────────────────────────"
    sudo mkdir -p "$WG_DIR"

    if [ -f "$WG_CONF" ]; then
        ts=$(date +%Y%m%d_%H%M%S)
        backup="${WG_CONF}.bak_${ts}"
        sudo cp "$WG_CONF" "$backup"
        sudo chmod 600 "$backup"
        ok "Backup created: $backup"
    fi

    sudo cp "$src" "$WG_CONF"
    sudo chmod 600 "$WG_CONF"
    sudo chown root:root "$WG_CONF"
    ok "Config installed: $WG_CONF (chmod 600, root:root)"
    info "PrivateKey was NOT logged during this operation"
}

# ── Status ────────────────────────────────────────────────────────────────────
cmd_status() {
    echo ""
    echo "── WireGuard Status ─────────────────────────────────"
    if ! command -v wg &>/dev/null; then
        err "wg not installed (sudo apt-get install wireguard-tools)"
        exit 1
    fi
    ok "wg binary found"

    if sudo wg show "$IFACE" &>/dev/null 2>&1; then
        ok "Interface $IFACE is UP"
        # Show wg show output but mask PrivateKey (wg show doesn't show it, but defensive)
        sudo wg show "$IFACE" | mask_config
    else
        warn "Interface $IFACE is DOWN or does not exist"
    fi

    if [ -f "$WG_CONF" ]; then
        ok "Config file exists: $WG_CONF"
        perms=$(stat -c "%a %U:%G" "$WG_CONF" 2>/dev/null || echo "unknown")
        info "Permissions: $perms"
        if [[ "$perms" == "600 root:root" ]]; then
            ok "Permissions correct (600 root:root)"
        else
            warn "Expected 600 root:root, got: $perms"
        fi
    else
        warn "No config at $WG_CONF"
    fi
}

# ── Start / Stop ──────────────────────────────────────────────────────────────
cmd_start() {
    echo ""
    echo "── Starting $IFACE ──────────────────────────────────"
    sudo wg-quick up "$IFACE" && ok "wg-quick up $IFACE" || err "Failed to start $IFACE"
}

cmd_stop() {
    echo ""
    echo "── Stopping $IFACE ──────────────────────────────────"
    sudo wg-quick down "$IFACE" && ok "wg-quick down $IFACE" || err "Failed to stop $IFACE"
}

# ── Dispatch ──────────────────────────────────────────────────────────────────
case "${1:-}" in
    --validate) cmd_validate "${2:?Usage: $0 --validate /path/to/wg0.conf}" ;;
    --install)  cmd_install  "${2:?Usage: $0 --install /path/to/wg0.conf}" ;;
    --status)   cmd_status ;;
    --start)    cmd_start ;;
    --stop)     cmd_stop ;;
    *)
        echo "Usage: $0 --validate|--install|--status|--start|--stop [conf_path]"
        echo ""
        echo "  --validate /path/to/wg0.conf   Validate config (safe preview)"
        echo "  --install  /path/to/wg0.conf   Install config with backup"
        echo "  --status                        Show current WG status"
        echo "  --start                         wg-quick up \$WG_IFACE (default: wg0)"
        echo "  --stop                          wg-quick down \$WG_IFACE"
        echo ""
        echo "SECURITY: PrivateKey is never printed by this script."
        exit 1
        ;;
esac
