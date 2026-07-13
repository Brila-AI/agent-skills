#!/usr/bin/env python3
"""Generate a site via the Brila public API: create -> poll -> export Markdown.

HTTP goes through `curl` (a subprocess), not Python's urllib: Cloudflare resets Python's
TLS fingerprint on this API, while curl passes cleanly with identical headers. Needs `curl`
on PATH (standard on macOS/Linux) plus Python 3. Emits one JSON object per line for progress,
and a final {"event":"done", ...} (or {"error":...}).

Flow against /api/public/v1:
  1. POST /generations {source_url}            -> 202, {id, status:"queue", ...}
  2. GET  /generations/{id}  (poll)            -> {status: queue|processing|ready|failed}
  3. GET  /sites/{id}        (once ready)      -> {site_url, site_name, name, ...}
  4. GET  /sites/{id}/export?format=md         -> Markdown body
"""

import argparse
import json
import os
import subprocess
import sys
import time


def emit(obj):
    print(json.dumps(obj), flush=True)


def safe_json(text):
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return text


def _plugin_version(default="0.0.0"):
    # Read the version from the plugin manifest so the User-Agent tracks releases automatically
    # instead of drifting out of a hardcoded string. Script lives at
    # skills/brila-generate-site/scripts/, so the manifest is three levels up.
    path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".claude-plugin", "plugin.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("version") or default
    except (OSError, ValueError):
        return default


USER_AGENT = f"brila-agent/{_plugin_version()}"


def api_request(method, url, api_key, body=None):
    # -w appends "\n<http_code>" after the body so we can split status from payload.
    cmd = [
        "curl", "-sS", "--max-time", "60", "-X", method, url,
        "-H", f"Api-Key: {api_key}",
        "-H", "Accept: application/json",
        "-H", f"User-Agent: {USER_AGENT}",
        # Skip the ngrok-free interstitial when testing through a tunnel; harmless otherwise.
        "-H", "ngrok-skip-browser-warning: true",
        "-w", "\n%{http_code}",
    ]
    if body is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(body)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, str(e)
    if result.returncode != 0:
        return None, result.stderr.strip() or f"curl exited with {result.returncode}"
    out = result.stdout
    split = out.rfind("\n")
    status, payload = out[split + 1:].strip(), out[:split] if split != -1 else ""
    try:
        return int(status), payload
    except ValueError:
        return None, out


def error_type(body):
    parsed = safe_json(body)
    return parsed.get("type") if isinstance(parsed, dict) else None


def main():
    parser = argparse.ArgumentParser(description="Generate a Brila site and export Markdown.")
    parser.add_argument(
        "business_url",
        nargs="?",
        help="Google Maps or Yelp business URL (https://maps.app.goo.gl/... or https://www.yelp.com/biz/...)",
    )
    # Resume an existing generation (poll + export) instead of creating a new one — use the id from a
    # previous "created" line if a run was interrupted, so you don't start a duplicate paid generation.
    parser.add_argument("--resume", metavar="GENERATION_ID", default=None)
    parser.add_argument("--api-key", default=os.environ.get("BRILA_API_KEY"))
    parser.add_argument("--base", default=os.environ.get("BRILA_API_BASE", "https://api.brila.ai"))
    parser.add_argument("--poll-interval", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--md-out", default=None)
    args = parser.parse_args()

    if not args.api_key:
        emit({"error": "MISSING_CREDENTIALS",
              "message": "Set BRILA_API_KEY or pass --api-key with your Brila API key."})
        return 2
    api_key = args.api_key

    base = args.base.rstrip("/") + "/api/public/v1"

    # 1. Start the generation — or resume an existing one (poll + export, no new job).
    if args.resume:
        gen_id = args.resume
        emit({"event": "resumed", "id": gen_id})
    elif args.business_url:
        status, body = api_request("POST", f"{base}/generations", api_key,
                                   {"source_url": args.business_url})
        if status != 202:
            emit({"error": "CREATE_FAILED", "http_status": status,
                  "type": error_type(body), "body": safe_json(body)})
            return 1
        created = json.loads(body)
        gen_id = created["id"]
        emit({"event": "created", "id": gen_id, "status": created.get("status", "queue")})
    else:
        emit({"error": "MISSING_INPUT",
              "message": "Provide a Google Maps or Yelp business URL, or --resume <generation_id> to continue an existing job."})
        return 2

    # 2. Poll the generation until ready/failed or timeout.
    state = None
    started = time.time()
    deadline = started + args.timeout
    while time.time() < deadline:
        status, body = api_request("GET", f"{base}/generations/{gen_id}", api_key)
        if status != 200:
            emit({"error": "STATUS_FAILED", "http_status": status,
                  "type": error_type(body), "body": safe_json(body), "id": gen_id})
            return 1
        state = json.loads(body).get("status")
        emit({"event": "poll", "status": state, "elapsed_sec": int(time.time() - started)})
        if state in ("ready", "failed"):
            break
        time.sleep(args.poll_interval)

    if state != "ready":
        emit({"error": "NOT_READY", "status": state, "id": gen_id,
              "message": "failed" if state == "failed" else "timed out before ready"})
        return 1

    # 3. Fetch the finished site (published URL + name).
    status, body = api_request("GET", f"{base}/sites/{gen_id}", api_key)
    if status != 200:
        emit({"error": "SITE_FETCH_FAILED", "http_status": status,
              "type": error_type(body), "body": safe_json(body), "id": gen_id})
        return 1
    site = json.loads(body)

    # 4. Export Markdown.
    status, md = api_request("GET", f"{base}/sites/{gen_id}/export?format=md", api_key)
    if status != 200:
        emit({"error": "EXPORT_FAILED", "http_status": status,
              "type": error_type(md), "body": safe_json(md), "id": gen_id})
        return 1

    site_name = site.get("site_name") or gen_id
    # Default the Markdown into the project the user launched from: CLAUDE_PROJECT_DIR (set by
    # Claude Code to the project root) when present, otherwise the current working directory.
    out_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    md_path = args.md_out or os.path.join(out_dir, f"{site_name}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)

    published_url = site.get("site_url") or f"https://{site_name}.brila.ai"
    emit({"event": "done", "id": gen_id, "name": site.get("name"),
          "site_name": site_name, "published_url": published_url, "markdown_path": md_path})
    return 0


if __name__ == "__main__":
    sys.exit(main())
