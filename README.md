# Sourcing refinement loop

A recruiter types a role in plain language. The app turns that note into objective filters and a fit rubric, filters a local pool of 48 profiles, scores the survivors with OpenAI, and revises the search from yes/no feedback until the recruiter freezes it.

This repository is the sourcing session: one search, refined in place, with no accounts and no saved history.

The business steps and the request path are written up in [DOCUMENTATION.md](DOCUMENTATION.md).

## Requirements

- Python 3.11 or newer
- Node.js 20 or newer
- An OpenAI API key from [platform.openai.com/api-keys](https://platform.openai.com/api-keys)

A ChatGPT subscription is not this key. The app calls `gpt-5.6-luna` with reasoning off, and falls back to `gpt-5.6-terra` if Luna is unavailable.

## Run the app

### 1. API key

`backend/.env.example` is committed with a placeholder key. Copy it, then replace the placeholder with your own key. Do not commit `backend/.env`.

```bash
cd backend
cp .env.example .env
```

Open `backend/.env` and change this line:

```bash
OPENAI_API_KEY=sk-your-openai-api-key
```

to your real key:

```bash
OPENAI_API_KEY=sk-...your key...
```

Save the file before you start the API. If you change the key later, restart the API process.

### 2. Backend

From the `backend` directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

On Windows, activate the virtual environment with `.venv\Scripts\activate`.

Leave this terminal running. The API listens on http://127.0.0.1:8001.

### 3. Frontend

In a second terminal, from the repository root:

```bash
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173. The Vite server proxies `/api` to port 8001. If port 5173 is already taken, Vite prints the port it used. Open that URL instead.

### 4. Use it

1. Leave the sample brief, or write your own, and choose **Run search**.
2. Review the filters, the fit rubric, and the ranked cards.
3. Choose **Match** to shortlist someone. The button changes to **Shortlisted**, and the count on the Shortlisted tab updates. Choose it again to remove them.
4. Edit filters and choose **Update results**, or mark people and use **Refine search**.
5. Choose **Freeze search** when the shortlist should stop changing.

## Tests

From `backend`, with the virtual environment active:

```bash
pytest
```

Tests use a fake model. They do not call OpenAI and do not need a real key.

## Decisions

Prioritised the loop a recruiter actually runs: free text, visible editable filters and rubric, four or five numbered profiles, feedback, a change summary, and a locked freeze view. Loading, empty results, and model failures keep the last good shortlist on screen.

The model proposes the spec, the scores, and the revision. Application code validates JSON, normalises rubric weights, and applies hard filters locally. A citation is shown only when the quote appears in that profile field. Match explanations are built from those citations.

Scoring is one OpenAI call, capped at 12 profiles. If more than 12 pass the filters, a deterministic pre-rank (skill overlap, then years) chooses who is scored. `gpt-5.6-luna` is used instead of a reasoning model so parse and score stay short. `rds` matches `AWS RDS`, and `Bengaluru` matches `Bangalore`.

Company background is explicit: current company, past companies, or either. "Worked at startups" is not treated as "current company is a startup" unless the note says so.

A revision is stored only after filtering and scoring both succeed. A failed model call leaves the last good shortlist in place, and Retry repeats that step.

Cut from this submission: login, saved searches, pagination, export, vector search, and background workers. At a real talent-map size, the same filters would run as indexed structured queries before any model saw a profile.
