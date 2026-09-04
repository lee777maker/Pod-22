# Larkspur disruption agent — the pod repo

A multi-tool disruption-care agent for Larkspur Airlines, built against nine
tools that already work (`support/tools.py`, backed by real airline fixture
data in `data/americas/`). Your job is `agent.py`: the tool schemas Claude
sees, and the loop that drives them.

**The build itself runs on the workshop site** — your facilitator gives you
the link and opens each block with a code. Every step's moves, commands and
gates live there, and the case study (the client, the ask, the five ticket
shapes) is the site's Case tab. This repo carries three things: your setup,
the case data, and the scripts the steps call.

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
   and the forward checks in one board, prints your two site
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
- **Your spec is yours too.** Before the first build,
  `cp spec/example.md spec/your-name.md`, and commit it the way you committed
  your `team/` file. `/coach` asks what YOUR spec says for a step before it
  writes any code — one file per person, same as the roster. See
  `spec/README.md`.

Everything else is a normal commit. `TEAM.md`, `team/`, `ready/`, `spec/`,
`PITCH.md` and `evals/cases.json` are the pod's shared record, and they do not
thrash the way `agent.py` does. `team/`, `ready/` and `spec/` are one file per
person, so five people can push at once and never collide.

---

## The scripts the site's steps call

| Script | What it does |
|---|---|
| `doctor.py` | Pre-work: diagnoses this laptop; `--fix` builds the venv. |
| `ready.py --name "You"` | The wiring check: laptop, pod, session, your two codes. `--stamp` pushes your receipt. |
| `run.py <PNR> --trace` | Runs the agent on one ticket and shows every turn on the wire. `--all` runs the five shapes and writes the totals. |
| `verify.py <n>` | A gate: checks behavior on the wire, prints your evidence code. No number = your status board. |
| `pod_sync.py` | The pod's canon: `--push-canon` (the block's committer), `--take-canon` (everyone else), `--status`. |
| `eval_harness.py` | Runs `evals/cases.json` — your pod's own cases — against your agent. |
| `bench.py --label <name>` | Measures a run: latency, tokens, cache, cost per contact. The before/after pair around your lever. |
| `readout.py` | Renders the one-page readout the canon push publishes. |

Which script, at which moment, with which arguments: the site says so on the
step you are standing on. `evals/cases.json`, `PITCH.md`, `TEAM.md`, `team/`,
`ready/` and `spec/` are the pod's shared record — normal commits. The bench
pair never leaves your laptop: `.workshop/` is gitignored, and
`bench-before.json` is a measurement of an agent that no longer exists.

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
`agent.py`, the readout, `PITCH.md`, the specs, the roster and the receipts.
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
number would be a fiction, and your pod's lever claim rests on it.
