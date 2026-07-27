---
name: brila-generate-site
description: Use this to build or change a website for a real local business — restaurants, cafes, taco spots, roasteries, salons, barbers, shops, clinics, and the like — via Brila. Trigger on any request to make, build, spin up, set up, or "turn this place into" a site or landing page, and treat a shared Google Maps or Yelp business link (maps.app.goo.gl/… or yelp.com/biz/…) as a strong go signal even without the words "website" or "Brila." No link yet? Still trigger and ask for it. Also use to edit an existing Brila site's text or images (hero headline, about section, hours, gallery photo), list or delete sites, take one down, or connect a custom domain. Do NOT use for embeddable reviews/testimonials widgets (that's the brila-widget skill), hand-coding or deploying a site yourself, Markdown conversion, or scraping a listing link.
---

# Brila — generate a site & return link + Markdown

This skill drives **Brila** end-to-end: it starts a site generation for a business, waits for it to
finish, and returns the **live published URL** plus the **site content as Markdown**.

There are **two ways** it reaches Brila — prefer the first whenever it's available:

1. **Brila MCP server (preferred).** This plugin ships the Brila MCP server, so its tools
   (`generate_site`, `get_generation`, `get_site`, …) are usually available in your session. The
   server owns the orchestration and handles auth — nothing to install, no API key for you to manage.
2. **Bundled script (fallback).** If the Brila MCP tools aren't available, run the bundled
   `brila_generate.py` with a Brila **API key**. Needs `curl` + Python 3.

Same result either way: a live URL + Markdown. Generation is the **main flow** (below); editing
sections, uploading images, listing/deleting sites, custom domains, other formats, and the full
error table live in **[REFERENCE.md](REFERENCE.md)** — read it when the user asks. (An embeddable
reviews widget from a site is a separate skill, `brila-widget`.)

## What you need before running

- **A Google Maps or Yelp business URL**: a Maps short link `https://maps.app.goo.gl/…` **or** a
  Yelp business page `https://www.yelp.com/biz/…`. This is the *only* accepted input — the API
  resolves the business from it and detects the source automatically. If the user gives a business
  name or address instead, ask them to paste the Maps share link (Maps app → Share → Copy link) or
  the Yelp `/biz/` URL; it cannot generate from a name alone.
- **Auth — depends on the path:**
  - *MCP path:* the MCP client/server handles auth (an OAuth browser sign-in on first connect, or a
    key configured on the server). You don't pass or ask for a key.
  - *Script path:* a **Brila API key** (an active subscription is required). Read `BRILA_API_KEY`
    from the env, or pass `--api-key`; the user can also paste it — it's shown in their Brila account
    settings. **When no key is configured, ASK the user for it.** Never invent, guess, or auto-fill a key from your own account, the environment, `git
    config`, chat context, or memory; use only what the user explicitly provides, and never hardcode
    a key into files.

The API base defaults to production `https://api.brila.ai`; override with `BRILA_API_BASE` only if asked.

## Before you launch — always send a heads-up (both paths)

Generation typically takes from tens of seconds up to a few minutes — that's normal. **Before you
start it, first send the user a short heads-up message with an emoji** (plain text, in the same
turn, *before* the tool/script call). For example:

> ⏳ Kicking off your Brila site — this usually takes ~30 seconds to a couple of minutes. Hang tight!

Never start generation silently. While it runs, give the user a short reassuring status update
about **once a minute** (not on every ~10s poll) — e.g. "🔄 Still generating, all good — ~90s in…".
Don't give up early; let it reach success or a terminal error.

## Path A — via MCP (preferred, when the tools are available)

Call **`generate_site`** with the Google Maps or Yelp URL. It returns a **`generation_id`** right
away (the build runs server-side). Then **poll `get_generation(generation_id)`** until `status` is
`ready` — it returns immediately (a short poll), so **space your checks out** (about once a minute is
plenty; the **MCP server** rate-limits to roughly one check per generation every ~45s and the
`get_generation` tool returns a `429` telling you how long to wait if you poll too soon),
**showing the user the returned `stage`** (e.g.
"🖼️ Collecting photos") between polls. On `ready`,
call **`get_site`** for the live URL + overview and **`export_site`** (format `md`) for the Markdown.
If a generation for this business is already running, `generate_site` resumes it — no duplicate paid
job. (`status`: `queue`/`processing` → keep polling, `ready` → done, `failed` → tell the user.)

Everything else is a matching tool — prefer these over curl when the MCP server is connected:
`list_sites` / `get_site` / `delete_site` / `export_site`; sections
`list_sections` / `get_section` / `update_section`; uploads
`upload_image` / `list_uploads` / `delete_upload`; domains
`add_domain` / `remove_domain` / `verify_domain` (or the one-step `connect_domain`);
`set_section_image` (upload + set on a section in one call); `analyze_reviews`; `account_info`;
`create_subscription_checkout` (start a subscription purchase — returns a payment link to give the user;
works without an active subscription, so use it when the user needs to subscribe).

MCP tool errors carry the API's `type` / `message` — translate them for the user (see "Handling
errors"); the meanings are the same as the script path.

## Path B — via the bundled script (fallback, when no MCP tools)

**Generate via the bundled script — never hand-roll generation with curl.** The script does the
whole async `create → poll → export` loop reliably in one process. Do NOT call `POST /v1/generations`
or poll `GET /v1/generations/{id}` yourself — run:

```bash
python3 scripts/brila_generate.py "<business_url>"
```

Call the interpreter as `python3`, falling back to `python` (or `py -3` on Windows) if `python3`
isn't on PATH. Requires `curl` and Python 3 (see the README for dependencies).

Useful flags: `--api-key <key>` (when not in `BRILA_API_KEY`), `--md-out <path.md>` (where to write
the Markdown; by default the **project root** — `$CLAUDE_PROJECT_DIR` if set, else the current
directory — as `<site_name>.md`), `--base <url>`, `--poll-interval <sec>` (default 10),
`--timeout <sec>` (default 600), `--resume <generation_id>` (poll + export an existing job instead of
creating a new one — see below).

The script prints **one JSON object per line** so you can follow progress:
- `{"event":"created","id":"…","status":"queue"}` — generation accepted (HTTP 202).
- `{"event":"poll","status":"queue"|"processing","elapsed_sec":N}` — still generating (repeats every ~10s).
- `{"event":"done", "published_url":"…", "markdown_path":"…", "site_name":"…", "name":"…"}` — success.
- `{"error":"…", …}` on failure (non-zero exit).

**Run it in the background** so a foreground command timeout can't cut off a long listing, and use
`elapsed_sec` for the ~once-a-minute update. When you see the `done` line, deliver the result.

**If a run is interrupted (timeout / killed) while a job is already `created`, DO NOT re-run the
generation** — that starts a *duplicate paid* job. Resume the existing one with the `id` from the
`created` line: `python3 scripts/brila_generate.py --resume <generation_id>` (poll + export only).
Same if a fresh create returns `409 GENERATION_IN_PROGRESS` — resume that job's id. (The MCP
`generate_site` tool auto-resumes an in-progress generation, so this caveat is script-only.)

## What to hand back to the user

Once generation succeeds, give the user, clearly:
1. **The live site link** — the published URL (e.g. `https://monte-verde.brila.ai`). Present it as a clickable URL.
2. **The Markdown** — show it inline (if short) or tell the user where it was saved and summarize the sections.

Keep it warm and concise: "Your site for **{name}** is live: {url} — and here's the content as Markdown."

Markdown is the default, but **mention the same site is also available as HTML** (or JSON) if they
want it — offer it briefly. Only fetch another format when the user asks (`export_site` over MCP, or
the "Other formats" section in [REFERENCE.md](REFERENCE.md)); don't dump HTML unprompted.

## Handling errors

Translate the API's error for the user rather than dumping raw JSON — an MCP tool error carries the
same `type` / `message` the script surfaces in its `{"error":...}` line. Common generation failures:

- `MISSING_CREDENTIALS` — no key on the script path: ask for their Brila API key (`BRILA_API_KEY` / `--api-key`).
- `403 SUBSCRIPTION_REQUIRED` — the API is a subscriber feature; an active Brila subscription is required.
- `403 SITE_LIMIT_REACHED` — all site slots on the plan are used for this period; free a slot or upgrade.
- `422 INSUFFICIENT_REVIEWS` — the business has too few reviews to generate a quality site.
- `422 BUSINESS_INFO_NOT_FOUND` — the Maps/Yelp link didn't resolve; check it points to a real listing.
- `409 GENERATION_IN_PROGRESS` — already generating; resume the returned `id` (script) — the MCP tool handles this itself.
- `NOT_READY` (`failed` / timeout) — failed server-side, or didn't finish in time; retry or resume the `id`.

The **full error table** (including editing/upload/domain errors) is in [REFERENCE.md](REFERENCE.md).

## Beyond generation

Listing sites, editing sections, uploading images, attaching a custom domain, deleting a site, and
exporting HTML/JSON are all in **[REFERENCE.md](REFERENCE.md)** — read it when the user asks. Each
has an MCP tool (preferred when connected) and a curl equivalent (the fallback); REFERENCE covers
both. (An embeddable reviews widget from a site is a separate skill, `brila-widget`.)

## Notes

- The skill only operates on the authenticated account's own data; each generated site belongs to that user.
- **Prefer the MCP tools when they're available** and fall back to the script/curl otherwise — this
  skill stays a thin layer on top either way.
