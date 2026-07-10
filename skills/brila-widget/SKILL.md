---
name: brila-widget
description: Build a self-contained, embeddable widget (most often a reviews widget) from a Brila-generated site's content, styled to match the store it will live on — Shopify, Webflow, WordPress, or any HTML block. Reads the real reviews already on a Brila site via the public API and bakes them into one inline HTML/CSS/JS snippet (no external calls, no API key) with schema.org JSON-LD structured reviews. Use when someone wants to embed/add reviews or testimonials to their store, asks for a "reviews widget" or "testimonials block", or wants to show their Brila site's reviews on Shopify/Webflow/WordPress. Needs an existing Brila site — ask for its live URL or id, or list the user's sites. Trigger even without the words "Brila" or "widget" when the intent is embedding a site's reviews somewhere else. Do NOT use it to generate or edit a Brila site (that's the brila-generate-site skill), or to build a widget from reviews you don't have on a Brila site.
---

# Brila — build an embeddable widget from a site

This skill turns the content of an already-generated **Brila site** into a **self-contained,
embeddable widget** — most commonly a **reviews widget** to drop into Shopify, Webflow, WordPress,
or any plain HTML block. It reads the site's real content via the Brila public API and bakes it
into one inline snippet, styled to look native to the store it will live on.

Generating or editing a Brila site is a **different** job — that's the `brila-generate-site` skill.
This skill assumes the site already exists.

## What you need before running

- **A Brila API key** (an active subscription is required). Read `BRILA_API_KEY` from the env, or
  pass it as the `Api-Key` header; the user can also paste it from their Brila account.

  **When no key is configured, ASK the user for it.** Never invent, guess, or auto-fill a key from
  your own account, the environment, `git config`, chat context, or memory; use only what the user
  explicitly provides. Never hardcode a key into files.
- **An existing Brila site** — you need its **site id**. If the user only gives the **live URL**
  (e.g. `https://monte-verde.brila.ai`), find the id by listing their sites and matching the URL:

  ```bash
  curl -s "$BRILA_API_BASE/api/public/v1/sites" -H "Api-Key: $BRILA_API_KEY"
  # → { "total": N, "sites": [ { "id": "...", "name": "...", "site_url": "https://…brila.ai" }, … ] }
  ```

  Match on `site_url` / `site_name` (paginate with `?page=`/`?per_page=` if needed), or just ask the
  user for the id. If they have no site yet, point them at `brila-generate-site` to make one first.

API base defaults to production `https://api.brila.ai`; override with `BRILA_API_BASE` only if asked.
All calls are plain request→response — use `curl` directly with `Api-Key: $BRILA_API_KEY`.

## How to build the widget

### 1. Get the reviews from the site

Reviews live in the **`advantages`** section. Fetch it directly and use the real review
text/authors from its `data` (look at the items) — **never invent reviews**:

```bash
curl -s "$BRILA_API_BASE/api/public/v1/sites/$SITE_ID/sections/advantages" -H "Api-Key: $BRILA_API_KEY"
```

For a different kind of widget, fetch the relevant section the same way
(`GET /v1/sites/{id}/sections` lists the available section names).

### 2. Ask for the destination store and look at it

Ask the user for the link to the Shopify store (or whatever site) the widget will be embedded in.
**Visually inspect it** — open/fetch the page and, if you can, take a screenshot — to read its
style: background and text colors, accent/brand color, fonts, button shape and border-radius,
card/section spacing, light vs dark. The goal is a widget that looks native to that store, not a
generic block.

### 3. Build a self-contained widget in the store's style

Produce **one** HTML snippet with **inline** CSS + vanilla JS — no external scripts, fonts, or
network calls, no build step. Match the palette, typography, and component styling you observed.
Prefix every CSS class uniquely (e.g. `.brila-reviews-…`) and keep styles scoped so it can't clash
with the theme. Make it responsive. Show the user a preview (and/or save a `.html` file) and iterate
if they want tweaks.

### 4. Embed schema.org structured reviews (JSON-LD)

In the same snippet, add a `<script type="application/ld+json">` block so the reviews are
machine-readable for search engines (rich results / SEO). Nest the reviews under the **item they're
about** — the business the site represents — not as standalone `Review` objects (search engines
require the reviewed item):

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

### 5. Hand it over for embedding

Give paste instructions for their platform — for **Shopify**: Online Store → Themes → **Customize**
→ add a **Custom Liquid** block (or Edit code → add a section) and paste the snippet. Explain it's
self-contained and carries the reviews from their Brila site.

## It's a static snapshot

You fetch the reviews here (server-side, with the API key) and **bake them into the snippet** as a
snapshot. The embedded widget makes **no API calls and carries no key**, so it's safe to paste on any
third-party site. To refresh the reviews later, **rebuild the widget**. (There is no Brila "widget"
API and no embed key — it's just self-contained HTML assembled from section data.)

## Handling errors

Direct curl calls return the API's error JSON — translate it for the user rather than dumping raw JSON:

- `MISSING_CREDENTIALS` / `401 INVALID_API_KEY` — no/bad key: ask for their Brila API key.
- `403 SUBSCRIPTION_REQUIRED` — the public API is a subscriber feature; an active subscription is required.
- `404 NOT_FOUND` — the site id (or section) doesn't exist — list sites (`GET /v1/sites`) to find the right id.
- `422 INVALID_SECTION` — the requested section name doesn't exist on this site; list them via `GET /v1/sites/{id}/sections`.
