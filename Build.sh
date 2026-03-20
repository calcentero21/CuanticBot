#!/usr/bin/env bash
set -e

echo "==> Instalando dependencias Python..."
pip install -r requirements.txt

echo "==> Instalando Node.js via nodeenv..."
pip install nodeenv
nodeenv --node=18.20.0 --prebuilt /opt/node
export PATH="/opt/node/bin:$PATH"

echo "==> Verificando Node.js..."
node --version

echo "==> Build completado ✅"
