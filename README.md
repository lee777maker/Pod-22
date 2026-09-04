# Larkspur disruption agent — the pod repo

A multi-tool disruption-care agent for Larkspur Airlines, built against nine
tools that already work (`support/tools.py`, backed by real airline fixture
data in `data/americas/`). Your job is `agent.py`: the tool schemas Claude
sees, and the loop that drives them.

Five to seven people share this one repo. Read "One repo, five to seven
people" below before the first build, because it is the part that goes wrong.

---

## Before the session (pre-work)

On your own laptop, at your own desk, with time to fix what it finds:

```bash
python3 doctor.py            # diagnose this laptop
python3 doctor.py --fix      # if it asks: creates .venv and installs
cp .env.example .env         # paste your key, or skip if you are `ant auth login`-ed in
python3 doctor.py            # until it says READY
```

`doctor.py` checks python, the venv, the SDK, git, a real reach to GitHub, a
credential, and one live call to Claude. Every failure it prints names the fix.

READY on this laptop is the whole pre-work. There is no offline mode: every
block calls the real API, so a credential that does not work is a blocker, not
an inconvenience. If you cannot clear it, say so in the pre-work channel before
the day rather than in the room.

---

## In the room / Block 2

Block 2 turns a set of laptops into a pod. Ten minutes, four steps.

1. **One person creates the pod repo** from the template and shares the URL.
   Private repo? That person adds every podmate as a collaborator, and everyone
   accepts the invite. This is the single most common Block 2 failure.
2. **Everyone clones it.** Clone, do not download the zip: the git history is
   what the checks read.
   ```bash
   git clone <your pod repo URL>
   cd <repo>
   ```
3. **Everyone shakes hands.** One file each, your own commit, pushed by you.
   Fill in `TEAM.md` first: the pod's name, and how many of you there are.
   ```bash
   echo "Your Name" > team/your-name.md
   git add team/ && git commit -m "join: Your Name" && git push
   ```
   One file per person means five people joining at once never collide. The
   commit is the handshake: the roster is something the repo can prove, not
   something one person typed.
4. **Everyone runs ready.py**, then stamps it when green.
   ```bash
   python3 ready.py --name "Your Name"
   python3 ready.py --name "Your Name" --stamp
   ```
   `ready.py` is the Block 2 command. It runs the laptop checks, the pod checks
   and the forward checks for both days in one board, prints your two site
   codes, and `--stamp` pushes your `ready/<you>.md` receipt to the repo.

Two codes come out of this, and they are different on purpose:

- **your personal code** banks your own gates. Different for every person.
- **your POD code** is the Block 2 gate. Identical on every laptop in the pod.
  It is minted from the pod name plus the roster, so if someone joins late,
  everyone re-runs and everyone gets a new one. That is expected.

---

## One repo, five to seven people

The protocol, in one sentence: **nobody commits `agent.py` mid-block; at the
end, the block's committer runs `python3 pod_sync.py --push-canon` and everyone
else runs `python3 pod_sync.py --take-canon`.**

That is it. During the block everyone builds their own `agent.py` on their own
laptop, and nobody pushes it. Five people editing one file in one repo at the
same time produces a merge conflict inside a loop they are all still learning
to read, and no breakout has ever had time for that.

Three things follow from it:

- **`--take-canon` saves your version first**, into `.workshop/mine/`, and
  prints the path. Nothing you wrote is lost, and `diff` against the canon is
  the most useful five minutes of the block.
- **Nobody ever runs `git add readout.html`.** The readout is regenerated and
  committed by `pod_sync.py --push-canon`, and only there. A hand-committed
  readout is a stale one, and it is the half of the submission that says what
  the agent actually did.
- **`python3 pod_sync.py --status`** answers "where is the pod, where am I"
  without anyone reading git output: what the canon is, who pushed it, how many
  handshakes and receipts landed, and what you have banked.

Everything else is a normal commit. `TEAM.md`, `team/`, `ready/`, `CHANGES.md`,
`PITCH.md` and `evals/cases.json` are the pod's shared record, and they do not
thrash the way `agent.py` does.

---

## The four builds

| Build | Block | Gate | What the canon push carries | Who pushes |
|---|---|---|---|---|
| 1 — tool schemas, the loop, prove it generalizes | 5 | `verify.py 2`, `3`, then `4` | `agent.py`, `readout.html` | one person, once the pod agrees whose passed |
| 2 — the tools you decided you need | 7 | `verify.py 7` | `agent.py`, `.workshop/build2_probe.txt`, `readout.html` | the pod's committer for that block |
| 3 — pull your lever, measure it | 13 | `verify.py 5` | `agent.py`, `CHANGES.md`, `readout.html` | the pod's committer for that block |
| 4 — build what the client sees | 15 | `verify.py 6` | `agent.py`, `PITCH.md`, `readout.html` | the pod's committer for that block |

Each build ends the same way:

```bash
python3 verify.py <n>              # the gate, on your own laptop
python3 pod_sync.py --push-canon   # the block's committer, once
python3 pod_sync.py --take-canon   # everyone else
```

`--push-canon` refuses if that gate has not passed on your laptop, because the
canon is the version that passed, not the newest one. `--take-canon` warns if
your own gate has not passed yet, because the block is where the learning is
and the canon is the answer. Out of time? `--take-canon --force` is there, on
purpose, and it still saves your version first.

`python3 verify.py` with no step number prints your status board.

## Ground rule

If you can't explain a turn on your own trace (`python3 run.py <PNR> --trace`),
you haven't finished the step, whatever the verifier says.

## Behind, or something broke?

**The pod repo is the checkpoint.** Whatever the pod last pushed is on GitHub,
and one command puts you back on it:

```bash
python3 pod_sync.py --take-canon --force
```

Know what it does and does not bring back. It restores the committed files:
`agent.py`, the readout, `PITCH.md`, `CHANGES.md`, the roster and the receipts.
It does not restore anything gitignored, and that list matters:

- **`.env`** — your key. Yours, never in the repo. Re-create it from
  `.env.example`.
- **`.venv/`** — rebuild with `python3 doctor.py --fix`.
- **`.workshop/`** — your banked evidence codes and your bench numbers. These
  are not on GitHub and cannot be regenerated: `bench-before.json` is a
  measurement of an agent that no longer exists.

So if you are about to re-clone into a fresh folder, copy `.workshop/` across
first, then copy it back in. If it is already gone, tell a facilitator rather
than re-running `bench.py --label before` against the current agent: that
number would be a fiction, and the whole day 2 claim rests on it.
