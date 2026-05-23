.PHONY: init plan apply destroy package

LAMBDA_DIR := modules/lambda

package:
	@echo "📦 Empaquetando lambdas con dependencias externas..."
	cd $(LAMBDA_DIR) && bash package.sh

init:
	terraform init

plan: package
	terraform plan -out=tfplan

apply:
	@test -f tfplan || (echo "❌ Corré 'make plan' primero" && exit 1)
	terraform apply tfplan
	@rm -f tfplan

destroy:
	terraform destroy
