# Larkspur disruption agent: the pod repo

A multi-tool disruption-care agent for Larkspur Airlines, built against nine
tools that already work (`support/tools.py`, backed by a frozen copy of real
airline data in `data/americas/`). Your job is `agent.py`: what Claude is told
about each tool, and the loop that drives them.

**Open `guide/index.html` for the steps.** It opens on **Welcome to your
build**, which is the case study, then the three questions your pod answers out
loud, then **Get set up**. After that it is the build page by page: what you are
building, what to do, what it looks like when it worked, and where to look when
it did not. `guide/Larkspur-Build-Guide.pdf` is the same thing on paper.

**The same steps run on the build site**, which your pod opens together in the
room: <https://virtual.partnerbasecamp.com/build/>. It opens on the welcome too,
and those three pages sit at the top of the left spine under **Start**, with a
standing **Get set up** button in the right-hand panel so a laptop that breaks
later can find it. It adds the build clock, a checklist per step, the
end-of-build ritual, and the box where you paste the evidence code a gate
prints. Nothing uploads either way. Pick your surface once on Get set up and it
stays picked.

**Nobody in the pod has an assigned job.** You decide in the moment who does
what. One rule holds: one person pushes the canon at the end of the build.
Agree who before the clock runs out. Everyone else takes it.

## The five commands

That is the whole path. Nothing else has to be held in your head.

```bash
git clone <your pod repo URL>      # once
python3 setup.py                   # until it says READY
python3 run.py K7PQ2M --trace      # every build
python3 verify.py 1.2              # every gate
python3 pod_sync.py --take-canon   # at the end of a build
```

`setup.py` checks python, the SDK, git, a real reach to the pod repo, and one
live call to Claude. Every failure it prints names the fix. Run it at your own
desk: there is no offline path in this pack, so a credential that does not work
is a blocker, not an inconvenience.

`run.py` shows the wire: every request and reply, exactly as it went. `verify.py`
checks behavior on the wire and prints your evidence code. `claude` in this folder gives you `/setup`, `/build`,
`/check` and `/readout`, which is the shortest path in if you would rather not
lead with a terminal.

## One repo, several people

One person in the pod makes this repo from the template the room lead posts in
chat: **Use this template**, then **Create a new repository**, owner their own
account, Private. Then **Settings**, **Collaborators**, **Add people** for every
podmate by GitHub username, plus the room lead's handle, which is in the chat.
That handle is how the overnight review reaches your repo: it is written in from
outside, into the repo you shared, and a repo nobody shared gets no file. Then
they post the repo URL in the pod thread, and nobody else does anything until it
is there.

Everyone else has an invitation email waiting. Accept it before you try to
clone, because a private repo refuses you until you do. Clone it rather than
downloading a zip, because the checks read git history.

The rule, in one sentence: **nobody commits `agent.py` mid-build. One person
pushes the canon at the end of the build with `python3 pod_sync.py
--push-canon`. Agree who before the clock runs out. Everyone else takes it with
`python3 pod_sync.py --take-canon`.**

Everyone builds their own `agent.py` on their own laptop. Several people
editing one file in one repo at once produces a merge conflict inside a loop
they are all still learning to read, and no build has time for that.

`--take-canon` saves your version to `.workshop/mine/` first and prints the
path. Nothing you wrote is lost, and `diff` against the canon is the most
useful five minutes of the build. Behind, or something broke? The pod repo is
the checkpoint:

```bash
python3 pod_sync.py --take-canon --force
```

It restores what the pod pushed. It does not restore anything gitignored: your
`.env` (re-create it from `.env.example`), `.venv/` (rebuild with
`python3 setup.py --fix`), and `.workshop/`, which holds your banked codes and
your bench numbers. So copy `.workshop/` across before you re-clone into a
fresh folder, and copy it back in after. If it is already gone, say so rather
than re-running `bench.py --label before` against the current agent.

## The scripts

| Script | What it does |
|---|---|
| `setup.py` | Checks this machine. `--fix` builds the venv and installs. Run it until READY. |
| `run.py <PNR> --trace` | Runs the agent on one ticket and shows every turn on the wire. `--all` runs the five shapes and writes the totals. |
| `verify.py <step>` | A gate: `1.2`, `1.3`, `1.4`, `2.1`, `2.2`, `3.1`, `4.1`. Run it with no step and it prints the status board. |
| `pod_sync.py` | The pod's canon: `--push-canon`, `--take-canon`, `--status`. |
| `eval_harness.py` | Runs `evals/cases.json`, your pod's own cases, against your agent. |
| `bench.py --label <name>` | Measures a run: latency, tokens, cache, cost per contact. The before/after pair around your lever. |
| `readout.py` | Writes the one page that says what your agent is and what it just did. The canon push publishes it. |

`TEAM.md` is the pod's name and a typed roster, written once by whoever created
the repo. The review reads the names off it. `PITCH.md` and `evals/cases.json`
are the pod's shared record, and they are normal commits. The bench pair never
leaves your laptop.

## Ground rule

If you cannot explain a turn on your own trace (`python3 run.py <PNR>
--trace`), you have not finished the step, whatever the gate says.
