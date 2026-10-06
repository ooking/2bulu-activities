#!/usr/bin/env python3
"""一键发布 2bulu 的 Cloudflare 资源。

环境变量:
  CF_API_TOKEN   Cloudflare API Token（需 Account -> Workers Scripts:Edit, D1:Edit）
  CF_ACCOUNT_ID  Cloudflare Account ID

用法:
  python3 deploy.py            # 发布接口 Worker + 查询页 Worker
  python3 deploy.py --domains  # 额外确保自定义域名绑定（需 Token 有 DNS:Edit）

GitHub Actions 里由 .github/workflows/deploy.yml 调用。
"""
import json
import os
import sys
import urllib.request
import urllib.error

API = "https://api.cloudflare.com/client/v4"
ACCOUNT = os.environ.get("CF_ACCOUNT_ID", "2f310a5cd7c2c533e9edf3d31f97fe88")
TOKEN = os.environ.get("CF_API_TOKEN", "")
D1_DB_ID = os.environ.get("CF_D1_DB_ID", "de55be6d-d662-4089-83d8-4aa4dfe8b67d")
ZONE_NAME = "168939.xyz"

HERE = os.path.dirname(os.path.abspath(__file__))


def cf(method, path, body=None, content_type="application/json"):
    req = urllib.request.Request(API + path, method=method)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    data = None
    if body is not None:
        if isinstance(body, dict):
            data = json.dumps(body).encode()
            req.add_header("Content-Type", content_type)
        else:
            data = body  # 已编码好的 multipart
            req.add_header("Content-Type", content_type)
        req.data = data
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode()[:300]}", file=sys.stderr)
        raise SystemExit(1)


def deploy_worker(name, script_text, bindings=None):
    metadata = {"main_module": "worker.js",
                "compatibility_date": "2024-11-01",
                "workers_dev": True}
    if bindings:
        metadata["bindings"] = bindings
    boundary = "----deploy0001"
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"metadata\"\r\n"
            f"Content-Type: application/json\r\n\r\n".encode()
            + json.dumps(metadata).encode() + b"\r\n"
            + f"--{boundary}\r\nContent-Disposition: form-data; name=\"script\"; "
            f"filename=\"worker.js\"\r\nContent-Type: application/javascript+module\r\n\r\n".encode()
            + script_text.encode() + b"\r\n"
            + f"--{boundary}--\r\n".encode())
    r = cf("PUT", f"/accounts/{ACCOUNT}/workers/scripts/{name}", body,
           content_type=f"multipart/form-data; boundary={boundary}")
    assert r.get("success"), f"deploy {name} failed: {r.get('errors')}"
    print(f"deployed worker: {name}")


def ensure_domain(hostname, service):
    r = cf("GET", f"/accounts/{ACCOUNT}/workers/domains")
    existing = {d["hostname"]: d for d in (r.get("result") or [])}
    if hostname in existing and existing[hostname]["service"] == service:
        print(f"domain ok: {hostname} -> {service}")
        return
    r = cf("PUT", f"/accounts/{ACCOUNT}/workers/domains",
           {"hostname": hostname, "service": service,
            "environment": "production", "zone_name": ZONE_NAME})
    assert r.get("success"), f"domain {hostname} failed: {r.get('errors')}"
    print(f"domain bound: {hostname} -> {service}")


API_WORKER_JS = os.path.join(HERE, "workers", "bulu-worker.js")
WEB_HTML = os.path.join(HERE, "web", "bulu-web.html")

WEB_WRAPPER = """const HTML = %s;
export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname === "/health") return new Response("ok");
    return new Response(HTML, {headers: {"Content-Type": "text/html; charset=utf-8", "Cache-Control": "public, max-age=300"}});
  }
};
"""


def main():
    if not TOKEN:
        print("缺少 CF_API_TOKEN 环境变量", file=sys.stderr)
        raise SystemExit(1)
    with open(API_WORKER_JS, encoding="utf-8") as f:
        api_js = f.read()
    deploy_worker("bulu-api", api_js,
                  [{"type": "d1", "name": "BULU_DB", "id": D1_DB_ID}])
    with open(WEB_HTML, encoding="utf-8") as f:
        html = f.read()
    deploy_worker("bulu-web", WEB_WRAPPER % json.dumps(html))
    if "--domains" in sys.argv:
        ensure_domain("2bulu-api.168939.xyz", "bulu-api")
        ensure_domain("2bulu.168939.xyz", "bulu-web")
    print("done")


if __name__ == "__main__":
    main()
