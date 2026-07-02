# Changelog

All notable changes to the **brila** plugin are documented here.
Format: [Keep a Changelog](https://keepachangelog.com); versioning: [SemVer](https://semver.org).
The plugin version lives in `.claude-plugin/plugin.json`.

## [0.1.0] — 2026-07-01

Initial release. Skill-first; authentication is by **API key** (`BRILA_API_KEY` / `--api-key`).

### Added
- **Generate** a published site from a Google Maps link, returns the live URL + content as Markdown — `/brila:generate-site`.
- **Edit** a generated site's sections (schema-aware read → edit → re-publish) and **upload** images to the CDN.
- **Reviews widget** — build a self-contained, embeddable widget styled to match the destination store — `/brila:widget`.
