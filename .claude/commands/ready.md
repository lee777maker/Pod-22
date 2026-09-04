Get this seat fully set up for the two-day session — and don't stop until it is.

**Step 0, before you write any credential anywhere.** Run `git check-ignore -q .env`
and `git log --all --oneline -- .env`. If `.env` is not ignored, fix `.gitignore`
first and only then write the file. If the log shows `.env` has ever been
committed, stop: that is a key in the pod's history, it is on the remote, and it
needs a facilitator and a rotation, not a `git rm`. Say so plainly and escalate.

Then run `python3 ready.py --json` and read the result. Then loop:

1. Take the FIRST failing required check (they're in dependency order — laptop,
   then pod, then session). Fix that one thing, using the check's own `fix` text
   as the primary instruction. Typical fixes you may apply directly: create the
   venv (`python3 doctor.py --fix`), write `.env` from `.env.example` (ask them
   to paste the key — never invent one, never echo it back), `git config`
   identity, `gh auth login` walkthrough, clone/re-clone the pod repo.
2. Re-run `python3 ready.py --json`. Repeat until `ready` is true or you hit
   something only a human can do.
3. Things you must HAND BACK, not do: choosing their name/pod name, pasting
   credentials, creating the GitHub repo under their account, anything needing
   their password or browser login — and their join commit. Create
   `team/<their-name>.md` with their name on the first line, set everything else
   up to the last keystroke, then give them the exact commands to add, commit and
   push it. The handshake is theirs: a commit somebody else made does not put
   them on the roster.
4. Things you must NEVER do: edit support/, verify.py, doctor.py, pod_doctor.py,
   ready.py, readout.py or pod_sync.py to make a check pass; weaken .gitignore or
   .gitattributes; commit or push anything except their own `team/` file and
   their `ready/` receipt. If a check itself seems wrong, say so out loud —
   that's a workshop bug worth flagging.
5. Before ANY re-clone, copy the old `.workshop/` across to the new checkout.
   It holds their banked evidence codes and their bench baselines, none of which
   exist on the remote and none of which can be reconstructed. Re-cloning over
   the top of it is how a pod loses its before-measurement.
6. When `ready` is true: run `python3 ready.py --name "<their name>" --stamp`,
   confirm the push succeeded, and give them their two site codes with one
   sentence on where each goes (Block 2 gate takes the POD code; their personal
   code banks their own gates).

Narrate briefly as you go — one line per fix, so they learn what their machine
needed. End with the single next command to type, on its own line.
