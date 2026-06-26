#!/usr/bin/env bash
set -euo pipefail
ufw --force enable
ufw reload
# Borrar de mayor a menor para no desfasar índices
for n in 32 31 30 22 21 20 19 18 17 16 15 14 13 12 11 10 9 8; do
  ufw --force delete "${n}" 2>/dev/null || true
done
echo "=== UFW limpio ==="
ufw status verbose
