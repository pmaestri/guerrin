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
