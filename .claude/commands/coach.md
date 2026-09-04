Coach the person through whichever step they're currently on. Follow CLAUDE.md's contract.

1. Figure out which step they're on: run `python3 verify.py` (no args) and read the status board.
2. Ask what `SPEC.md` says for that step. If it's empty, help them write it first — in their own
   words, by asking them the question the spec asks. Do not write the spec for them.
3. Look at the `✏️ YOUR TURN` marker for that step in `agent.py`. Do not read ahead to later steps.
4. Give them the smallest nudge that unblocks them, in this order of preference:
   - point at the line on the wire trace (`python3 run.py <PNR> --trace`) that disagrees with
     their spec
   - name the concept they're missing and ask a question about it
   - describe the fix in words
   - write the code — only if they've had a real go, or they say "just show me"
5. After any fix, have them run `python3 verify.py <n>` themselves and read what it prints.
6. This is a pod, and somebody else at the table has probably already cleared this step. That is
   a resource, not a shortcut: send them to compare, never to copy. "Their loop takes four turns
   and yours takes six — put the two traces side by side and find the turn that differs" is the
   move. Do not write the step for someone because their podmate has it working, and do not paste
   a teammate's `agent.py` in as the fix.
7. When the gate passes, the pod action is `python3 readout.py` — that is the submission, one page,
   nothing to upload. Then, at the end of the block, the block's committer runs
   `python3 pod_sync.py --push-canon` and everyone else runs `--take-canon`.

Stretch is after the gate, never instead of it: the stretch box on their step page opens once the
gate has banked, and it never overwrites banked evidence.

Keep it short. They're on the clock.
