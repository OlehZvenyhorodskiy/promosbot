# GitHub workflow

`OlehZvenyhorodskiy/promosbot` is the source of truth for the bot. Production runs from Google Cloud Run in `europe-west1`; local development and pull requests must keep the bot runnable without production credentials.

## Repository rules

- `main` is the deployable branch.
- Use short branches such as `feature/source-adapter-colruyt` or `fix/alert-batching`.
- Run the test suite before every commit: `python -m pytest -q`.
- Keep credentials out of Git. `.env` is ignored; use `.env.example` as the documented shape.
- Store production secrets in Google Secret Manager or Cloud Run secret references. Never paste a Telegram token into README files, deployment commands, issues, or logs.
- Do not commit the local SQLite database, browser cache, screenshots containing credentials, or generated exports.

## Change flow

1. Create a feature branch from `main`.
2. Make the smallest reviewable change and add or update tests.
3. Verify `git diff --check`, `python -m pytest -q`, and a local `/health` smoke check.
4. Open a pull request describing the source, parsing assumptions, deduplication behavior, and rollback plan.
5. Merge to `main` only after the scraper fixtures and production-risk notes are reviewed.

## Deployment notes

The current deployment is a single Cloud Run instance in Belgium (`europe-west1`) because Telegram long polling must not run in multiple active replicas. Browser-based scrapers use Playwright/Chromium and therefore need more memory than a plain HTTP bot. Keep the production settings documented in `DEPLOYMENT.md`, but inject `BOT_TOKEN` through a secret rather than a plain environment-variable value.

Cloud Run's local filesystem is ephemeral. SQLite is suitable for local development and a single-instance prototype, but a durable production deployment should eventually move promo/user state to a managed datastore or attach a deliberate backup/export strategy.

