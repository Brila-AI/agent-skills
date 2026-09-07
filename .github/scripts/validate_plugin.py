#!/usr/bin/env python3
"""Validate the plugin's tracked files: packaging invariants and portability guarantees.

    python3 .github/scripts/validate_plugin.py

Runs on Linux in CI and needs no network, no credentials, and no packages outside the standard
library. Every check here covers a defect that has shipped or nearly shipped: a version that drifted
between manifests, a marketplace source that hid the plugin, an `.mcp.json` that stopped being a
symlink, a locale-dependent decode that broke Windows, a documented command that could not run.

The eval suite under `evals/` is gitignored and stays a local release step — nothing here reads it.
"""

import json
import os
import py_compile
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "brila-generate-site" / "scripts" / "brila_generate.py"

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


def read_json(rel):
    # A caller further down the file (e.g. the "*.json parses" loop) reports malformed JSON as
    # its own FAIL; this must not raise first and abort the run before that check runs. An
    # unparsed file becomes an empty dict, so every .get()-based check on it reports its own,
    # accurate FAIL instead of a bare traceback.
    try:
        return json.loads((REPO / rel).read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def first_plugin(rel):
    # Same reasoning as read_json: a marketplace file with malformed JSON, a missing "plugins"
    # key, or an empty "plugins" list must not raise KeyError/IndexError and abort the run — the
    # checks that read this entry already report FAIL on an empty dict via their own .get() calls.
    plugins = read_json(rel).get("plugins")
    return plugins[0] if isinstance(plugins, list) and plugins else {}


# --- 1. one version, and release notes to go with it ---------------------------
MANIFESTS = ("plugin.json", ".claude-plugin/plugin.json", ".codex-plugin/plugin.json")
versions = {m: read_json(m).get("version") for m in MANIFESTS}
check("the three manifests declare one version",
      len(set(versions.values())) == 1 and all(versions.values()), f"{versions}")

version = versions["plugin.json"]
changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
check(f"CHANGELOG.md documents {version}", f"## [{version}]" in changelog,
      "the bump and its release notes have to land together")

# --- 2. the MCP server is declared exactly once --------------------------------
index = subprocess.run(["git", "ls-files", "-s", ".mcp.json"], cwd=REPO,
                       capture_output=True, text=True).stdout
check(".mcp.json is a symlink in the index (mode 120000)", index.startswith("120000 "),
      f"git ls-files reported {index.strip() or 'nothing'!r}; a copy reintroduces two definitions")

link = REPO / ".mcp.json"
check(".mcp.json points at mcp.json",
      link.is_symlink() and os.readlink(link) == "mcp.json",
      f"resolves to {os.readlink(link) if link.is_symlink() else 'a regular file'!r}")

servers = read_json("mcp.json").get("mcpServers", {})
check("mcp.json declares exactly one server, named brila", list(servers) == ["brila"],
      f"declares {list(servers)}")
check("the brila server is streamable-http", servers.get("brila", {}).get("type") == "streamable-http",
      f"type is {servers.get('brila', {}).get('type')!r}")

for manifest in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
    declared = read_json(manifest).get("mcpServers")
    check(f"{manifest} points at ./mcp.json by path", declared == "./mcp.json",
          f"got {declared!r}; an inline object is a second declaration to keep in sync")

check("the portable manifest adds no second declaration", "mcpServers" not in read_json("plugin.json"),
      "plugin.json must leave the declaration to mcp.json")

# --- 3. both marketplaces resolve to this repository ---------------------------
codex_entry = first_plugin(".agents/plugins/marketplace.json")
check("the Codex marketplace uses a local source",
      codex_entry.get("source") == {"source": "local", "path": "./"},
      f"got {codex_entry.get('source')!r}; git-subdir resolves only for a real subdirectory, "
      "and this plugin sits at the repository root")

claude_entry = first_plugin(".claude-plugin/marketplace.json")
check("both marketplaces name the brila plugin",
      codex_entry.get("name") == "brila" and claude_entry.get("name") == "brila",
      f"codex={codex_entry.get('name')!r}, claude={claude_entry.get('name')!r}")

# --- 4. every skill is loadable and every tracked JSON file parses -------------
for skill_dir in sorted((REPO / "skills").iterdir()):
    if not skill_dir.is_dir():
        continue
    name = skill_dir.name
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    matter = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    check(f"{name}: SKILL.md opens with frontmatter", matter is not None,
          "the loader reads name and description from it")
    if not matter:
        continue
    fields = dict(re.findall(r"^(name|description):[ \t]*(.+)$", matter.group(1), re.M))
    check(f"{name}: frontmatter name matches the directory", fields.get("name") == name,
          f"frontmatter says {fields.get('name')!r}")
    check(f"{name}: frontmatter carries a description", bool(fields.get("description", "").strip()),
          "an empty description means the skill never triggers")

tracked_json = subprocess.run(["git", "ls-files", "*.json"], cwd=REPO,
                              capture_output=True, text=True).stdout.split()
# This only guards against git ls-files coming back empty (wrong cwd, a git failure, or a repo
# with no tracked JSON at all), which would make the "*.json parses" loop below silently vacuous.
# It does not assert that every expected manifest is present — a single deleted manifest still
# leaves plenty of other tracked JSON here, and that specific loss is caught by the checks above
# that read each manifest by name (version, mcpServers, marketplace entries, ...).
check("git ls-files returns tracked JSON files (the parse loop below isn't vacuous)",
      len(tracked_json) > 0, f"found {tracked_json}")
for rel in tracked_json:
    try:
        json.loads((REPO / rel).read_text(encoding="utf-8"))
        ok, detail = True, ""
    except (OSError, ValueError) as e:
        ok, detail = False, str(e)
    check(f"{rel} parses", ok, detail)

# --- 5. the bundled script is at least syntactically loadable ------------------
# cfile can't be os.devnull: /dev/null is a character device, and CPython's atomic bytecode
# writer refuses to overwrite a non-regular file, raising a bare FileExistsError (not
# py_compile.PyCompileError) that would crash this script instead of reporting a failed check.
with tempfile.TemporaryDirectory() as tmp_dir:
    try:
        py_compile.compile(str(SCRIPT), cfile=os.path.join(tmp_dir, "brila_generate.pyc"), doraise=True)
        ok, detail = True, ""
    except py_compile.PyCompileError as e:
        ok, detail = False, str(e)
check("brila_generate.py byte-compiles", ok, detail)

# --- 6. the Windows fixes cannot be dropped by a later rewrite -----------------
source = SCRIPT.read_text(encoding="utf-8")


def function_source(name):
    # Bound a top-level function's own body: from its "def NAME(" line up to (not including) the
    # next top-level "def ", or EOF. Every function in this script is unindented, so this is exact.
    match = re.search(rf"^def {name}\(.*?(?=^def |\Z)", source, re.M | re.S)
    return match.group(0) if match else ""


# A plain re.search for "subprocess.run(...)" or "open(md_path...)" binds to whichever call comes
# FIRST in the file — not necessarily the real one. A decoy call added anywhere else (before the
# function that matters, with or without the property this check wants) can make a broken real
# call look fine, or a correct real call look broken. Scoping to the named function's own source
# closes that: a decoy outside api_request()/main() cannot affect either verdict, whichever
# direction it's wrong in. Checking every subprocess.run call found even inside the function
# (rather than just the first) also survives the real call being duplicated or reordered there.
api_request_src = function_source("api_request")
run_calls = re.findall(r"subprocess\.run\((?:[^()]|\([^()]*\))*\)", api_request_src, re.S)
text_mode_calls = [c for c in run_calls if "text=True" in c]
check("the HTTP call names its decoding explicitly",
      bool(text_mode_calls) and all("encoding=" in c for c in text_mode_calls),
      "without encoding= Python decodes with the platform locale, which is the ANSI code page on "
      "Windows: cp1252 raises UnicodeDecodeError and cp1251 produces mojibake")

main_src = function_source("main")
write_calls = re.findall(r"open\(md_path(?:[^()]|\([^()]*\))*\)", main_src, re.S)
check('the export is written with newline="\\n"',
      bool(write_calls) and all('newline="\\n"' in c for c in write_calls),
      "Windows text mode otherwise rewrites every LF as CRLF")

# --- 7. the documented commands can actually run on Windows -------------------
DOCS = ("skills/brila-generate-site/SKILL.md", "commands/generate-site.md",
        "skills/brila-widget/SKILL.md")

# One line, one invocation: "python3 ./scripts/x.py" or "python3 skills/.../x.py" are both relative
# (an old whole-file regex required "scripts/" to sit directly after whitespace, so any other
# prefix slipped past). \S* eats whatever precedes the filename — "./", a full relative path, a
# quote, or $CLAUDE_PLUGIN_ROOT — so the captured group is the whole path token to classify below.
INVOCATION = re.compile(r"(?:python3?|py\s+-3)\s+(\S*brila_generate\.py)")

for rel in DOCS:
    text = (REPO / rel).read_text(encoding="utf-8")
    lines = text.splitlines()
    # Bind each of the two checks below to the SPECIFIC line it's about, not to the whole file —
    # a whole-file substring check is satisfied by any one matching line, so quoting stripped from
    # one of several invocations still passes as long as another invocation stays quoted.
    for lineno, line in enumerate(lines, start=1):
        match = INVOCATION.search(line)
        if not match:
            continue
        path_token = match.group(1).strip("\"'`")
        rooted = path_token.startswith("/") or path_token.startswith("$CLAUDE_PLUGIN_ROOT") \
            or path_token.startswith("${CLAUDE_PLUGIN_ROOT}")
        check(f"{rel}:{lineno}: no relative script path", rooted,
              f"line {lineno}: {line.strip()!r}; the agent's working directory is the user's "
              "project, not this plugin")
        check(f"{rel}:{lineno}: the script path is quoted against spaces",
              '"$CLAUDE_PLUGIN_ROOT' in line or '"${CLAUDE_PLUGIN_ROOT}' in line,
              f"line {lineno}: {line.strip()!r}; Windows profile directories routinely contain a space")
    if "python3" in text:
        # This one stays file-scoped on purpose: the Windows fallback is documented once, in
        # prose, for the whole file — not repeated on every invocation line.
        check(f"{rel}: names the Windows interpreter", "py -3" in text,
              "python.org's installer creates no python3, and the Store stub exits without running")

widget = (REPO / "skills/brila-widget/SKILL.md").read_text(encoding="utf-8")
one_liner = next((ln for ln in widget.splitlines()
                   if "json.dumps" in ln and ("python3 -c" in ln or "py -3 -c" in ln)), None)
if one_liner is None:
    no_line_detail = "no line with `python3 -c`/`py -3 -c` and json.dumps found in skills/brila-widget/SKILL.md"
    check("the widget one-liner reads the section as UTF-8", False, no_line_detail)
    check("the widget one-liner writes UTF-8 whatever the console code page is", False, no_line_detail)
    check("the widget one-liner still escapes <", False, no_line_detail)
else:
    check("the widget one-liner reads the section as UTF-8", 'encoding="utf-8"' in one_liner,
          f"open() without encoding uses the ANSI code page: {one_liner[:120]}")
    check("the widget one-liner writes UTF-8 whatever the console code page is",
          "stdout.buffer.write" in one_liner,
          f"print() of non-ASCII raises UnicodeEncodeError on a cp866 console: {one_liner[:120]}")
    check("the widget one-liner still escapes <", "\\u003c" in one_liner,
          "that escape is what stops a review containing </script> from closing the block")

print()
print(f"{len(failures)} failure(s)" if failures else "ALL CHECKS PASSED")
sys.exit(1 if failures else 0)
