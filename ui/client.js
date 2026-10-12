/** Connect any browser app to a Micro-models workspace base URL. */
export class MicroModelsClient {
  constructor(baseUrl, {apiKey = ""} = {}) {
    const url = new URL(baseUrl);
    if (!["http:", "https:"].includes(url.protocol)) throw new Error("Use an HTTP or HTTPS service URL.");
    this.baseUrl = url.href.replace(/\/$/, "");
    this.apiKey = apiKey;
  }
  async request(path, {body, binary = false, method = "POST"} = {}) {
    const headers = {};
    if (this.apiKey) headers.Authorization = `Bearer ${this.apiKey}`;
    if (body !== undefined && !(body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(body);
    }
    let response;
    try { response = await fetch(this.baseUrl + path, {method, headers, body}); }
    catch { throw new Error("Cannot reach the service. Check its URL, HTTPS and allowed website origin."); }
    if (!response.ok) {
      let detail = `Request failed (${response.status})`;
      try { const data = await response.json(); detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail || data); } catch {}
      throw new Error(detail);
    }
    return binary ? response.blob() : response.json();
  }
  services() { return this.request("/api/services", {method: "GET"}); }
  health(task) { return this.request(`/services/${task}/health`, {method: "GET"}); }
  text(prompt, {tenant = "default", maxTokens = 256} = {}) {
    return this.request("/services/text/v1/text", {body: {prompt, tenant, max_tokens: maxTokens}});
  }
  memory(tenant, source, text) {
    return this.request("/services/text/v1/memory", {body: {tenant, source, text}});
  }
  upload(task, file) {
    const body = new FormData(); body.append("file", file);
    return this.request(`/services/${task}/v1/${task}`, {body});
  }
  document(file) { return this.upload("document", file); }
  transcribe(file) { return this.upload("asr", file); }
  speech(text, speed = 1) {
    return this.request("/services/tts/v1/tts", {body: {text, speed}, binary: true});
  }
  async prepareDocument(file) {
    const result = await this.document(file);
    if (!result.text.trim()) throw new Error("No text was extracted from this document.");
    const tenant = "doc-" + crypto.randomUUID();
    await this.memory(tenant, file.name, result.text);
    return {...result, tenant};
  }
}
