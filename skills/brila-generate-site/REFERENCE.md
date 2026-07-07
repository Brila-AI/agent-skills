# Brila skill — reference

Everything beyond the main generation flow. Read this file when the user wants to edit a
site, upload an image, build a widget, export another format, or when you need to translate
a less-common API error.

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

## Building an embeddable widget (e.g. a reviews widget for Shopify)

When the user wants an embeddable widget from a generated site — most commonly a **reviews widget**
to drop into Shopify, Webflow, WordPress, or a plain HTML block — build it from the site's own content
via the API (don't invent reviews) and **make it match the look of the store it will live on**.

1. **Get the reviews.** Reviews live in the **`advantages`** section. Fetch it directly:
   `curl -s "$BRILA_API_BASE/api/public/v1/sites/$SITE_ID/sections/advantages" -H "Api-Key: $BRILA_API_KEY"`
   and use the real review text/authors from its `data` (look at the items). For other widgets, fetch
   the relevant section the same way.
2. **Ask for the destination store URL and look at it.** Ask the user for the link to the Shopify store
   (or whatever site) the widget will be embedded in. **Visually inspect it** — open/fetch the page and,
   if you can, take a screenshot — to read its style: background and text colors, accent/brand color,
   fonts, button shape and border-radius, card/section spacing, light vs dark. The goal is a widget that
   looks native to that store, not a generic block.
3. **Build a self-contained widget in the store's style.** Produce **one** HTML snippet with **inline**
   CSS + vanilla JS — no external scripts, fonts, or network calls, no build step. Match the palette,
   typography, and component styling you observed. Prefix every CSS class uniquely (e.g.
   `.brila-reviews-…`) and keep styles scoped so it can't clash with the theme. Make it responsive.
   Show the user a preview (and/or save a `.html` file) and iterate if they want tweaks.
4. **Embed schema.org structured reviews (JSON-LD).** In the same snippet, add a
   `<script type="application/ld+json">` block so the reviews are machine-readable for search engines
   (rich results / SEO). Nest the reviews under the **item they're about** — the business the site
   represents — not as standalone `Review` objects (search engines require the reviewed item):

   ```html
   <script type="application/ld+json">
   {
     "@context": "https://schema.org",
     "@type": "LocalBusiness",
     "name": "<business name from the site>",
     "review": [
       {
         "@type": "Review",
         "author": { "@type": "Person", "name": "<author>" },
         "reviewBody": "<review text>",
         "reviewRating": { "@type": "Rating", "ratingValue": <n>, "bestRating": 5 }
       }
     ],
     "aggregateRating": { "@type": "AggregateRating", "ratingValue": <avg>, "reviewCount": <count> }
   }
   </script>
   ```

   Rules:
   - **Only when the store is the same business.** Add this markup **only if the destination site is the
     same business as the Brila site** (its own reviews on its own page). If the widget is going on a
     different or unrelated site, **skip the JSON-LD** — business-level review markup about someone else's
     reviews on a third-party page is misleading and can be flagged as spam. When in doubt, ask the user.
   - **Only real data.** Use the same reviews you baked into the visible widget — the JSON-LD **must
     match what's shown** (search engines penalize markup that doesn't reflect visible content). Never
     invent reviews, authors, or ratings.
   - **Ratings only if present.** Include `reviewRating` per review and the top-level `aggregateRating`
     **only when the source data actually has numeric ratings.** If the reviews have no rating, omit
     both (a `Review`/`reviewBody` without a rating is still valid) — do not fabricate stars.
   - **Pick an accurate `@type`.** Use the business's real category if you can tell (e.g. `Restaurant`,
     `CafeOrCoffeeShop`, `HairSalon`); otherwise `LocalBusiness` is a safe default. Add `name` (and,
     if known, `url`/`address`) so the item is identifiable.
   - Note: for a business's own testimonials on its own page, Google may not render star rich results
     (self-serving-review policy), but the structured data is still valid and worth including.
5. **Hand it over for embedding.** Give paste instructions for their platform — for **Shopify**: Online
   Store → Themes → **Customize** → add a **Custom Liquid** block (or Edit code → add a section) and
   paste the snippet. Explain it's self-contained and pulls the reviews already on their Brila site.

The widget is **static**: you fetch the reviews here (server-side, with the API key) and **bake them
into the snippet** as a snapshot. The embedded widget makes **no API calls and carries no key**, so
it's safe to paste on any third-party site. To refresh the reviews later, rebuild the widget. (There
is no Brila "widget" API and no embed key — it's just self-contained HTML assembled from section data.)

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

## Full error table

The generation script surfaces the API's error in the `{"error":...}` line; direct curl calls return
the API's JSON. Translate it for the user rather than dumping raw JSON.

| error / HTTP | Meaning | What to tell the user |
|---|---|---|
| `MISSING_CREDENTIALS` | No key in env/flags | Ask for their Brila API key (`BRILA_API_KEY` / `--api-key`). |
| `401 INVALID_API_KEY` | Bad/expired key | The API key is invalid — check it. |
| `403 SUBSCRIPTION_REQUIRED` | No active subscription | The public API is a subscriber feature — an active Brila subscription is required. |
| `403 SITE_LIMIT_REACHED` | Plan site limit reached | You've used all site slots on your plan for this period (`details.max_sites`); free a slot or upgrade. |
| `422 INSUFFICIENT_REVIEWS` | Business has too few Google reviews | This business doesn't have enough reviews yet to generate a quality site. |
| `422 BUSINESS_INFO_NOT_FOUND` | Maps link didn't resolve | Double-check the Google Maps link points to a real business listing. |
| `409 GENERATION_IN_PROGRESS` | Already generating this business | A generation for this business is already running; resume the returned `id` instead of re-creating. |
| `429 TOO_MANY_REQUESTS` | Rate limited | Too many requests in a short window — wait a moment and retry. |
| `503 SERVICE_UNAVAILABLE` | Generation service down | Brila's generation service is temporarily unavailable; try again shortly. |
| `NOT_READY` status `failed` | Generation failed server-side | Generation failed for this business; try again or try a different listing. |
| `NOT_READY` (timeout) | Didn't finish within `--timeout` | Still generating — resume polling on the same `id`, or raise `--timeout`. |
| `422 SITE_SECTION_INVALID_DATA` | Edit failed schema validation | Read the `fields` array (which field broke which rule), fix the data, and retry. |
| `422 SITE_SECTION_INVALID_URL` | Image field not a Brila URL | Upload the image first and use the returned `asset.url`. |
| `403 SECTION_READ_ONLY` | Section can't be edited | That section is read-only. |
