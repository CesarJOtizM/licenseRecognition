#!/usr/bin/env bash
# Prueba de humo de la infraestructura local: valida compose, levanta PostgreSQL
# y revisa las bases porteria y porteria_test.
# Uso (Git Bash o Linux), desde la raiz del repo:  bash infra/scripts/smoke.sh
# No apaga nada al terminar. Apagar:  docker compose -f infra/compose.yaml down
# Apagar y borrar los datos:          docker compose -f infra/compose.yaml down -v
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1

readonly COMPOSE_FILE=infra/compose.yaml
readonly PROYECTO=porteria
readonly BD_PRUEBAS=porteria_test
readonly VOLUMEN="${PROYECTO}_postgres-data"
readonly RUTA_DATOS=/var/lib/postgresql
compose=(docker compose -f "$COMPOSE_FILE")

fallar() { echo "FALLO: $*" >&2; exit 1; }
paso() { echo "==> $*"; }
comprobar() {
  [[ "$3" == "$2" ]] || fallar "$1: se esperaba '$2' y se obtuvo '$3'"
  echo "    ok: $1 = $3"
}

paso "Revisando requisitos"
[[ -f "$COMPOSE_FILE" ]] || fallar "no existe $COMPOSE_FILE"
command -v docker >/dev/null 2>&1 || fallar "no se encontro 'docker'. Instala Docker Desktop."
docker info >/dev/null 2>&1 || fallar "Docker no responde. Abre Docker Desktop y espera 'Engine running'."

paso "Validando la configuracion de compose"
"${compose[@]}" config --quiet || fallar "compose.yaml no es valido (perfil por defecto)"
"${compose[@]}" --profile tools config --quiet || fallar "compose.yaml no es valido (perfil tools)"

paso "Levantando PostgreSQL (maximo 90 s)"
"${compose[@]}" up -d --wait --wait-timeout 90 \
  || fallar "PostgreSQL no quedo saludable. Revisa: docker compose -f $COMPOSE_FILE logs postgres"

usuario="$("${compose[@]}" exec -T postgres printenv POSTGRES_USER)"
bd_app="$("${compose[@]}" exec -T postgres printenv POSTGRES_DB)"

consultar() {
  "${compose[@]}" exec -T postgres psql -v ON_ERROR_STOP=1 -U "$usuario" -d "$1" -tAc "$2"
}

for bd in "$bd_app" "$BD_PRUEBAS"; do
  paso "Revisando la base '$bd'"
  respuesta="$(consultar "$bd" 'select 1')" \
    || fallar "no se pudo consultar '$bd'. Si el volumen es anterior al script de init, usa down -v y repite."
  comprobar "select 1" 1 "$respuesta"
  comprobar "codificacion" UTF8 "$(consultar "$bd" 'show server_encoding')"
  comprobar "zona horaria" UTC "$(consultar "$bd" 'show timezone')"
  comprobar "proveedor de locale" b \
    "$(consultar "$bd" 'select datlocprovider from pg_database where datname = current_database()')"
done

paso "Revisando que los datos vivan en el volumen '$VOLUMEN'"
# La imagen declara VOLUME en esa ruta: sin el volumen con nombre habria uno anonimo, por eso se compara el nombre.
contenedor="$("${compose[@]}" ps -q postgres)"
montajes="$(docker inspect --format \
  '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}} {{.Destination}}{{println}}{{end}}{{end}}' \
  "$contenedor")" || fallar "no se pudo inspeccionar el contenedor de postgres"
grep -qx "$VOLUMEN $RUTA_DATOS" <<<"$montajes" \
  || fallar "no hay un volumen '$VOLUMEN' montado en $RUTA_DATOS. Montajes de tipo volume: ${montajes:-ninguno}"
echo "    ok: $VOLUMEN -> $RUTA_DATOS"

paso "Revisando que el puerto solo escuche en 127.0.0.1"
publicado="$("${compose[@]}" port postgres 5432)"
[[ "$publicado" == 127.0.0.1:* ]] || fallar "puerto publicado en '$publicado' (se esperaba 127.0.0.1:...)"
echo "    ok: $publicado"

paso "Revisando que Adminer no arranque sin --profile tools"
adminer="$(docker ps -q --filter "label=com.docker.compose.project=$PROYECTO" \
  --filter label=com.docker.compose.service=adminer)"
[[ -z "$adminer" ]] || fallar "Adminer esta corriendo. Si lo levantaste tu: docker compose -f $COMPOSE_FILE --profile tools stop adminer"

echo "Listo: la infraestructura local funciona."
