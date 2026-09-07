#!/usr/bin/env python3
"""Run the shipped generation script on every path that needs no network, on every OS.

    python3 .github/scripts/smoke_cli.py

The assertions matter less than the fact that a Windows runner imports and executes the real file:
a syntax error, a bad import, a lost `shutil`, or a changed argparse surface fails here.

The script refuses in a fixed order — `--api-key`, then the key, then `curl`, then the input — so a
case has to satisfy every earlier gate to reach the one it tests. That is why some cases below set a
dummy key. The key is a literal, not a secret: nothing here reaches the network.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "brila-generate-site" / "scripts" / "brila_generate.py"
TIMEOUT_SEC = 60  # single source of truth: the subprocess.run timeout and every message quoting it

# Our own output carries an em dash, and on Windows stdout is a pipe in CI, which Python encodes
# with the ANSI code page — the first real run turned that dash into a replacement character in the
# job log. Force UTF-8 so the diagnostics stay readable on every runner; this suite exists to catch
# exactly this class of defect and is not exempt from it.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

failures = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}{'' if ok else ' — ' + detail}")
    if not ok:
        failures.append(name)


def base_env(**overrides):
    """A minimal environment that still lets python.exe start on Windows."""
    # CPython upper-cases environment variable names on Windows, so os.environ.items() never
    # yields "SystemRoot" — only "SYSTEMROOT" — there is no need to list both forms.
    keep = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATHEXT",
            "COMSPEC", "HOME", "USERPROFILE", "LOCALAPPDATA")
    env = {k: v for k, v in os.environ.items() if k in keep}
    env.pop("BRILA_API_KEY", None)
    env.pop("BRILA_API_KEY_FILE", None)
    env.pop("BRILA_API_BASE", None)
    env.update({k: v for k, v in overrides.items() if v is not None})
    return env


def run(args, env):
    # A hang in the script under test must not abort this script with a bare traceback: the
    # caller needs a chance to turn it into a FAIL line, so a timeout here is reported as
    # `None`, not raised.
    try:
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True,
                              text=True, encoding="utf-8", timeout=TIMEOUT_SEC, env=env, cwd=str(REPO))
    except subprocess.TimeoutExpired:
        return None


def emitted(stdout):
    """Every line the script prints must be one JSON object — that is its contract."""
    objects = []
    for line in stdout.splitlines():
        if line.strip():
            objects.append(json.loads(line))
    return objects


def expect_error(name, args, env, code, exit_code=2):
    res = run(args, env)
    if res is None:
        check(name, False, f"the process did not exit within the {TIMEOUT_SEC}s timeout")
        return
    try:
        codes = [o.get("error") for o in emitted(res.stdout)]
    except ValueError as e:
        check(name, False, f"stdout was not one JSON object per line: {e}; got {res.stdout[:200]!r}")
        return
    check(name, code in codes and res.returncode == exit_code,
          f"rc={res.returncode} (want {exit_code}), errors={codes}, stderr={res.stderr[:200]}")


print(f"python {sys.version.split()[0]} on {sys.platform}")

res = run(["--help"], base_env())
if res is None:
    check("--help exits cleanly and offers the key file", False,
          f"the process did not exit within the {TIMEOUT_SEC}s timeout")
    check("--help never advertises --api-key", False,
          f"the process did not exit within the {TIMEOUT_SEC}s timeout")
else:
    check("--help exits cleanly and offers the key file",
          res.returncode == 0 and "--api-key-file" in res.stdout,
          f"rc={res.returncode}, stdout={res.stdout[:200]}")
    check("--help never advertises --api-key",
          "--api-key " not in res.stdout and "--api-key\n" not in res.stdout,
          "a key on the command line is readable via ps and kept in shell history")

expect_error("--api-key is refused", ["https://maps.app.goo.gl/x", "--api-key", "sk_dummy"],
             base_env(), "API_KEY_ARG_REFUSED")

expect_error("no key reports MISSING_CREDENTIALS", ["https://maps.app.goo.gl/x"],
             base_env(), "MISSING_CREDENTIALS")

with tempfile.TemporaryDirectory() as empty:
    expect_error("a missing curl reports CURL_NOT_FOUND", ["--resume", "gen_x"],
                 base_env(PATH=empty, BRILA_API_KEY="test_key"), "CURL_NOT_FOUND")

expect_error("no URL and no --resume reports MISSING_INPUT", [],
             base_env(BRILA_API_KEY="test_key"), "MISSING_INPUT")

print()
print(f"{len(failures)} failure(s)" if failures else "ALL CHECKS PASSED")
sys.exit(1 if failures else 0)
