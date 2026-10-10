# Scheme Sniper

Helps citizens (including low-literacy users) find Indian government welfare
schemes they may qualify for, see which documents they have or lack, and
know exactly where to go next.

## What this is NOT

This project does **not** submit applications to any real government
system (PM-Kisan, NSAP, UMANG, etc.). Those portals require official
integration agreements, Aadhaar e-KYC biometric authority, and
government-issued API credentials that a project like this cannot
legitimately obtain. The "online submission" feature (`app/submission.py`)
is a clearly labeled **simulation** for demo purposes only: it generates a
local, prefixed (`SIM-...`) reference number and a local status record.
Nothing is ever transmitted to an external government system.

Eligibility is **never** decided by an LLM. `app/rules_engine.py` is
deterministic code that reads admin-approved rule JSON
(`schema/rule.schema.json`) and a citizen's known fields, and computes one
of four outcomes: `likely_qualifies`, `maybe_confirm_at_office`,
`likely_not_eligible`, `cant_tell`. The app never says "You qualify".

## Stack

Python 3.11, FastAPI, SQLAlchemy (SQLite locally, Postgres via
`DATABASE_URL` in production), plain HTML/CSS/JS served by FastAPI, JSON
i18n files, pytest, Docker.

## Project layout

```
app/                FastAPI app, models, rules engine, routers
  routers/           auth, consent, documents, questions, results, schemes,
                      admin, csc, submission, daily_job
  i18n/               en.json, hi.json (fully written); other languages fall
                      back to English with a "preview" flag
data/
  raw/                operator-provided official source text (seed data)
  schemes/            scheme + rule JSON built ONLY from data/raw
  offices.json        hand-curated office list
  languages.json      22 Eighth Schedule languages + English
schema/               JSON Schemas for rules and schemes
static/               citizen/admin/CSC HTML/CSS/JS pages
tests/                pytest suite (rules engine, validator, PII scrubber)
.github/workflows/    daily.yml - daily source-refresh trigger
```

## Local setup

1. Install Python 3.11 and create a virtual environment.
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in values (OTP stays in
   `test` mode by default; vision/LLM keys are optional - features
   degrade gracefully without them).
4. Seed the three demo schemes (PM-Kisan, PM Ujjwala, NSAP pension) from
   `data/raw/` and `data/schemes/`:
   ```
   python -m app.seed
   ```
5. Run the server:
   ```
   uvicorn app.main:app --reload
   ```
6. Open http://127.0.0.1:8000/ for the citizen flow, `/admin.html` for the
   admin dashboard, `/csc.html` for the CSC operator view.

## Tests

```
pytest -v
```

Covers: rules engine boundary cases and a property-based test proving
`likely_qualifies` never occurs when a rule has an ambiguous condition;
rule schema + source-quote validator; and the document PII scrubber
(Aadhaar/PAN/voter ID/passport/bank account/phone/VID rejection).

## Hard rules enforced in code

- Phone numbers live in a separate table (`PhoneNumber`) from profile data
  (`Person`); citizen data is session-only unless the user opts in to save.
  A delete-my-data endpoint (`DELETE /api/persons/{id}`) is provided.
- Document images are sent to a vision model (if `VISION_API_KEY` is set),
  the response is allow-list filtered and pattern-scrubbed in code
  (`app/vision_extract.py`), and the image bytes are discarded immediately
  - never written to disk or the database.
- The next-question selector (`app/questions.py`) is deterministic code,
  not an LLM.
- Admin rule approval (`POST /api/admin/rules/review`) requires schema
  validity and that every quote exists verbatim in the scheme's source
  text file in `data/raw/`.
- Rules past their `review_by` date, or marked `verified: false`, always
  downgrade `likely_qualifies` to `maybe_confirm_at_office`.

## Deployment

Build and run with Docker:

```
docker build -t scheme-sniper .
docker run -p 8000:8000 --env-file .env scheme-sniper
```

For production, set `DATABASE_URL` to a Postgres connection string and
provide real `JWT_SECRET`, `VISION_API_KEY`, and `DAILY_REFRESH_TOKEN`
values via environment variables/secrets - never commit them.

The daily source-refresh job runs in-process at `DAILY_REFRESH_TIME`
(local server time) and is also exposed as a protected endpoint
(`POST /api/jobs/daily-refresh`, requires `X-Daily-Refresh-Token`) that
`.github/workflows/daily.yml` can call as a backup/CI trigger.

## Health check

`GET /health` returns `{"status": "ok"}`.
