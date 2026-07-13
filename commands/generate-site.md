---
description: Generate a published Brila website for a local business from its Google Maps or Yelp listing; returns the live URL + content as Markdown.
argument-hint: "[google maps or yelp url]"
---

The user wants to generate a Brila website. Use the **brila-generate-site** skill.

Business listing URL — Google Maps (`https://maps.app.goo.gl/…`) or Yelp (`https://www.yelp.com/biz/…`);
may be empty — if so, ask the user for one (it generates only from a Maps/Yelp URL, not a
name/address): $ARGUMENTS

**Before launching anything, first send the user a short heads-up with an emoji** (plain text, before
the tool call), e.g. "⏳ Kicking off your Brila site — usually ~30s to a couple of minutes. Hang tight!"
Never generate silently.

Then **always run generation via the bundled script** — `python3 scripts/brila_generate.py "<business_url>"`
(fall back to `python`, or `py -3` on Windows, if `python3` isn't on PATH) — never hand-roll
create/poll/export with curl. It reads `BRILA_API_KEY`; if there's no key, ask the user for their Brila
API key — don't guess or auto-fill one. Let it poll create → ready → export to completion, then hand
back the **live published URL** and the **site content as Markdown**.

Markdown is the default — also mention the site is available as **HTML** (or JSON) if they want it.
