class AgentSDKClient {
  constructor({ baseUrl, apiKey, orgId = "default", fetchImpl = null }) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.apiKey = apiKey;
    this.orgId = orgId;
    this.fetchImpl = fetchImpl || fetch;
  }

  async request(method, path, body = null) {
    const res = await this.fetchImpl(`${this.baseUrl}${path}`, {
      method,
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": this.apiKey,
        "X-Org-Id": this.orgId,
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    return res.json();
  }

  runTask(task) {
    return this.request("POST", "/run", { task });
  }

  listOrgs() {
    return this.request("GET", "/admin/orgs");
  }
}

module.exports = { AgentSDKClient };
