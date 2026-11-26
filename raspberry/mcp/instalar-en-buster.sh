#!/usr/bin/env bash
# Instala el MCP en la Raspberry Pi 3 con Raspberry Pi OS Buster (glibc 2.28).
#
# Por qué existe: FastMCP depende de `cryptography`, cuyo wheel para ARMv7 pide glibc >= 2.31.
# Solución (la misma del .eim, ver docs/inconvenientes.md): correr Python con el loader y las
# bibliotecas de Debian Bookworm guardadas en ~/eim-libs. Con Python 3.11 todo sale de wheels
# ya compilados (PyPI + piwheels), sin compilar nada en la Pi.
#
# Uso (en la Pi):  bash instalar-en-buster.sh
# Después:         ~/py-bookworm.sh .venv/bin/python server.py
set -euo pipefail

LIBS="$HOME/eim-libs"
UV="$HOME/.local/bin/uv"
DEBIAN="http://deb.debian.org/debian/pool/main"
cd "$(dirname "$0")"

[ -x "$LIBS/lib/ld-linux-armhf.so.3" ] || { echo "Falta $LIBS (ver docs/inconvenientes.md)"; exit 1; }

echo "1/5 Bibliotecas de Bookworm que piden cffi y pyyaml (libffi8, libyaml)"
tmp=$(mktemp -d)
wget -q -P "$tmp" "$DEBIAN/libf/libffi/libffi8_3.4.4-1_armhf.deb"
wget -q -P "$tmp" "$DEBIAN/liby/libyaml/libyaml-0-2_0.2.5-1_armhf.deb"
for d in "$tmp"/*.deb; do dpkg-deb -x "$d" "$LIBS"; done
rm -rf "$tmp"

echo "2/5 Lanzador ~/py-bookworm.sh (corre un programa con el loader de Bookworm)"
cat > "$HOME/py-bookworm.sh" <<EOF
#!/bin/sh
exec $LIBS/lib/ld-linux-armhf.so.3 --library-path $LIBS/lib/arm-linux-gnueabihf:$LIBS/usr/lib/arm-linux-gnueabihf "\$@"
EOF
chmod +x "$HOME/py-bookworm.sh"

echo "3/5 Python 3.11 y entorno .venv"
"$UV" python install 3.11
rm -rf .venv
"$UV" venv --seed --python 3.11 .venv

echo "4/5 Dependencias desde uv.lock (solo wheels, sin compilar)"
"$UV" export --no-dev --frozen --no-hashes --no-emit-project > requirements-pi.txt
"$HOME/py-bookworm.sh" .venv/bin/python -m pip install -q --disable-pip-version-check \
  --only-binary=:all: --extra-index-url https://www.piwheels.org/simple -r requirements-pi.txt

echo "5/5 Prueba de importación"
"$HOME/py-bookworm.sh" .venv/bin/python -c \
  "import fastmcp, cryptography, yaml, boto3; print('OK: fastmcp', fastmcp.__version__)"
