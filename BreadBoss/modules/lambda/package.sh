#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PACKAGED=("ingress" "kitchen-manager" "delivery-tracker" "stock-updater" "notifier")

for lambda in "${PACKAGED[@]}"; do
  echo "Empaquetando $lambda..."
  cd "$SCRIPT_DIR/$lambda"

  rm -rf package
  rm -f "${lambda}.zip"
  mkdir package

  if [ -f requirements.txt ]; then
    pip3 install -r requirements.txt \
      --platform manylinux2014_x86_64 \
      --python-version 3.11 \
      --only-binary=:all: \
      --implementation cp \
      -t ./package --quiet
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
