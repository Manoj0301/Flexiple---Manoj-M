# Sourcing refinement loop

This document explains what the product does for a recruiter, and how the application carries that work from a sentence to a frozen shortlist.

The code lives in this repository, managed as the Flexiple sourcing assignment for Manoj M.

## Business flow

A recruiter is hiring for a role. They do not want to write Boolean search syntax. They want to say what they need, see a short list of people who fit, correct the search, and lock the result.

The product is one session. There is no login, no saved history, and no shared inbox. The session lives in memory until the API process stops.

### 1. Describe the role

The recruiter writes a brief in plain language, for example: RDS developers with 4–7 years who have worked at startups, for a role in Bangalore.

That sentence is the source of truth for the first search. The app does not ask them to fill skills, years, and location before the first run. Those controls appear after the brief has been interpreted.

### 2. See filters, a rubric, and a short list

The first response does three jobs:

- It turns the brief into objective filters: required skills, a year range, locations, company types, whether company background means the current company, a past company, or either, and whether every required skill is mandatory.
- It proposes a fit rubric: a few weighted criteria that describe what "good" means beyond the hard filters.
- It returns the people who passed the filters, scored and ordered, with the top matches on screen.

The recruiter can read why someone ranked where they did. Each explanation is tied to words that actually appear on that profile. A score without that evidence is not shown.

### 3. Correct the search

There are two ways to change the search, and they do different jobs.

**Edit the spec.** The recruiter changes a skill chip, the year slider, a location, a company type, or a rubric weight, then chooses Update results. This is a direct edit. The application re-filters and re-scores. It does not ask the model to guess what the recruiter meant.

**Refine from feedback.** The recruiter marks people as a match or a reject, and can write a note such as "1 is too junior, 2 and 4 are right." Match and Reject are recruiter judgement. They do not by themselves remove anyone from the current list. Refine search sends those marks, plus the note, to the model, which proposes the smallest change to the filters or rubric. Positions in the note refer to the cards on screen, in order.

A change summary shows what moved: the field, the old value, the new value, and why.

### 4. Shortlist while reviewing

Match keeps the recruiter on the results. The button becomes Shortlisted, the name is labelled, and the Shortlisted count in the top bar increases. Shortlisted is the set of people they want to keep from this search. Clicking the button again removes them. Opening Shortlisted shows that set. It does not start a new search.

### 5. Freeze

Freeze search locks the current shortlist. Filters, the rubric, refine, and further scoring stop. The frozen view is the result the recruiter would hand to the next step of hiring. Run search on a new brief starts a new session.

### What the recruiter should trust

- Hard filters are applied in application code, not by the model. If someone fails a required skill, a year bound, a location, or the company-history rule, they are not scored.
- The model proposes the spec, the scores, and later revisions. It does not get to invent profile facts. A citation is kept only when the quote is present in that profile field.
- A failed model call does not replace the last good shortlist. Retry repeats the failed step.
- Company background is explicit. "Worked at startups" is not treated as "the current company is a startup" unless the brief or a later edit says so.

## Technical flow

The system is a modular monolith: a FastAPI service and a React client. The browser never calls OpenAI. The API holds the key, the profiles, and the session.

```text
Recruiter
  -> React (Vite, port 5173)
    -> /api proxied to FastAPI (port 8001)
      -> OpenAI Responses API (structured output)
      -> local filter and evidence checks
      -> in-memory session
```

### Repository layout

| Path | Responsibility |
| --- | --- |
| `frontend/` | Search workspace, filters, cards, shortlist, messages, analytics |
| `backend/app/main.py` | HTTP routes, CORS, error shape, env load |
| `backend/app/service.py` | Session loop: parse, score, edit, refine, freeze, retry |
| `backend/app/filters.py` | Deterministic filter and pre-rank |
| `backend/app/evidence.py` | Citation checks |
| `backend/app/feedback.py` | Maps "1, 2, 4" and Match/Reject onto profile ids |
| `backend/app/llm.py` | OpenAI client, model fallback, timeouts |
| `backend/prompts/` | Parse, score, and refine prompts |
| `backend/data/profiles.json` | The 48-profile pool |
| `backend/tests/` | Filters, evidence, positional feedback, and the loop with a fake model |

### Data the loop is built around

**SearchSpec** is the only criteria object. It has objective filters and a fit rubric. Rubric weights are positive numbers. The server normalises them so they sum to 100. The model is not required to emit weights that already sum to 100.

**Profile** fields used by filters and citations include id, name, title, years, location, current company, current company type, past companies, skills, education, and summary.

**Session** stores the original brief, status (`active` or `frozen`), and an ordered list of revisions. A revision is stored only after filtering and scoring both succeed. The last revision is what the UI renders. A failed edit or refine is remembered so Retry can repeat that step without committing a bad revision.

### Request path for a new search

1. The client sends `POST /api/search-sessions` with `{ "query": "..." }`.
2. The parse prompt plus the brief go to OpenAI. The response is parsed into a Pydantic schema (`LLMParse`). Invalid JSON is repaired once. If it is still invalid, the call fails and no session is stored.
3. The parsed object is validated into a `SearchSpec`. Unknown company-history or skill-match values fall back to `any` and `all`. Empty criterion ids and non-positive weights are repaired. Weights are normalised.
4. `filter_profiles` walks the 48 profiles in process. Matching is case-insensitive. Skill aliases treat `rds` as `AWS RDS`, and the same idea covers Postgres, Node, and Kubernetes. Location aliases treat Bengaluru as Bangalore, and cover Delhi NCR and Remote - India. Company history respects current, past, or either.
5. If nobody passes, the session is still created, with an empty shortlist, so the recruiter can loosen the spec.
6. If more than 12 pass, `pre_rank` keeps 12 using skill overlap, then years. Scoring is one model call, not one call per person.
7. Each returned score is checked. The quote must occur in the named profile field. If the model omitted a valid quote but the reason names a real field, the server infers a citation. A profile with no citation is dropped. Scores are clamped to 0–100 and sorted descending.
8. The server commits revision 0 and returns a session view: spec, filtered count, the full ranked list, and the visible top 5.

### Request path for an edit

`PATCH /api/search-sessions/{id}/spec` accepts a full `SearchSpec` from the form. The server normalises it, re-filters, and re-scores. The diff against the previous spec is attached as the change list, with the reason "Edited directly by the recruiter." The previous revision remains if scoring fails.

### Request path for refine

`POST /api/search-sessions/{id}/refine` sends the note and the Match/Reject marks. The server maps positions in the note onto `visible_profile_ids` for the cards on screen, so "1" means the first visible card, not an arbitrary profile id the model might invent.

The refine prompt includes the original brief, the current spec, the visible candidates, the feedback, and the last few change summaries. The instruction to the model is to make the smallest spec change that answers the feedback. The new spec is validated, filtered, and scored before it replaces the current revision. The change list uses the model's notes where they name a field, and the computed diff otherwise.

### Freeze and retry

`POST /api/search-sessions/{id}/freeze` sets status to `frozen`. Later edit, refine, and score calls return 409. The UI hides those controls.

`POST /api/search-sessions/{id}/retry` reruns the last failed edit or refine. If nothing failed, it returns 400.

### Model client

`OpenAIClient` reads `OPENAI_API_KEY` from `backend/.env` at process start. Changing the file requires an API restart. The client calls the Responses API with `responses.parse` and a Pydantic `text_format`, so the model is constrained to the schema.

The primary model is `gpt-5.6-luna`, with reasoning left off so parse and score stay short. If Luna is missing, out of quota, rate-limited, overloaded, or times out, the client tries `gpt-5.6-terra`. An invalid API key does not fall through to the second model. The outer wait is 120 seconds. The OpenAI client timeout is 90 seconds.

Errors are `AppError` JSON: `code`, `message`, `retryable`, `request_id`. The UI shows that message and offers Retry when `retryable` is true.

`X-Force-Failure: timeout` or `malformed` fails inside the client before a revision is committed. The product UI does not expose this. It exists so tests and a walkthrough can show recovery without a canned model body.

### Frontend states

The workspace is one screen.

- Before a session, the left card is the brief and the right side offers example briefs.
- While a request is in flight, a spinner and status lines stay on screen, including "Searching for the best candidates for your organization." The Run search button reads Hold on. An existing shortlist stays visible until the new one arrives.
- After a session, the left side is the brief, filters, and rubric. The right side is numbered cards: fit score, skill chips, the reason, View profile, Reject, and Match.
- Match toggles Shortlisted locally. That set is not a separate backend object. Refine is what sends those marks to the server.
- Empty filters, a scoring result with nobody cited, a model error, and the frozen shortlist each have their own state. The last good cards are not cleared on error.

Vite proxies `/api` to `http://127.0.0.1:8001`.

### Tests

From `backend`, `pytest` runs the filter aliases, citation checks, positional feedback mapping, and the service loop against a fake model. Those tests do not call OpenAI.

### What this submission leaves out

Accounts, persisted searches, pagination, export, a vector index, and background workers are out of scope. Forty-eight profiles fit in memory. At a real talent-map size, the same filter object would run as indexed structured queries, and only the survivors would be sent to the model.
