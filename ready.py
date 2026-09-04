#!/usr/bin/env python3
"""ready.py — one command that proves you're set up for both sessions.

    python3 ready.py --name "Your Name"          # the full readiness board
    python3 ready.py --json                      # machine-readable, for Claude Code
    python3 ready.py --name "Your Name" --stamp  # green? push your READY receipt
    python3 ready.py --no-live                   # skip the live API call

This is the Block 2 command. Run it in the breakout, on your own laptop, after
you have cloned the pod repo and pushed your team/<you>.md handshake.

Don't want to fix things by hand? Run `claude` in this folder and say `/ready` —
Claude Code will run this script, fix what it can, and re-run until it's green.

Four sections, in dependency order:
  LAPTOP   — doctor.py's checks: python, venv, SDK, network, credential, live call
  POD      — pod_doctor.py's checks: shared repo, remote, roster, one commit each
  SESSION  — everything BOTH SESSIONS need, checked now while there's time to
             fix it: .env can't leak, every harness script compiles, fixtures
             load, git identity is set, you can actually push, Claude Code is here
  SITE     — the two codes the workshop site asks for, printed when earned

Green all the way down means nothing about your setup can surprise you mid-build.
`--stamp` then pushes a READY receipt to the pod repo, one file of your own, so
the facilitation team can see in the repo itself that this seat is good.

Design rule (inherited from doctor.py): never ends on a stack trace, every
failure names the fix.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

RULE = "─" * 66
COMPILE_FILES = ["agent.py", "run.py", "verify.py", "bench.py", "eval_harness.py",
                 "readout.py", "doctor.py", "pod_doctor.py", "pod_sync.py"]
# The names every later block reaches for. verify.py, readout.py and bench.py all
# import agent and expect these; a missing one shows up as a confusing failure
# three blocks later, so it is cheaper to catch it here.
AGENT_ATTRS = ["build_tools", "run_agent", "MAX_TOOL_CALLS", "EXTRA_TOOLS",
               "TONE_ADDENDUM", "LOCAL_TOOLS"]
READY_DIR = os.path.join(HERE, "ready")


def _git(*args, timeout=20):
    try:
        r = subprocess.run(["git", *args], cwd=HERE, capture_output=True, text=True,
                           timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except FileNotFoundError:
        return 127, "git is not installed"
    except subprocess.TimeoutExpired:
        return 124, "timed out"


def slug(name):
    """A filename that is one person and cannot collide with a real name."""
    s = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return s or "member"


class C:
    """One check result, with a stable id so an agent can track it across runs."""
    def __init__(self, id, ok, label, fix="", severity="required"):
        self.id, self.ok, self.label, self.fix, self.severity = id, ok, label, fix, severity


# ---------------------------------------------------------------------------
# SESSION — forward checks: what BOTH sessions will need
# ---------------------------------------------------------------------------

def check_env_ignored():
    """First, before anything else. A key in the repo is the one mistake here
    that follows you home."""
    code, _ = _git("check-ignore", "-q", ".env")
    if code != 0:
        return C("session.envleak", False, ".env is gitignored",
                 "Your API key would go to GitHub on the next push. Add `.env` to .gitignore\n"
                 "     before anything else, and tell a facilitator if it was ever pushed.")
    code, out = _git("log", "--all", "--oneline", "--", ".env")
    if code == 0 and out:
        return C("session.envleak", False, ".env has never been committed",
                 "Found in this repo's history: %s\n"
                 "     A key reached this repo's history — rotate it now and tell a "
                 "facilitator.\n"
                 "     Rotating is the fix. Deleting the file is not: the old commit still "
                 "has it."
                 % out.splitlines()[0])
    return C("session.envleak", True, ".env is gitignored and never committed")


def missing_agent_attrs(module):
    """Split out so it can be tested against a stub module. Returns the names
    a later block would blow up on."""
    return [a for a in AGENT_ATTRS if not hasattr(module, a)]


def check_compiles():
    bad = []
    for name in COMPILE_FILES:
        path = os.path.join(HERE, name)
        if not os.path.exists(path):
            bad.append("%s (missing)" % name)
            continue
        try:
            ast.parse(open(path).read())
        except SyntaxError as exc:
            bad.append("%s (line %s: %s)" % (name, exc.lineno, exc.msg))
    if bad:
        return C("session.compiles", False, "every harness script compiles",
                 "Broken: %s\n     A syntax error here stops a later block dead. If it's in a "
                 "given file,\n     take the pod's canon: python3 pod_sync.py --take-canon"
                 % "; ".join(bad))
    # Compiling is not enough: verify.py, readout.py and bench.py all import
    # agent and reach for these names by hand.
    try:
        import agent
    except Exception as exc:  # noqa: BLE001
        return C("session.compiles", False, "agent.py imports",
                 "%s: %s\n     agent.py parses but does not import. Take the pod's canon:\n"
                 "       python3 pod_sync.py --take-canon" % (type(exc).__name__, exc))
    missing = missing_agent_attrs(agent)
    if missing:
        return C("session.compiles", False, "agent.py has the names later blocks need",
                 "agent.py imports but is missing %s — take the pod's canon "
                 "(python3 pod_sync.py --take-canon)" % ", ".join(missing))
    return C("session.compiles", True,
             "every harness script compiles (%d checked), agent.py has all %d names"
             % (len(COMPILE_FILES), len(AGENT_ATTRS)))


def check_fixtures():
    try:
        from support import mock_backend, tools, data  # noqa: F401
        return C("session.fixtures", True, "fixtures + mock backend import clean")
    except Exception as exc:  # noqa: BLE001
        return C("session.fixtures", False, "fixtures + mock backend import clean",
                 "%s: %s\n     support/ and data/ are given — if these fail, the clone is "
                 "incomplete. Re-clone." % (type(exc).__name__, exc))


def check_git_identity():
    code_n, name = _git("config", "user.name")
    code_e, email = _git("config", "user.email")
    if code_n != 0 or not name or code_e != 0 or not email:
        return C("session.gitid", False, "git identity set",
                 "Your commits would land as nobody — and the pod handshake counts authors.\n"
                 "       git config user.name \"Your Name\"\n"
                 "       git config user.email \"you@yourfirm.com\"")
    return C("session.gitid", True, "git identity: %s <%s>" % (name, email))


def check_can_push():
    code, out = _git("push", "--dry-run", "origin", "HEAD", timeout=30)
    if code != 0:
        return C("session.push", False, "can push to origin (dry run)",
                 "%s\n     Both sessions end with a push. Fix GitHub access NOW, not at "
                 "16:55.\n     Private pod repo? The creator has to add you as a collaborator.\n"
                 "     https auth → `gh auth login`; SSH → check `ssh -T git@github.com`."
                 % (out.splitlines()[-1] if out else "no response"))
    return C("session.push", True, "can push to origin (dry run)")


def check_claude_cli():
    path = shutil.which("claude")
    if not path:
        return C("session.claude", False, "Claude Code installed",
                 "The go-read block and /coach both lean on it. Install:\n"
                 "       npm install -g @anthropic-ai/claude-code    (or see docs.claude.com)",
                 severity="advisory")
    return C("session.claude", True, "Claude Code installed (%s)" % path)


def session_checks():
    return [check_env_ignored(), check_compiles(), check_fixtures(),
            check_git_identity(), check_can_push(), check_claude_cli()]


# ---------------------------------------------------------------------------
# assemble all four sections
# ---------------------------------------------------------------------------

def all_checks(live=True):
    import doctor
    import pod_doctor

    out = []
    for i in doctor.run_checks(quiet=False, live=live):
        cid = "laptop." + i.label.split(":")[0].split()[0].lower()
        out.append(("LAPTOP", C(cid, i.ok, i.label, i.fix, i.severity)))

    for n, i in enumerate(pod_doctor.pod_checks()):
        out.append(("POD", C("pod.%d" % n, i.ok, i.label, i.fix, i.severity)))

    for c in session_checks():
        out.append(("SESSION", c))
    return out


def codes_for(name):
    """The SITE section: the two codes the workshop site gates on."""
    lines = []
    try:
        import verify
        lines.append(("your personal code (banks your own gates, different for every person)",
                      verify.evidence_code(1, name)))
    except Exception:  # noqa: BLE001
        pass
    try:
        import pod_doctor
        pod, members = pod_doctor.parse_team()
        if pod and members:
            lines.append(("your POD code (the Block 2 gate, identical on every laptop in "
                          "your pod)", pod_doctor.pod_code(pod, members)))
    except Exception:  # noqa: BLE001
        pass
    return lines


def bank_step_1(name):
    """Setup is step 1 on the same board every other gate lands on, so the
    status board reads as one arc instead of starting at step 2. Written
    through verify.py's own loader and saver, so the file shape can never
    drift from what the gate expects."""
    try:
        import verify
        profile = verify._load_profile()
        profile["name"] = name
        profile["banked"][str(1)] = verify.evidence_code(1, name)
        verify._save_profile(profile)
        return profile["banked"]["1"]
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# the READY receipt
# ---------------------------------------------------------------------------

def _upstream():
    code, branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    branch = branch if code == 0 and branch and branch != "HEAD" else "main"
    return branch


def _push_with_retry(attempts=3):
    """Everyone in the pod stamps within the same two minutes, so the first
    push usually loses the race. Fetch, rebase, try again."""
    branch = _upstream()
    for n in range(1, attempts + 1):
        code, out = _git("push", "origin", "HEAD", timeout=40)
        if code == 0:
            return True, ""
        if n == attempts:
            return False, out
        _git("fetch", "-q", "origin", timeout=40)
        # --autostash, because a dirty agent.py mid-block is the normal state of
        # this repo and refusing to rebase over it would be a wall, not a fix.
        rcode, rout = _git("rebase", "--autostash", "origin/%s" % branch, timeout=40)
        if rcode != 0:
            _git("rebase", "--abort")
            return False, rout
    return False, "gave up"


def stamp(name):
    """Push the READY receipt: your own file, your own commit, in the pod repo.

    One file per person, like team/. Nobody appends to a shared file, so five
    people stamping at once never collide."""
    os.makedirs(READY_DIR, exist_ok=True)
    path = os.path.join(READY_DIR, "%s.md" % slug(name))
    with open(path, "w") as f:
        f.write("# %s\nREADY %s\n" % (name, time.strftime("%Y-%m-%d %H:%M")))
    rel = os.path.relpath(path, HERE)
    _git("add", rel)
    code, _ = _git("diff", "--cached", "--quiet")
    if code != 0:  # something staged
        code, out = _git("commit", "-m", "ready: %s" % name, timeout=40)
        if code != 0:
            print("Could not commit the receipt. git said:")
            print("  %s" % (out.splitlines()[-1] if out else "no response"))
            print("Fix: check `git config user.name` and `git config user.email` are set,")
            print("then re-run this same command. Nothing else is needed.")
            return 1
    ok, out = _push_with_retry()
    if not ok:
        print("Your receipt is committed here, but three pushes in a row were rejected.")
        print("git said:\n  %s" % (out.splitlines()[-1] if out else "no response"))
        print("Fix, in order:")
        print("  1. python3 pod_sync.py --status     (is origin reachable, are you behind)")
        print("  2. git pull --rebase && git push")
        print("  3. Still stuck: tell a facilitator. Your receipt is safe in %s." % rel)
        return 1
    print("READY receipt on the pod repo: %s" % rel)
    return 0


# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Prove this seat is ready for the whole session.")
    parser.add_argument("--name", default="", help="your name, exactly as on the site")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--stamp", action="store_true", help="when green: push your READY receipt")
    parser.add_argument("--no-live", action="store_true", help="skip the live API call")
    args = parser.parse_args()

    checks = all_checks(live=not args.no_live)
    blocking = [c for _, c in checks if not c.ok and c.severity == "required"]
    ready = not blocking

    if args.json:
        print(json.dumps({
            "ready": ready,
            "blocking": len(blocking),
            "checks": [{"section": s, "id": c.id, "ok": c.ok, "label": c.label,
                        "fix": c.fix, "severity": c.severity} for s, c in checks],
        }, indent=2))
        return 0 if ready else 1

    print("\n%s\nLARKSPUR READY  ·  both sessions, checked now\n%s" % (RULE, RULE))
    section = None
    for s, c in checks:
        if s != section:
            print("\n  [%s]" % s)
            section = s
        mark = "  ✓" if c.ok else ("  !" if c.severity == "advisory" else "  ✗")
        print("%s %s" % (mark, c.label))
        if not c.ok and c.fix:
            for line in c.fix.splitlines():
                print("      %s" % line)

    print("\n" + RULE)
    if not ready:
        print("NOT READY — %d check(s) to fix, top to bottom, then re-run." % len(blocking))
        print("Or let the tool drive: run `claude` here and say `/ready`.")
        print(RULE)
        return 1

    print("READY — every check for both sessions is green on this laptop.")
    if args.name:
        banked = bank_step_1(args.name)
        if banked:
            print("Setup banked as step 1: %s" % banked)
        print("\n  [SITE] enter these on the workshop site:")
        for label, code in codes_for(args.name):
            print("    %s\n      %s" % (label, code))
    else:
        print("Run again with --name \"Your Name\" to print your site codes.")
    if args.stamp:
        if not args.name:
            print("--stamp needs --name.")
            return 1
        print()
        return stamp(args.name)
    print("Then: python3 ready.py --name \"Your Name\" --stamp   (pushes your READY receipt)")
    print(RULE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
