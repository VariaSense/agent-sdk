"""HTML for the lightweight admin UI."""

ADMIN_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Agent SDK Admin</title>
  <style>
    body { font-family: "IBM Plex Sans", "Segoe UI", sans-serif; margin: 24px; color: #1f2933; }
    h1 { margin-bottom: 8px; }
    .panel { border: 1px solid #d9e2ec; padding: 16px; margin-bottom: 16px; border-radius: 8px; }
    label { display: block; margin-bottom: 6px; font-weight: 600; }
    input, button { padding: 8px 10px; font-size: 14px; }
    button { cursor: pointer; }
    pre { background: #f5f7fa; padding: 12px; border-radius: 8px; overflow-x: auto; }
  </style>
</head>
<body>
  <h1>Agent SDK Admin</h1>
  <p>Use this console to inspect orgs, keys, and usage. Provide an API key first.</p>

  <div class="panel">
    <label for="apiKey">API Key</label>
    <input id="apiKey" type="password" placeholder="sk_..." size="40" />
    <button id="saveKey">Save Key</button>
  </div>

  <div class="panel">
    <h2>Orgs</h2>
    <button data-action="orgs">Refresh Orgs</button>
    <pre id="orgs"></pre>
  </div>

  <div class="panel">
    <h2>API Keys</h2>
    <label for="newOrg">Org ID</label>
    <input id="newOrg" type="text" value="default" />
    <label for="newLabel">Label</label>
    <input id="newLabel" type="text" placeholder="staging" />
    <button data-action="create-key">Create Key</button>
    <button data-action="keys">Refresh Keys</button>
    <pre id="keys"></pre>
  </div>

  <div class="panel">
    <h2>Usage</h2>
    <button data-action="usage">Refresh Usage</button>
    <pre id="usage"></pre>
  </div>

  <script>
    const apiKeyInput = document.getElementById("apiKey");
    const saveKeyButton = document.getElementById("saveKey");
    const orgsEl = document.getElementById("orgs");
    const keysEl = document.getElementById("keys");
    const usageEl = document.getElementById("usage");

    function getKey() {
      return localStorage.getItem("agent_sdk_api_key") || "";
    }

    function setKey(key) {
      localStorage.setItem("agent_sdk_api_key", key);
    }

    apiKeyInput.value = getKey();

    saveKeyButton.addEventListener("click", () => {
      setKey(apiKeyInput.value.trim());
      alert("API key saved in local storage.");
    });

    async function apiFetch(path, options = {}) {
      const key = getKey();
      const headers = Object.assign({ "X-API-Key": key }, options.headers || {});
      const response = await fetch(path, { ...options, headers });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      return response.json();
    }

    async function refreshOrgs() {
      orgsEl.textContent = JSON.stringify(await apiFetch("/admin/orgs"), null, 2);
    }

    async function refreshKeys() {
      keysEl.textContent = JSON.stringify(await apiFetch("/admin/api-keys"), null, 2);
    }

    async function refreshUsage() {
      usageEl.textContent = JSON.stringify(await apiFetch("/admin/usage"), null, 2);
    }

    async function createKey() {
      const orgId = document.getElementById("newOrg").value.trim();
      const label = document.getElementById("newLabel").value.trim() || "default";
      const payload = { org_id: orgId, label };
      const response = await apiFetch("/admin/api-keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      keysEl.textContent = JSON.stringify(response, null, 2);
    }

    document.querySelectorAll("button[data-action]").forEach((button) => {
      button.addEventListener("click", async () => {
        try {
          const action = button.getAttribute("data-action");
          if (action === "orgs") return await refreshOrgs();
          if (action === "keys") return await refreshKeys();
          if (action === "usage") return await refreshUsage();
          if (action === "create-key") return await createKey();
        } catch (err) {
          alert(err.message || err);
        }
      });
    });
  </script>
</body>
</html>
"""
