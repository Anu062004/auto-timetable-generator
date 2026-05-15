# Automated College Timetable Generator

Conflict-free college timetables, built on Google OR-Tools CP-SAT with an LLM natural-language front door. Designed against the BMSIT AIML 4th Sem (2025-26) reference dataset.

See `timetable_generator_blueprint.md` for the full design.

## Status

- Layer 1 — LLM Interface (Claude API): ready (uses `ANTHROPIC_API_KEY`)
- Layer 2 — Pre-Flight Validator: ready
- Layer 3 — CP-SAT Solver: ready, hard constraints H1–H12 + soft S1–S7
- Layer 4 — Independent Verifier: ready
- Layer 5 — Output: PDF, Excel, JSON, iCal (per-faculty)
- React frontend: chat panel + section / faculty grids + exports

## LLM provider

The LLM layer (Layer 1) supports two providers and picks one automatically:

1. **AWS Bedrock** (default) — uses your AWS CLI credentials. No API key
   needed. Region defaults to `ap-southeast-2`; override with `AWS_REGION`.
   Default model: **Claude Opus 4.5** with auto-fallback to Sonnet 4.5 / Sonnet 4 / Haiku 4.5.
2. **Anthropic direct API** — used when `ANTHROPIC_API_KEY` is set.

### One-time Bedrock setup (required on a fresh account)

Before any Claude 4.x model will serve, AWS asks each account to submit a short
"Anthropic use-case details" form. To do this:

1. Open the Bedrock console:
   `https://<region>.console.aws.amazon.com/bedrock/home#/model-access`
2. Click **Modify model access** → check Anthropic Claude (Opus 4.5 / Sonnet 4.5 / Haiku 4.5).
3. Fill the use-case form once. Access is usually granted within 15 minutes.

`GET /llm/info` runs a one-token Bedrock ping and surfaces the exact error
if the form hasn't been submitted yet — the frontend can use this to show a
clear "click here to enable" banner.

## Quick start

### Backend
```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
# Bedrock by default — picks up AWS CLI credentials.
# OR: $env:ANTHROPIC_API_KEY = "sk-ant-..."  to use the direct Anthropic API.
uvicorn app.main:app --reload --port 8000
```

### Frontend
```powershell
cd frontend
npm install
npm run dev    # http://localhost:5173
```

### Tests
```powershell
cd backend
pytest -q
```

## End-to-end smoke test (no LLM key required)

```powershell
# Reference dataset
curl http://localhost:8000/reference/bmsit_4th_sem -o ref.json

# Solve
curl -X POST http://localhost:8000/generate -H "content-type: application/json" --data-binary "@ref.json" -o gen.json

# Exports (use the job_id from gen.json)
curl "http://localhost:8000/job/<JOB_ID>/export/pdf" -o tt.pdf
curl "http://localhost:8000/job/<JOB_ID>/export/xlsx" -o tt.xlsx
```

Expected result on the BMSIT 4th Sem reference: OPTIMAL solution in ~30s, 216 placements across 6 sections × 6 days × 7 slots, zero verifier violations, soft score ~50/100.

## API

| Method | Path | What |
|---|---|---|
| `GET`  | `/health` | liveness |
| `GET`  | `/reference/bmsit_4th_sem` | seed `TimetableRequest` |
| `POST` | `/preflight` | run Layer 2 only |
| `POST` | `/generate` | Layer 2 + Layer 3 + Layer 4 → `GenerateResponse` |
| `GET`  | `/job/{id}` | retrieve a generated job |
| `GET`  | `/job/{id}/export/{pdf|xlsx|json|ical}` | exports |
| `POST` | `/llm/parse` | natural language → `TimetableRequest` |
| `POST` | `/llm/explain` | summarise the solver's result |

## Architecture

```
User text / PDF
      │
      ▼
LLM Interface (Claude)  → TimetableRequest JSON
      │
      ▼
Pre-Flight Validator    → PreflightReport (errors / warnings)
      │ (only if ok)
      ▼
CP-SAT Solver           → Timetable (OPTIMAL / FEASIBLE / INFEASIBLE)
      │
      ▼
Independent Verifier    → VerificationReport (H1..H12)
      │
      ▼
Exporters               → PDF / XLSX / JSON / iCal
```

## What still has rough edges

1. **Faculty assignment for electives** is treated as combined teaching (one faculty
   per option per slot) rather than per-section assignment. Real BMSIT runs this
   way; if you actually want parallel teaching for an option with multiple
   sections, expand the option's `faculty_pool` and toggle the per-section
   mapping in `cpsat_solver._apply_elective_blocks`.
2. **Saturday alternating weeks** are modeled as one canonical active week.
   Calendar projection (which week is off) is left to the consumer.
3. **PDF look-and-feel** is functional, not pixel-matched to the college's
   template. Map your template via `app/export/renderers.py`.
4. **Drag-and-drop manual edits** in the frontend are not yet wired; the UI
   currently renders the read-only solver output.
