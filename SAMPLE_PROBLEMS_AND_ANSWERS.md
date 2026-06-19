# Sample Problem Statements and Prompting Answers

Participants submit their **prompting answer** in the `user_prompt` field — the prompt they would give an LLM, not the final solution.

---

## Problem 1 — Customer support drafting

### Problem statement
A customer emailed saying their subscription was charged twice this month. They want a refund for the duplicate charge and confirmation it won't happen again. Write a prompt that instructs an LLM to draft a professional, empathetic reply. The reply should acknowledge the issue, explain next steps, and ask for any info needed to process the refund. Tone: calm, not defensive. Max 150 words.

### Strong prompting answer (`user_prompt`)
```
You are a senior customer support specialist at a SaaS company.

Task: Draft a reply email to a customer who reports being charged twice for their subscription this month. They want a refund for the duplicate charge and assurance this will not happen again.

Requirements:
- Tone: calm, empathetic, professional — never defensive or dismissive
- Acknowledge the duplicate charge and apologize for the inconvenience
- Explain the refund process and expected timeline (3-5 business days)
- Ask for: transaction ID or last 4 digits of card, and the date of both charges
- Confirm we will investigate the billing system to prevent recurrence
- Max length: 150 words
- Do NOT admit legal liability or promise outcomes we cannot guarantee

Output: Return only the email body, ready to send.
```

### Weak prompting answer (for contrast)
```
Write a professional email to a customer about their billing issue.
```

---

## Problem 2 — Meeting notes to action items

### Problem statement
You have a raw transcript from a 30-minute product standup. Teams discussed three features, two blockers, and four action items — but the transcript is messy (crosstalk, incomplete sentences). Write a prompt that turns this transcript into structured output: a JSON object with summary (2-3 sentences), decisions (array), action_items (array of owner, task, due_date), and open_questions (array). The prompt must handle missing due dates gracefully and flag ambiguous owners.

### Strong prompting answer (`user_prompt`)
```
You are a meeting-notes analyst.

I will paste a raw transcript from a 30-minute product standup below. Extract structured information and return ONLY valid JSON with this schema:

{
  "summary": "2-3 sentence overview",
  "decisions": ["decision 1", ...],
  "action_items": [{"owner": "name or UNKNOWN", "task": "...", "due_date": "YYYY-MM-DD or null"}],
  "open_questions": ["question 1", ...]
}

Rules:
- If an owner is unclear from context, set owner to "UNKNOWN" and add a note in open_questions
- If due_date is not mentioned, use null — do not invent dates
- Ignore crosstalk and filler; focus on features, blockers, and action items
- Do not include markdown or explanation outside the JSON

<<<TRANSCRIPT>>>
[paste transcript here]
<<<END TRANSCRIPT>>>
```

---

## Problem 3 — Debug a Python function

### Problem statement
The following Python function is supposed to return the top N most frequent words in a string (case-insensitive, ignoring punctuation). It has a bug — it returns wrong counts for some inputs. Write a prompt that asks an LLM to: (1) identify the bug, (2) explain why it fails, (3) provide a corrected version, and (4) suggest two test cases that would have caught the bug. Assume the buggy code will be pasted below your prompt. Do not solve it yourself in the submission — only write the prompt.

### Strong prompting answer (`user_prompt`)
```
You are an expert Python debugger.

Below is a buggy function that should return the top N most frequent words in a string (case-insensitive, punctuation ignored). Analyze it and respond in four sections:

1. **Bug identification** — name the specific bug
2. **Why it fails** — explain with an example input that produces wrong output
3. **Corrected code** — provide the fixed function only, in a Python code block
4. **Test cases** — two unit-test-style inputs that would have caught this bug

Do not rewrite unrelated code. Focus only on the function provided.

<<<BUGGY CODE>>>
[paste code here]
<<<END CODE>>>
```

---

## Problem 4 — Executive summary from metrics

### Problem statement
A CSV export contains monthly SaaS metrics: MRR, churn rate, new signups, support tickets, and NPS for the last 12 months. MRR grew overall but churn spiked in Q3. Write a prompt that produces a one-page executive summary for the CEO. The summary must: highlight the top 3 trends, call out Q3 churn as a concern, recommend 2-3 investigative questions (not solutions), and use plain language (no jargon). Include how the LLM should handle missing or anomalous data points.

### Strong prompting answer (`user_prompt`)
```
You are a data analyst preparing a briefing for a non-technical CEO.

I will provide a CSV with 12 months of SaaS metrics: MRR, churn_rate, new_signups, support_tickets, NPS.

Write a one-page executive summary (max 400 words) that:
- Highlights the top 3 trends across the year
- Specifically calls out the Q3 churn spike as a concern requiring attention
- Lists 2-3 investigative questions (not solutions) the leadership team should explore
- Uses plain language — no jargon (avoid terms like cohort, ARR unless explained)

If any month has missing or anomalous values (e.g. NPS of 0 or null), note the gap explicitly rather than interpolating or guessing.

<<<CSV DATA>>>
[paste CSV here]
<<<END CSV>>>
```

---

## Problem 5 — Product launch tweet thread

### Problem statement
Write a prompt for generating a 5-tweet thread announcing a new AI note-taking app. Constraints: tweet 1 must be a hook (no product name), tweet 5 must include a CTA link placeholder [LINK], no tweet over 240 characters, no hype words (revolutionary, game-changer), target audience is busy consultants. The prompt should produce all 5 tweets in one response, numbered 1-5.

### Strong prompting answer (`user_prompt`)
```
You are a social media copywriter targeting busy management consultants.

Generate a 5-tweet thread announcing a new AI note-taking app. Return exactly 5 tweets, numbered 1-5.

Constraints:
- Tweet 1: Hook only — do NOT mention the product name
- Tweet 5: Must end with CTA placeholder [LINK]
- Each tweet: max 240 characters
- Forbidden words: revolutionary, game-changer, disruptive, cutting-edge
- Tone: practical, time-saving, no hype
- Audience: consultants who live in back-to-back meetings

Output format:
1. [tweet text]
2. [tweet text]
...
5. [tweet text]
```

---

## Problem 6 — Security review prompt chain

### Problem statement
You are designing a prompt for an LLM to review a pull request diff for common security issues (SQL injection, XSS, hardcoded secrets, insecure deserialization). The reviewer LLM has no access to the full codebase — only the diff and a short PR description. Write a single prompt that: assigns a security-reviewer role, lists what to check, defines severity levels (critical / high / medium / low), requires output as a markdown table with columns file, line, issue, severity, recommendation, and instructs the model to say insufficient context rather than guess when the diff alone is not enough. The problem domain is a Node.js Express API.

### Strong prompting answer (`user_prompt`)
```
You are a senior application security engineer reviewing a Node.js Express API pull request.

You have ONLY the PR description and diff below — no access to the full codebase.

Review for: SQL injection, XSS, hardcoded secrets/credentials, insecure deserialization, missing input validation, and unsafe dependency usage.

Output a markdown table with columns: file | line | issue | severity | recommendation

Severity levels: critical | high | medium | low

Rules:
- If the diff alone does not provide enough context to confirm an issue, write "insufficient context" in the issue column — do NOT speculate
- Cite specific line numbers from the diff when possible
- If no issues found, return a table with one row: "No issues identified" with severity "low"

<<<PR DESCRIPTION>>>
[paste description]
<<<END DESCRIPTION>>>

<<<DIFF>>>
[paste diff]
<<<END DIFF>>>
```

---

## How to test with the API

```bash
# Direct test (no round needed)
curl -X POST http://localhost:8000/v1/evaluate/direct \
  -H "Content-Type: application/json" \
  -d '{
    "problem_statement": "A customer emailed saying their subscription was charged twice...",
    "user_prompt": "You are a senior customer support specialist..."
  }'
```

Or fetch samples from the API:
- `GET /v1/samples/problems`
- `GET /v1/samples/answers?problem_id=problem-1`

---

## Build problems (dual evaluation: prompt + code)

Use `POST /v1/evaluate/build/direct` for these. Participant submits a `user_prompt`; the API generates code and scores both.

### Build 1 — SaaS landing page (`static_web`)

**Problem statement:**
Build a landing page for an AI note-taking app targeting busy consultants. Must include: a hero section with headline and CTA button, 3 feature cards, a pricing table with 2 tiers, and a contact form (name, email, message). Mobile-responsive.

**Strong `user_prompt`:**
```
You are an expert frontend developer.

Build a complete, self-contained landing page in a single index.html file for an AI note-taking app called NoteFlow, targeting busy consultants.

Requirements:
- Hero: compelling headline, subtext, and a primary CTA button "Start Free Trial"
- Features: exactly 3 feature cards with icons, title, and description
- Pricing: table with 2 tiers (Free and Pro)
- Contact form: name, email, message, submit button
- Modern, mobile-responsive CSS

Output production-ready HTML with inline CSS.
```

### Build 2 — React todo app (`react_spa`)

**Problem statement:**
Build a todo app using React. Users must be able to: add a new task, mark tasks complete, delete tasks, and filter by All / Active / Completed. Show a task count.

**Strong `user_prompt`:**
```
You are a React developer. Build a todo app using React (CDN in index.html, no build step).
Features: add task, mark complete, delete, filter All/Active/Completed, active task count.
Use useState. Files: index.html + component. Fully functional.
```

### Build 3 — Task REST API (`backend_api`)

**Problem statement:**
Build a REST API for task management. Endpoints: GET/POST /tasks, PUT/DELETE /tasks/:id. Task fields: id, title, completed. Input validation and HTTP status codes required.

**Strong `user_prompt`:**
```
You are a backend developer. Build a FastAPI REST API in main.py for task management.
Endpoints: GET/POST /tasks, PUT/DELETE /tasks/{id}.
In-memory storage. Validate title not empty (400), 404 if not found.
```
