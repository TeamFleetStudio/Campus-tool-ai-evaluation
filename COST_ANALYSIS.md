# Cost Analysis — Prompt Evaluation API (GPT-4o)

Simple cost guide for the full evaluation flow using **GPT-4o**.

**Pricing used:** $2.50 / 1M input tokens · $10.00 / 1M output tokens

---

## Two evaluation modes

| Mode | Endpoint | API calls | What it does |
|------|----------|-----------|--------------|
| **Prompt only** | `POST /v1/evaluate/direct` | 1 | Scores the participant's prompt |
| **Build (full flow)** | `POST /v1/evaluate/build/direct` | 3 | Scores prompt → generates code → scores code |

---

## Build flow — 3 steps

```
Participant submits user_prompt
        │
        ├─► Step 1: Prompt Judge     → prompt_score
        ├─► Step 2: Code Generator   → generated_code (HTML, React, API, Docker, etc.)
        └─► Step 3: Code Judge       → output_score
                    │
                    ▼
            combined_score = (40% × prompt) + (60% × output)
```

---

## Cost per evaluation (observed)

Based on current testing with a new API key:

| Problem complexity | Total tokens | Est. cost per eval |
|--------------------|-------------|-------------------|
| **Simple / medium** (landing page, todo app, short prompts) | ~5,000 | **~$0.03–0.04** |
| **Complex** (full-stack app + deployment, many files) | ~9,000 | **~$0.06–0.08** |
| **Prompt only** (no code generation) | ~1,400–1,500 | **~$0.01** |

### Example breakdown — medium build (~5,000 tokens)

| Step | Tokens | Share |
|------|--------|-------|
| Prompt judge | ~1,400 | 28% |
| Codegen | ~1,400 | 28% |
| Code judge | ~2,200 | 44% |
| **Total** | **~5,000** | **~$0.03** |

### Example breakdown — complex build (~9,000 tokens)

| Step | Tokens | Share |
|------|--------|-------|
| Prompt judge | ~1,800 | 20% |
| Codegen | ~3,500 | 39% |
| Code judge | ~3,700 | 41% |
| **Total** | **~9,000** | **~$0.08** |

Codegen and code judge use the most tokens on complex problems because the model **writes** and then **reads** large multi-file output (Docker, backend, frontend, README).

---

## Cost formula

```
cost = (input_tokens × $2.50 / 1,000,000) + (output_tokens × $10.00 / 1,000,000)
```

Output tokens cost **4× more** than input tokens.

---

## Cohort estimates (build flow)

| Participants | Simple/medium (~$0.035 each) | Complex (~$0.08 each) |
|--------------|------------------------------|-------------------------|
| 50 | ~$1.75 | ~$4.00 |
| 100 | ~$3.50 | ~$8.00 |
| 500 | ~$17.50 | ~$40.00 |
| 1,000 | ~$35.00 | ~$80.00 |

Prompt-only rounds are ~**4× cheaper** (~$0.01 per person).

---

## What drives cost up

| Factor | Impact |
|--------|--------|
| Longer `problem_statement` | More tokens in all 3 steps |
| Longer `user_prompt` | More tokens in prompt judge + codegen |
| Complex builds (full-stack, Docker, many files) | Large codegen output + large code judge input |
| Using `/evaluate/build/direct` vs `/evaluate/direct` | 3× API calls instead of 1 |

---

## Ways to reduce cost

1. **Use prompt-only** (`/evaluate/direct`) when you only need to score prompt craft — ~$0.01/eval
2. **Keep problem statements concise** — aim for 200–600 tokens
3. **Cap user prompt length** — max 8,000 tokens (already enforced)
4. **Use Batch API** for offline grading — 50% off (slower, async)
5. **Prompt caching** — static rubric blocks can be cached after first call (~small savings)

---

## Quick reference

| Question | Answer |
|----------|--------|
| Cheapest eval? | Prompt only → ~$0.01 |
| Typical build eval? | ~5,000 tokens → ~$0.03–0.04 |
| Heaviest build eval? | Full-stack + deployment → ~9,000 tokens → ~$0.08 |
| 100 people, medium builds? | ~$3.50 total |
| 100 people, complex builds? | ~$8.00 total |

---

*Last updated: June 2026 · Model: gpt-4o · Weights: 40% prompt score + 60% output score*
