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
