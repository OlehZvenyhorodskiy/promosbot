# Master prompt: deep audit and design of the Belgian promotions scraper

Copy the prompt below into a capable coding/research AI after giving it access to this repository. The task is analysis first: do not modify the code until the report has been reviewed.

```text
You are the lead data-platform and web-scraping architect reviewing the repository for Belgium Promo's Telegram Bot. Produce an evidence-based technical audit and an implementation blueprint for a reliable, legally respectful, production-grade Belgian supermarket promotions ingestion system.

Context:
- The bot serves Belgium and supports multiple languages, Telegram menus, filters, favorites, notifications, and promotion browsing.
- The target retailers currently include Colruyt, Carrefour, Delhaize, Aldi, Lidl, Albert Heijn, Jumbo, Spar, Cora, and Intermarché.
- The application runs in Google Cloud Run in europe-west1, uses Telegram long polling, SQLite today, and has both HTTP parsers and a Playwright/Chromium fallback.
- The desired result is broad coverage of official promotion pages, weekly brochures/folders, retailer campaign pages, retailer APIs or embedded JSON, newsletters, and other publicly available official sources where permitted.
- Some sources may use store selection, locale/session state, lazy loading, SSR/CSR frameworks, anti-bot pages, CAPTCHA, Cloudflare, robots restrictions, or inaccessible endpoints. Never recommend bypassing authentication, CAPTCHA, access controls, or terms of service. If a source cannot be collected responsibly, mark it as a limitation and propose an official alternative or manual ingestion path.

First, read the entire repository. Do not trust README claims without verifying the code, tests, deployment files, schemas, and runtime behavior. Do not invent live results. If internet access is available, verify each proposed source against the official retailer domain and record the retrieval date; otherwise clearly label live facts as unverified.

Deliver one report in Ukrainian, keeping code identifiers and URLs in their original form. Include these sections:

1. Executive summary
   - What works today, what is missing, and the three highest-impact risks.
   - Separate observed evidence, reasonable inference, and unknowns.

2. Repository and runtime audit
   - Map bot handlers, scheduler, scraper engine, source adapters, parser/normalizer, repository/database, alert deduplication, language settings, and deployment entry points.
   - Trace one promotion from discovery to persistence, filtering, alert batching, and Telegram rendering.
   - Identify blocking I/O, cold-start or browser costs, polling concurrency hazards, retry behavior, and data-loss risks.

3. Retailer source inventory
   For every current retailer and every additional high-value Belgian retailer you recommend, create a source matrix with:
   - official domain and exact page/API/feed URL;
   - source type: HTML, embedded JSON, JSON-LD, REST/GraphQL, brochure PDF, image flyer, newsletter, or browser-rendered UI;
   - locale and store-selection requirements;
   - pagination/lazy-loading behavior;
   - product, regular price, promotional price, unit price, loyalty price, bundle/multibuy, validity dates, images, terms, and availability fields;
   - stable identifiers and the proposed extraction key;
   - rate-limit, robots, terms, anti-bot, and legal/compliance considerations;
   - expected reliability, freshness, implementation effort, and a fallback source.
   Include a separate list of sources that must not be scraped automatically because they require login, CAPTCHA solving, access-control bypass, or violate stated restrictions.

4. Coverage and correctness design
   Design a canonical promotion schema that preserves:
   - retailer, branch/store scope, product name, brand, category, package size, quantity;
   - regular price, promotional price, unit price, currency, discount percentage, and explicit price semantics;
   - loyalty/member-only conditions, multibuy rules, minimum quantity, validity interval, publication timestamp, and source URL;
   - image/brochure evidence and parser/source version.
   Explain how to avoid false promotions, empty cards, navigation placeholders, stale deals, duplicate items, misleading “from” prices, and the common error of treating a unit price as the item price. If the original price is unavailable, preserve that fact instead of fabricating it.

5. Recommended architecture
   Propose a source-adapter system with:
   - fast HTTP/API/embedded-state collection first;
   - Playwright only for sources that genuinely require rendering or session/store selection;
   - brochure/PDF/image processing only where the official source and usage permit it;
   - per-source configuration, schema version, parser version, health status, timeout, backoff, cache/ETag support, and rate limits;
   - a shared browser pool with bounded concurrency and resource blocking;
   - deterministic normalization, stable IDs, snapshots, validation, and replayable fixtures;
   - separate discovery, parsing, validation, persistence, and alerting stages.
   Explain what should stay in-process and what should move to a queue/worker or managed datastore as volume grows. Account for Cloud Run's ephemeral filesystem and the fact that Telegram long polling should have exactly one active consumer.

6. Freshness, baseline, and notification behavior
   Define how the system distinguishes a newly discovered promotion from an old item after restart, scraper outage, or parser change. Design bounded 10-minute digest batches grouped by retailer, with per-user notification preferences, quiet/silent mode, retry safety, and a manual “new promotions” view. Include a strategy for source outages so users are not spammed with the same stale items.

7. Testing and observability
   Specify unit tests, golden HTML/JSON/PDF fixtures, browser smoke tests, contract tests per retailer, price-semantic tests, deduplication tests, restart/baseline tests, and alert batching tests. Define metrics and structured logs for source success, item counts, new/updated/expired items, parse errors, challenge pages, latency, memory, browser crashes, and Telegram delivery failures. Include thresholds for alerts and a health endpoint that reports degraded sources without claiming the whole system is healthy.

8. Cloud and cost plan
   Compare the current Cloud Run shape with a scheduled worker, Cloud Run Jobs, Compute Engine, or another suitable Google Cloud design. Estimate the main cost drivers qualitatively: browser minutes, memory, network, persistent storage, and frequency. Recommend a Belgium or nearby region only when it materially helps; do not assume region alone fixes scraper latency. Explain secret handling and deployment rollback.

9. Prioritized roadmap
   Give a phased plan:
   - Phase 0: correctness and security fixes;
   - Phase 1: stabilize existing official sources;
   - Phase 2: add the highest-value retailers and brochure sources;
   - Phase 3: durable storage, observability, and operational hardening.
   For every phase list exact files/modules, acceptance criteria, dependencies, risks, and a rough effort (S/M/L). Rank work by user value multiplied by reliability, not by the number of stores claimed.

10. Final recommendation
   State the smallest safe next implementation slice, the sources that should be deferred, and the evidence needed before calling the scraper “complete”.

Rules:
- Do not modify files, deploy, send Telegram messages, or create accounts during this audit.
- Do not expose secrets found in the repository; report only the file and remediation.
- Do not recommend CAPTCHA bypass, stealth evasion, credential sharing, or scraping behind access controls.
- Cite exact repository file paths and line numbers whenever possible.
- Prefer official retailer sources and documented feeds over brittle UI automation.
- If a source returns a challenge or no usable product data, report that as a verified limitation and do not fill the gap with seed/fake data without labeling it.
``` 

