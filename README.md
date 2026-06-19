# Campus Tool — AI Evaluation

GPT-4o powered evaluation for the AI Talent Summit: prompt scoring, build/code scoring, and n8n orchestration for final candidate scores (MCQ 40% + Prompting 60%).

Repository: [TeamFleetStudio/Campus-tool-ai-evaluation](https://github.com/TeamFleetStudio/Campus-tool-ai-evaluation)

---

## Repository layout

| Path | Purpose |
|------|---------|
| **`app/main.py`** | **Run this** — FastAPI entry point |
| `app/` | API routes, services, database models |
| `aiservices.py` | Single-file copy of all evaluation logic (handoff / reference) |
| `rubrics/v1.json` | Prompt scoring rubric |
| `rubrics/code_v1.json` | Generated code scoring rubric |
| `data/seed_problems.json` | Sample problem bank |
| `data/sample_answers.json` | Sample prompting answers |
| **`n8n/`** | **Import these** into n8n (see [n8n/README.md](n8n/README.md)) |
| `requirements.txt` | Python dependencies |
| `.env.example` | Environment variable template |

---

## 1. Run the FastAPI backend

### Prerequisites

- Python 3.11+
- OpenAI API key with access to `gpt-4o`

### Setup

```bash
git clone https://github.com/TeamFleetStudio/Campus-tool-ai-evaluation.git
cd Campus-tool-ai-evaluation

python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set at minimum:

```env
OPENAI_API_KEY=sk-your-key-here
```

### Start the server

```bash
uvicorn app.main:app --reload --port 8000
```

- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/v1/health

### Expose for n8n (required when n8n runs in Docker)

n8n cannot call `localhost:8000` on your machine. Use a public tunnel:

```bash
ngrok http 8000
```

Copy the HTTPS URL (e.g. `https://xxxx.ngrok-free.app`) and set it as `api_base_url` in n8n workflows or webhook payloads.

---

## 2. Key API endpoints

| Endpoint | Use case |
|----------|----------|
| `POST /v1/evaluate/direct` | Prompt-only evaluation (testing) |
| `POST /v1/evaluate/build/direct` | Full build eval: prompt judge → codegen → code judge |
| `POST /v1/evaluate` | Prompt eval in competition round flow |
| `POST /v1/evaluate/build` | Build eval in competition round flow |
| `GET /v1/rubrics` | Prompt rubric |
| `GET /v1/rubrics/code` | Code rubric |

### Build evaluation (used by n8n final-score workflow)

```bash
curl -X POST http://localhost:8000/v1/evaluate/build/direct \
  -H "Content-Type: application/json" \
  -d '{
    "problem_statement": "Build a todo app using React...",
    "user_prompt": "You are a React developer. Build a todo app...",
    "problem_type": "react_spa",
    "acceptance_criteria": ["add task", "mark complete", "delete task", "filter tabs", "task count"]
  }'
```

**Important:** `user_prompt` is the participant's **prompting answer** (what they would tell an LLM). It is **not** submitted code.

**Combined score formula:**

```
combined_score = (0.4 × prompt_score) + (0.6 × output_score)
```

---

## 3. n8n workflows

Import JSON files from the `n8n/` folder. Full instructions: **[n8n/README.md](n8n/README.md)**

| File | When to use |
|------|-------------|
| **`n8n/AI_Talent_Summit_Final_Score.json`** | **Production** — MCQ (Evolve) + build eval → final score, pass/fail, recommendation |
| `n8n/AI_Talent_Summit_Full_Build_Only.json` | Build evaluation only (no MCQ) |
| `n8n/AI_Talent_Summit_Prompt_Only.json` | Prompt evaluation only |
| `n8n/AI_Talent_Summit_Evaluation.json` | Router: prompt vs build mode |

### Final score formula (n8n)

```
round_score = (0.40 × mcq_score) + (0.60 × prompting_combined_score)
overall.score = average of all round_score values
```

---

## 4. Final-score webhook payload

Send to the n8n **Final Score** webhook after a candidate completes a round:

```json
{
  "email": "candidate@example.com",
  "name": "Candidate Name",
  "round": "round_1",
  "testScheduleId": "6a33a3a95f1bbf5aec52f319",
  "api_base_url": "https://YOUR_NGROK_OR_HOST_URL",
  "problem_statement": "Build a todo app using React...",
  "user_prompt": "You are a React developer. Build a todo app...",
  "problem_type": "react_spa",
  "acceptance_criteria": ["add task", "mark complete", "delete task"],
  "pass_threshold": 50,
  "overall_pass_threshold": 50
}
```

For round 2+, include prior results:

```json
{
  "previous_rounds": [
    {
      "round": "round_1",
      "round_score": 53.04,
      "mcq_score": 10.5,
      "prompting_combined_score": 81.4,
      "status": "pass",
      "passed": true
    }
  ]
}
```

---

## 5. Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | — | OpenAI API key |
| `OPENAI_MODEL` | No | `gpt-4o` | Judge / codegen model |
| `DATABASE_URL` | No | `sqlite:///./evaluations.db` | SQLite path |
| `PROMPT_SCORE_WEIGHT` | No | `0.4` | Build eval: prompt weight |
| `OUTPUT_SCORE_WEIGHT` | No | `0.6` | Build eval: code output weight |

Evolve credentials are configured **inside n8n** (Evolve Admin Login node), not in the FastAPI `.env`.

---

## 6. Sample data

- `data/seed_problems.json` — problem bank for rounds
- `data/sample_answers.json` — example prompting answers
- `SAMPLE_PROBLEMS_AND_ANSWERS.md` — copy-paste examples
- `COST_ANALYSIS.md` — token/cost estimates

---

## 7. Quick test checklist

1. Start FastAPI: `uvicorn app.main:app --reload --port 8000`
2. Test build eval: `curl` to `/v1/evaluate/build/direct` (see above)
3. Start ngrok if n8n is remote: `ngrok http 8000`
4. Import `n8n/AI_Talent_Summit_Final_Score.json` into n8n
5. Set Evolve admin credentials + `api_base_url` in the workflow
6. Activate workflow and POST to the production webhook

---

## Scoring rubrics

**Prompt (6 criteria, 0–10 each):** problem_alignment, specificity, clarity, structure, actionability, technique.

**Code output:** functional_completeness, code_quality, requirements_match, best_practices, error_handling, maintainability.

See `rubrics/v1.json` and `rubrics/code_v1.json` for weights and definitions.
