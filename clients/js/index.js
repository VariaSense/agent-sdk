const CLIENT_SDK_VERSION = "0.1.0";

class AgentSDKClient {
  constructor({ baseUrl, apiKey, orgId = "default", clientVersion = CLIENT_SDK_VERSION, fetchImpl = null }) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.apiKey = apiKey;
    this.orgId = orgId;
    this.clientVersion = clientVersion;
    this.fetchImpl = fetchImpl || fetch;
  }

  async request(method, path, body = null) {
    const res = await this.fetchImpl(`${this.baseUrl}${path}`, {
      method,
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": this.apiKey,
        "X-Org-Id": this.orgId,
        "X-Client-Version": this.clientVersion,
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

  async getServerVersion() {
    const res = await this.request("GET", "/v1/health");
    return res.version;
  }

  async checkCompatibility() {
    const serverVersion = await this.getServerVersion();
    const clientMajor = parseInt(this.clientVersion.split(".")[0], 10);
    const serverMajor = parseInt((serverVersion || "0").split(".")[0], 10);
    return {
      clientVersion: this.clientVersion,
      serverVersion,
      compatible: clientMajor === serverMajor,
    };
  }
}

module.exports = { AgentSDKClient, CLIENT_SDK_VERSION };
