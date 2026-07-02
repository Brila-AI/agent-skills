# Brila — Agent Skills

[![Discord](https://img.shields.io/badge/Discord-Join-5865F2?logo=discord&logoColor=white)](https://discord.gg/uQ97scyNTX)

**Brila's official agent skills** — a growing set of skills and slash commands from the makers of
[Brila](https://brila.ai), the AI-native website builder. They drive the
[Brila public API](https://developers.brila.ai)
end-to-end: give a Google Maps link and get back a **live website** + its content as **Markdown**,
edit a site's sections, or build an embeddable widget — all over plain HTTPS. Runs in Claude Code,
OpenAI Codex, or any agent (see [Install](#install)). Skills follow the
[Agent Skills](https://agentskills.io/) open standard.

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

### OpenAI Codex

```
codex plugin marketplace add brila-ai/agent-skills
```

Then install **brila** from the plugin browser (`/plugins`, or the Plugins section in the Codex app).
On Codex the skill triggers by intent — just ask (slash commands are Claude Code-only).

### Any agent via npx

Using the community [`skills`](https://www.npmjs.com/package/skills) installer (installs the bare
skill, not the plugin/marketplace):

```
npx skills add brila-ai/agent-skills --skill brila-generate-site -a claude-code
# -a codex to target Codex instead; add -g for a global install
```

### Then ask

> "Generate a Brila site for https://maps.app.goo.gl/…"

An [**active Brila subscription**](https://brila.ai/pricing) is required. Authenticate with your
**API key**: set `BRILA_API_KEY=sk_…`, or just **paste the key into the chat** — the skill picks it up
and passes it via `--api-key`.

## Requirements

- **`curl`** and **Python 3** on PATH (generation runs through the bundled `brila_generate.py`).
- A **POSIX shell** — on Windows use **Git Bash** / WSL. The script is invoked as `python3`, falling
  back to `python` or `py -3`.

## Commands

The plugin adds two slash commands (you can also just ask in plain language — the skill triggers on
intent):

- **`/brila:generate-site <google-maps-link>`** — generate a site from a Google Maps listing, poll until
  it's `ready`, and return the live URL + content as Markdown. (Omit the link and it'll ask.)
- **`/brila:widget <site id or live URL>`** — build a self-contained, embeddable **reviews widget** from
  a generated site's content, styled to match the store it will live on (Shopify / WordPress / Webflow).

Both need an active subscription and your API key. Section editing and image uploads work by asking in
plain language ("change the hero headline") — the skill calls the API directly.

## Configuration

- `BRILA_API_KEY` — your API key (or pass `--api-key`).
- `BRILA_API_BASE` — API base (defaults to `https://api.brila.ai`).

## Issues

Found a problem or have a suggestion? [Open an issue](https://github.com/brila-ai/agent-skills/issues/new)
and we'll review it.

## License

[Apache-2.0](LICENSE) © 2026 Generated Media LLC. "Brila" is a trademark of Generated Media LLC.
