---
name: detect-chinese-sms-risk
description: Analyze Chinese SMS, chat messages, and notification text for fraud or spam risk. Use when a user asks whether a Chinese message is suspicious, wants an explainable risk assessment, or needs several Chinese messages triaged.
---

# Detect Chinese SMS Risk

Use the bundled detector to produce a model-backed, explainable assessment. Treat the result as decision support, not definitive proof.

## Workflow

1. Run:

   ```bash
   python scripts/predict_sms.py "message text"
   ```

   From outside the skill directory, use the absolute script path.

2. Report:
   - final label and risk probability
   - model and policy probabilities
   - matched risk categories
   - a short explanation and recommended verification step

3. For multiple messages, run the script separately for each message and summarize the highest-risk items first.

4. If the result conflicts with obvious context, state the uncertainty. Review [references/risk-patterns.md](references/risk-patterns.md) when explaining policy evidence.

## Safety

- Do not claim the detector proves fraud.
- Do not send, click, call, transfer funds, or expose private information based on a message.
- Recommend verification through an independently sourced official channel.
- Avoid repeating sensitive personal data unnecessarily.
