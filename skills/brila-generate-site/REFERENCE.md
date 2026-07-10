# Brila skill — reference

Everything beyond the main generation flow. Read this file when the user wants to edit a
site, upload an image, list or delete sites, attach a custom domain, export another format,
or when you need to translate a less-common API error. (Building an embeddable reviews
widget from a site is a separate skill, `brila-widget`.)

**All calls here are plain request→response — use `curl` directly (no script).** Auth is the
`Api-Key: $BRILA_API_KEY` header; base URL `$BRILA_API_BASE` (default `https://api.brila.ai`).

**The full contract is the source of truth — fetch it when you need an endpoint, param, or
field not spelled out here:**

```bash
curl -s "$BRILA_API_BASE/api/public/v1/swagger_doc"   # public — no API key needed
```

That's the complete OpenAPI 2.0 spec (machine-readable JSON; human-readable docs live at
[developers.brila.ai](https://developers.brila.ai)). Read the spec for anything not below.

## Account & creation budget

Before generating you can check the plan's remaining slots:

```bash
curl -s "$BRILA_API_BASE/api/public/v1/user/info" -H "Api-Key: $BRILA_API_KEY"
# → { "user": { "id": "...", "email": "..." },
#     "subscription": { "max_sites": 3, "sites_used": 2, "resets_at": <epoch ms> } }
```

`sites_used < max_sites` means a new generation will be accepted (otherwise it's `403 SITE_LIMIT_REACHED`).

## Finding & managing your sites

When the user refers to "my site" without giving an id or live URL, **list their sites and match by
name** rather than guessing — you need the `id` for editing, widgets, custom domains, or export:

```bash
curl -s "$BRILA_API_BASE/api/public/v1/sites" -H "Api-Key: $BRILA_API_KEY"
# → { "total": 2, "sites": [ { "id": "...", "name": "Monte Verde",
#     "site_url": "https://monte-verde.brila.ai", "rating": 4.8, "reviews_count": 1420,
#     "city": "...", "country": "...",
#     "domain": { "name": "monteverde.com", "status": "active" } | null }, ... ] }
```

Paginate with `?page=` (default 1) and `?per_page=` (default 10, max 100) when the list is long.
Fetch a single site with `GET /v1/sites/{id}` (same object shape). The `domain` field shows the
attached custom domain and its `pending`/`active` status, or `null` if none is attached.

### Deleting a site

`DELETE /v1/sites/{id}` takes the site offline:

```bash
curl -s -X DELETE "$BRILA_API_BASE/api/public/v1/sites/$SITE_ID" -H "Api-Key: $BRILA_API_KEY"  # → 204
```

**Warn the user before deleting.** A site deleted **within the current billing period still counts
toward the creation limit** (`sites_used`) until it resets (`resets_at` from `/v1/user/info`) —
deleting does not free a slot right away. Deletion is irreversible, so confirm the intent (and which
site) before calling it.

## Editing a generated site's sections

When the user wants to change the wording/content of a site Brila already made (e.g. "change the
hero headline", "edit the about text"), call the section endpoints directly. You need the **site id** —
it's the `id` from the earlier generation `done` line; if you don't have it, ask the user for the live
URL (a site's id is stable across edits).

The flow is **read → edit → PUT**:

```bash
# section names
curl -s "$BRILA_API_BASE/api/public/v1/sites/$SITE_ID/sections" -H "Api-Key: $BRILA_API_KEY"

# read one section: current data + a read-only $schema telling you exactly what's editable
curl -s "$BRILA_API_BASE/api/public/v1/sites/$SITE_ID/sections/$NAME" -H "Api-Key: $BRILA_API_KEY"

# update: send ONLY the editable fields, under `data`
curl -s -X PUT "$BRILA_API_BASE/api/public/v1/sites/$SITE_ID/sections/$NAME" \
  -H "Api-Key: $BRILA_API_KEY" -H "Content-Type: application/json" \
  -d '{"data": {"headline": "New headline"}}'
```

Rules:
- **Always read the section first.** The response's read-only `data.$schema` tells you exactly which
  fields you may change (names, types, `required`, sizes). Only edit fields the schema allows.
- **Send just the editable fields** under `data`. Do **not** send `$schema` or `_meta` back — the
  server ignores them and validates your `data` against the stored schema.
- **Image fields must be a Brila-hosted URL.** Upload the image first (see below) and use the returned
  `asset.url`; external image URLs are rejected (`422 SITE_SECTION_INVALID_URL`). Keep an existing image
  by leaving its current URL unchanged.
- `"disabled": true|false` (top-level, next to `data`) hides/shows a whole section.
- After a successful PUT the site **re-renders in the background** — tell the user the live URL will
  reflect the change shortly; re-read the section or re-export to confirm.

Errors are the API's JSON, read it directly: `422 SITE_SECTION_INVALID_DATA` carries a `fields` array
(which field broke which rule) — fix the data and retry; `403 SECTION_READ_ONLY` means that section
can't be edited.

## Uploading an image

Images placed into section fields must be hosted on Brila's CDN. Upload one (`multipart/form-data`,
a single `file`) and use the returned `asset.url`:

```bash
curl -s -X POST "$BRILA_API_BASE/api/public/v1/uploads" \
  -H "Api-Key: $BRILA_API_KEY" \
  -F "file=@/path/to/image.jpg"
# → { "id": "...", "asset": { "url": "https://cdn…/…jpg", "width": 1920, "height": 1080 },
#     "created_at": <epoch ms> }
```

Put `asset.url` into the section's image field in a `PUT` (above). `GET /v1/uploads` lists your uploads
and `DELETE /v1/uploads/{id}` removes one. Allowed types: png, jpeg, webp, svg.

## Other formats (HTML / JSON)

Markdown is the default hand-back, but the same finished site can be exported as **HTML** or **JSON** —
proactively let the user know this is available, and fetch it (directly with curl, no script) when they
ask. Use the site `id` from the generation `done` line:

```bash
# full published page as HTML
curl -s "$BRILA_API_BASE/api/public/v1/sites/$SITE_ID/export?format=html" -H "Api-Key: $BRILA_API_KEY" -o site.html
# structured content as JSON
curl -s "$BRILA_API_BASE/api/public/v1/sites/$SITE_ID/export?format=json" -H "Api-Key: $BRILA_API_KEY"
```

Only pull HTML/JSON when the user wants it — don't dump it unprompted.

## Custom domain

Attach a **custom domain** to a published site — a subscriber feature, **one domain per site**. The
API deliberately returns **no DNS records**: the user points the domain's **CNAME** at their Brila
site in their own DNS provider, out of band. You need the site `id` (list sites if you don't have it).

```bash
# attach a domain — starts in `pending`
curl -s -X POST "$BRILA_API_BASE/api/public/v1/sites/$SITE_ID/domain" \
  -H "Api-Key: $BRILA_API_KEY" -H "Content-Type: application/json" \
  -d '{"domain": "www.example.com"}'
# → 201 { "name": "www.example.com", "status": "pending" }

# re-check the status now (verification also runs automatically in the background)
curl -s -X POST "$BRILA_API_BASE/api/public/v1/sites/$SITE_ID/domain/verify" -H "Api-Key: $BRILA_API_KEY"
# → 200 { "name": "www.example.com", "status": "pending" | "active" }

# remove the domain
curl -s -X DELETE "$BRILA_API_BASE/api/public/v1/sites/$SITE_ID/domain" -H "Api-Key: $BRILA_API_KEY"  # → 204
```

Walk the user through it:
1. **Attach** the domain — it comes back `pending`.
2. Tell them to add a **CNAME** for that domain pointing at their Brila site, in their DNS provider.
   (The API returns no records — the target is the site's Brila hostname / live URL.)
3. Verification runs **automatically in the background**, so `status` on `GET /v1/sites/{id}` moves
   `pending` → `active` on its own once the CNAME resolves — no need to poll aggressively. Use
   `POST .../domain/verify` only to trigger an immediate re-check right after they set the CNAME.

**Attach and remove share one rate limit** (a few requests per window per IP) — exceeding it returns
`429 TOO_MANY_REQUESTS`; `verify` is not throttled. The current domain and its status also appear in
the `domain` field of the site object (`GET /v1/sites/{id}`).

## Full error table

The generation script surfaces the API's error in the `{"error":...}` line; direct curl calls return
the API's JSON. Translate it for the user rather than dumping raw JSON.

| error / HTTP | Meaning | What to tell the user |
|---|---|---|
| `401 INVALID_API_KEY` | Bad/expired key | The API key is invalid — check it. |
| `403 SUBSCRIPTION_REQUIRED` | No active subscription | The public API is a subscriber feature — an active Brila subscription is required. |
| `403 SITE_LIMIT_REACHED` | Plan site limit reached | You've used all site slots on your plan for this period (`details.max_sites`); free a slot or upgrade. |
| `403 SECTION_READ_ONLY` | Section can't be edited | That section is read-only. |
| `403 FORBIDDEN` | Not the owner, or the site is locked | This site can't be changed right now — it isn't yours, or it's locked. |
| `404 NOT_FOUND` | Site / section / resource doesn't exist | Double-check the id — list sites (`GET /v1/sites`) to find the right one. |
| `404 HTML_NOT_AVAILABLE` | HTML export isn't ready for this site | The HTML isn't available yet; try JSON/Markdown, or re-export shortly. |
| `409 GENERATION_IN_PROGRESS` | Already generating this business | A generation for this business is already running; resume it instead of re-creating (its `details.site_id` names the site, when it's yours). |
| `422 INSUFFICIENT_REVIEWS` | Business has too few Google reviews | This business doesn't have enough reviews yet to generate a quality site. |
| `422 BUSINESS_INFO_NOT_FOUND` | Maps link didn't resolve | Double-check the Google Maps link points to a real business listing. |
| `422 SITE_SECTION_INVALID_DATA` | Edit failed schema validation | Read the `fields` array (which field broke which rule), fix the data, and retry. |
| `422 SITE_SECTION_INVALID_URL` | Image field not a Brila URL | Upload the image first and use the returned `asset.url`. |
| `422 INVALID_FORMAT` | Bad export `format` | Use `format=html`, `json`, or `md`. |
| `422 INVALID_SECTION` | Unknown section name in `sections` | A requested section name doesn't exist — list them via `GET /v1/sites/{id}/sections`. |
| `422 INVALID_PARAMS` | Invalid request body / params | Read the `fields` array (which field broke which rule), fix it, and retry. |
| `429 TOO_MANY_REQUESTS` | Rate limited | Too many requests in a short window — wait a moment and retry. |
| `503 SERVICE_UNAVAILABLE` | Generation service down | Brila's generation service is temporarily unavailable; try again shortly. |

**Client-side states** — surfaced by the generation script, not HTTP responses from the API:

- `MISSING_CREDENTIALS` — no key in env/flags: ask for their Brila API key (`BRILA_API_KEY` / `--api-key`).
- `NOT_READY` (`failed`) — generation failed server-side: try again, or try a different listing.
- `NOT_READY` (timeout) — didn't finish within `--timeout`: resume polling on the same `id`, or raise `--timeout`.
