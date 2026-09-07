# Brila — Agent Skills

[![Discord](https://img.shields.io/badge/Discord-Join-5865F2?logo=discord&logoColor=white)](https://discord.gg/uQ97scyNTX)

**Brila's official agent skills** — a growing set of skills and slash commands from the makers of
[Brila](https://brila.ai), the AI-native website builder. They drive the
[Brila public API](https://developers.brila.ai)
end-to-end: give a Google Maps or Yelp business link and get back a **live website** + its content as **Markdown**,
edit and manage a site (sections, images, custom domains), or build an embeddable reviews widget —
all over plain HTTPS. Runs in Claude Code,
OpenAI Codex, or any agent (see [Install](#install)). Skills follow the
[Agent Skills](https://agentskills.io/) open standard, and the plugin follows
[Agent Plugins v1.0.0](https://agent-plugins.org/specification) — a portable `plugin.json` and
`mcp.json` at the repo root, alongside the client-specific manifests.

> [!NOTE]
> **Technical Preview**
>
> These skills are in early release and under active development. Expect changes as skills are codified with robust
> evaluations and as the model landscape evolves. Check back frequently for updates.

## Install

### Claude Code

```
/plugin marketplace add brila-ai/agent-skills
/plugin install brila@brila
```

The plugin **bundles the Brila MCP server** (`https://mcp.brila.ai/mcp`), so Claude Code registers it
on install — approve it (and sign in with OAuth) on first use via `/mcp`. The skills then run over
the MCP tools; without it they fall back to the bundled Python script + an API key. Requires a recent
Claude Code that supports plugin-bundled MCP servers.

### OpenAI Codex

```
codex plugin marketplace add brila-ai/agent-skills
```

Then install **brila** from the plugin browser (`/plugins`, or the Plugins section in the Codex app).
On Codex the skill triggers by intent — just ask (slash commands are Claude Code-only).

The plugin **bundles the Brila MCP server** here too, so installing it registers `brila`
(`https://mcp.brila.ai/mcp`) — check with `codex mcp list` and sign in with `codex mcp login brila`
(Codex discovers the OAuth endpoints on its own). On an older Codex that doesn't read `mcpServers`
from a plugin manifest, add it yourself:

```
codex mcp add brila --url https://mcp.brila.ai/mcp
codex mcp login brila
```

Either way, the bundled script + an API key remains as a fallback.

### Any agent via npx

Using the community [`skills`](https://www.npmjs.com/package/skills) installer (installs the bare
skill, not the plugin/marketplace):

```
npx skills add brila-ai/agent-skills --skill brila-generate-site -a claude-code
# add --skill brila-widget for the reviews-widget skill
# -a codex to target Codex instead; add -g for a global install
```

### Then ask

> "Generate a Brila site for https://maps.app.goo.gl/…"

With the bundled **MCP server** (the default install above), the first run signs you in via **OAuth**
in the browser — nothing to configure. On the **script fallback** (no MCP), authenticate with a
**Brila API key** that you install yourself, so it never passes through the chat:

```bash
# either: export it from your shell profile (~/.zshrc, ~/.bashrc)
export BRILA_API_KEY=sk_…

# or: keep it in a file and point the script at it
mkdir -p ~/.brila && printf '%s' 'sk_…' > ~/.brila/api_key && chmod 600 ~/.brila/api_key
# … then run with --api-key-file ~/.brila/api_key
```

Don't paste the key into the chat and don't put it on a command line: a pasted key is stored in the
agent's transcript, and a key in a command's arguments is readable by other users via `ps` and kept in
your shell history. The script has no `--api-key` flag for that reason.

Generating a site needs an [**active Brila subscription**](https://brila.ai/pricing) — over MCP the
skill can start a checkout and hand you a payment link if you don't have one yet.

## Requirements

- **`curl`** and **Python 3** on PATH (generation runs through the bundled `brila_generate.py`).
  Windows ships `curl.exe` from Windows 10 1803 on, and Git Bash carries one too.
- A **POSIX shell** — on Windows use **Git Bash** / WSL. The script is invoked as `python3`, falling
  back to `python`; **on Windows use `py -3`** — python.org's installer creates no `python3`, and the
  Microsoft Store stub of that name exits without running anything.

The script reads and writes UTF-8 everywhere, independent of the system code page, so accented and
non-Latin business names survive on Windows.

## Commands

The plugin adds two slash commands (you can also just ask in plain language — the skill triggers on
intent):

- **`/brila:generate-site <google-maps-or-yelp-url>`** — generate a site from a Google Maps or Yelp
  business listing, poll until it's `ready`, and return the live URL + content as Markdown. (Omit the link and it'll ask.)
- **`/brila:widget <site id or live URL>`** — build a self-contained, embeddable **reviews widget** from
  a generated site's content, styled to match the store it will live on (Shopify / WordPress / Webflow).

Both need an active subscription (over MCP you sign in with OAuth; only the script fallback uses an API
key). Section editing, image uploads, custom domains, and
listing/deleting sites all work by asking in plain language ("change the hero headline", "point
example.com at my site") — the skill calls the API directly.

Under the hood the plugin ships **two skills**: `brila-generate-site` (generate + edit + manage a
site) and `brila-widget` (build the embeddable reviews widget). You don't pick — they trigger on intent.

## Configuration

- `BRILA_API_KEY` — your API key. Never passed as a command-line argument; there is no `--api-key` flag.
- `BRILA_API_KEY_FILE` — path to a file holding the key instead (same as `--api-key-file`).
- `BRILA_API_BASE` — API base (defaults to `https://api.brila.ai`).

## Issues

Found a problem or have a suggestion? [Open an issue](https://github.com/brila-ai/agent-skills/issues/new)
and we'll review it.

## License

[Apache-2.0](LICENSE) © 2026 Generated Media LLC. "Brila" is a trademark of Generated Media LLC.
