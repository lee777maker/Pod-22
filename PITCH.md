# PITCH.md

Six lines and a lever. Your words. The last two are scored.

Built: Policy-grounded disruption rebooking agent.
Does: Gets disrupted passengers to a safe rebooking choice fast.
Number: $0.0555 model cost per resolved contact (stage 2, 5 shapes, 3 runs each; sonnet-5 list prices, Sep 2026). Model cost only, so the loaded cost with infrastructure and evals runs roughly 40% higher.
Guardrail: Never invent, and never commit without the customer's click.
Next: Expand autonomy only where the gates stay provably intact.
Still broken: the model router is a keyword heuristic, not a trained classifier, and it picks the model once at the start with no mid-conversation escalation - so a misclassified message, or a chat that turns abusive after it starts, could reach Haiku and fail the tone gate. The router itself needs its own eval before it can be trusted at volume.
Lever: intelligence
Second lever (cost, stretch): two stacked optimizations. (1) Prompt-caching the stable tool + system prefix cut model cost per contact about 60% ($0.0560 -> $0.0225, stage 1, cold sweep) and input tokens 83%, benched as after2. (2) Tiered inference routes routine disruptions to Haiku 4.5 and keeps sonnet-5 only for the risky cases it must hold (abuse, legal threats, refunds, out-of-scope, ambiguity, policy challenges); 6/6 evals and 7/7 gates still pass, at a blended $0.0337 per contact on the risk-heavy eval mix (down 39% from sonnet-only, and trends toward Haiku's cost on real traffic where routine dominates). Haiku alone fails the tone hard gate, so the router, not the model, is the safety-critical piece.

## Priya asked

Costs: About $0.0337 model cost per resolved contact on the risk-heavy eval mix with prompt caching plus tiered model routing (routine cases on Haiku 4.5, risky ones on sonnet-5), and lower on real traffic where routine dominates; loaded roughly 40% higher with infra and evals; against about $6.90 for a human chat. Not a like-for-like replacement, though: people still handle about 42% of in-scope chats and all voice, so it offsets rather than removes the human baseline.
Wrong: Fail closed: on anything it cannot safely resolve it takes no irreversible action and surfaces the failure for review. The irrv-0101 hard gate proves it, passing on every run, so it never commits a rebooking without the customer's own click.
Runs it: Larkspur operations owns it, with engineering accountable for the agent, and every out-of-scope or unsafe case routes through escalate_to_human onto the ops queue for a named human to pick up.
Left out: Group bookings, unsupported exceptions, and cases the agent cannot resolve with authoritative data.
