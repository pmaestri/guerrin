#!/bin/bash
set -e

LAMBDAS=("ingress" "order-processor" "kitchen-manager" "stock-updater" "delivery-tracker" "notifier")

for lambda in "${LAMBDAS[@]}"; do
  echo "📦 Empaquetando $lambda..."
  cd "$lambda"

  rm -rf package dist
  mkdir package

  pip3 install -r requirements.txt -t ./package --quiet

  cd package
  zip -r "../${lambda}.zip" . --quiet
  cd ..

  zip "${lambda}.zip" handler.py --quiet

  rm -rf package
  echo "✅ ${lambda}.zip listo"
  cd ..
done

echo ""
echo "🚀 Zips generados:"
ls -lh *//*.zip 2>/dev/null || ls */*.zip
