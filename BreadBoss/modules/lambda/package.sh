#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PACKAGED=("ingress" "kitchen-manager" "delivery-tracker" "stock-updater" "notifier")

for lambda in "${PACKAGED[@]}"; do
  echo "Empaquetando $lambda..."
  cd "$SCRIPT_DIR/$lambda"

  rm -rf package
  mkdir package

  if [ -f requirements.txt ]; then
    pip3 install -r requirements.txt -t ./package --quiet
  fi

  mkdir -p ./package/shared
  cp "$SCRIPT_DIR/shared/idempotency.py" ./package/shared/

  cd package
  zip -r "../${lambda}.zip" . --quiet
  cd ..

  zip "${lambda}.zip" handler.py --quiet

  rm -rf package
  echo "${lambda}.zip listo"
  cd "$SCRIPT_DIR"
done

echo ""
echo "Zips generados:"
find . -name "*.zip" | head -20
