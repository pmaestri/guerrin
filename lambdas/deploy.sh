#!/bin/bash
# Empaqueta las Lambdas del D3 y despliega el código en AWS.
# Requiere que el `terraform apply` del equipo ya haya corrido.
# Uso: ./deploy.sh [prefix]   (default: breadboss)
set -e

PREFIX=${1:-breadboss}
REGION=${AWS_REGION:-us-east-1}
LAMBDAS=("ingress" "order-processor")

echo "▶ Empaquetando Lambdas..."
bash "$(dirname "$0")/package.sh"

echo ""
for lambda in "${LAMBDAS[@]}"; do
  FUNCTION_NAME="${PREFIX}-${lambda}"
  ZIP_PATH="$(dirname "$0")/${lambda}/${lambda}.zip"

  echo "🚀 Desplegando ${FUNCTION_NAME}..."
  aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file "fileb://${ZIP_PATH}" \
    --region "$REGION" \
    --output json \
    --query '{FunctionName:FunctionName,CodeSize:CodeSize,LastModified:LastModified}' \
    --no-cli-pager

  echo "✅ ${FUNCTION_NAME} actualizada"
  echo ""
done

echo "🎉 Deploy completo. Verificá los logs:"
for lambda in "${LAMBDAS[@]}"; do
  echo "  aws logs tail /aws/lambda/${PREFIX}-${lambda} --follow --region ${REGION}"
done
