# Changelog

All notable changes to the **brila** plugin are documented here.
Format: [Keep a Changelog](https://keepachangelog.com); versioning: [SemVer](https://semver.org).
The plugin version lives in `.claude-plugin/plugin.json`.

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
