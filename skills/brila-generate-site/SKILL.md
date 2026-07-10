---
name: brila-generate-site
description: Use this to build or change a website for a real local business — restaurants, cafes, taco spots, roasteries, salons, barbers, shops, clinics, and the like — via Brila. Trigger on any request to make, build, spin up, set up, or "turn this place into" a site or landing page, and treat a shared Google Maps link (maps.app.goo.gl/…) as a strong go signal even without the words "website" or "Brila." No link yet? Still trigger and ask for it. Also use to edit an existing Brila site's text or images (hero headline, about section, hours, gallery photo), list or delete sites, take one down, or connect a custom domain. Do NOT use for embeddable reviews/testimonials widgets (that's the brila-widget skill), hand-coding or deploying a site yourself, Markdown conversion, or scraping a Maps link.
---

# Brila — generate a site & return link + Markdown

This skill drives the **Brila public API** end-to-end: it starts a site generation
for a business, waits for it to finish, and returns the **live published URL** plus
the **site content as Markdown**. Generation is AI-driven and runs server-side; the
skill just orchestrates create → poll → export over plain HTTPS.

Generating a site is the **main flow** and lives below. Editing a site's sections,
uploading images, listing/deleting sites, attaching a custom domain, exporting other
formats, and the full error table live in **[REFERENCE.md](REFERENCE.md)** — read that
file when the user asks for one of those. (Building an embeddable reviews widget from a
site is a separate skill, `brila-widget`.)

## What you need before running

- **A Brila API key** (an active subscription is required). Read `BRILA_API_KEY` from
  the env, or pass `--api-key`; the user can also paste it from their Brila account /
  profile (`GET /api/frontend/v1/user` returns `api_key`). It's sent as the `Api-Key`
  header.

  **When no key is configured, ASK the user for it.** Never invent, guess, or auto-fill
  a key from your own account, the environment, `git config`, chat context, or memory;
  use only what the user explicitly provides. Never hardcode a key into files.
- **A Google Maps short link** to the business: `https://maps.app.goo.gl/…`. This is the
  *only* accepted input — the API resolves the business from it. If the user gives a
  business name or address instead, ask them to paste the Google Maps share link (Maps
  app → Share → Copy link); the API cannot generate from a name alone.

The API base defaults to production `https://api.brila.ai`. Override with the
`BRILA_API_BASE` env var only if asked.

## How to run it

**Always generate via the bundled script — never hand-roll generation with curl.**
Generation is an async `create → poll → export` loop, and the script does the whole thing
reliably in one process (polling until `ready`/`failed`, then exporting Markdown). Do NOT
call `POST /v1/generations` or poll `GET /v1/generations/{id}` yourself with curl — run:

```bash
python3 scripts/brila_generate.py "<google_maps_url>"
```

Call the interpreter as `python3`, falling back to `python` (or `py -3` on Windows) if
`python3` isn't on PATH. Requires `curl` and Python 3 (see the README for dependencies).

Useful flags: `--api-key <key>` (when not in `BRILA_API_KEY`), `--md-out <path.md>`
(where to write the Markdown; by default it's saved to the **project root** —
`$CLAUDE_PROJECT_DIR` if set, else the current directory — as `<site_name>.md`),
`--base <url>`, `--poll-interval <sec>` (default 10), `--timeout <sec>` (default 600),
`--resume <generation_id>` (poll + export an existing job instead of creating a new one —
see below).

The script prints **one JSON object per line** so you can follow progress:
- `{"event":"created","id":"…","status":"queue"}` — generation accepted (HTTP 202).
- `{"event":"poll","status":"queue"|"processing","elapsed_sec":N}` — still generating (repeats every ~10s).
- `{"event":"done", "published_url":"…", "markdown_path":"…", "site_name":"…", "name":"…"}` — success.
- `{"error":"…", …}` on failure (non-zero exit).

**Keep the user posted.** Generation typically takes from tens of seconds up to a few
minutes — that's normal. Don't kill it early; let it reach `done` or a terminal error.

1. **REQUIRED — before you launch the script, first send the user a short heads-up message
   with an emoji** (as plain text, in the same turn, *before* the tool call). For example:
   > ⏳ Kicking off your Brila site — this usually takes ~30 seconds to a couple of minutes. Hang tight!

   Never run the generation silently; always send this line first.
2. Then run the script. Some listings take several minutes — **run it in the background** so
   a foreground command timeout can't cut it off — and, when you can read its streaming
   output, give a short reassuring update about **once a minute** (not every 10s poll line)
   using `elapsed_sec` — e.g. "🔄 Still generating, all good — ~90s in…".
3. When you see the `done` line, deliver the result (see "What to hand back").

**If a run is interrupted (timeout / killed) while a job is already `created`, DO NOT re-run
the generation** — that starts a *duplicate paid* job. Resume the existing one instead, using
the `id` from the `created` line: `python3 scripts/brila_generate.py --resume <generation_id>`
(poll + export only, no new job). Same if a fresh create returns `409 GENERATION_IN_PROGRESS` —
resume that job's id.

## What to hand back to the user

On the final `done` line, give the user, clearly:
1. **The live site link** — `published_url` (e.g. `https://monte-verde.brila.ai`). Present it as a clickable URL.
2. **The Markdown** — read the file at `markdown_path` and either show it inline (if short) or tell the user where it was saved and summarize the sections.

Keep it warm and concise: "Your site for **{name}** is live: {published_url} — and here's the content as Markdown ({markdown_path})."

Markdown is the default, but **mention that the same site is also available as HTML** (or
JSON) if they want it — offer it briefly, e.g. "want the full page as HTML? I can grab that
too." Only fetch another format when the user asks (see the "Other formats" section in
[REFERENCE.md](REFERENCE.md)); don't dump HTML unprompted.

## Handling errors

The script surfaces the API's error in the `{"error":...}` line — translate it for the user
rather than dumping raw JSON. The common generation failures:

- `MISSING_CREDENTIALS` — no key set: ask for their Brila API key (`BRILA_API_KEY` / `--api-key`).
- `403 SUBSCRIPTION_REQUIRED` — the public API is a subscriber feature; an active Brila subscription is required.
- `403 SITE_LIMIT_REACHED` — all site slots on the plan are used for this period; free a slot or upgrade.
- `422 INSUFFICIENT_REVIEWS` — the business has too few Google reviews to generate a quality site.
- `422 BUSINESS_INFO_NOT_FOUND` — the Maps link didn't resolve; check it points to a real listing.
- `409 GENERATION_IN_PROGRESS` — already generating; resume the returned `id` instead of re-creating.
- `NOT_READY` (`failed` / timeout) — failed server-side, or didn't finish within `--timeout`; retry or resume the `id`.

The **full error table** (including editing/upload/domain errors) is in [REFERENCE.md](REFERENCE.md).

## Beyond generation

Listing your sites, editing sections, uploading images, attaching a custom domain, deleting a
site, and exporting HTML/JSON are all covered in **[REFERENCE.md](REFERENCE.md)** — read it when
the user asks for one of those. Those calls are plain request→response and go **directly through
curl** (auth: `Api-Key: $BRILA_API_KEY`); only generation uses the script. (Building an embeddable
reviews widget from a site is a separate skill, `brila-widget`.)

## Notes

- The skill only operates on the authenticated account's own data; each generated site belongs to that user.
- **All API access is centralized** — generation in `scripts/brila_generate.py`, everything else as the
  curl snippets in [REFERENCE.md](REFERENCE.md). Keep it that way: it's the seam where a future Brila MCP
  server would replace these calls with MCP tools, leaving this skill a thin procedure layer on top.
