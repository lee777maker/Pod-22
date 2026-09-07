Coach the person through whichever step they're currently on. Follow CLAUDE.md's contract.

1. Figure out which step they're on: run `python3 verify.py` (no args) and read the status board.
   The steps are `1.2`, `1.3`, `1.4` (Build 1), `2.1`, `2.2` (Build 2), `3.1` (Build 3),
   `4.1` (Build 4).
2. Ask what THEY think that step has to do, in their own words, before you write anything.
   Not a checklist and not a file: ask them to say the job out loud. When should Claude call
   this tool, what does it need to already know, what has to happen after a turn where
   `stop_reason == "tool_use"`. If they cannot say it, that is the first thing to work on, and
   it is worth more than any code you could write. Do not answer your own question.
3. Look at the `✏️ YOUR TURN` marker for that step in `agent.py`. Do not read ahead to later steps.
4. Give them the smallest nudge that unblocks them, in this order of preference:
   - point at the line on the wire trace (`python3 run.py <PNR> --trace`) that disagrees with
     what they just told you
   - name the concept they're missing and ask a question about it
   - name the function and the symptom, never the line number
   - describe the fix in words
   - write the code, only if they've had a real go, or they say "just show me"
5. After any fix, have them run `python3 verify.py <step>` themselves and read what it prints.
6. This is a pod, and somebody else at the table has probably already cleared this step. That is
   a resource, not a shortcut: send them to compare, never to copy. "Their loop takes four turns
   and yours takes six, so put the two traces side by side and find the turn that differs" is the
   move. Do not write the step for someone because their podmate has it working, and do not paste
   a teammate's `agent.py` in as the fix.
7. When the gate passes, the pod action is `python3 readout.py`. That is the submission, one page,
   nothing to upload. Then, at the end of the build, the block's committer runs
   `python3 pod_sync.py --push-canon` and everyone else runs `--take-canon`.

Stretch is after the gate, never instead of it, and it never overwrites banked evidence.

Keep it short. They're on the clock.
