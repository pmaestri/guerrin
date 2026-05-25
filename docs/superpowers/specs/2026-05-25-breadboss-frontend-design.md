# BreadBoss Frontend — Design Spec

**Fecha:** 2026-05-25
**Branch sugerido:** `feature/frontend-customer-kitchen`
**Alcance:** tres pantallas funcionales nuevas (cliente + admin cocina) + módulo de auth + hosting S3+CloudFront.

---

## 1. Objetivo

Agregar pantallas funcionales al proyecto BreadBoss para que la presentación universitaria muestre el ciclo completo del pedido desde la perspectiva del cliente y del admin de cocina. El dashboard analítico existente (`index.html`) se mantiene sin cambios — es complementario.

**Resultado esperado:** un usuario logueado puede ver el menú, hacer un pedido y trackear su estado; un admin (cualquier usuario logueado, link oculto) puede ver pedidos en cocina y marcarlos como listos para retirar.

---

## 2. Decisiones de diseño tomadas

| Tema | Decisión |
|---|---|
| Stack | HTML + Vanilla JS (sin build) |
| Auth flow | Form propio que llama Cognito con `USER_PASSWORD_AUTH` vía `fetch` (sin SDK) |
| Acceso `kitchen.html` | Cualquier usuario Cognito logueado, link oculto |
| Update del tracking | Botón "Actualizar estado" (refresh manual, no polling) |
| Hosting | S3 privado + CloudFront con OAC |
| Estilo | Reutiliza `styles.css` existente |
| Logout | Botón presente en cada pantalla |
| Tracking sin `orderId` en URL | Fallback a `localStorage` (último `orderId` guardado al crear pedido) |

---

## 3. Estructura de archivos

```
BreadBoss-Front/
├── index.html                  (sin cambios — dashboard estático)
├── dashboard.js                (sin cambios)
├── styles.css                  (extender con componentes nuevos)
│
├── login.html                  NUEVO
├── menu.html                   NUEVO
├── tracking.html               NUEVO
├── kitchen.html                NUEVO
│
└── js/
    ├── config.js               NUEVO — constantes públicas
    ├── auth.js                 NUEVO — login/logout/getToken/requireAuth
    └── api.js                  NUEVO — wrapper fetch con Authorization

BreadBoss/
└── modules/
    └── frontend/               NUEVO módulo Terraform
        ├── main.tf             S3 bucket privado + CloudFront + OAC
        ├── variables.tf
        └── outputs.tf          cloudfront_url
```

---

## 4. Componentes — interfaces

### 4.1 `js/config.js`

Exporta constantes:

```js
window.BB_CONFIG = {
  API_URL: "https://<api-id>.execute-api.us-east-1.amazonaws.com",
  COGNITO_REGION: "us-east-1",
  COGNITO_CLIENT_ID: "<cognito-client-id>",
};
```

Valores se completan a mano después de `terraform apply` (o un script que los pueda inyectar; para esta fase aceptamos edición manual).

### 4.2 `js/auth.js`

API pública (todas funciones globales en `window.BB_AUTH`):

| Función | Comportamiento |
|---|---|
| `login(email, password)` | POST a `https://cognito-idp.<region>.amazonaws.com/` con header `X-Amz-Target: AWSCognitoIdentityProviderService.InitiateAuth`, body `{AuthFlow: "USER_PASSWORD_AUTH", ClientId, AuthParameters: {USERNAME, PASSWORD}}`. Guarda `IdToken` y `expiresAt` en `localStorage`. Retorna `{ok: true}` o `{ok: false, error}`. |
| `logout()` | Limpia `localStorage` (token + lastOrderId opcionalmente). Redirige a `login.html`. |
| `getToken()` | Lee `IdToken` de `localStorage`. Si está expirado, retorna `null`. |
| `requireAuth()` | Si `getToken()` retorna `null`, redirige a `login.html`. Se llama al inicio de cada pantalla protegida. |
| `getEmail()` | Parsea el JWT (decode base64 del payload) y retorna `claims.email`. Usado para mostrar "Hola, agus@..." en header. |

### 4.3 `js/api.js`

Wrapper que inyecta `Authorization: Bearer <token>`:

| Función | Endpoint |
|---|---|
| `getMenu()` | GET `/menu` |
| `createOrder({deliveryAddress, items, channel})` | POST `/orders` |
| `getOrder(orderId)` | GET `/orders/{id}` |
| `listOrdersByStatus(status)` | GET `/orders?status=...` |
| `markReady(orderId)` | POST `/orders/{id}/ready` |
| `deliverOrder(orderId)` | POST `/orders/{id}/deliver` (usado por kitchen.html para cerrar el pedido tras la entrega) |

Manejo de errores: si la respuesta es 401, llamar `BB_AUTH.logout()` (token expirado). Si es 4xx/5xx, lanzar Error con `body.error`.

---

## 5. Pantallas — comportamiento

### 5.1 `login.html`

- Layout: card centrada, logo BreadBoss arriba, dos inputs (email, password), botón "Entrar".
- Submit → `BB_AUTH.login(email, password)`. Si OK → redirect a `menu.html`. Si error → mostrar mensaje rojo debajo del form.
- Si ya hay token válido al cargar → redirect directo a `menu.html`.

### 5.2 `menu.html`

- Header: logo + email del usuario + "Mis pedidos" (link a `tracking.html`) + botón "Salir" (logout).
- Body:
  - Grid de cards con cada item del menú (`getMenu()`): foto placeholder, nombre, precio, botón "+".
  - Sidebar derecho: carrito (items con qty editable, subtotal, total).
  - Input para `deliveryAddress`.
  - Botón "Hacer pedido" → `createOrder()`. En success: guardar `orderId` en `localStorage.lastOrderId` y redirect a `tracking.html?orderId=...`.
- Carrito persiste en `localStorage` mientras no se confirme.

### 5.3 `tracking.html`

- Lee `orderId` de query string. Si no hay → lee `localStorage.lastOrderId`. Si tampoco → mostrar mensaje "No tenés pedidos recientes" + link a `menu.html`.
- Header: igual que `menu.html` (logo + email + nav + logout).
- Body:
  - Card grande con `orderId` y `status` actual.
  - Stepper visual horizontal: 4 nodos (RECIBIDO → EN_PREPARACION → EN_CAMINO → ENTREGADO). El nodo actual y los previos están "activos" (color principal), los siguientes en gris.
  - Lista de items del pedido (`item.name × qty — $price`).
  - Línea: total, deliveryAddress, tiempo_entrega_min (si ENTREGADO).
  - Botón "Actualizar estado" → vuelve a llamar `getOrder()` y re-renderiza.

### 5.4 `kitchen.html`

- Header: igual al resto + indicador "MODO COCINA" como badge.
- Body:
  - Botón "Refrescar lista" arriba.
  - Dos secciones:
    - **"En preparación"**: cards con pedidos `EN_PREPARACION` (`listOrdersByStatus("EN_PREPARACION")`). Por card: `orderId` (cortado a 8 chars), tiempo desde creación, items, total, deliveryAddress. Botón **"Listo para retirar"** → `markReady(orderId)`. En success: card desaparece al próximo refresh.
    - **"En camino"**: cards con pedidos `EN_CAMINO` (`listOrdersByStatus("EN_CAMINO")`). Mismos datos. Botón **"Marcar entregado"** → `deliverOrder(orderId)`. En success: card desaparece al próximo refresh.
- Al cargar, llama ambos `listOrdersByStatus(...)` automáticamente.

---

## 6. Estilo

Reutilizar `BreadBoss-Front/styles.css` y agregar al final un bloque comentado `/* =========== APP SCREENS =========== */` con:

- `.app-shell` — wrapper con max-width y padding consistente
- `.app-header` — barra superior con logo, nav links, email pill, logout button
- `.menu-grid`, `.menu-card`, `.cart-panel` — para `menu.html`
- `.stepper`, `.stepper-node`, `.stepper-node.active`, `.stepper-line` — para `tracking.html`
- `.kitchen-card`, `.kitchen-card .btn-ready` — para `kitchen.html`
- `.login-card`, `.login-form input` — para `login.html`

Paleta y tipografía: las que ya usa `index.html` (Inter, fondo crema #f5f1ea, acento naranja).

---

## 7. Infra — `BreadBoss/modules/frontend/`

### 7.1 Recursos Terraform

| Recurso | Propósito |
|---|---|
| `aws_s3_bucket.frontend` | Bucket privado |
| `aws_s3_bucket_public_access_block.frontend` | Bloquea todo acceso público directo |
| `aws_cloudfront_origin_access_control.frontend` | OAC para que CloudFront pueda leer del bucket |
| `aws_cloudfront_distribution.frontend` | Distribución con default_root_object = "login.html", SPA-style error responses (403/404 → /login.html) |
| `aws_s3_bucket_policy.frontend` | Permite GetObject solo desde la distribución (vía OAC) |

### 7.2 Subida de archivos

Para esta fase, subida manual con:

```bash
aws s3 sync BreadBoss-Front/ s3://<bucket-name>/ --exclude ".DS_Store"
```

(Opcional futuro: `aws_s3_object` con `for_each` sobre `fileset()`, pero agrega ruido al estado.)

### 7.3 Cambio en módulo Cognito

Habilitar `USER_PASSWORD_AUTH` en el `aws_cognito_user_pool_client` existente, agregando a `explicit_auth_flows`:
```
"ALLOW_USER_PASSWORD_AUTH"
```
(además de los que ya tenga).

### 7.4 Outputs nuevos

- `module.frontend.cloudfront_url` — URL pública (`https://dxxxxxx.cloudfront.net`).
- Opcional: `aws_cognito_user_pool_client.client_id` ya está expuesto por el módulo cognito; lo usamos en `config.js`.

---

## 8. Flujo de datos

```
                ┌──────────────────┐
                │   CloudFront     │
                │   (S3 origin)    │
                └────────┬─────────┘
                         │ servir HTML/JS/CSS
                         ▼
                    Browser
                         │
                         ├─ login.html ──► Cognito InitiateAuth ──► IdToken
                         │
                         │  (con Authorization: Bearer IdToken)
                         ├─ menu.html      ──► API GW ──► menu-reader / ingress
                         ├─ tracking.html  ──► API GW ──► order-reader
                         └─ kitchen.html   ──► API GW ──► order-reader / order-ready
```

---

## 9. Testing manual (criterios de aceptación)

1. Abro la URL de CloudFront → me redirige a `login.html`.
2. Ingreso credenciales válidas → entro a `menu.html` con mi email visible en el header.
3. Veo los items del menú; agrego dos al carrito; ingreso dirección; click "Hacer pedido" → redirige a `tracking.html?orderId=...`.
4. `tracking.html` muestra `RECIBIDO`. Click "Actualizar estado" después de unos segundos → muestra `EN_PREPARACION`.
5. Abro `kitchen.html` en otra pestaña → veo el pedido recién creado en la lista.
6. Click "Listo para retirar" → el pedido desaparece del listado (próximo refresh).
7. Vuelvo a `tracking.html`, click "Actualizar estado" → `EN_CAMINO`. En `kitchen.html` (sección "En camino") click "Marcar entregado" → en `tracking.html`, próximo "Actualizar estado" → `ENTREGADO` con `tiempo_entrega_min`.
8. Click "Salir" en cualquier pantalla → vuelve a `login.html` y el token se borra.
9. Entrar a `tracking.html` sin query param → muestra el último pedido (de `localStorage`).

---

## 10. Fuera de alcance (YAGNI)

- Registro de usuarios (asumimos que el usuario Cognito ya existe; creado vía Terraform o consola).
- Refresh token automático cuando expira (logout fuerza re-login).
- Roles/grupos Cognito.
- Tracking via WebSocket/SSE.
- Edición de pedidos.
- Historial de pedidos previos (solo último orden via localStorage).
- CI/CD para deploy del frontend (sync manual con `aws s3 sync`).
- Dominio custom + HTTPS personalizado (usamos `*.cloudfront.net`).

---

## 11. Decisiones abiertas a confirmar antes del plan

Ninguna — todas las decisiones del cuestionario están reflejadas arriba. Si al releer encontrás algo que no encaja, lo ajustamos antes de pasar a writing-plans.
