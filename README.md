# Larkspur disruption agent: the pod repo

A multi-tool disruption-care agent for Larkspur Airlines, built against nine
tools that already work (`support/tools.py`, backed by real airline fixture
data in `data/americas/`). Your job is `agent.py`: the tool schemas Claude
sees, and the loop that drives them.

**Open `guide/index.html` for the steps.** It is the build, page by page: what
you are building, what to do, what it looks like when it worked, and where to
look when it did not. `guide/Larkspur-Build-Guide.pdf` is the same thing on
paper.

## The four commands

That is the whole path. Nothing else is ceremony you have to remember.

```bash
git clone <your pod repo URL>      # once
python3 setup.py                   # until it says READY
python3 run.py K7PQ2M --trace      # every build
python3 verify.py 1.2              # every gate
```

`setup.py` checks python, the SDK, git, a real reach to the pod repo, and one
live call to Claude. Every failure it prints names the fix. Run it at your own
desk, with time to fix what it finds: there is no offline path in this pack, so
a credential that does not work is a blocker, not an inconvenience.

`run.py` shows the wire. `verify.py` checks behaviour on the wire and prints
your evidence code. No number gives you your status board.

## One repo, several people

The rule, in one sentence: **nobody commits `agent.py` mid-build. At the end,
the block's committer runs `python3 pod_sync.py --push-canon` and everyone else
runs `python3 pod_sync.py --take-canon`.**

Everyone builds their own `agent.py` on their own laptop. Several people
editing one file in one repo at the same time produces a merge conflict inside
a loop they are all still learning to read, and no breakout has time for that.

`--take-canon` saves your version to `.workshop/mine/` first and prints the
path. Nothing you wrote is lost, and `diff` against the canon is the most
useful five minutes of the build.

Behind, or something broke? The pod repo is the checkpoint:

```bash
python3 pod_sync.py --take-canon --force
```

It restores what the pod pushed. It does not restore anything gitignored, and
that list matters:

- **`.env`**: your key. Yours, never in the repo. Re-create it from
  `.env.example`.
- **`.venv/`**: rebuild with `python3 setup.py --fix`.
- **`.workshop/`**: your banked codes and your bench numbers. Not on GitHub,
  and `bench-before.json` is a measurement of an agent that no longer exists.

So copy `.workshop/` across before you re-clone into a fresh folder, and copy
it back in after. If it is already gone, say so rather than re-running
`bench.py --label before` against the current agent. That number would be a
fiction, and your pod's claim rests on it.

## The scripts

| Script | What it does |
|---|---|
| `setup.py` | Checks this seat. `--fix` builds the venv and installs. Run it until READY. |
| `run.py <PNR> --trace` | Runs the agent on one ticket and shows every turn on the wire. `--all` runs the five shapes and writes the totals. |
| `verify.py <step>` | A gate: `1.2`, `1.3`, `1.4`, `2.1`, `2.2`, `3.1`, `4.1`. No step gives you the status board. |
| `pod_sync.py` | The pod's canon: `--push-canon`, `--take-canon`, `--status`. |
| `eval_harness.py` | Runs `evals/cases.json`, your pod's own cases, against your agent. |
| `bench.py --label <name>` | Measures a run: latency, tokens, cache, cost per contact. The before/after pair around your lever. |
| `readout.py` | Renders the one-page readout the canon push publishes. |

`TEAM.md` is the pod's name and a typed roster, written once by whoever created
the repo. `PITCH.md` and `evals/cases.json` are the pod's shared record, and
they are normal commits. The bench pair never leaves your laptop.

## Ground rule

If you cannot explain a turn on your own trace (`python3 run.py <PNR>
--trace`), you have not finished the step, whatever the verifier says.
