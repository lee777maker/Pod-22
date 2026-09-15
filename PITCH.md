# PITCH.md

Six lines and a lever. Your words. The last two are scored.

Built: A disruption-care chat agent for Larkspur Airlines on the Claude Messages API: nine in-process tools plus two served over MCP, driven by a tool loop.
Does: Looks up the booking, checks live flight status and applies policy, then resolves the disruption with rebooking options, care and vouchers, and escalates to a human when the request is out of scope.
Number: $0.0555 model cost per resolved contact (stage 2, 5 shapes, 3 runs each), about $760/week at 13,700 chats/week versus $94,530 for humans.
Guardrail: Irreversible actions require the customer's own confirm-click; a "yes" typed in chat is never a valid confirmation token.
Next: Pass group size into next_available_day so it stops answering for a party of one.
Still broken: next_available_day ignores group size, so it answers for a single passenger even on a group booking.
Lever: intelligence

## Priya asked

Costs: About $760/week at Larkspur volume (model cost only), against roughly $94,530/week to handle the same chats with people.
Wrong: On abuse or a legal threat it stays calm and escalates to a human instead of placating; on an out-of-scope request it hands off rather than guessing.
Runs it: Larkspur's disruption-care team, with escalations landing on a human agent's queue.
Left out: Refunds, group bookings, unaccompanied minors and partner segments are all escalated, not handled.
