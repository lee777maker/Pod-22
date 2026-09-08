# Five seats, rotating every build

`TEAM.md` is the roster, and the roster order is the seat order. Every build the
seats move down it by one, the same way the committer already does.

Build 1 gives the first seat to the first name. Build 2 gives it to the second
name. It wraps.

    committer      = the Nth name on the roster, for build N, and it wraps
    reader         = the next name after the committer
    trace-caller   = the name after that
    typist         = the name after that
    client chair   = the name after that

Print your pod's seats for a build:

```bash
python3 pod_sync.py --status --build 2
```

## The seats

**Committer.** Pushes the pod's canon at the end of the build:
`python3 pod_sync.py --push-canon`. Everyone else runs `--take-canon`. One
committer per build, because two canon pushes in one build is the conflict the
rotation exists to prevent.

**Reader.** Reads the step aloud off the site before anyone types, and keeps the
pod on the Do list. When two people start solving item 5 while item 2 is
unbuilt, the reader says so.

**Trace-caller.** Runs `python3 run.py <PNR> --trace` and reads the wire out
loud, turn by turn. Give this seat to the least confident person in the pod, on
purpose. Reading the wire out loud is the skill both sessions exist to build,
and the person who needs it most gets it first.

**Typist.** Edits `agent.py` on the shared screen when the pod pairs. Everyone
still has their own `agent.py` on their own laptop and their own gate to bank.
The typist types while the pod is talking through one thing together, and then
everyone goes back to their own file.

**Client chair.** Writes the question a client would ask about what just
changed, before the gate banks, into the pod thread. One question per build, in
the client's words, not the code's. The client chair also owns 5 things the
pod is scored on:

| Where | What the client chair writes |
|---|---|
| 1.4 | The one sentence the five shapes now let the pod claim |
| 2.1 | The probe sentence in `build2_probe.txt` |
| 3.1 | The eval case a client would sign as the bar, with their own name in the `author` field so the gate reads it |
| 4.1 | The caveat, written before anyone benches |
| Pitch | The pitch itself. Six lines in `PITCH.md` |

The client chair is never the same person as the committer. The hand that
publishes the canon and the hand that writes the claim are different hands, in
every pod size below.

## Pods that are not 5

**3 people.** Three seats: committer, trace-caller, client chair. The committer
also reads the step aloud and types.

**4 people.** Four seats: committer, reader, trace-caller, client chair. The
committer types. Drop the typist seat first, because it is the only one that
exists for a pod that is pairing on one screen.

**6 people.** All five seats, and the sixth name is a second trace-caller. Two
people run `--trace` on the same step and put the turn counts side by side. The
turn that differs is the sharpest question in the room.

**7 people.** All five seats, a second trace-caller, and a second client chair.
The two client chairs write their question separately, then pick one for the pod
thread.

**Fewer than 3.** One person holds every seat. Say the step out loud anyway, and
read the trace out loud anyway.

## Ground rule

A seat is a job for the build, not a rank, and it is never a license to watch.
Everyone builds their own `agent.py` and everyone banks their own gate. The
seats decide who talks first, not who works.
