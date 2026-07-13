# Changelog

All notable changes to the **brila** plugin are documented here.
Format: [Keep a Changelog](https://keepachangelog.com); versioning: [SemVer](https://semver.org).
The plugin version lives in `.claude-plugin/plugin.json`.

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
