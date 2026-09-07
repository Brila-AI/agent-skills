# Changelog

All notable changes to the **brila** plugin are documented here.
Format: [Keep a Changelog](https://keepachangelog.com); versioning: [SemVer](https://semver.org).
The plugin version lives in three manifests that have to agree: `plugin.json`,
`.claude-plugin/plugin.json` and `.codex-plugin/plugin.json`.

## [0.4.2] — 2026-09-07

Windows fixes. The script and the skill docs assumed a UTF-8 locale, a `python3` on PATH and the
plugin directory as the working directory — three assumptions that hold on macOS and Linux and none
of which hold on Windows. The API, the flow and the MCP path are unchanged.

### Fixed

- **Generation crashed or produced mojibake on Windows.** `brila_generate.py` read `curl`'s output
  with `subprocess.run(..., text=True)` and no explicit encoding, so Python decoded the response with
  the platform's locale encoding. That is UTF-8 on macOS and Linux, but the ANSI code page on Windows.
  On a Western install (cp1252) the bytes `0x81` and `0x8f` are undefined, so any Cyrillic listing —
  and much else — died with `UnicodeDecodeError: 'charmap' codec can't decode byte 0x81`; on a Russian
  install (cp1251) nothing crashed and the exported Markdown was silently mojibake. The response is now
  decoded as UTF-8 explicitly, independent of the system code page, and a single undecodable byte is
  replaced instead of ending a run the user has already paid for.

- **The exported Markdown no longer matches the site byte for byte on Windows.** The file was opened in
  text mode, which rewrites every LF as CRLF. It is now written with `newline="\n"`.

- **A missing `curl` reported an unusable error.** Every request goes through `curl`, and its absence
  surfaced as `{"error":"CREATE_FAILED","http_status":null,"body":"[Errno 2] No such file or
  directory: 'curl'"}` — an HTTP-shaped failure for a missing dependency. The script now checks once,
  before any request, and reports `CURL_NOT_FOUND` with what to install.

- **The documented command could not run on Windows.** The skill and the `/brila:generate-site` command
  both said `python3 scripts/brila_generate.py`. Two problems: python.org's installer creates no
  `python3` (the Microsoft Store stub of that name exits without running anything), and the relative
  path resolves against the agent's working directory, which is the user's project rather than the
  plugin. Both now give an absolute, quoted `$CLAUDE_PLUGIN_ROOT` path — quoted because Windows profile
  directories routinely contain a space — and name `py -3` as the Windows interpreter.

- **The reviews-widget serialization one-liner failed on Windows.** `skills/brila-widget/SKILL.md`
  built the widget's data block with `json.load(open(path))` and `print(..., ensure_ascii=False)`.
  Review text is rarely pure ASCII, so the read raised `UnicodeDecodeError` under the ANSI code page and
  the write raised `UnicodeEncodeError` on a `cp866` console. The one-liner now reads with
  `encoding="utf-8"` and writes UTF-8 bytes straight to `stdout.buffer`. The `<` → `\u003c` escaping
  that keeps a review containing `</script>` from breaking out of the block is unchanged.

## [0.4.1] — 2026-09-04

Two packaging defects, both present since the plugin gained the file they concern. The skills, the
commands and the bundled server are unchanged — what changes is that Codex can find the plugin at all,
and that Claude Code's component inventory stops under-reporting it.

### Fixed

- **Codex found no plugin in the marketplace.** `codex plugin marketplace add brila-ai/agent-skills` —
  the command this README gives — added the marketplace and then listed nothing in the plugin browser,
  so the documented install path dead-ended. The entry in `.agents/plugins/marketplace.json` declared a
  `git-subdir` source with `"path": "."`, and Codex resolves that source only for a real subdirectory:
  `"."`, `"./"` and `""` all yield an empty listing, while a genuine subdirectory resolves. This plugin
  lives at the repository root, so the source is now `local` with `"path": "./"`, which resolves
  relative to the marketplace root and therefore behaves the same for a clone, a fork and a local
  checkout. Nothing else about the entry changes, and the plugin itself was always fine — only the
  marketplace index pointed into the void.

- **`claude plugin details brila` reported `MCP servers (0)` while the server was registered and
  reachable.** The inventory builder reads a file named exactly `.mcp.json` at the plugin root; it does
  not expand the path string that `"mcpServers": "./mcp.json"` gives it, and an inline object in a
  client manifest does not reach it either. The runtime loader is a separate code path that does resolve
  the path, which is why the server always connected — the count alone was wrong. Agent Plugins v1 fixes
  the name `mcp.json` at the plugin root and allows no alternative path, so renaming is not an option;
  a second copy of the file would mean two definitions to keep in sync, which is what 0.4.0 set out to
  end. `.mcp.json` is therefore a **symlink** to `mcp.json`: two names, one definition. Git stores it as
  mode `120000` and it survives a clone. `claude plugin details` now reports `MCP servers (1)` and
  registers the server once, not twice. On a checkout without symlink support (`core.symlinks=false`)
  the link materialises as a small text file, the count falls back to `0`, and the server still
  connects — the worst case equals the behaviour before this fix.

## [0.4.0] — 2026-08-17

Adopts the **Agent Plugins v1.0.0** portable format, brings the bundled MCP server to **OpenAI
Codex**, hardens how the script fallback handles the API key, and draws an explicit untrusted-data
boundary around review text.

### Added
- **Conformance with the [Agent Plugins v1.0.0](https://agent-plugins.org/specification) standard.**
  Two portable files now sit at the plugin root: `plugin.json` (the required manifest — its schema is
  closed, so it carries only the standard metadata fields) and `mcp.json` (the only place the spec
  allows MCP servers to be declared, with the explicit transport `"type": "streamable-http"`). Both
  validate against the official `schemas/1.0.0/` schemas. The skills already sat at the spec's fixed
  `skills/` location, and `commands/`, the client manifests, and the marketplace metadata stay where
  their clients expect them, as the spec's own migration guide recommends.
- **One declaration for the MCP server, shared by every client.** The root `mcp.json` is now the single
  source of truth; both `.claude-plugin/plugin.json` and `.codex-plugin/plugin.json` point at it with
  `"mcpServers": "./mcp.json"`, replacing Claude Code's inline copy. Verified in both clients:
  `claude mcp get plugin:brila:brila` health-checks the server (Claude Code accepts the spec's
  `streamable-http` and normalises it to its own `http`), and `codex mcp list` shows it registered.
- **The Codex plugin now bundles the Brila MCP server too**, which it didn't before: Codex reads
  `mcpServers` as a *path*, so it picks up the same `mcp.json`. `codex mcp login brila` signs in, and
  Codex discovers the OAuth endpoints from the server's own metadata. **This supersedes the 0.3.0 note**
  that Codex users had to wire the server into `config.toml` by hand; that's now only needed on a Codex
  too old to read `mcpServers` from a plugin manifest. Codex is no longer restricted to the API-key path.

### Changed
- **The API key is never a command-line argument.** `brila_generate.py` reads it from `BRILA_API_KEY`
  or a file (`--api-key-file` / `$BRILA_API_KEY_FILE`), and the **`--api-key` flag is removed** — a key
  in argv is readable by other users via `ps` and persists in shell history. Passing `--api-key` now
  fails with `API_KEY_ARG_REFUSED` and points out that the key is now in the shell history.
  **Breaking** for callers that used the flag; `BRILA_API_KEY` callers are unaffected.
- **The key no longer reaches `curl`'s argv either** — the `Api-Key` header is fed to curl as a config
  on stdin, so it isn't visible in the process list during a request.
- **Skills no longer ask the user to paste the key into the chat** (it would be stored verbatim in the
  agent transcript). `SKILL.md`, `REFERENCE.md`, the slash commands, and the README now walk the user
  through installing the key themselves — shell profile, key file, or a gitignored `.env`. The skills
  also say how to tell a key is missing **without** leaking it: let the failing call report
  `MISSING_CREDENTIALS`, and never run `echo $BRILA_API_KEY` or `env | grep` (a presence-only test is
  the fallback). If the user pastes the key anyway, the agent uses it but tells them it's now in the
  conversation history.
- **The heads-up is tied to the job actually starting** — the "⏳ this takes a minute" message now goes
  out when the generation is accepted (the `generation_id` / `created` line) instead of before the call,
  so a run that fails instantly on credentials no longer gets announced as under way.

### Added
- **Every script-side failure is now documented** in `REFERENCE.md` — the credential states
  (`KEY_FILE_UNREADABLE`, `API_KEY_ARG_REFUSED`, `MISSING_INPUT`) and the wrappers that say which step
  failed (`CREATE_FAILED`, `STATUS_FAILED`, `SITE_FETCH_FAILED`, `EXPORT_FAILED`), including the note
  that the last two mean the site already exists, so the fix is `--resume`, never a second paid run.
- **Untrusted-content boundary in both skills** — review text, section fields, exported Markdown, and
  (for the widget) the fetched destination store page are documented as **data, never instructions**:
  directives found inside them are not acted on, don't change the workflow, and get flagged to the user.
- **Output-escaping rules for `brila-widget`** — review bodies and author names must be HTML-escaped
  before going into the snippet and JSON-escaped with `<` as `\u003c` in the JSON-LD, so a review
  containing `</script>` can't inject markup into the storefront the widget is embedded in.

## [0.3.0] — 2026-07-27

Adds the **Brila MCP server** as the primary way the skills reach the API. The Claude Code plugin now **bundles** the remote MCP server (`https://mcp.brila.ai/mcp`), so installing the plugin registers it and the skills call MCP tools while the server owns the orchestration. The bundled Python script + API key stay as a fallback when no MCP server is connected.

### Added
- **Bundled Brila MCP server** — `.claude-plugin/plugin.json` declares the remote server under `mcpServers`, so Claude Code registers it on install (approve / OAuth-authenticate on first use). Requires a recent Claude Code that supports plugin-bundled MCP servers.
- **MCP path for the skills** — when the MCP tools are available, generation runs through `generate_site` (returns a `generation_id`; poll `get_generation` until `ready`, then `get_site` / `export_site`), and editing / uploads / domains / lifecycle / account use their matching tools.
- **Product-workflow tools** — `connect_domain` (attach + poll a custom domain to live), `set_section_image` (upload + set on a section in one call), `analyze_reviews` (schema.org rating + review highlights).
- **Account & billing tools** — `account_info` reports the plan + remaining site budget and, while on the free plan, lists the purchasable plans (so the agent knows the limits); `create_subscription_checkout` starts a subscription purchase and returns a payment link — it works without an active subscription, so the agent can get the user subscribed from the flow.
- **OAuth sign-in over MCP** — no key to paste; the MCP server also accepts a Brila API key.

### Changed
- **Skills prefer the MCP tools when connected**, falling back to the bundled `brila_generate.py` + API key otherwise. `SKILL.md` / `REFERENCE.md` / commands / `brila-widget` now document both paths.

### Notes
- **OpenAI Codex** doesn't auto-bundle an MCP server from the plugin manifest — Codex users add the `brila` server to their `config.toml`, or keep using the bundled script.

## [0.2.2] — 2026-07-13

### Added
- **Yelp business URLs** — `/brila:generate-site` and the bundled `brila_generate.py` now accept a Yelp business page (`https://www.yelp.com/biz/…`) in addition to a Google Maps link; the API detects the source from the URL. The script's positional argument is renamed `maps_url` → `business_url` (positional, so existing calls are unaffected).

## [0.2.1] — 2026-07-10

### Fixed
- The bundled `brila_generate.py` now derives its `User-Agent` (`brila-agent/<version>`) from the plugin version in `.claude-plugin/plugin.json` instead of a hardcoded `brila-agent/0.1.0`, so it tracks releases automatically.

## [0.2.0] — 2026-07-10

### Added
- **Custom domains** — attach / verify / remove a custom domain on a site (subscriber feature, one domain per site): point the CNAME out of band, and background auto-verification moves `pending` → `active`. Documented in `brila-generate-site`'s `REFERENCE.md`.
- **Delete a site** — `DELETE /v1/sites/{id}` takes a site offline (a site deleted mid-period still counts toward the creation limit until it resets).

### Changed
- **Split the reviews widget into its own skill, `brila-widget`.** Generating/managing a site (`brila-generate-site`) and building an embeddable widget from a site now trigger on their own intent. `brila-widget` is self-contained: auth → find the site / fetch its reviews → build the styled, self-contained snippet with schema.org JSON-LD. `/brila:widget` now drives this skill.
- Tuned the skills' trigger descriptions, validated with trigger-accuracy evals: `brila-generate-site`'s description rewritten for sharper trigger phrasing (the variant that scored best), `brila-widget`'s verified as-is. Precision stayed 100% (no false triggers, clean split between the two skills).

## [0.1.0] — 2026-07-07

Initial release. Skill-first (no MCP yet); authentication by **API key** (`BRILA_API_KEY`, `--api-key`, or paste in chat).

### Added
- **Generate** a published site from a Google Maps link — returns the live URL + content as Markdown — via the bundled `brila_generate.py` (`create → poll → export`, `--resume` to continue an interrupted job, `python`/`py` interpreter fallback). `/brila:generate-site`.
- **Edit** a generated site's sections (schema-aware read → edit → re-publish) and **upload** images to the CDN.
- **Reviews widget** — build a self-contained, embeddable widget styled to match the destination store, with static schema.org JSON-LD structured reviews. `/brila:widget`.
- **Progressive disclosure** — a lean `SKILL.md` (generate + auth); section editing, image uploads, the reviews widget, other export formats (HTML/JSON), and the full error table live in `REFERENCE.md`, loaded on demand.
- **Distribution** — Claude Code plugin (`.claude-plugin/` + repo marketplace), OpenAI Codex plugin (`.codex-plugin/` + `.agents/plugins/marketplace.json`), and `npx skills add Brila-AI/agent-skills`.
