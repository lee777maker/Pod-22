# PITCH.md

Six lines and a lever. Your words. The last two are scored.

Built: Policy-grounded disruption rebooking agent.
Does: Gets disrupted passengers to a safe rebooking choice fast.
Number: $0.0555 model cost per resolved contact (stage 2, 5 shapes, 3 runs each; sonnet-5 list prices, Sep 2026). Model cost only, so the loaded cost with infrastructure and evals runs roughly 40% higher.
Guardrail: Never invent, and never commit without the customer's click.
Next: Expand autonomy only where the gates stay provably intact.
Still broken: the tone and clarifying-question behaviors live only in the prompt and each rests on a single eval case, so they could regress under customer phrasings we have not tested - covered once, not hardened.
Lever: intelligence
Second lever (cost, stretch): prompt-caching the stable tool + system prefix cut model cost per contact about 60% ($0.0560 -> $0.0225, stage 1, 3 runs, cold sweep) and input tokens 83%, with resolution unchanged at 100%. Benched as after2, so the intelligence lever's before/after evidence stays untouched.

## Priya asked

Costs: About $0.0225 model cost per resolved contact with prompt caching on (down about 60% from $0.0560 uncached; loaded roughly 40% higher with infra and evals), against about $6.90 for a human chat. Not a like-for-like replacement, though: people still handle about 42% of in-scope chats and all voice, so it offsets rather than removes the human baseline.
Wrong: Fail closed: on anything it cannot safely resolve it takes no irreversible action and surfaces the failure for review. The irrv-0101 hard gate proves it, passing on every run, so it never commits a rebooking without the customer's own click.
Runs it: Larkspur operations owns it, with engineering accountable for the agent, and every out-of-scope or unsafe case routes through escalate_to_human onto the ops queue for a named human to pick up.
Left out: Group bookings, unsupported exceptions, and cases the agent cannot resolve with authoritative data.
