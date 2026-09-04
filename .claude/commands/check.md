Run the verifier for whichever step the person is on and translate the result into plain English.
For someone who isn't comfortable in a terminal — lead with this, don't wait to be told.

1. Run `python3 verify.py` to see the status board, then `python3 verify.py <n>` for their current step.
2. If it passes: tell them plainly, and give them the evidence code to type into the site. Say which
   code it is. `verify.py` mints their PERSONAL code — it is different for every person in the pod,
   because the site tracks individuals inside a pod. The POD code is the other one, it comes from
   `python3 ready.py`, and it is identical across the whole pod. Two people comparing a personal
   code and finding it different have found nothing wrong.
3. Then point them at `python3 readout.py`. It is the one-page submission for the block: what the
   agent IS and what it just DID, no upload, nothing to write up.
4. If it fails: read the ✗ lines and hints, and translate — don't just repeat the tool's own text.
5. If it won't import at all — that's a typo in their edit, not a misunderstanding. Find it, show
   them the one-character fix, move on. Don't turn a stray comma into a teaching moment.
6. If they're stuck on the same step twice in a row, ask a coach and walk the trace with a podmate.
   Two traces of the same step side by side is the fastest diagnosis available in the room. Do not
   paste a teammate's `agent.py` in as the fix — that clears the gate and teaches nothing, and the
   next gate will find them out.
7. End every run with the single next command to type, on its own line.
