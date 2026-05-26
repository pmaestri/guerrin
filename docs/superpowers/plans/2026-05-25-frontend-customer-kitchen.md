# BreadBoss Frontend (Cliente + Cocina) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar 4 pantallas HTML/Vanilla JS (login, menu, tracking, kitchen) + módulo de auth contra Cognito + hosting S3+CloudFront, manteniendo la identidad visual del dashboard existente.

**Architecture:** HTML estático servido por CloudFront sobre S3 privado (OAC). 3 módulos JS compartidos (`config.js`, `auth.js`, `api.js`) que cada pantalla incluye. Auth contra Cognito vía `fetch` directo a `cognito-idp.<region>.amazonaws.com` con `USER_PASSWORD_AUTH` (ya habilitado en Terraform). JWT en `localStorage`. Sin polling — refresh manual en tracking y kitchen.

**Tech Stack:** HTML5, Vanilla JS (ES6+, sin build), CSS (extendiendo `styles.css` existente), Terraform AWS, S3, CloudFront.

**Branch:** Usuario ya está en `feature/frontend-customer-kitchen` con el spec commiteado.

---

## File Structure

**Files a crear (BreadBoss-Front/):**
- `BreadBoss-Front/js/config.js` — constantes públicas (API_URL, COGNITO_*).
- `BreadBoss-Front/js/auth.js` — login/logout/getToken/requireAuth/getEmail.
- `BreadBoss-Front/js/api.js` — wrapper fetch con Authorization header + helpers por endpoint.
- `BreadBoss-Front/login.html` — pantalla de login.
- `BreadBoss-Front/menu.html` — listado del menú + carrito + crear pedido.
- `BreadBoss-Front/tracking.html` — stepper de estado del pedido + refresh manual.
- `BreadBoss-Front/kitchen.html` — admin: pedidos EN_PREPARACION + EN_CAMINO + acciones.

**Files a modificar:**
- `BreadBoss-Front/styles.css` — agregar bloque `/* === APP SCREENS === */` con clases para las nuevas pantallas.

**Files a crear (Terraform):**
- `BreadBoss/modules/frontend/main.tf` — S3 + CloudFront + OAC + policy.
- `BreadBoss/modules/frontend/variables.tf` — `prefix`.
- `BreadBoss/modules/frontend/outputs.tf` — `cloudfront_url`, `bucket_name`.

**Files a modificar (Terraform):**
- `BreadBoss/main.tf` — agregar `module "frontend"`.
- `BreadBoss/outputs.tf` (si existe; si no, crear) — exponer `cloudfront_url`, `bucket_name`, `api_url`, `cognito_client_id` para configurar el frontend.

---

## Task 1: Crear `config.js`

**Files:**
- Create: `BreadBoss-Front/js/config.js`

- [ ] **Step 1: Obtener valores de Terraform**

Run:
```bash
cd /Users/agustin/Documents/Projects/guerrin/BreadBoss && terraform output -json 2>&1 | grep -E "(api|cognito)" || terraform output
```
Expected: imprime los outputs disponibles. Anotar `api_url` (o equivalente) y `cognito_client_id`. Si no están expuestos, usar la consola AWS o revisar `BreadBoss/modules/api_gateway/outputs.tf` y `BreadBoss/modules/cognito/outputs.tf`.

Si no hay `terraform output` con esos valores, ejecutar:
```bash
cd /Users/agustin/Documents/Projects/guerrin/BreadBoss && terraform state show 'module.api_gateway.aws_apigatewayv2_api.this' | grep api_endpoint
cd /Users/agustin/Documents/Projects/guerrin/BreadBoss && terraform state show 'module.cognito.aws_cognito_user_pool_client.app' | grep '\bid\b'
```

- [ ] **Step 2: Crear `BreadBoss-Front/js/config.js`**

Reemplazar los valores `<...>` con los obtenidos en Step 1:

```js
window.BB_CONFIG = {
  API_URL: "<api_endpoint>",
  COGNITO_REGION: "us-east-1",
  COGNITO_CLIENT_ID: "<cognito_client_id>",
};
```

- [ ] **Step 3: Commit**

```bash
cd /Users/agustin/Documents/Projects/guerrin
git add BreadBoss-Front/js/config.js
git commit -m "feat(front): config.js con endpoints API y Cognito"
```

---

## Task 2: Crear `auth.js`

**Files:**
- Create: `BreadBoss-Front/js/auth.js`

- [ ] **Step 1: Crear `auth.js` con login/logout/token helpers**

Contenido completo de `BreadBoss-Front/js/auth.js`:

```js
(function () {
  const STORAGE_KEY = "bb_auth";

  function _save(idToken, expiresInSec) {
    const expiresAt = Date.now() + expiresInSec * 1000;
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ idToken, expiresAt }));
  }

  function _read() {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch (_) {
      return null;
    }
  }

  async function login(email, password) {
    const url = `https://cognito-idp.${BB_CONFIG.COGNITO_REGION}.amazonaws.com/`;
    const body = {
      AuthFlow: "USER_PASSWORD_AUTH",
      ClientId: BB_CONFIG.COGNITO_CLIENT_ID,
      AuthParameters: { USERNAME: email, PASSWORD: password },
    };
    try {
      const resp = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-amz-json-1.1",
          "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
        },
        body: JSON.stringify(body),
      });
      const data = await resp.json();
      if (!resp.ok) {
        return { ok: false, error: data.message || "Error de autenticación" };
      }
      const result = data.AuthenticationResult;
      if (!result || !result.IdToken) {
        return { ok: false, error: "Respuesta inesperada de Cognito" };
      }
      _save(result.IdToken, result.ExpiresIn || 3600);
      return { ok: true };
    } catch (e) {
      return { ok: false, error: e.message || "Error de red" };
    }
  }

  function logout() {
    localStorage.removeItem(STORAGE_KEY);
    window.location.href = "login.html";
  }

  function getToken() {
    const data = _read();
    if (!data) return null;
    if (Date.now() >= data.expiresAt) {
      localStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return data.idToken;
  }

  function requireAuth() {
    if (!getToken()) {
      window.location.href = "login.html";
    }
  }

  function getEmail() {
    const token = getToken();
    if (!token) return null;
    try {
      const payload = JSON.parse(atob(token.split(".")[1]));
      return payload.email || payload["cognito:username"] || null;
    } catch (_) {
      return null;
    }
  }

  window.BB_AUTH = { login, logout, getToken, requireAuth, getEmail };
})();
```

- [ ] **Step 2: Commit**

```bash
cd /Users/agustin/Documents/Projects/guerrin
git add BreadBoss-Front/js/auth.js
git commit -m "feat(front): auth.js con Cognito USER_PASSWORD_AUTH"
```

---

## Task 3: Crear `api.js`

**Files:**
- Create: `BreadBoss-Front/js/api.js`

- [ ] **Step 1: Crear `api.js` con wrappers por endpoint**

Contenido completo de `BreadBoss-Front/js/api.js`:

```js
(function () {
  async function _request(method, path, body) {
    const token = BB_AUTH.getToken();
    if (!token) {
      BB_AUTH.logout();
      throw new Error("No autenticado");
    }
    const resp = await fetch(`${BB_CONFIG.API_URL}${path}`, {
      method,
      headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (resp.status === 401) {
      BB_AUTH.logout();
      throw new Error("Sesión expirada");
    }
    let data = null;
    const text = await resp.text();
    if (text) {
      try { data = JSON.parse(text); } catch (_) { data = { raw: text }; }
    }
    if (!resp.ok) {
      const msg = (data && data.error) || `HTTP ${resp.status}`;
      throw new Error(msg);
    }
    return data;
  }

  async function getMenu() {
    return _request("GET", "/menu");
  }

  async function createOrder({ deliveryAddress, items, channel }) {
    return _request("POST", "/orders", {
      deliveryAddress,
      items,
      channel: channel || "web",
    });
  }

  async function getOrder(orderId) {
    return _request("GET", `/orders/${encodeURIComponent(orderId)}`);
  }

  async function listOrdersByStatus(status) {
    return _request("GET", `/orders?status=${encodeURIComponent(status)}`);
  }

  async function markReady(orderId) {
    return _request("POST", `/orders/${encodeURIComponent(orderId)}/ready`);
  }

  async function deliverOrder(orderId) {
    return _request("POST", `/orders/${encodeURIComponent(orderId)}/deliver`);
  }

  window.BB_API = {
    getMenu,
    createOrder,
    getOrder,
    listOrdersByStatus,
    markReady,
    deliverOrder,
  };
})();
```

- [ ] **Step 2: Commit**

```bash
cd /Users/agustin/Documents/Projects/guerrin
git add BreadBoss-Front/js/api.js
git commit -m "feat(front): api.js con wrappers por endpoint"
```

---

## Task 4: Extender `styles.css` con clases para las nuevas pantallas

**Files:**
- Modify: `BreadBoss-Front/styles.css` (append al final)

- [ ] **Step 1: Agregar bloque APP SCREENS al final de styles.css**

Agregar al final de `BreadBoss-Front/styles.css`:

```css
/* ============================================================
   APP SCREENS — login, menu, tracking, kitchen
   ============================================================ */

.app-shell {
    max-width: 1180px;
    margin: 0 auto;
    padding: 32px 48px 80px;
}

.app-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-bottom: 24px;
    border-bottom: 1px solid var(--line);
    margin-bottom: 40px;
}

.app-header .brand {
    font-size: 20px;
    font-weight: 800;
    letter-spacing: -0.01em;
    color: var(--ink);
}

.app-header .nav {
    display: flex;
    gap: 24px;
    align-items: center;
}

.app-header .nav a {
    font-size: 13px;
    font-weight: 600;
    color: var(--ink-soft);
    text-decoration: none;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}

.app-header .nav a:hover { color: var(--accent); }

.app-header .email-pill {
    font-size: 12px;
    color: var(--ink-mute);
    padding: 6px 12px;
    background: var(--bg-soft);
    border-radius: 999px;
}

.btn {
    font-family: var(--font);
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    padding: 10px 18px;
    border-radius: var(--radius);
    border: 1px solid var(--accent);
    background: var(--accent);
    color: #fff;
    cursor: pointer;
    transition: background 0.15s, border 0.15s;
}

.btn:hover { background: var(--accent-2); border-color: var(--accent-2); }

.btn.btn-ghost {
    background: transparent;
    color: var(--accent);
}

.btn.btn-ghost:hover { background: var(--bg-soft); }

.btn.btn-danger {
    background: var(--danger);
    border-color: var(--danger);
}

.btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

/* ---------- login ---------- */
.login-wrap {
    min-height: 100vh;
    display: grid;
    place-items: center;
    padding: 40px;
}

.login-card {
    width: 100%;
    max-width: 380px;
    background: var(--bg-card);
    border: 1px solid var(--line);
    border-radius: var(--radius-lg);
    padding: 40px 36px;
}

.login-card h1 {
    font-size: 26px;
    font-weight: 800;
    margin-bottom: 6px;
}

.login-card .subtitle {
    font-size: 13px;
    color: var(--ink-mute);
    margin-bottom: 28px;
}

.login-form { display: grid; gap: 16px; }

.login-form label {
    font-size: 11px;
    font-weight: 600;
    color: var(--ink-soft);
    letter-spacing: 0.1em;
    text-transform: uppercase;
}

.login-form input {
    font-family: var(--font);
    font-size: 14px;
    padding: 12px 14px;
    border: 1px solid var(--line-strong);
    border-radius: var(--radius);
    background: #fff;
    color: var(--ink);
    width: 100%;
}

.login-form input:focus {
    outline: none;
    border-color: var(--accent);
}

.error-msg {
    font-size: 13px;
    color: var(--danger);
    margin-top: 8px;
    min-height: 18px;
}

/* ---------- menu + cart ---------- */
.menu-layout {
    display: grid;
    grid-template-columns: 1.6fr 1fr;
    gap: 40px;
    align-items: start;
}

.menu-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 20px;
}

.menu-card {
    background: var(--bg-card);
    border: 1px solid var(--line);
    border-radius: var(--radius-lg);
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.menu-card .name {
    font-size: 16px;
    font-weight: 700;
    color: var(--ink);
}

.menu-card .price {
    font-size: 18px;
    font-weight: 800;
    color: var(--accent);
}

.menu-card .stock {
    font-size: 11px;
    color: var(--ink-mute);
    text-transform: uppercase;
    letter-spacing: 0.08em;
}

.cart-panel {
    background: var(--bg-card);
    border: 1px solid var(--line);
    border-radius: var(--radius-lg);
    padding: 24px;
    position: sticky;
    top: 24px;
}

.cart-panel h2 {
    font-size: 14px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--ink-soft);
    margin-bottom: 18px;
}

.cart-items { display: grid; gap: 12px; margin-bottom: 18px; }

.cart-item {
    display: grid;
    grid-template-columns: 1fr auto auto;
    gap: 10px;
    align-items: center;
    font-size: 13px;
}

.cart-item .qty-ctrl {
    display: flex;
    align-items: center;
    gap: 6px;
}

.cart-item .qty-ctrl button {
    width: 24px; height: 24px;
    font-size: 14px;
    background: var(--bg-soft);
    border: 1px solid var(--line-strong);
    border-radius: 4px;
    cursor: pointer;
    color: var(--ink);
}

.cart-empty {
    font-size: 13px;
    color: var(--ink-mute);
    padding: 16px 0;
    text-align: center;
}

.cart-total {
    display: flex;
    justify-content: space-between;
    padding-top: 16px;
    border-top: 1px solid var(--line);
    font-weight: 700;
    margin-bottom: 18px;
}

.address-input {
    width: 100%;
    font-family: var(--font);
    font-size: 13px;
    padding: 10px 12px;
    margin-bottom: 14px;
    border: 1px solid var(--line-strong);
    border-radius: var(--radius);
    background: #fff;
}

/* ---------- tracking stepper ---------- */
.tracking-card {
    background: var(--bg-card);
    border: 1px solid var(--line);
    border-radius: var(--radius-lg);
    padding: 36px;
}

.tracking-card .order-id {
    font-size: 11px;
    color: var(--ink-mute);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 8px;
}

.tracking-card .current-status {
    font-size: 32px;
    font-weight: 800;
    color: var(--accent);
    margin-bottom: 28px;
}

.stepper {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0;
    margin-bottom: 32px;
    position: relative;
}

.stepper-node {
    text-align: center;
    position: relative;
}

.stepper-node .dot {
    width: 36px; height: 36px;
    border-radius: 50%;
    background: var(--line);
    border: 2px solid var(--line-strong);
    margin: 0 auto 8px;
    display: grid;
    place-items: center;
    color: #fff;
    font-weight: 800;
    font-size: 14px;
}

.stepper-node.active .dot {
    background: var(--accent);
    border-color: var(--accent);
}

.stepper-node .label {
    font-size: 11px;
    font-weight: 600;
    color: var(--ink-mute);
    text-transform: uppercase;
    letter-spacing: 0.08em;
}

.stepper-node.active .label { color: var(--ink); }

.stepper-line {
    position: absolute;
    top: 17px;
    left: calc(50% + 18px);
    right: calc(-50% + 18px);
    height: 2px;
    background: var(--line-strong);
    z-index: 0;
}

.stepper-node.active + .stepper-node .stepper-line {
    background: var(--accent);
}

.tracking-meta {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 24px;
    padding-top: 24px;
    border-top: 1px solid var(--line);
    margin-bottom: 28px;
}

.tracking-meta .label {
    font-size: 11px;
    color: var(--ink-mute);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 4px;
}

.tracking-meta .value {
    font-size: 15px;
    font-weight: 600;
    color: var(--ink);
}

.tracking-items {
    list-style: none;
    padding: 0;
    margin-bottom: 24px;
}

.tracking-items li {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px dashed var(--line);
    font-size: 14px;
}

/* ---------- kitchen ---------- */
.kitchen-section { margin-bottom: 40px; }

.kitchen-section h2 {
    font-size: 14px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--ink-soft);
    margin-bottom: 16px;
}

.kitchen-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
}

.kitchen-card {
    background: var(--bg-card);
    border: 1px solid var(--line);
    border-left: 4px solid var(--accent);
    border-radius: var(--radius);
    padding: 18px 20px;
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.kitchen-card .order-id {
    font-family: 'SF Mono', Menlo, monospace;
    font-size: 12px;
    color: var(--ink-mute);
}

.kitchen-card .items {
    font-size: 13px;
    color: var(--ink-soft);
}

.kitchen-card .total {
    font-size: 16px;
    font-weight: 800;
    color: var(--accent);
}

.kitchen-card .address {
    font-size: 12px;
    color: var(--ink-mute);
}

.empty-state {
    font-size: 13px;
    color: var(--ink-mute);
    padding: 24px;
    text-align: center;
    background: var(--bg-soft);
    border-radius: var(--radius);
}

.badge-mode {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    padding: 4px 10px;
    background: var(--warn);
    color: #fff;
    border-radius: 4px;
}

/* ---------- toolbar ---------- */
.toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
}

.toolbar h1 {
    font-size: 22px;
    font-weight: 800;
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/agustin/Documents/Projects/guerrin
git add BreadBoss-Front/styles.css
git commit -m "feat(front): estilos de pantallas app (login/menu/tracking/kitchen)"
```

---

## Task 5: Crear `login.html`

**Files:**
- Create: `BreadBoss-Front/login.html`

- [ ] **Step 1: Crear `login.html`**

Contenido completo:

```html
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>BreadBoss · Login</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="styles.css" />
  <script src="js/config.js"></script>
  <script src="js/auth.js"></script>
</head>
<body>
  <div class="login-wrap">
    <div class="login-card">
      <h1>Bread Boss</h1>
      <p class="subtitle">Iniciá sesión para hacer un pedido</p>
      <form class="login-form" id="loginForm">
        <div>
          <label for="email">Email</label>
          <input id="email" type="email" required autocomplete="email" />
        </div>
        <div>
          <label for="password">Contraseña</label>
          <input id="password" type="password" required autocomplete="current-password" />
        </div>
        <button type="submit" class="btn" id="submitBtn">Entrar</button>
        <div class="error-msg" id="errorMsg"></div>
      </form>
    </div>
  </div>

  <script>
    if (BB_AUTH.getToken()) {
      window.location.href = "menu.html";
    }

    const form = document.getElementById("loginForm");
    const errorMsg = document.getElementById("errorMsg");
    const submitBtn = document.getElementById("submitBtn");

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      errorMsg.textContent = "";
      submitBtn.disabled = true;
      submitBtn.textContent = "Entrando...";
      const email = document.getElementById("email").value.trim();
      const password = document.getElementById("password").value;
      const result = await BB_AUTH.login(email, password);
      if (result.ok) {
        window.location.href = "menu.html";
      } else {
        errorMsg.textContent = result.error;
        submitBtn.disabled = false;
        submitBtn.textContent = "Entrar";
      }
    });
  </script>
</body>
</html>
```

- [ ] **Step 2: Verificación manual local**

Run: `cd /Users/agustin/Documents/Projects/guerrin/BreadBoss-Front && python3 -m http.server 8000`
Abrir en el browser: `http://localhost:8000/login.html`

Verificar:
- Si ya hay token, redirige a `menu.html` (404 esperado por ahora — menu.html no existe).
- Si no hay token, muestra el form.
- Submit con credenciales válidas (mismas del test user de Cognito) → redirige a `menu.html`.
- Submit con credenciales inválidas → muestra mensaje de error en rojo.

Cortar el server con Ctrl+C.

- [ ] **Step 3: Commit**

```bash
cd /Users/agustin/Documents/Projects/guerrin
git add BreadBoss-Front/login.html
git commit -m "feat(front): pantalla de login"
```

---

## Task 6: Crear `menu.html`

**Files:**
- Create: `BreadBoss-Front/menu.html`

- [ ] **Step 1: Crear `menu.html`**

Contenido completo:

```html
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>BreadBoss · Menú</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="styles.css" />
  <script src="js/config.js"></script>
  <script src="js/auth.js"></script>
  <script src="js/api.js"></script>
</head>
<body>
  <div class="app-shell">
    <header class="app-header">
      <div class="brand">Bread Boss</div>
      <nav class="nav">
        <a href="menu.html">Menú</a>
        <a href="tracking.html">Mis pedidos</a>
        <span class="email-pill" id="emailPill"></span>
        <button class="btn btn-ghost" id="logoutBtn">Salir</button>
      </nav>
    </header>

    <div class="toolbar">
      <h1>Menú del día</h1>
    </div>

    <div class="menu-layout">
      <div class="menu-grid" id="menuGrid">
        <div class="empty-state">Cargando menú...</div>
      </div>

      <aside class="cart-panel">
        <h2>Tu pedido</h2>
        <div class="cart-items" id="cartItems"></div>
        <div class="cart-total">
          <span>Total</span>
          <span id="cartTotal">$0</span>
        </div>
        <input type="text" class="address-input" id="addressInput" placeholder="Dirección de entrega" />
        <button class="btn" id="placeOrderBtn" style="width: 100%;">Hacer pedido</button>
        <div class="error-msg" id="errorMsg"></div>
      </aside>
    </div>
  </div>

  <script>
    BB_AUTH.requireAuth();

    document.getElementById("emailPill").textContent = BB_AUTH.getEmail() || "";
    document.getElementById("logoutBtn").addEventListener("click", () => BB_AUTH.logout());

    let menuItems = [];
    let cart = JSON.parse(localStorage.getItem("bb_cart") || "{}");

    function saveCart() {
      localStorage.setItem("bb_cart", JSON.stringify(cart));
    }

    function renderMenu() {
      const grid = document.getElementById("menuGrid");
      if (menuItems.length === 0) {
        grid.innerHTML = '<div class="empty-state">No hay items en el menú.</div>';
        return;
      }
      grid.innerHTML = menuItems.map(item => `
        <div class="menu-card">
          <div class="name">${escapeHtml(item.name || item.itemId)}</div>
          <div class="price">$${formatPrice(item.price)}</div>
          ${item.stock !== undefined ? `<div class="stock">Stock: ${item.stock}</div>` : ""}
          <button class="btn" data-id="${escapeHtml(item.itemId)}">Agregar</button>
        </div>
      `).join("");
      grid.querySelectorAll("button[data-id]").forEach(btn => {
        btn.addEventListener("click", () => addToCart(btn.dataset.id));
      });
    }

    function addToCart(itemId) {
      cart[itemId] = (cart[itemId] || 0) + 1;
      saveCart();
      renderCart();
    }

    function setQty(itemId, qty) {
      if (qty <= 0) delete cart[itemId];
      else cart[itemId] = qty;
      saveCart();
      renderCart();
    }

    function renderCart() {
      const container = document.getElementById("cartItems");
      const entries = Object.entries(cart);
      if (entries.length === 0) {
        container.innerHTML = '<div class="cart-empty">Carrito vacío</div>';
        document.getElementById("cartTotal").textContent = "$0";
        return;
      }
      let total = 0;
      container.innerHTML = entries.map(([id, qty]) => {
        const item = menuItems.find(m => m.itemId === id);
        const price = item ? item.price : 0;
        const subtotal = price * qty;
        total += subtotal;
        return `
          <div class="cart-item">
            <span>${escapeHtml(item ? (item.name || id) : id)}</span>
            <div class="qty-ctrl">
              <button data-dec="${escapeHtml(id)}">−</button>
              <span>${qty}</span>
              <button data-inc="${escapeHtml(id)}">+</button>
            </div>
            <span>$${formatPrice(subtotal)}</span>
          </div>
        `;
      }).join("");
      document.getElementById("cartTotal").textContent = `$${formatPrice(total)}`;

      container.querySelectorAll("button[data-inc]").forEach(btn => {
        btn.addEventListener("click", () => setQty(btn.dataset.inc, (cart[btn.dataset.inc] || 0) + 1));
      });
      container.querySelectorAll("button[data-dec]").forEach(btn => {
        btn.addEventListener("click", () => setQty(btn.dataset.dec, (cart[btn.dataset.dec] || 0) - 1));
      });
    }

    function formatPrice(n) {
      return Number(n || 0).toFixed(2);
    }

    function escapeHtml(s) {
      return String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
    }

    document.getElementById("placeOrderBtn").addEventListener("click", async () => {
      const errorMsg = document.getElementById("errorMsg");
      const btn = document.getElementById("placeOrderBtn");
      errorMsg.textContent = "";
      const address = document.getElementById("addressInput").value.trim();
      if (!address) {
        errorMsg.textContent = "Falta dirección de entrega";
        return;
      }
      const entries = Object.entries(cart);
      if (entries.length === 0) {
        errorMsg.textContent = "El carrito está vacío";
        return;
      }
      btn.disabled = true;
      btn.textContent = "Enviando...";
      try {
        const items = entries.map(([itemId, qty]) => ({ itemId, qty }));
        const result = await BB_API.createOrder({ deliveryAddress: address, items });
        localStorage.setItem("bb_last_order_id", result.orderId);
        localStorage.removeItem("bb_cart");
        window.location.href = `tracking.html?orderId=${encodeURIComponent(result.orderId)}`;
      } catch (e) {
        errorMsg.textContent = e.message;
        btn.disabled = false;
        btn.textContent = "Hacer pedido";
      }
    });

    (async function init() {
      try {
        const data = await BB_API.getMenu();
        menuItems = Array.isArray(data) ? data : (data.items || []);
        renderMenu();
        renderCart();
      } catch (e) {
        document.getElementById("menuGrid").innerHTML = `<div class="empty-state">Error: ${escapeHtml(e.message)}</div>`;
      }
    })();
  </script>
</body>
</html>
```

- [ ] **Step 2: Verificación manual local**

Run: `cd /Users/agustin/Documents/Projects/guerrin/BreadBoss-Front && python3 -m http.server 8000`
Abrir: `http://localhost:8000/login.html` → login → debería redirigir a `menu.html`.

Verificar:
- Carga el menú desde la API (cards con nombre, precio).
- Click en "Agregar" suma al carrito.
- Botones `+` / `−` modifican qty correctamente.
- Total se actualiza.
- Sin dirección → error "Falta dirección de entrega".
- Con dirección → POST exitoso → redirige a `tracking.html?orderId=...` (404 esperado, tracking.html aún no existe).
- Botón "Salir" borra token y vuelve a `login.html`.

Cortar el server.

- [ ] **Step 3: Commit**

```bash
cd /Users/agustin/Documents/Projects/guerrin
git add BreadBoss-Front/menu.html
git commit -m "feat(front): pantalla de menú con carrito y crear pedido"
```

---

## Task 7: Crear `tracking.html`

**Files:**
- Create: `BreadBoss-Front/tracking.html`

- [ ] **Step 1: Crear `tracking.html`**

Contenido completo:

```html
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>BreadBoss · Seguimiento</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="styles.css" />
  <script src="js/config.js"></script>
  <script src="js/auth.js"></script>
  <script src="js/api.js"></script>
</head>
<body>
  <div class="app-shell">
    <header class="app-header">
      <div class="brand">Bread Boss</div>
      <nav class="nav">
        <a href="menu.html">Menú</a>
        <a href="tracking.html">Mis pedidos</a>
        <span class="email-pill" id="emailPill"></span>
        <button class="btn btn-ghost" id="logoutBtn">Salir</button>
      </nav>
    </header>

    <div class="toolbar">
      <h1>Seguimiento del pedido</h1>
      <button class="btn" id="refreshBtn">Actualizar estado</button>
    </div>

    <div id="content"></div>
  </div>

  <script>
    BB_AUTH.requireAuth();

    document.getElementById("emailPill").textContent = BB_AUTH.getEmail() || "";
    document.getElementById("logoutBtn").addEventListener("click", () => BB_AUTH.logout());

    const STATES = ["RECIBIDO", "EN_PREPARACION", "EN_CAMINO", "ENTREGADO"];
    const LABELS = {
      "RECIBIDO": "Recibido",
      "EN_PREPARACION": "En preparación",
      "EN_CAMINO": "En camino",
      "ENTREGADO": "Entregado",
    };

    function getOrderIdFromUrl() {
      const params = new URLSearchParams(window.location.search);
      return params.get("orderId") || localStorage.getItem("bb_last_order_id");
    }

    function escapeHtml(s) {
      return String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
    }

    function renderEmpty() {
      document.getElementById("content").innerHTML = `
        <div class="empty-state">
          No tenés pedidos recientes. <a href="menu.html">Hacé uno ahora</a>.
        </div>
      `;
    }

    function renderOrder(order) {
      const currentIdx = STATES.indexOf(order.status);
      const stepperHtml = STATES.map((s, i) => `
        <div class="stepper-node ${i <= currentIdx ? "active" : ""}">
          ${i > 0 ? '<div class="stepper-line"></div>' : ""}
          <div class="dot">${i + 1}</div>
          <div class="label">${LABELS[s]}</div>
        </div>
      `).join("");

      const items = Array.isArray(order.items) ? order.items : [];
      const itemsHtml = items.map(it => `
        <li>
          <span>${escapeHtml(it.name || it.itemId)} × ${escapeHtml(it.qty)}</span>
          <span>$${Number(it.price || 0).toFixed(2)}</span>
        </li>
      `).join("");

      const tiempo = order.tiempo_entrega_min ? `${order.tiempo_entrega_min} min` : "—";

      document.getElementById("content").innerHTML = `
        <div class="tracking-card">
          <div class="order-id">Pedido ${escapeHtml(order.orderId)}</div>
          <div class="current-status">${LABELS[order.status] || order.status}</div>
          <div class="stepper">${stepperHtml}</div>
          <div class="tracking-meta">
            <div>
              <div class="label">Total</div>
              <div class="value">$${Number(order.total || 0).toFixed(2)}</div>
            </div>
            <div>
              <div class="label">Dirección</div>
              <div class="value">${escapeHtml(order.deliveryAddress)}</div>
            </div>
            <div>
              <div class="label">Tiempo de entrega</div>
              <div class="value">${tiempo}</div>
            </div>
          </div>
          <ul class="tracking-items">${itemsHtml}</ul>
        </div>
      `;
    }

    async function loadOrder() {
      const orderId = getOrderIdFromUrl();
      if (!orderId) {
        renderEmpty();
        return;
      }
      const btn = document.getElementById("refreshBtn");
      btn.disabled = true;
      btn.textContent = "Actualizando...";
      try {
        const order = await BB_API.getOrder(orderId);
        renderOrder(order);
      } catch (e) {
        document.getElementById("content").innerHTML = `<div class="empty-state">Error: ${escapeHtml(e.message)}</div>`;
      } finally {
        btn.disabled = false;
        btn.textContent = "Actualizar estado";
      }
    }

    document.getElementById("refreshBtn").addEventListener("click", loadOrder);
    loadOrder();
  </script>
</body>
</html>
```

- [ ] **Step 2: Verificación manual local**

Run: `cd /Users/agustin/Documents/Projects/guerrin/BreadBoss-Front && python3 -m http.server 8000`
Abrir `http://localhost:8000/login.html` → login → menu → hacer pedido → debería caer en `tracking.html?orderId=...`.

Verificar:
- Stepper muestra primer nodo activo en `RECIBIDO`, los siguientes grises.
- Click "Actualizar estado" después de unos segundos → muestra `EN_PREPARACION` (segundo nodo activo).
- Meta (total, dirección, tiempo) se muestra.
- Items del pedido listados.
- Entrar a `tracking.html` sin `?orderId=...` → usa el `bb_last_order_id` de localStorage y muestra ese pedido.
- Limpiar localStorage `bb_last_order_id` y entrar sin query param → muestra estado vacío con link al menú.

Cortar el server.

- [ ] **Step 3: Commit**

```bash
cd /Users/agustin/Documents/Projects/guerrin
git add BreadBoss-Front/tracking.html
git commit -m "feat(front): pantalla de seguimiento con stepper visual"
```

---

## Task 8: Crear `kitchen.html`

**Files:**
- Create: `BreadBoss-Front/kitchen.html`

- [ ] **Step 1: Crear `kitchen.html`**

Contenido completo:

```html
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>BreadBoss · Cocina</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="styles.css" />
  <script src="js/config.js"></script>
  <script src="js/auth.js"></script>
  <script src="js/api.js"></script>
</head>
<body>
  <div class="app-shell">
    <header class="app-header">
      <div class="brand">Bread Boss <span class="badge-mode">Cocina</span></div>
      <nav class="nav">
        <span class="email-pill" id="emailPill"></span>
        <button class="btn btn-ghost" id="logoutBtn">Salir</button>
      </nav>
    </header>

    <div class="toolbar">
      <h1>Tablero de cocina</h1>
      <button class="btn" id="refreshBtn">Refrescar lista</button>
    </div>

    <section class="kitchen-section">
      <h2>En preparación</h2>
      <div class="kitchen-grid" id="prepGrid"></div>
    </section>

    <section class="kitchen-section">
      <h2>En camino</h2>
      <div class="kitchen-grid" id="enRouteGrid"></div>
    </section>
  </div>

  <script>
    BB_AUTH.requireAuth();

    document.getElementById("emailPill").textContent = BB_AUTH.getEmail() || "";
    document.getElementById("logoutBtn").addEventListener("click", () => BB_AUTH.logout());

    function escapeHtml(s) {
      return String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
    }

    function minutesAgo(timestamp) {
      if (!timestamp) return "—";
      const ms = Date.now() - Number(timestamp);
      const mins = Math.floor(ms / 60000);
      if (mins < 1) return "ahora";
      return `${mins} min`;
    }

    function renderCard(order, actionLabel, actionFn) {
      const items = Array.isArray(order.items) ? order.items : [];
      const itemsStr = items.map(it => `${it.name || it.itemId} × ${it.qty}`).join(", ");
      const card = document.createElement("div");
      card.className = "kitchen-card";
      card.innerHTML = `
        <div class="order-id">#${escapeHtml(String(order.orderId).slice(0, 8))} · hace ${minutesAgo(order.timestamp)}</div>
        <div class="items">${escapeHtml(itemsStr)}</div>
        <div class="total">$${Number(order.total || 0).toFixed(2)}</div>
        <div class="address">${escapeHtml(order.deliveryAddress)}</div>
        <button class="btn">${actionLabel}</button>
      `;
      const btn = card.querySelector("button");
      btn.addEventListener("click", async () => {
        btn.disabled = true;
        btn.textContent = "Procesando...";
        try {
          await actionFn(order.orderId);
          card.style.opacity = "0.4";
          btn.textContent = "Listo";
        } catch (e) {
          btn.disabled = false;
          btn.textContent = actionLabel;
          alert("Error: " + e.message);
        }
      });
      return card;
    }

    async function loadBoard() {
      const refreshBtn = document.getElementById("refreshBtn");
      refreshBtn.disabled = true;
      refreshBtn.textContent = "Refrescando...";

      const prep = document.getElementById("prepGrid");
      const route = document.getElementById("enRouteGrid");
      prep.innerHTML = "";
      route.innerHTML = "";

      try {
        const [prepData, routeData] = await Promise.all([
          BB_API.listOrdersByStatus("EN_PREPARACION"),
          BB_API.listOrdersByStatus("EN_CAMINO"),
        ]);

        const prepItems = (prepData && prepData.items) || [];
        const routeItems = (routeData && routeData.items) || [];

        if (prepItems.length === 0) {
          prep.innerHTML = '<div class="empty-state">No hay pedidos en preparación</div>';
        } else {
          prepItems.forEach(o => prep.appendChild(renderCard(o, "Listo para retirar", BB_API.markReady)));
        }

        if (routeItems.length === 0) {
          route.innerHTML = '<div class="empty-state">No hay pedidos en camino</div>';
        } else {
          routeItems.forEach(o => route.appendChild(renderCard(o, "Marcar entregado", BB_API.deliverOrder)));
        }
      } catch (e) {
        prep.innerHTML = `<div class="empty-state">Error: ${escapeHtml(e.message)}</div>`;
      } finally {
        refreshBtn.disabled = false;
        refreshBtn.textContent = "Refrescar lista";
      }
    }

    document.getElementById("refreshBtn").addEventListener("click", loadBoard);
    loadBoard();
  </script>
</body>
</html>
```

- [ ] **Step 2: Verificación manual local end-to-end**

Run: `cd /Users/agustin/Documents/Projects/guerrin/BreadBoss-Front && python3 -m http.server 8000`

Probar el flujo end-to-end:
1. Pestaña 1: `http://localhost:8000/login.html` → login → menú → hacer pedido → tracking muestra RECIBIDO.
2. Pestaña 2: `http://localhost:8000/kitchen.html` → debería ver el pedido en "En preparación" (después de unos segundos cuando kitchen-manager lo procese).
3. Click "Listo para retirar" → card se opaca.
4. Click "Refrescar lista" → ese pedido ahora aparece en "En camino" (porque order-ready publicó ORDER_READY → delivery-tracker lo puso en EN_CAMINO).
5. Pestaña 1: Click "Actualizar estado" → muestra EN_CAMINO.
6. Pestaña 2: Click "Marcar entregado" → card se opaca.
7. Click "Refrescar lista" → ya no aparece en ningún listado.
8. Pestaña 1: Click "Actualizar estado" → muestra ENTREGADO con `tiempo_entrega_min`.

Cortar el server.

- [ ] **Step 3: Commit**

```bash
cd /Users/agustin/Documents/Projects/guerrin
git add BreadBoss-Front/kitchen.html
git commit -m "feat(front): pantalla de cocina con secciones EN_PREPARACION y EN_CAMINO"
```

---

## Task 9: Crear módulo Terraform `frontend` (S3 + CloudFront)

**Files:**
- Create: `BreadBoss/modules/frontend/main.tf`
- Create: `BreadBoss/modules/frontend/variables.tf`
- Create: `BreadBoss/modules/frontend/outputs.tf`

- [ ] **Step 1: Crear `variables.tf`**

```hcl
variable "prefix" { type = string }
```

- [ ] **Step 2: Crear `main.tf`**

```hcl
resource "aws_s3_bucket" "frontend" {
  bucket        = "${var.prefix}-frontend-${random_id.suffix.hex}"
  force_destroy = true
  tags          = { Name = "${var.prefix}-frontend" }
}

resource "random_id" "suffix" {
  byte_length = 4
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket                  = aws_s3_bucket.frontend.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "${var.prefix}-frontend-oac"
  description                       = "OAC for ${var.prefix} frontend bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "login.html"
  comment             = "${var.prefix} frontend"

  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = "s3-frontend"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  default_cache_behavior {
    target_origin_id       = "s3-frontend"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }

    min_ttl     = 0
    default_ttl = 60
    max_ttl     = 300
  }

  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/login.html"
    error_caching_min_ttl = 10
  }

  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/login.html"
    error_caching_min_ttl = 10
  }

  restrictions {
    geo_restriction { restriction_type = "none" }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = { Name = "${var.prefix}-frontend" }
}

data "aws_iam_policy_document" "frontend_bucket" {
  statement {
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.frontend.arn}/*"]
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.frontend.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  policy = data.aws_iam_policy_document.frontend_bucket.json
}
```

- [ ] **Step 3: Crear `outputs.tf`**

```hcl
output "cloudfront_url" {
  value = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

output "bucket_name" {
  value = aws_s3_bucket.frontend.id
}
```

- [ ] **Step 4: Wirear el módulo en `BreadBoss/main.tf`**

Read `BreadBoss/main.tf`. Agregar al final del archivo (después del último `module`):

```hcl
module "frontend" {
  source = "./modules/frontend"
  prefix = var.prefix
}
```

- [ ] **Step 5: Crear/actualizar `BreadBoss/outputs.tf` para exponer datos al frontend**

Si `BreadBoss/outputs.tf` no existe, crearlo con este contenido. Si existe, agregar estos outputs al final (sin duplicar si ya existe alguno):

```hcl
output "cloudfront_url" {
  value = module.frontend.cloudfront_url
}

output "frontend_bucket" {
  value = module.frontend.bucket_name
}
```

- [ ] **Step 6: terraform validate**

Run: `cd /Users/agustin/Documents/Projects/guerrin/BreadBoss && terraform validate`
Expected: `Success! The configuration is valid.`

- [ ] **Step 7: terraform plan**

Run: `cd /Users/agustin/Documents/Projects/guerrin/BreadBoss && terraform plan -out=/tmp/breadboss-frontend.tfplan 2>&1 | tail -30`
Expected: plan muestra crear `aws_s3_bucket.frontend`, `aws_cloudfront_distribution.frontend`, `aws_cloudfront_origin_access_control.frontend`, `aws_s3_bucket_policy.frontend`, `aws_s3_bucket_public_access_block.frontend`, `random_id.suffix`. Sin destroys inesperados.

- [ ] **Step 8: Commit (sin aplicar todavía — apply se hace en Task 10)**

```bash
cd /Users/agustin/Documents/Projects/guerrin
git add BreadBoss/modules/frontend/ BreadBoss/main.tf BreadBoss/outputs.tf
git commit -m "infra(frontend): módulo S3 + CloudFront para hosting estático"
```

---

## Task 10: Apply Terraform + subir archivos a S3 + smoke test

**Files:** N/A (deploy)

- [ ] **Step 1: Apply**

Run: `cd /Users/agustin/Documents/Projects/guerrin/BreadBoss && terraform apply /tmp/breadboss-frontend.tfplan`
Expected: `Apply complete!`. Anotar los outputs `cloudfront_url` y `frontend_bucket`.

- [ ] **Step 2: Sync archivos a S3**

```bash
cd /Users/agustin/Documents/Projects/guerrin
BUCKET=$(cd BreadBoss && terraform output -raw frontend_bucket)
aws s3 sync BreadBoss-Front/ "s3://$BUCKET/" --exclude ".DS_Store" --exclude "*.zip"
```
Expected: lista archivos subidos (login.html, menu.html, tracking.html, kitchen.html, styles.css, dashboard.js, index.html, js/config.js, js/auth.js, js/api.js).

- [ ] **Step 3: Verificar acceso vía CloudFront**

```bash
CF_URL=$(cd BreadBoss && terraform output -raw cloudfront_url)
echo "Abrir: $CF_URL"
```

En un browser, abrir esa URL. Esperar 5–10 minutos para la primera propagación si da 403.

Verificar:
- Redirige (o sirve directamente) `login.html`.
- Login funciona.
- Flujo completo (menu → pedido → tracking → kitchen) funciona end-to-end desde CloudFront.

- [ ] **Step 4: Documentar la URL en el README**

Read `/Users/agustin/Documents/Projects/guerrin/README.md`. Agregar al final una sección:

```markdown
---

## Frontend (cliente + cocina)

Las pantallas funcionales están hosteadas en CloudFront. Después de `terraform apply`, ejecutar:

\`\`\`bash
BUCKET=$(cd BreadBoss && terraform output -raw frontend_bucket)
aws s3 sync BreadBoss-Front/ "s3://$BUCKET/" --exclude ".DS_Store" --exclude "*.zip"
\`\`\`

La URL pública se obtiene con `terraform output -raw cloudfront_url`. Pantallas:
- `/login.html` — login con Cognito
- `/menu.html` — menú y pedido (cliente)
- `/tracking.html?orderId=...` — seguimiento del pedido
- `/kitchen.html` — admin de cocina (link oculto)
```

(Reemplazar los `\`\`\`` por triple backtick en el archivo real.)

- [ ] **Step 5: Commit**

```bash
cd /Users/agustin/Documents/Projects/guerrin
git add README.md
git commit -m "docs: cómo desplegar y acceder al frontend"
```

---

## Task 11: Push y abrir PR

**Files:** N/A

- [ ] **Step 1: Push**

```bash
git push -u origin feature/frontend-customer-kitchen
```

- [ ] **Step 2: Crear PR contra `main`**

```bash
gh pr create --title "feat: frontend cliente + admin cocina con hosting S3/CloudFront" --body "$(cat <<'EOF'
## Summary
- Cuatro pantallas Vanilla JS: login, menu, tracking, kitchen.
- Módulo `auth.js` contra Cognito USER_PASSWORD_AUTH, `api.js` con wrappers a todos los endpoints.
- Módulo Terraform `frontend` (S3 privado + CloudFront + OAC).
- Reutiliza la identidad visual del dashboard existente.

## Test plan
- [x] Login con credenciales válidas → menú
- [x] Login con credenciales inválidas → mensaje de error
- [x] Carrito persiste en localStorage entre recargas (mientras no se confirma)
- [x] Crear pedido → redirige a tracking con orderId
- [x] Tracking sin orderId → usa último de localStorage
- [x] Stepper muestra estado actual y previos como activos
- [x] Kitchen lista pedidos EN_PREPARACION y EN_CAMINO
- [x] Botón "Listo para retirar" → pedido pasa a EN_CAMINO
- [x] Botón "Marcar entregado" → pedido pasa a ENTREGADO
- [x] Logout limpia token y vuelve a login

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR creado contra `main`.
