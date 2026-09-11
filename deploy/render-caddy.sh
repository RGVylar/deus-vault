#!/usr/bin/env bash
# Renderiza deploy/Caddyfile → /etc/caddy/Caddyfile y recarga Caddy.
# Lo usa install.sh y el comando de actualización del README: sin este paso,
# un cambio en deploy/Caddyfile (p. ej. una ruta nueva al backend) se queda
# en el repo y producción sigue con la config vieja aunque se recargue Caddy.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/deus-vault}"
BACKEND_PORT="${BACKEND_PORT:-8000}"

[[ -f "$APP_DIR/deploy/Caddyfile" ]] || { echo "Missing $APP_DIR/deploy/Caddyfile" >&2; exit 1; }
sed -e "s|__BACKEND_PORT__|$BACKEND_PORT|g" \
    -e "s|__APP_DIR__|$APP_DIR|g" \
    "$APP_DIR/deploy/Caddyfile" > /etc/caddy/Caddyfile.new
caddy validate --config /etc/caddy/Caddyfile.new --adapter caddyfile >/dev/null 2>&1 \
    || { echo "Generated Caddyfile is invalid" >&2; rm -f /etc/caddy/Caddyfile.new; exit 1; }
mv /etc/caddy/Caddyfile.new /etc/caddy/Caddyfile
systemctl reload caddy
echo "Caddy config rendered and reloaded ✓"
