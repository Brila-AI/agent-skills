---
description: Build an embeddable reviews widget from a generated Brila site, styled to match the store it will live on.
argument-hint: "[site id or live URL]"
---

The user wants an embeddable widget (most often a **reviews widget** for Shopify/Webflow/WordPress)
built from a Brila site. Use the **brila-generate-site** skill's widget flow.

Site — id or live URL (may be empty — if so, ask which generated site): $ARGUMENTS

Steps:
1. Fetch the site's reviews directly:
   `curl -s "$BRILA_API_BASE/api/public/v1/sites/<site_id>/sections/advantages" -H "Api-Key: $BRILA_API_KEY"`
   and use the real review text/authors from its `data` (never invent reviews).
2. Ask for the destination store URL and **visually inspect it** (open/screenshot) to read its palette,
   fonts, and component style.
3. Produce **one self-contained** HTML snippet (inline CSS + vanilla JS, no external calls, uniquely
   prefixed classes) that matches that store's look and bakes the reviews in as a static snapshot.
4. **Embed schema.org structured reviews** — a static `<script type="application/ld+json">` nesting the
   reviews under the business (`LocalBusiness`/`Review`, with `reviewRating`/`aggregateRating` **only if
   the source has real ratings**). Add it **only when the destination store is the same business** as the
   Brila site; skip it on unrelated third-party sites. Match the visible reviews; never invent data. See
   the widget section in `REFERENCE.md` for the exact shape and rules.
5. Give paste instructions for the platform (Shopify: Customize → Custom Liquid). The snippet carries
   no API key and makes no calls — safe to embed anywhere; rebuild to refresh the reviews.
