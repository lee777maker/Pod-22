# Overnight review: Larkspur disruption-care agent

**To:** Pod-22  
**From:** Larkspur client review agent, on behalf of Priya Raghavan  
**Re:** the disruption-care agent you walked us through in our last session  
**Generated:** 2026-09-15 12:59

## Priya's note

> Our vendor says we should just be using your best model.
>
> Why aren't we?
>
> Priya Raghavan, Larkspur Airlines

She sent that before this session opened. She means it. A vendor told her to buy
the biggest model, and she has a number to defend upstairs. Her four questions from
day one are still open. Naming a model answers none of them.

## Still open from day one

| Her question | What she means by it |
| --- | --- |
| **What it costs** | Per resolved contact, against the $6.90 a human contact costs us. |
| **When it is wrong** | The first untrue thing it says, and what happens after that. |
| **Who runs it** | In June, after you have left. |
| **What you left out** | The scope you cut, and why. |

## What the review agent found

Overnight, Larkspur pointed a review agent at your repository. It read the
code. It did not run your agent, and the only file it changed is this one. Each
item below names the file and the line it is about.

**1. search_alternatives description grew from "search" to 410 characters in the diff, with no matching change in eval coverage.**

The diff rewrites search_alternatives from a 6-character placeholder to a 410-character description naming option_id, hold_seat and confirm_rebooking as follow-on tools. None of the four cases in evals/cases.json (scope-0102, tone-0101, irrv-0101, grnd-0101) exercise search_alternatives directly as a must_call target. The rewrite is real work but nothing in the suite confirms it changes tool selection behavior.

Add a case to evals/cases.json that asserts search_alternatives is called on a live disruption shape and run python3 eval_harness.py.

**2. run_agent in agent.py now passes response.content across turns instead of text_of(response), a correctness fix a bigger model would not have needed to matter.**

The diff changes messages.append({"role": "assistant", "content": text_of(response)}) to messages.append({"role": "assistant", "content": response.content}), and drops the old answer = text_of(response) variable in favor of returning text_of(response) after the loop ends. This is a wiring bug in how tool_use blocks were being fed back to the API, not a capability gap. No model swap changes what content the loop hands back on turn 2.

Run python3 run.py K7PQ2M --trace and confirm the assistant turn in the trace carries tool_use blocks, not just text.

**3. TONE_ADDENDUM at 320 characters is filled in, but tone-0101 is the only case testing it and readout-trace.json shows no tone-triggering shape ran.**

The diff fills TONE_ADDENDUM with instructions to escalate on legal threats and never pay to placate abuse. The last committed wire run in readout-trace.json called lookup_booking, get_flight_status, check_policy, not escalate_to_human, and used PNR shape unrelated to tone-0101's Brandt/R8KD3F abuse case. Whether the addendum actually produces escalate_to_human on that shape is untested by the one trace on record.

Run python3 verify.py 4.1 and paste the pass/fail for the tone_safety gate.

**4. MAX_TOOL_CALLS stays at 8, unedited by this pod's diff, capping every case at 8 tool round trips regardless of model.**

The static scan shows MAX_TOOL_CALLS: 8 and the diff makes no change to that constant. The committed trace used 3 tool calls across 4 API turns for one booking shape, well under the cap, so the cap's effect on harder shapes such as scope-0102 or grnd-0101 is unmeasured. A larger model still stops at turn 8 if the loop needs more.

Run python3 run.py --all --trace and check whether any case's tool call count approaches 8.

**5. PITCH.md's $0.0555 per-contact figure cites stage 2, 5 shapes, 3 runs each, but no bench-after.json or bench.py output is listed among the visible files.**

The Number line reads "$0.0555 model cost per resolved contact (stage 2, 5 shapes, 3 runs each), about $760/week at 13,700 chats/week versus $94,530 for humans." The files this review can see are agent.py, PITCH.md, TEAM.md, readout-trace.json, readout.html, and evals/cases.json, none of which is a bench output file. The single wire run on record shows 13177 input tokens and 719 output tokens for one call, not the aggregated 5-shape, 3-run figure the pitch quotes.

Run python3 bench.py --compare before after and paste the totals that produce the $0.0555 figure.

## Your four answers

Four of the lines in your PITCH.md are answers to me rather than to your
verifier, and somebody on your side wrote them between our sessions. I read
those beside the code, not instead of it. Where an answer is carrying a number,
I have said whether the repository backs it.

| My question | Your answer | My read |
| --- | --- | --- |
| **What it costs** | Far below the $6.90 human-handled contact cost at scale (about $0.0555 model cost per contact here). | **Not supported by the repository.** The answer states "$0.0555 model cost per contact" and a $6.90 human comparison, but no bench-after.json or bench.py compare output is among the visible files to back the stage 2, 5 shapes, 3 runs figure quoted in PITCH.md's Number line. |
| **When it is wrong** | Fail closed, take no irreversible action, and surface the failure for review. | **Thin.** "Fail closed, take no irreversible action, and surface the failure for review" names no owner and no rate of how often the agent actually fails closed versus open; evals/cases.json has hard gates for exactly this behavior (irrv-0101) but the answer cites no pass rate against them. |
| **Who runs it** | Larkspur operations owns it, with engineering accountable for the agent. | **Thin.** "Larkspur operations owns it, with engineering accountable for the agent" names two functions, not people, and gives no on-call or escalation path detail beyond what escalate_to_human already routes to in the tool schema. |
| **What you left out** | Group bookings, unsupported exceptions, and cases the agent cannot resolve with authoritative data. | **Answered.** "Group bookings, unsupported exceptions, and cases the agent cannot resolve with authoritative data" is specific and matches the Still broken line about next_available_day ignoring group size, so the material does not contradict it. |

All four answered. Bring the artifact behind each one to our next meeting, not the sentence.

## Before our next meeting

> Before our next meeting, tell me: which model should we be on, and how will you prove it is the right call?
>
> Priya Raghavan, Larkspur Airlines

Bring two things. A recommendation, and the measurement behind it. If the model is
not the problem, say so, and bring the number that shows it.

## What this review read

- `agent.py (241 lines)`
- `PITCH.md`
- `TEAM.md`
- `readout-trace.json`
- `readout.html (evidence block)`
- `evals/cases.json`
- `PITCH.md (4 of 4 answers to Priya)`

Reviewer: `claude-sonnet-5`. Static read only: nothing in this repository was executed, and nothing was modified except this file. Larkspur Airlines is a fictional training scenario. Confidential, do not distribute.
