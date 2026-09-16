# PITCH.md

Six lines and a lever. Your words. The last two are scored.

Built: A disruption-care chat agent for Larkspur Airlines that handles cancelled and delayed flights end-to-end.
Does: Looks up the booking, checks live flight status, applies policy, finds rebooking options, and issues vouchers — without a human agent involved for standard disruptions.
Number: 5/5 disruption shapes resolved in 3–4 turns and 2–4 tool calls each, 78k tokens across all five.
Guardrail: Escalates groups, partner segments, unaccompanied minors, and refund requests to a human; never finalises a rebooking without a customer-generated confirmation token.
Next: Tone intelligence — right now the agent responds calmly to abusive messages with no gate on tone at all.
Still broken: R8KD3F (abusive message) gets a calm, helpful resolution with no acknowledgement of the conduct. Build 4 fixes this.
Lever: intelligence

## Priya asked

Costs: 11 tools on every turn adds ~2,900 schema tokens per call regardless of what Claude picks; a busy queue at 50 conversations/hour runs to real API spend fast.
Wrong: A vague tool description misdirects Claude — it calls the wrong tool or skips one, and the customer gets the wrong entitlement.
Runs it: The airline's disruption ops team, with a human escalation queue behind it for out-of-scope cases.
Left out: Multi-passenger rebooking, refund execution, and tone guardrails are not handled — the agent escalates or defers all three.
