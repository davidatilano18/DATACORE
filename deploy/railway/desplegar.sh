#!/usr/bin/env bash
# Despliegue de DATACORE en Railway, en su propio proyecto ("datacore").
#
# Requisitos: `railway login` hecho y el directorio enlazado al proyecto datacore (`railway link`), que ya
# tiene el servicio Postgres (`railway add --database postgres`).
#
# Uso (desde la raíz del repositorio):
#   bash deploy/railway/desplegar.sh servicios   # crea API, dashboard y operación con sus variables
#   bash deploy/railway/desplegar.sh inicial     # carga única: roles, esquema, datos simulados, ETL y modelo
#   bash deploy/railway/desplegar.sh apps        # sube la imagen a la API y al dashboard y les da dominio público
#   bash deploy/railway/desplegar.sh diario      # convierte "operación" en la tarea diaria (2:00, Centro de México)
#   bash deploy/railway/desplegar.sh estado      # servicios y ligas públicas
#
# Las contraseñas se generan la primera vez en deploy/railway/secretos.env (no se versiona) y nunca se imprimen.
set -euo pipefail
cd "$(dirname "$0")/../.."

SECRETOS=deploy/railway/secretos.env
API=datacore-api
DASH=datacore-dashboard
OPER=datacore-diario
paso() { printf '\n== %s\n' "$*"; }

# Seguridad: nunca operar sobre otro proyecto de la cuenta.
proyecto=$(railway status --json | python -c "import json,sys; print(json.load(sys.stdin)['name'])")
[[ $proyecto == datacore ]] || { echo "el directorio está enlazado a '$proyecto', no a 'datacore'; abortando" >&2; exit 1; }
PROYECTO_ID=$(railway status --json | python -c "import json,sys; print(json.load(sys.stdin)['id'])")

if [[ ! -f $SECRETOS ]]; then
  python - "$SECRETOS" <<'PY'
import secrets, string, sys
alfabeto = string.ascii_letters + string.digits
clave = lambda n=28: "".join(secrets.choice(alfabeto) for _ in range(n))
with open(sys.argv[1], "w", encoding="utf8") as f:
    f.write(f"PG_APP_PASSWORD={clave()}\nPG_LECTOR_PASSWORD={clave()}\nDATACORE_API_KEY={clave(40)}\n")
PY
  echo "secretos generados en $SECRETOS (no se versiona)"
fi
set -a; source "$SECRETOS"; set +a

# Conexión por la red privada de Railway; el administrador es el usuario del servicio Postgres.
PG_VARS=('PG_HOST=${{Postgres.PGHOST}}' 'PG_PORT=${{Postgres.PGPORT}}' PG_DB=datacore
         PG_APP_USER=datacore_app "PG_APP_PASSWORD=$PG_APP_PASSWORD"
         PG_LECTOR_USER=datacore_lector "PG_LECTOR_PASSWORD=$PG_LECTOR_PASSWORD"
         "DATACORE_API_KEY=$DATACORE_API_KEY")
ADMIN_VARS=('PG_ADMIN_USER=${{Postgres.PGUSER}}' 'PG_ADMIN_PASSWORD=${{Postgres.PGPASSWORD}}')

existe() { railway service list --json | python -c "import json,sys; d=json.load(sys.stdin); n=sys.argv[1]; \
sys.exit(0 if any((s.get('name') or s.get('serviceName'))==n for s in (d if isinstance(d,list) else d.get('services',[]))) else 1)" "$1"; }

# Sube una copia limpia (solo archivos versionados o no ignorados, sin la memoria): en Windows, `railway up` desde la
# carpeta de trabajo falla con "Acceso denegado" si hay bitácoras abiertas por la API o el dashboard locales.
subir() {  # subir <servicio>
  local copia; copia=$(mktemp -d)
  git -c core.quotepath=off ls-files -z -co --exclude-standard | grep -zv '^docs/memoria/' | tar --null -cf - -T - | tar -xf - -C "$copia"
  railway up "$copia" --path-as-root --service "$1" --project "$PROYECTO_ID" --environment production --detach
  rm -rf "$copia"
}

variables() {  # variables <servicio> k=v ...
  local s=$1; shift
  local args=(); for kv in "$@"; do args+=(--set "$kv"); done
  railway variables --service "$s" --skip-deploys "${args[@]}" >/dev/null
}

servicios() {
  for s in $API $DASH $OPER; do
    paso "servicio $s"
    existe "$s" && echo "ya existe" || railway add --service "$s" >/dev/null
  done
  variables $API SERVICIO=api "${PG_VARS[@]}"
  variables $DASH SERVICIO=dashboard "DATACORE_API_KEY=$DATACORE_API_KEY" \
    'DATACORE_API_URL=https://${{datacore-api.RAILWAY_PUBLIC_DOMAIN}}'
  variables $OPER SERVICIO=inicial "${PG_VARS[@]}" "${ADMIN_VARS[@]}"
  # Las tareas terminan solas: no se reinician al salir.
  instancia $OPER 'restartPolicyType: NEVER'
}

# Configura la instancia de un servicio con la API de Railway (`railway environment edit` no aplicaba estos cambios).
instancia() {  # instancia <servicio> '<campos de ServiceInstanceUpdateInput>'
  local sid eid
  sid=$(railway service list --json | python -c "import json,sys; print(next(s['id'] for s in json.load(sys.stdin) if s['name']==sys.argv[1]))" "$1")
  eid=$(railway status --json | python -c "import json,sys; d=json.load(sys.stdin); print(next(e['node']['id'] for e in d['environments']['edges'] if e['node']['name']=='production'))")
  railway api "mutation { serviceInstanceUpdate(serviceId: \"$sid\", environmentId: \"$eid\", input: { $2 }) }" >/dev/null
}

inicial() {
  paso "carga inicial en $OPER (unos 15 minutos)"
  variables $OPER SERVICIO=inicial
  subir $OPER
  echo "sigue el avance con: railway logs --service $OPER"
}

apps() {
  for s in $API $DASH; do
    paso "despliegue de $s"
    subir "$s"
    railway domain --service "$s" >/dev/null 2>&1 || true
  done
}

diario() {
  paso "tarea diaria: 08:00 UTC = 2:00 en el Centro de México"
  # El monitoreo revisa la API y el dashboard por sus dominios públicos.
  variables $OPER SERVICIO=diario 'DATACORE_API_URL=https://${{datacore-api.RAILWAY_PUBLIC_DOMAIN}}'     'DATACORE_DASHBOARD_URL=https://${{datacore-dashboard.RAILWAY_PUBLIC_DOMAIN}}'
  instancia $OPER 'cronSchedule: "0 8 * * *", restartPolicyType: NEVER'
  # Con el horario activo, la subida no ejecuta la tarea en ese momento. (No usar `railway service redeploy`:
  # reconstruye sin el Dockerfile.)
  subir $OPER
}

estado() {
  railway service status --all 2>/dev/null || railway service list
  for s in $API $DASH; do railway domain --service "$s" 2>/dev/null | grep -o 'https://[^ ]*' | head -1; done
}

case "${1:-}" in
  servicios|inicial|apps|diario|estado) "$1" ;;
  *) sed -n '2,13p' "$0"; exit 2 ;;
esac
