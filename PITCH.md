# PITCH.md

Six lines and a lever. Your words. The last two are scored.

Built: Policy-grounded disruption rebooking agent.
Does: Gets disrupted passengers to a safe rebooking choice fast.
Number: $0.0555 model cost per resolved contact (stage 2, 5 shapes, 3 runs each), about $760/week at 13,700 chats/week versus $94,530 for humans.
Guardrail: Never invent, and never commit without the customer's click.
Next: Expand autonomy only where the gates stay provably intact.
Still broken: next_available_day ignores group size, so it answers for a single passenger even on a group booking.
Lever: intelligence

## Priya asked

Costs: Far below the $6.90 human-handled contact cost at scale (about $0.0555 model cost per contact here).
Wrong: Fail closed: on anything it cannot safely resolve it takes no irreversible action and surfaces the failure for review. The irrv-0101 hard gate proves it, passing on every run, so it never commits a rebooking without the customer's own click.
Runs it: Larkspur operations owns it, with engineering accountable for the agent, and every out-of-scope or unsafe case routes through escalate_to_human onto the ops queue for a named human to pick up.
Left out: Group bookings, unsupported exceptions, and cases the agent cannot resolve with authoritative data.
