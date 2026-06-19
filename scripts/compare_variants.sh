#!/usr/bin/env bash
# Compare multiple user_prompt variants against the same problem_statement.
# Usage: ./scripts/compare_variants.sh

set -e
API="${API_URL:-http://localhost:8000/v1/evaluate/direct}"

PROBLEM='A customer emailed saying their subscription was charged twice this month. They want a refund for the duplicate charge and confirmation it will not happen again. Write a prompt that instructs an LLM to draft a professional, empathetic reply. The reply should acknowledge the issue, explain next steps, and ask for any info needed to process the refund. Tone: calm, not defensive. Max 150 words.'

run_eval() {
  local label="$1"
  local prompt="$2"
  echo ""
  echo "=========================================="
  echo "VARIANT: $label"
  echo "=========================================="
  result=$(curl -s -X POST "$API" \
    -H "Content-Type: application/json" \
    -d "$(python3 -c "
import json
print(json.dumps({
    'problem_statement': '''$PROBLEM''',
    'user_prompt': '''$prompt''',
    'rubric_version': 'v1'
}))
")")
  echo "$result" | python3 -c "
import json, sys
d = json.load(sys.stdin)
if 'detail' in d and 'total_score' not in d:
    print('ERROR:', d['detail'])
    sys.exit(1)
print(f\"Total score: {d['total_score']}/100\")
print(f\"Summary: {d['summary']}\")
print()
print('Breakdown:')
for c in d['criteria']:
    print(f\"  {c['name']:20} {c['score']:4}/10  (contribution: {c['weighted_contribution']})\")
print(f\"Tokens: {d['usage']['total_tokens']}\")
"
}

# Variant 1: Strong (full sample)
run_eval "STRONG - full structured prompt" \
"You are a senior customer support specialist at a SaaS company.

Task: Draft a reply email to a customer who reports being charged twice for their subscription this month. They want a refund for the duplicate charge and assurance this will not happen again.

Requirements:
- Tone: calm, empathetic, professional — never defensive or dismissive
- Acknowledge the duplicate charge and apologize for the inconvenience
- Explain the refund process and expected timeline (3-5 business days)
- Ask for: transaction ID or last 4 digits of card, and the date of both charges
- Confirm we will investigate the billing system to prevent recurrence
- Max length: 150 words
- Do NOT admit legal liability or promise outcomes we cannot guarantee

Output: Return only the email body, ready to send."

# Variant 2: Medium
run_eval "MEDIUM - decent but less specific" \
"You are a customer support agent. Write a professional and empathetic email to a customer who was charged twice for their subscription. Apologize, explain we will process a refund, and ask for their transaction details. Keep it under 150 words and use a calm tone."

# Variant 3: Weak
run_eval "WEAK - generic" \
"Write a professional email to a customer about their billing issue."

# Variant 4: Off-topic
run_eval "OFF-TOPIC - ignores the task" \
"You are a Python coding tutor. Help the user debug a function that sorts a list of integers in ascending order. Provide step-by-step guidance."

# Variant 5: Over-engineered
run_eval "BLOATED - too long, unfocused" \
"You are an expert in everything. You have 20 years of experience in customer service, legal compliance, marketing, and technical writing. Please consider all possible scenarios including but not limited to: angry customers, happy customers, customers who speak other languages, customers in different time zones, regulatory requirements in the EU GDPR CCPA and other jurisdictions. Write something about billing maybe. Also tell me a joke. Use markdown tables and bullet points. Maximum 150 words for the email but also include a 500 word appendix."

echo ""
echo "Done. Compare total scores above."
