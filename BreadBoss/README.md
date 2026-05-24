# BreadBoss — Infraestructura AWS con Terraform

Este repositorio contiene toda la infraestructura de BreadBoss desplegada en AWS mediante Terraform.

## Prerequisitos

| Herramienta | Versión mínima | Instalación |
|---|---|---|
| Terraform | >= 1.6 | `brew install terraform` |
| AWS CLI | cualquiera | `brew install awscli` |
| Python | >= 3.9 | para empaquetar las Lambdas |
| bash | cualquiera | viene en macOS/Linux |

### Perfil AWS

El provider de Terraform usa el perfil `terraform-admin`. Antes de cualquier comando, asegurate de tenerlo configurado:

```bash
aws configure --profile terraform-admin
```

Necesitás un Access Key y Secret Key con permisos de administración sobre la cuenta AWS del proyecto.

---

## Configuración de variables (obligatorio)

Terraform requiere un archivo `terraform.tfvars` con los valores de las variables sensibles y de entorno. **Este archivo no está commiteado** porque contiene secretos.

Copiá el ejemplo y completá los valores:

```bash
cp terraform.tfvars.example terraform.tfvars
```

Luego editá `terraform.tfvars` con los valores reales:

```hcl
aws_region                 = "us-east-1"
prefix                     = "breadboss"
az_count                   = 2
cognito_test_user_email    = "tu-email@ejemplo.com"
cognito_test_user_password = "TuPassword123!"
ses_sender_email           = "email-verificado-en-ses@ejemplo.com"
openai_api_key             = "sk-..."
```

| Variable | Descripción |
|---|---|
| `aws_region` | Región AWS donde se despliega todo |
| `prefix` | Prefijo para nombrar los recursos (no cambiar en prod) |
| `az_count` | Cantidad de Availability Zones (mínimo 2) |
| `cognito_test_user_email` | Email del usuario de prueba en Cognito |
| `cognito_test_user_password` | Password del usuario de prueba en Cognito |
| `ses_sender_email` | Email verificado en SES para envío de notificaciones |
| `openai_api_key` | API key de OpenAI para el agente auditor |

> **Importante:** `cognito_test_user_password` y `openai_api_key` son sensibles. Nunca los commitees.

---

## Flujo de trabajo para aplicar cambios de infra

### 1. Inicializar Terraform (solo la primera vez o al agregar providers)

```bash
make init
```

Descarga los providers y configura el backend local.

---

### 2. Planificar los cambios

```bash
make plan
```

Este comando hace dos cosas en orden:

1. **Empaqueta las Lambdas** — ejecuta `modules/lambda/package.sh` para generar los `.zip` con el código y las dependencias Python de cada función.
2. **Genera el plan** — corre `terraform plan` y guarda el resultado en un archivo `tfplan`.

El output muestra exactamente qué recursos se van a crear, modificar o eliminar. **Revisalo siempre antes de aplicar.**

```
+ resource will be created
~ resource will be updated in-place
- resource will be destroyed
```

---

### 3. Aplicar los cambios

```bash
make apply
```

- Requiere que exista un `tfplan` generado en el paso anterior. Si no existe, el comando falla con un mensaje de error.
- Aplica exactamente lo que el plan mostró — sin sorpresas.
- Al terminar, elimina el archivo `tfplan` automáticamente.

> Si pasó mucho tiempo entre el `plan` y el `apply`, o si alguien más hizo cambios en la infra, volvé a correr `make plan` para generar un plan fresco.

---

### Flujo completo de un cambio típico

```bash
# Una sola vez por máquina:
cp terraform.tfvars.example terraform.tfvars
# (editar terraform.tfvars con los valores reales)
make init

# Cada vez que se quiera aplicar un cambio:
make plan   # revisar el output
make apply  # aplicar solo si el plan es el esperado
```

---

## Destruir la infraestructura

```bash
make destroy
```

Elimina **todos** los recursos gestionados por Terraform. Usar con precaución — en producción esto borra la base de datos, las colas, las funciones y todo lo demás.

---

## Estructura del repositorio

```
BreadBoss/
├── main.tf                  # recursos principales
├── variables.tf             # declaración de variables
├── outputs.tf               # outputs del stack
├── versions.tf              # versiones de providers y perfil AWS
├── terraform.tfvars.example # plantilla de variables (commiteable)
├── terraform.tfvars         # valores reales (NO commitear)
├── Makefile                 # comandos del proyecto
└── modules/
    ├── lambda/              # código y packaging de cada Lambda
    │   ├── package.sh       # script de empaquetado
    │   ├── ingress/
    │   ├── kitchen-manager/
    │   ├── order-processor/
    │   ├── delivery-tracker/
    │   ├── stock-updater/
    │   ├── notifier/
    │   └── ...
    └── ...
```
