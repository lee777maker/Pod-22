# spec/ — one file per person

This folder is the actual exercise. Before you touch `agent.py` for a step, you
write down what you are about to build — in your own words, not Claude's.

**One file each, your own commit, same as `team/` and `ready/`.**

```bash
cp spec/example.md spec/your-name.md
# fill it in as you go
git add spec/your-name.md && git commit -m "spec: Your Name" && git push
```

Your file is `spec/<your-name>.md`. Nobody else writes in it and you do not
write in anybody else's, so five people specifying the same agent at the same
time never collide — and at the end of the block the pod has five specs to
compare, which is a better conversation than one shared file could ever have
produced.

## Why it is per person

The spec is the thing a vague tool description traces back to. If six people
share one file, one person writes it and five people inherit it, and the gate
that catches a vague description catches it in somebody else's words. Two
people who specified `search_alternatives` differently and got different
routing have the sharpest question in the room; one file cannot hold that.

## How it is used

- `/coach` asks what YOUR spec says for the step you are on before it helps you
  write code. An empty section is the problem to fix first — it will ask you the
  question, not answer it.
- `python3 run.py --show-tools` prints what Claude actually receives about each
  tool. Read it back against your own file.
- Nothing in `verify.py` reads this folder. The gate checks the wire; the spec
  is for you.

`spec/example.md` is the template: copy it, don't edit it in place.
