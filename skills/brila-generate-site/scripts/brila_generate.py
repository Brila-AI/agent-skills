#!/usr/bin/env python3
"""Generate a site via the Brila public API: create -> poll -> export Markdown.

HTTP goes through `curl` (a subprocess), not Python's urllib: Cloudflare resets Python's
TLS fingerprint on this API, while curl passes cleanly with identical headers. Needs `curl`
on PATH (standard on macOS/Linux, and on Windows 10 1803+) plus Python 3 — on Windows call the
interpreter `py -3` or `python`, since python.org's installer creates no `python3`. All I/O is
UTF-8 regardless of the platform locale. Emits one JSON object per line for progress, and a final
{"event":"done", ...} (or {"error":...}).

Credentials: the API key comes from $BRILA_API_KEY or --api-key-file, and reaches curl over stdin.
It is never a command-line argument, so it can't leak into `ps`, shell history, or an agent
transcript.

Flow against /api/public/v1:
  1. POST /generations {source_url}            -> 202, {id, status:"queue", ...}
  2. GET  /generations/{id}  (poll)            -> {status: queue|processing|ready|failed}
  3. GET  /sites/{id}        (once ready)      -> {site_url, site_name, name, ...}
  4. GET  /sites/{id}/export?format=md         -> Markdown body
"""

import argparse
import json
import os
import shutil
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


def curl_auth_config(api_key):
    """Render the Api-Key header as a curl config, fed to curl on stdin.

    The key must never reach curl's argv: anything there is readable by other users via `ps` for
    the life of the request. curl's config syntax is one option per line; inside double quotes it
    honours backslash escapes, so escape those two characters.
    """
    escaped = api_key.replace("\\", "\\\\").replace('"', '\\"')
    return f'header = "Api-Key: {escaped}"\n'


def api_request(method, url, api_key, body=None):
    # -w appends "\n<http_code>" after the body so we can split status from payload.
    cmd = [
        "curl", "-sS", "--max-time", "60", "-X", method, url,
        # Read the Api-Key header from stdin (see curl_auth_config) — keeps the secret out of argv.
        "-K", "-",
        "-H", "Accept: application/json",
        "-H", f"User-Agent: {USER_AGENT}",
        # Skip the ngrok-free interstitial when testing through a tunnel; harmless otherwise.
        "-H", "ngrok-skip-browser-warning: true",
        "-w", "\n%{http_code}",
    ]
    if body is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(body)]
    try:
        # Decode the response as UTF-8 explicitly. `text=True` alone decodes with the platform's
        # locale encoding — UTF-8 on macOS/Linux, but the ANSI code page on Windows (cp1252, cp1251),
        # where the API's UTF-8 body either raises UnicodeDecodeError or turns into mojibake. A
        # business name with an accent or Cyrillic is enough to trigger it. `errors="replace"` keeps
        # a single bad byte from killing a run the user has already paid for.
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90,
                                encoding="utf-8", errors="replace",
                                input=curl_auth_config(api_key))
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


def resolve_api_key(key_file):
    """Get the API key from a file or the environment — never from a command-line argument.

    A key in argv leaks into `ps`, shell history, and the transcript of whatever agent ran the
    command, so the CLI deliberately has no --api-key flag. Raises OSError on an unreadable file.
    """
    if key_file:
        with open(os.path.expanduser(key_file), encoding="utf-8") as f:
            return f.read().strip()
    return os.environ.get("BRILA_API_KEY")


def error_type(body):
    parsed = safe_json(body)
    return parsed.get("type") if isinstance(parsed, dict) else None


def main():
    # allow_abbrev=False so that a stale `--api-key <secret>` call can't be silently accepted as an
    # abbreviation of --api-key-file (which would treat the secret as a path, keeping it in argv).
    parser = argparse.ArgumentParser(description="Generate a Brila site and export Markdown.",
                                     allow_abbrev=False)
    parser.add_argument(
        "business_url",
        nargs="?",
        help="Google Maps or Yelp business URL (https://maps.app.goo.gl/... or https://www.yelp.com/biz/...)",
    )
    # Resume an existing generation (poll + export) instead of creating a new one — use the id from a
    # previous "created" line if a run was interrupted, so you don't start a duplicate paid generation.
    parser.add_argument("--resume", metavar="GENERATION_ID", default=None)
    # The key is read from BRILA_API_KEY or a key file only — never a command-line argument.
    parser.add_argument(
        "--api-key-file",
        metavar="PATH",
        default=os.environ.get("BRILA_API_KEY_FILE"),
        help="File holding the Brila API key (e.g. ~/.brila/api_key, chmod 600). "
             "Defaults to $BRILA_API_KEY_FILE; otherwise the key is read from $BRILA_API_KEY.",
    )
    # Removed in 0.4.0. Kept only to refuse it with a useful message instead of an opaque
    # "unrecognized argument", and to tell the caller the key is now in their shell history.
    parser.add_argument("--api-key", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--base", default=os.environ.get("BRILA_API_BASE", "https://api.brila.ai"))
    parser.add_argument("--poll-interval", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--md-out", default=None)
    args = parser.parse_args()

    if args.api_key is not None:
        emit({"error": "API_KEY_ARG_REFUSED",
              "message": "--api-key was removed: a key on the command line is visible to other "
                         "users via `ps` and lands in shell history and agent transcripts. Set "
                         "BRILA_API_KEY instead, or use --api-key-file. Note that the key you just "
                         "passed is now in your shell history."})
        return 2

    try:
        api_key = resolve_api_key(args.api_key_file)
    except OSError as e:
        emit({"error": "KEY_FILE_UNREADABLE", "message": str(e)})
        return 2
    if not api_key:
        emit({"error": "MISSING_CREDENTIALS",
              "message": "No Brila API key. Set BRILA_API_KEY in your environment (shell profile "
                         "or a gitignored .env), or point --api-key-file at a file holding the key. "
                         "For your own safety the key is never taken as a command-line argument."})
        return 2

    # Every request goes through curl, so check it once here — otherwise each call fails as an
    # opaque "[Errno 2] No such file or directory: 'curl'" inside an HTTP error. Windows ships
    # curl.exe from 10 1803 on; older boxes and stripped images need it installed.
    if shutil.which("curl") is None:
        emit({"error": "CURL_NOT_FOUND",
              "message": "curl was not found on PATH, and every request goes through it. macOS, "
                         "Linux, and Windows 10 1803+ ship curl; Git Bash provides one on Windows "
                         "too. Install curl (or open a shell that has it) and re-run."})
        return 2

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
    # newline="\n" writes the export exactly as the API sent it; Windows text mode would otherwise
    # rewrite every LF as CRLF and the file would no longer match the site's content byte for byte.
    with open(md_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(md)

    published_url = site.get("site_url") or f"https://{site_name}.brila.ai"
    emit({"event": "done", "id": gen_id, "name": site.get("name"),
          "site_name": site_name, "published_url": published_url, "markdown_path": md_path})
    return 0


if __name__ == "__main__":
    sys.exit(main())
