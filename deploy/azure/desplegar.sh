#!/usr/bin/env bash
# Despliegue de DATACORE en Azure for Students (Azure Container Apps + PostgreSQL Flexible Server).
#
# Uso (desde la raíz del repositorio, con `az login` hecho):
#   bash deploy/azure/desplegar.sh infra     # grupo, base PostgreSQL, registro y entorno de Container Apps
#   bash deploy/azure/desplegar.sh imagen    # construye la imagen en Azure y la sube al registro
#   bash deploy/azure/desplegar.sh inicial   # carga única: roles, esquema, datos simulados, ETL y modelo (~15 min)
#   bash deploy/azure/desplegar.sh apps      # API (interna) y dashboard (público)
#   bash deploy/azure/desplegar.sh diario    # tarea programada diaria (2:00, Centro de México)
#   bash deploy/azure/desplegar.sh estado    # URL pública y estado de los recursos
#   bash deploy/azure/desplegar.sh todo      # todo lo anterior, en orden
#
# Las contraseñas se generan la primera vez en deploy/azure/secretos.env (no se versiona) y nunca se imprimen.
# Cada paso se puede repetir: si el recurso ya existe, se actualiza o se omite.
set -euo pipefail
cd "$(dirname "$0")/../.."

# --- configuración (se puede cambiar con variables de entorno) ---------------------------------------
GRUPO="${GRUPO:-datacore}"
REGION="${REGION:-eastus2}"
SUFIJO="${SUFIJO:-}"                      # se fija la primera vez en secretos.env (nombres únicos en Azure)
ENTORNO="${ENTORNO:-datacore-entorno}"
SECRETOS=deploy/azure/secretos.env

command -v az >/dev/null || PATH="/c/Program Files/Microsoft SDKs/Azure/CLI2/wbin:$PATH"  # recién instalado en Windows
az() { command az "$@" --only-show-errors; }
paso() { printf '\n== %s\n' "$*"; }

# --- secretos -----------------------------------------------------------------------------------------
if [[ ! -f $SECRETOS ]]; then
  python - "$SECRETOS" <<'PY'
import secrets, string, sys
alfabeto = string.ascii_letters + string.digits
clave = lambda n=28: "".join(secrets.choice(alfabeto) for _ in range(n))
sufijo = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(5))
with open(sys.argv[1], "w", encoding="utf8") as f:
    f.write(f"SUFIJO={sufijo}\nPG_ADMIN_USER=datacoreadmin\nPG_ADMIN_PASSWORD={clave()}\n"
            f"PG_APP_USER=datacore_app\nPG_APP_PASSWORD={clave()}\n"
            f"PG_LECTOR_USER=datacore_lector\nPG_LECTOR_PASSWORD={clave()}\n"
            f"DATACORE_API_KEY={clave(40)}\n")
PY
  echo "secretos generados en $SECRETOS (no se versiona)"
fi
set -a; source "$SECRETOS"; set +a

PG_SERVIDOR="datacore-pg-$SUFIJO"
PG_HOST="$PG_SERVIDOR.postgres.database.azure.com"
REGISTRO="datacore$SUFIJO"
IMAGEN="$REGISTRO.azurecr.io/datacore:latest"

# Variables comunes de los contenedores. Las claves van como secretos de Container Apps (secretref).
SECRETOS_APP=(pg-admin-password="$PG_ADMIN_PASSWORD" pg-app-password="$PG_APP_PASSWORD"
              pg-lector-password="$PG_LECTOR_PASSWORD" api-key="$DATACORE_API_KEY")
VARS_BASE=(PG_HOST="$PG_HOST" PG_PORT=5432 PG_DB=datacore PGSSLMODE=require
           PG_APP_USER="$PG_APP_USER" PG_APP_PASSWORD=secretref:pg-app-password
           PG_LECTOR_USER="$PG_LECTOR_USER" PG_LECTOR_PASSWORD=secretref:pg-lector-password
           DATACORE_API_KEY=secretref:api-key)
VARS_ADMIN=(PG_ADMIN_USER="$PG_ADMIN_USER" PG_ADMIN_PASSWORD=secretref:pg-admin-password)

credenciales_registro() {
  REG_USUARIO=$(az acr credential show -n "$REGISTRO" --query username -o tsv)
  REG_CLAVE=$(az acr credential show -n "$REGISTRO" --query "passwords[0].value" -o tsv)
}

infra() {
  paso "proveedores de recursos"
  for p in Microsoft.App Microsoft.OperationalInsights Microsoft.ContainerRegistry Microsoft.DBforPostgreSQL; do
    az provider register -n "$p" >/dev/null
  done
  az extension add -n containerapp --upgrade -y >/dev/null 2>&1 || true

  paso "grupo de recursos $GRUPO ($REGION)"
  az group create -n "$GRUPO" -l "$REGION" -o none

  paso "PostgreSQL Flexible Server $PG_SERVIDOR (Burstable B1ms, 32 GB, versión 16)"
  if ! az postgres flexible-server show -g "$GRUPO" -n "$PG_SERVIDOR" -o none 2>/dev/null; then
    az postgres flexible-server create -g "$GRUPO" -n "$PG_SERVIDOR" -l "$REGION" \
      --tier Burstable --sku-name Standard_B1ms --storage-size 32 --version 16 \
      --admin-user "$PG_ADMIN_USER" --admin-password "$PG_ADMIN_PASSWORD" \
      --public-access 0.0.0.0 --backup-retention 7 --yes -o none
  else
    echo "ya existe"
  fi

  paso "registro de contenedores $REGISTRO (Basic)"
  az acr show -n "$REGISTRO" -o none 2>/dev/null || az acr create -g "$GRUPO" -n "$REGISTRO" --sku Basic --admin-enabled true -o none

  paso "entorno de Container Apps $ENTORNO"
  az containerapp env show -g "$GRUPO" -n "$ENTORNO" -o none 2>/dev/null || \
    az containerapp env create -g "$GRUPO" -n "$ENTORNO" -l "$REGION" -o none
}

imagen() {
  paso "construcción de la imagen en Azure: $IMAGEN"
  az acr build -r "$REGISTRO" -t datacore:latest --platform linux/amd64 .
}

job() {  # job <nombre> <SERVICIO> <tipo: Manual|Schedule> [cron]
  local nombre=$1 servicio=$2 tipo=$3 cron=${4:-}
  credenciales_registro
  local comunes=(--image "$IMAGEN" --cpu 1 --memory 2Gi --replica-timeout 3600 --replica-retry-limit 0
                 --env-vars SERVICIO="$servicio" "${VARS_BASE[@]}" "${VARS_ADMIN[@]}")
  if az containerapp job show -g "$GRUPO" -n "$nombre" -o none 2>/dev/null; then
    az containerapp job secret set -g "$GRUPO" -n "$nombre" --secrets "${SECRETOS_APP[@]}" -o none
    az containerapp job update -g "$GRUPO" -n "$nombre" "${comunes[@]}" -o none
  else
    local trigger=(--trigger-type "$tipo")
    [[ $tipo == Schedule ]] && trigger+=(--cron-expression "$cron")
    az containerapp job create -g "$GRUPO" -n "$nombre" --environment "$ENTORNO" "${trigger[@]}" \
      --registry-server "$REGISTRO.azurecr.io" --registry-username "$REG_USUARIO" --registry-password "$REG_CLAVE" \
      --secrets "${SECRETOS_APP[@]}" "${comunes[@]}" -o none
  fi
}

inicial() {
  paso "tarea de carga inicial"
  job datacore-inicial inicial Manual
  local ejecucion
  ejecucion=$(az containerapp job start -g "$GRUPO" -n datacore-inicial --query name -o tsv)
  echo "ejecución $ejecucion iniciada; tarda unos 15 minutos"
  local estado=Running
  while [[ $estado == Running || $estado == Processing || $estado == "" ]]; do
    sleep 30
    estado=$(az containerapp job execution show -g "$GRUPO" -n datacore-inicial --job-execution-name "$ejecucion" \
             --query properties.status -o tsv 2>/dev/null || echo Running)
    printf '  %s %s\n' "$(date +%H:%M)" "$estado"
  done
  [[ $estado == Succeeded ]] || { echo "la carga inicial terminó en $estado; revisa los registros con:"; \
    echo "  az containerapp job logs show -g $GRUPO -n datacore-inicial --execution $ejecucion --container datacore-inicial"; exit 1; }
}

app() {  # app <nombre> <SERVICIO> <external|internal> [variables extra...]
  local nombre=$1 servicio=$2 ingreso=$3; shift 3
  credenciales_registro
  local vars=(SERVICIO="$servicio" PORT=8000 "${VARS_BASE[@]}" "$@")
  if az containerapp show -g "$GRUPO" -n "$nombre" -o none 2>/dev/null; then
    az containerapp secret set -g "$GRUPO" -n "$nombre" --secrets "${SECRETOS_APP[@]}" -o none
    az containerapp update -g "$GRUPO" -n "$nombre" --image "$IMAGEN" --set-env-vars "${vars[@]}" -o none
  else
    az containerapp create -g "$GRUPO" -n "$nombre" --environment "$ENTORNO" --image "$IMAGEN" \
      --registry-server "$REGISTRO.azurecr.io" --registry-username "$REG_USUARIO" --registry-password "$REG_CLAVE" \
      --ingress "$ingreso" --target-port 8000 --cpu 0.5 --memory 1Gi --min-replicas 0 --max-replicas 1 \
      --secrets "${SECRETOS_APP[@]}" --env-vars "${vars[@]}" -o none
  fi
}

apps() {
  paso "API (ingreso interno)"
  app datacore-api api internal
  paso "dashboard (ingreso público)"
  # Dentro del entorno, la API responde por su nombre.
  app datacore-dashboard dashboard external DATACORE_API_URL=http://datacore-api
}

diario() {
  paso "tarea diaria (08:00 UTC = 2:00 en el Centro de México)"
  job datacore-diario diario Schedule "0 8 * * *"
}

estado() {
  paso "recursos en $GRUPO"
  az resource list -g "$GRUPO" --query "[].{nombre:name, tipo:type}" -o table
  paso "dashboard"
  echo "https://$(az containerapp show -g "$GRUPO" -n datacore-dashboard --query properties.configuration.ingress.fqdn -o tsv)"
}

case "${1:-}" in
  infra|imagen|inicial|apps|diario|estado) "$1" ;;
  todo) infra; imagen; inicial; apps; diario; estado ;;
  *) sed -n '2,13p' "$0"; exit 2 ;;
esac
