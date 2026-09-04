# Larkspur disruption agent — spec

Copy this to `spec/<your-name>.md` and fill it in there. This file is the
template; leave it as it is so the next person has one.

```bash
cp spec/example.md spec/your-name.md
```

Fill in each blank *before* you touch `agent.py` for that step — in your own
words, not Claude's. `/coach` will ask what your file says before it helps you
write code, and if a section is empty, that's the problem to fix first.

## Step 2 — Tool schemas

`search_alternatives`'s description in `agent.py` currently says `"search"`.
Before you rewrite it:

**When should Claude call this tool?**


**What does it need to already know? What does it NOT need to pass in, and why?**
(hint: it takes only a `pnr` — where does the rest come from?)


**What does a result look like, and what should Claude do with it?**


## Step 3 — The agentic loop

Run `python3 run.py K7PQ2M --trace` before you write anything.

**In your own words, what does the trace show is missing?**


**What has to happen after a turn where `stop_reason == "tool_use"`, in order?**
1.
2.
3.
4.

## Step 4 — Prove it generalizes

**Why isn't "it worked on K7PQ2M" the same claim as "the loop works"?**


**If one of the five Stage 1 shapes fails and the other four pass, what does
that tell you — and what wouldn't it tell you?**


## Step 4 — stretch: where the context went

Only if you cleared the gate early. Open the `readout.html` your pod just
pushed and find the turn with the largest tokens-in.

**Why was that turn the most expensive one, and what would have to change for
turn 5 to cost less than turn 4?**

