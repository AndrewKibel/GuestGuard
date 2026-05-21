[README.md](https://github.com/user-attachments/files/28119330/README.md)
# GuestGuard

GuestGuard is a 24-hour prototype QA tool for AI guest messaging in short-term rentals.

The app evaluates whether an AI-generated guest response is accurate, safe, SOP-compliant, and ready to send. It compares three inputs:

1. Guest message
2. Property SOP / rules
3. AI draft response

GuestGuard then returns a response score, a Send / Review / Escalate decision, detected issue types, risk breakdown, flags, upsell opportunities, and a suggested better response.

## Why I built this

I built GuestGuard because I think one of the hardest parts of AI guest messaging is not just generating a response, but knowing whether the response should actually be trusted.

A message can sound friendly while still creating a real problem. For example, an AI might promise early check-in before cleaning is complete, approve a refund without manager approval, miss a pet fee, or fail to escalate a lockout. I wanted to prototype a simple evaluation layer for catching those issues.

## How it works

GuestGuard has two evaluation modes:

- A rule-based evaluator that catches common high-risk hospitality scenarios
- An optional LLM evaluator that can review the same guest message, SOP, and AI draft using a structured prompt

The rule-based evaluator checks for things like:

- Access or lockout issues
- Refund requests
- Early check-in
- Late checkout
- Pet policies
- Parties or outside guests
- Parking issues
- Safety concerns
- Irrelevant AI responses

The scoring is based on rough prototype severity weights. Higher-risk issues, like safety problems, lockouts, refunds, or major SOP violations, reduce the score more than smaller missing details.

## Optional LLM mode

The optional LLM evaluator requires an OpenAI API key. I did not hardcode an API key into the project because API keys should not be shared publicly. Instead, the app lets the user enter an API key in the sidebar.

The app still works without an API key because the rule-based evaluator is the default.

## How to run

Install requirements:

    pip3 install -r requirements.txt

Run the app:

    python3 -m streamlit run app.py

## Files

    app.py
    requirements.txt
    README.md

## Limitations

The rule-based evaluator is intentionally transparent but limited; the optional LLM mode is there to handle more flexible language. In a real product, I’d use both: deterministic guardrails for high-risk cases and LLM evaluation for nuance.

## Future improvements

With more time, I would improve GuestGuard by testing it on more realistic guest conversations as well as comparing rule-based and LLM evaluations when they disagree.

A more advanced version could also use logged evaluations as training data. For example, if property managers marked whether GuestGuard’s decision was correct, that feedback could be used to improve the evaluator over time, fine-tune prompts, identify common failure patterns, or eventually train a more accurate model for hospitality-specific AI response QA.

A more complete version could become a QA and monitoring layer that reviews AI guest responses before they are sent and helps identify recurring failure modes in the AI system.
