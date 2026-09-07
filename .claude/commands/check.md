Run the verifier for whichever step the person is on and translate the result into plain English.
For someone who isn't comfortable in a terminal, lead with this, don't wait to be told.

1. Run `python3 verify.py` to see the status board, then `python3 verify.py <step>` for their
   current step. The steps are `1.2`, `1.3`, `1.4` (Build 1), `2.1`, `2.2` (Build 2), `3.1`
   (Build 3), `4.1` (Build 4).
2. If it passes: tell them plainly, and give them the evidence code it printed. That is their
   receipt for the step. There is nothing to upload and nothing to push.
3. Then point them at `python3 readout.py`. It is the one-page submission for the build: what the
   agent IS and what it just DID, no upload, nothing to write up.
4. If it fails: read the ✗ lines and hints, and translate. Don't just repeat the tool's own text.
5. If it won't import at all, that's a typo in their edit, not a misunderstanding. Find it, show
   them the one-character fix, move on. Don't turn a stray comma into a teaching moment.
6. If they're stuck on the same step twice in a row, ask a coach and walk the trace with a podmate.
   Two traces of the same step side by side is the fastest diagnosis available in the room. Do not
   paste a teammate's `agent.py` in as the fix. That clears the gate and teaches nothing, and the
   next gate will find them out.
7. End every run with the single next command to type, on its own line.
