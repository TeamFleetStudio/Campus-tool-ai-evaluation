# n8n Workflows — AI Talent Summit Evaluation

Import these JSON files into your n8n instance. They call the FastAPI backend for AI scoring and (for final score) the Evolve API for MCQ results.

**Prerequisite:** FastAPI must be running and reachable from n8n. See the root [README.md](../README.md).

---

## Which file to import

| File | Import when… |
|------|----------------|
| **`AI_Talent_Summit_Final_Score.json`** | You need **full candidate scoring**: Evolve MCQ + build eval → round score, pass/fail, overall score, recommendation. **This is the main production workflow.** |
| `AI_Talent_Summit_Full_Build_Only.json` | You only need **build evaluation** (prompt + codegen + code judge). No MCQ, no final score. |
| `AI_Talent_Summit_Prompt_Only.json` | You only need **prompt-only** evaluation. |
| `AI_Talent_Summit_Evaluation.json` | You want a **single webhook** that routes to prompt or build mode via a `mode` field. |

---

## How to import

1. Open n8n → **Workflows** → **Import from File**
2. Select the `.json` file from this folder
3. Open the imported workflow and configure credentials (see below)
4. **Save** and toggle **Active** (for production webhooks)

---

## Post-import configuration

### All workflows

| Setting | Where | Value |
|---------|-------|-------|
| `api_base_url` | Normalize Input / HTTP Request node | Public URL of FastAPI (e.g. ngrok HTTPS URL). **Not** `localhost` if n8n runs in Docker. |

If using ngrok, keep the header on HTTP nodes:

```
ngrok-skip-browser-warning: true
```

### Final Score workflow only

| Setting | Node | Value |
|---------|------|-------|
| Evolve admin email | **Evolve Admin Login** | Service account for Evolve API (not the candidate email) |
| Evolve admin password | **Evolve Admin Login** | Password for that account |
| Round 1 schedule ID | **Normalize Input** default / webhook | `6a33a3a95f1bbf5aec52f319` |
| Candidate email | Webhook payload `email` | Candidate's Evolve email (used to fetch MCQ score) |

**Do not** use the candidate email for Evolve admin login — Evolve returns "Multiple logins not allowed".

---

## Workflow: Final Score (recommended)

**File:** `AI_Talent_Summit_Final_Score.json`

### Flow

```
Webhook / Manual Test
  → Normalize Input
  → (parallel) Evolve Admin Login → Fetch MCQ Score → Extract MCQ Score
  → (parallel) Build Evaluation → POST /v1/evaluate/build/direct
  → Wait For Both → Compute Final Score → Respond to Webhook
```

### Formula

```
round_score = (0.40 × mcq_score) + (0.60 × prompting_combined_score)
overall.score = average of all round_score values (current + previous_rounds)
```

### Webhook paths

| Environment | URL pattern |
|-------------|-------------|
| Production (workflow Active) | `https://YOUR_N8N_HOST/webhook/ai-talent-summit/final-score` |
| Test (Listen for test event) | `https://YOUR_N8N_HOST/webhook-test/ai-talent-summit/final-score` |

### Webhook payload (POST JSON)

```json
{
  "email": "candidate@example.com",
  "name": "Candidate Name",
  "round": "round_1",
  "testScheduleId": "6a33a3a95f1bbf5aec52f319",
  "api_base_url": "https://YOUR_API_PUBLIC_URL",
  "problem_statement": "Build a todo app using React...",
  "user_prompt": "You are a React developer. Build a todo app...",
  "problem_type": "react_spa",
  "acceptance_criteria": ["add task", "mark complete", "delete task"],
  "pass_threshold": 50,
  "overall_pass_threshold": 50
}
```

**`user_prompt`** = the participant's prompting answer. **Do not** send `codeSubmitted` or raw code as the prompt.

### Response fields

| Field | Description |
|-------|-------------|
| `current_round` | Scores and pass/fail for this round |
| `round_summary` | All rounds at a glance |
| `overall.score` | Average across rounds |
| `overall.passed` | All rounds passed + score ≥ threshold |
| `recommendation` | Strong Recommend / Recommend / Borderline / Not Recommended |
| `final_score` | Current round score (backward compatible) |

### Manual test in n8n

1. Open workflow → click **Execute Workflow** on **Manual Test** node
2. Or use **Webhook** → **Listen for test event** → POST with curl

---

## Workflow: Full Build Only

**File:** `AI_Talent_Summit_Full_Build_Only.json`

- Calls `POST {api_base_url}/v1/evaluate/build/direct`
- Returns `prompt_score`, `output_score`, `combined_score`
- No Evolve / MCQ integration

---

## Workflow: Prompt Only

**File:** `AI_Talent_Summit_Prompt_Only.json`

- Calls `POST {api_base_url}/v1/evaluate/direct`
- Returns prompt rubric scores only

---

## Workflow: Evaluation Router

**File:** `AI_Talent_Summit_Evaluation.json`

- Single webhook; set `"mode": "prompt"` or `"mode": "build"` in payload
- Routes to the appropriate FastAPI endpoint

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `Workflow could not be started` | Ensure workflow is **Active**; check n8n queue workers; try deactivate + reactivate |
| n8n cannot reach API | Use ngrok/public URL, not `localhost:8000` |
| Evolve login fails | Use admin service account, not candidate email |
| MCQ score missing | Verify `testScheduleId`, candidate `email`, and `isCompleted=true` on Evolve |
| Build eval timeout | Build eval runs 3 LLM calls; allow 60–120s on HTTP node timeout |

---

## Nodes to update after import

1. **Evolve Admin Login** — credentials
2. **Normalize Input** or **Build Evaluation** — `api_base_url` default
3. **Compute Final Score** — only if you change scoring weights or recommendation tiers (Code node)
