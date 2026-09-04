#!/usr/bin/env python3
"""pod_doctor.py — the pod layer: is this one repo actually wired to N people?

    python3 pod_doctor.py            # check the pod is wired together
    python3 pod_doctor.py --no-live  # skip the live API call (faster re-runs)

You do not normally run this by hand. `ready.py` is the Block 2 command and it
runs these checks for you, alongside the laptop and session ones:

    python3 ready.py --name "Your Name"

This file is the library behind that: doctor.py checks YOUR laptop, this checks
the POD. One shared repo, everyone on it, everyone's first commit through the
remote. The repo's own history is the evidence, so nobody is "on the team"
without a commit that proves it.

What it expects, built in Block 2:
  1. One member creates the pod repo from the template and pushes it.
  2. Everyone else clones it.
  3. EACH member adds their own file, team/<their name>.md, with their name on
     the first line. Their own commit, pushed by them. That commit is the
     handshake, and one file per person means two people joining at once can
     never collide.
  4. TEAM.md declares the pod name and the pod size, so a roster that is short
     one person is a failure the script can see instead of a code that quietly
     means the wrong thing.
  5. Everyone runs `git pull`, then everyone runs ready.py.

Design rule (same as doctor.py): never ends on a stack trace, every failure
names the fix.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import hmac
import os
import re
import subprocess
import sys
from typing import List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

RULE = "─" * 66
TEAM_PATH = os.path.join(HERE, "TEAM.md")
TEAM_DIR = os.path.join(HERE, "team")
SHARED_SECRET = b"larkspur-basecamp-reference-architecture"  # same as verify.py
POD_SIZE = (3, 7)  # smaller than 3 defeats the point; larger than 7 hides people


class Item:
    def __init__(self, ok: bool, label: str, fix: str = "", severity: str = "required") -> None:
        self.ok, self.label, self.fix, self.severity = ok, label, fix, severity


def _git(*args: str, timeout: int = 15) -> Tuple[int, str]:
    try:
        r = subprocess.run(["git", *args], cwd=HERE, capture_output=True,
                           text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except FileNotFoundError:
        return 127, "git is not installed"
    except subprocess.TimeoutExpired:
        return 124, "timed out"


def parse_pod_name() -> Optional[str]:
    """TEAM.md line one: `# Pod: <name>`."""
    if not os.path.exists(TEAM_PATH):
        return None
    with open(TEAM_PATH) as f:
        for line in f:
            m = re.match(r"#\s*Pod\s*:\s*(.+)", line.strip(), re.I)
            if m:
                name = m.group(1).strip()
                return None if name.startswith("<") else name
    return None


def parse_size() -> Optional[int]:
    """TEAM.md line two: `# Size: <n>`. The declared roster size."""
    if not os.path.exists(TEAM_PATH):
        return None
    with open(TEAM_PATH) as f:
        for line in f:
            m = re.match(r"#\s*Size\s*:\s*(\d+)", line.strip(), re.I)
            if m:
                return int(m.group(1))
    return None


def roster() -> List[str]:
    """One file per member in team/. A member file's first non-empty line is
    their display name. One file per person is the whole point: two people
    joining in the same minute touch different files and never conflict."""
    names = []
    for path in sorted(glob.glob(os.path.join(TEAM_DIR, "*.md"))):
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip().lstrip("#").strip()
                    if line:
                        names.append(line)
                        break
        except OSError:
            continue
    return names


def parse_team() -> Tuple[Optional[str], List[str]]:
    """(pod name, roster). Kept as one call because ready.py and readout.py
    both want the pair."""
    return parse_pod_name(), roster()


def pod_code(pod: str, members: List[str]) -> str:
    """Same speed-bump-not-security scheme as verify.py's evidence codes."""
    roster_key = "|".join(sorted(re.sub(r"\s+", " ", m.strip()).lower() for m in members))
    payload = "pod:%s|%s" % (re.sub(r"\s+", " ", pod.strip()).lower(), roster_key)
    digest = hmac.new(SHARED_SECRET, payload.encode(), hashlib.sha256).hexdigest().upper()
    return "POD-%s-%s" % (digest[:3], digest[3:6])


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------

def check_team_file() -> Item:
    pod, size = parse_pod_name(), parse_size()
    if not os.path.exists(TEAM_PATH):
        return Item(False, "TEAM.md exists",
                    "It ships in the template. If it is gone, you are in the wrong folder,\n"
                    "     or someone deleted it. Recreate it with two lines:\n"
                    "       # Pod: <your pod name>\n"
                    "       # Size: <how many people are in this pod>")
    if not pod:
        return Item(False, "TEAM.md names the pod",
                    "First line must be:  # Pod: <name>\n"
                    "     Pick a name, agree it out loud, one person commits it.")
    if size is None:
        return Item(False, "TEAM.md declares the pod size",
                    "Second line must be:  # Size: <n>\n"
                    "     Count the people in the breakout, including yourself. The size is\n"
                    "     what makes a missing handshake visible instead of silent.")
    label = "TEAM.md: pod %r, size %d" % (pod, size)
    lo, hi = POD_SIZE
    if not (lo <= size <= hi):
        return Item(True, label + "  (expected %d-%d)" % (lo, hi), "", "advisory")
    return Item(True, label)


def check_roster() -> Item:
    """The roster is team/, one file per person, and it has to match the size
    TEAM.md declares. A short roster mints a different pod code, so a pod that
    skipped this would hand the site a code that does not match their podmates'
    and never find out why."""
    size = parse_size()
    names = roster()
    if size is None:
        return Item(False, "roster in team/ matches the declared size",
                    "Fix TEAM.md first (above): it has to say  # Size: <n>")
    if not names:
        return Item(False, "roster in team/ matches the declared size (0 of %d)" % size,
                    "Nobody has shaken hands yet. Each member, on their own laptop:\n"
                    "       echo \"Your Name\" > team/your-name.md\n"
                    "       git add team/ && git commit -m \"join: Your Name\" && git push\n"
                    "     Waiting on %d more handshakes — the pod code cannot be minted "
                    "from a partial roster" % size)
    if len(names) < size:
        return Item(False, "roster in team/ matches the declared size (%d of %d)"
                    % (len(names), size),
                    "Here so far: %s\n"
                    "     Waiting on %d more handshakes — the pod code cannot be minted "
                    "from a partial roster\n"
                    "     Missing members: add your own file and push, then everyone runs\n"
                    "       git pull"
                    % (", ".join(names), size - len(names)))
    if len(names) > size:
        return Item(False, "roster in team/ matches the declared size (%d of %d)"
                    % (len(names), size),
                    "More files in team/ than TEAM.md declares. Someone joined late, or\n"
                    "     someone made two files. Fix whichever is true: update  # Size: %d\n"
                    "     in TEAM.md, or delete the duplicate file. Then everyone re-runs."
                    % len(names))
    return Item(True, "roster in team/ matches the declared size (%d of %d)" % (len(names), size))


def check_repo() -> Item:
    code, out = _git("rev-parse", "--is-inside-work-tree")
    if code != 0 or out.split()[-1:] != ["true"]:
        return Item(False, "this folder is a git repo",
                    "The pod repo wasn't cloned — clone it, don't download the zip:\n"
                    "       git clone <your pod repo URL>")
    return Item(True, "git repo present")


def check_remote() -> Item:
    code, out = _git("remote", "get-url", "origin")
    if code != 0:
        return Item(False, "remote 'origin' configured",
                    "No remote — this is a local-only copy. Clone the pod's GitHub repo,\n"
                    "     or: git remote add origin <pod repo URL>")
    return Item(True, "origin: %s" % out)


def check_remote_reachable() -> Item:
    code, out = _git("ls-remote", "--heads", "origin", timeout=20)
    if code != 0:
        return Item(False, "origin reachable",
                    "If the repo is private, the creator has to add you as a collaborator —\n"
                    "     that is the usual answer, not your SSH key. Whoever made the repo:\n"
                    "     Settings, Collaborators, add every podmate, and they accept the invite.\n"
                    "     Still failing after that? git said: %s"
                    % (out.splitlines()[-1] if out else "no response"))
    return Item(True, "origin reachable")


def check_up_to_date() -> Item:
    code, _ = _git("fetch", "-q", "origin", timeout=30)
    if code != 0:
        return Item(False, "fetched latest from origin", "git fetch failed — see the check above.")
    code, upstream = _git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if code != 0:
        # No upstream configured for this branch — count against origin's default
        code, head = _git("symbolic-ref", "refs/remotes/origin/HEAD", "--short")
        upstream = head if code == 0 else "origin/main"
    code, out = _git("rev-list", "--left-right", "--count", "HEAD...%s" % upstream)
    if code != 0:
        return Item(True, "up to date with %s (could not compare)" % upstream, "", "advisory")
    ahead, behind = (out.split() + ["0", "0"])[:2]
    if behind != "0":
        return Item(False, "up to date with %s" % upstream,
                    "You're %s commit(s) behind — someone's handshake isn't on this laptop yet:\n"
                    "       git pull" % behind)
    label = "up to date with %s" % upstream
    if ahead != "0":
        return Item(True, label + "  (%s local commit(s) not pushed yet: git push)" % ahead,
                    "", "advisory")
    return Item(True, label)


def check_handshakes() -> Item:
    """The check-and-balance: N member files need N distinct committers, and
    those commits have to have made it through the remote — so 'on the team'
    is something the repo can prove, not something one person typed."""
    names = roster()
    if not names:
        return Item(False, "one commit per member in team/", "Fix the roster first (above).")
    # team/*.md, not team/: the directory ships with a .gitkeep, and whoever
    # created the repo committed that. A .gitkeep is not a handshake.
    code, out = _git("log", "--remotes=origin", "--format=%an", "--", "team/*.md")
    if code != 0 or not out:
        return Item(False, "one commit per member in team/",
                    "No team/ commits on origin yet. Each member, from their own laptop:\n"
                    "       echo \"Your Name\" > team/your-name.md\n"
                    "       git add team/ && git commit -m \"join: Your Name\" && git push")
    authors = sorted(set(out.splitlines()))
    if len(authors) < len(names):
        return Item(False,
                    "one commit per member in team/ (%d committer(s) for %d name(s))"
                    % (len(authors), len(names)),
                    "Committers so far: %s\n"
                    "     A file someone else committed isn't a handshake. Missing members:\n"
                    "     add your OWN file in your OWN commit, from your OWN laptop, and push.\n"
                    "     If two people share a laptop, git config user.name has to change\n"
                    "     between the two commits."
                    % ", ".join(authors))
    return Item(True, "one commit per member in team/ (%d distinct committers)" % len(authors))


def check_my_seat(live: bool) -> Item:
    """This laptop still has to work on its own — pod wiring doesn't fix a
    broken env. Reuses doctor.py's own required checks verbatim."""
    try:
        import doctor
    except ImportError as exc:
        return Item(False, "this laptop passes doctor.py", str(exc))
    items = doctor.run_checks(quiet=True, live=live)
    bad = [i for i in items if not i.ok]
    if bad:
        return Item(False, "this laptop passes doctor.py",
                    "Failing: %s\n     Run `python3 doctor.py` for the full fixes."
                    % "; ".join(i.label for i in bad))
    return Item(True, "this laptop passes doctor.py (%d checks%s)"
                % (len(items), ", incl. live API call" if live else ""))


def pod_checks() -> List[Item]:
    """The pod layer on its own, in dependency order. ready.py runs exactly
    this list, so the two commands can never drift apart."""
    return [check_team_file(), check_repo(), check_remote(), check_remote_reachable(),
            check_up_to_date(), check_roster(), check_handshakes()]


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Check the pod is wired together.")
    parser.add_argument("--no-live", action="store_true", help="skip the live API call")
    args = parser.parse_args()

    print("\n%s\nLARKSPUR POD DOCTOR\n%s" % (RULE, RULE))
    items = pod_checks() + [check_my_seat(live=not args.no_live)]
    for item in items:
        mark = "  ✓" if item.ok else ("  !" if item.severity == "advisory" else "  ✗")
        print("%s %s" % (mark, item.label))
        if not item.ok and item.fix:
            for line in item.fix.splitlines():
                print("      %s" % line)

    blocking = [i for i in items if not i.ok and i.severity == "required"]
    print("\n" + RULE)
    if blocking:
        print("POD NOT WIRED — %d check(s) to fix, top to bottom, then re-run." % len(blocking))
        print("This has to pass on EVERY laptop, not just one.")
        print("No pod code until it does: a code minted from a partial roster is the")
        print("wrong code, and it would not match your podmates'.")
        print(RULE)
        return 1
    pod, members = parse_team()
    print("POD WIRED — %s, %d members, everyone's handshake is on the remote." % (pod, len(members)))
    print("Pod evidence code:  %s   (same code on every laptop — that's the point)" % pod_code(pod, members))
    print("This code is minted from the roster. If someone joins late, everyone")
    print("re-runs and gets a new one — that is expected.")
    print("Enter it on the workshop site.")
    print(RULE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
