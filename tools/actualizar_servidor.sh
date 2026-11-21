#!/usr/bin/env bash
# Despliega en el servidor Docker cada merge a main.
#
# Si la rama remota tiene commits nuevos: git pull --ff-only y
# docker compose up -d --build. Si no, sale sin hacer nada.
# Pensado para cron cada 5 minutos:
#   */5 * * * * /ruta/a/silverlitofanos/tools/actualizar_servidor.sh >> $HOME/silver-actualizar.log 2>&1
#
# Los pedidos y archivos viven en ./datos (volumen del compose), así que no se tocan.
set -euo pipefail

RAMA="${SILVER_RAMA:-main}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

# Que dos corridas de cron no se encimen.
exec 9>"${TMPDIR:-/tmp}/silver-actualizar.lock"
if ! flock -n 9; then
  echo "$(date '+%F %T') otra actualización sigue corriendo; salgo."
  exit 0
fi

{
  # Todo el trabajo va dentro de una función que bash lee completa antes de
  # correrla: si el pull cambia este mismo archivo, se sigue usando la copia leída.
  actualizar() {
    git fetch --quiet origin "$RAMA"
    local local_sha remoto_sha
    local_sha="$(git rev-parse HEAD)"
    remoto_sha="$(git rev-parse "origin/$RAMA")"

    # También reconstruye si version.json falta o no es del commit actual.
    if [[ "$local_sha" == "$remoto_sha" ]] && grep -q "\"${local_sha:0:7}\"" backend/version.json 2>/dev/null; then
      exit 0
    fi

    echo "$(date '+%F %T') ${local_sha:0:7} -> ${remoto_sha:0:7}: actualizando"
    git checkout --quiet "$RAMA"
    git pull --ff-only --quiet origin "$RAMA"
    # La imagen no lleva .git: la versión que muestra la app va en version.json.
    printf '{"version": %s, "commit": "%s", "fecha": "%s"}\n' \
      "$(git rev-list --count HEAD)" "$(git rev-parse --short=7 HEAD)" \
      "$(git log -1 --format=%cd --date=format:'%Y-%m-%d %H:%M')" > backend/version.json
    docker compose up -d --build
    docker image prune -f >/dev/null
    echo "$(date '+%F %T') listo: $(git log -1 --format='%h %s')"
  }
  actualizar
  exit 0
}
