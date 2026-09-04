#!/usr/bin/env python3
"""doctor.py — run this first, before the day. It tells you exactly what's wrong
and what to type.

    python3 doctor.py            # diagnose
    python3 doctor.py --fix      # create .venv and install, then re-run

This is the pre-work command and it checks one thing: this laptop. Python, the
SDK, the network, a credential that actually works, git, and a real path to
GitHub. Doing it now is the whole point. Everything it finds is a ten minute
fix at your desk and a lost block in the room.

Design rule: this script never ends on a stack trace and never ends on "something
went wrong". Every failure names the fix. If you hit one it can't explain, that's
a bug in the workshop — tell a facilitator, it will be wrong for someone else too.
"""

from __future__ import annotations

import argparse
import os
import platform
import socket
import ssl
import subprocess
import sys
from typing import List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

RULE = "─" * 66
REQUIRED_FILES = ["agent.py", "run.py", "verify.py", "SPEC.md", "CLAUDE.md",
                  "ready.py", "pod_doctor.py", "pod_sync.py", "TEAM.md", "PITCH.md",
                  "support/data.py", "support/tools.py", "support/trace.py",
                  "support/client.py", "support/mock_backend.py",
                  "data/americas/bookings.json", "data/americas/disruption_policy.json"]
MIN_PY = (3, 9)
GOOD_PY = (3, 10)
# [TEMPLATE-URL] the participant template every pod repo is created from. Used
# here only as a real thing to reach for, to prove git can talk to GitHub from
# this laptop before the day starts.
TEMPLATE_URL = "https://github.com/victorsteeb/larkspur-exercise"


class Item:
    def __init__(self, ok: bool, label: str, fix: str = "", severity: str = "required") -> None:
        self.ok, self.label, self.fix, self.severity = ok, label, fix, severity


# ---------------------------------------------------------------------------
# individual checks
# ---------------------------------------------------------------------------

def check_python() -> Item:
    version = sys.version_info
    label = "Python %d.%d.%d at %s" % (version[0], version[1], version[2], sys.executable)
    if version < MIN_PY:
        return Item(False, label,
                    "Too old. Install Python 3.11 from python.org, or `brew install python@3.11`.")
    if version < GOOD_PY:
        return Item(True, label + "  (3.11 preferred, 3.9 works)", "", "advisory")
    return Item(True, label)


def check_isolated() -> Item:
    """Are we in a venv/conda, rather than the OS Python?"""
    if sys.prefix != getattr(sys, "base_prefix", sys.prefix):
        return Item(True, "isolated environment: %s" % os.path.basename(sys.prefix))
    if hasattr(sys, "real_prefix"):
        return Item(True, "isolated environment: legacy virtualenv")
    conda = os.environ.get("CONDA_PREFIX")
    if conda and os.path.realpath(sys.executable).startswith(os.path.realpath(conda)):
        return Item(True, "isolated environment: conda (%s)" % os.path.basename(conda))
    return Item(
        False,
        "running on system Python, not a virtual environment",
        "Fix: python3 doctor.py --fix\n"
        "     (creates .venv here and installs into it — nothing touches your system Python,\n"
        "      so no admin rights and no IT ticket)",
    )


def check_files() -> Item:
    missing = [name for name in REQUIRED_FILES if not os.path.exists(os.path.join(HERE, name))]
    if missing:
        return Item(False, "repo files present",
                    "Missing: %s\n"
                    "     You're either in the wrong folder or the download was partial.\n"
                    "     `pwd` should end in /exercise." % ", ".join(missing))
    return Item(True, "repo files present (%d checked)" % len(REQUIRED_FILES))


def check_writable() -> Item:
    target = os.path.join(HERE, ".workshop")
    try:
        os.makedirs(target, exist_ok=True)
        probe = os.path.join(target, ".probe")
        with open(probe, "w") as handle:
            handle.write("ok")
        os.remove(probe)
        return Item(True, "can write to .workshop/ (progress + traces)")
    except OSError as exc:
        return Item(False, "can write to .workshop/",
                    "%s\n     Move the folder somewhere you own — Desktop or home, not a "
                    "synced/managed directory." % exc)


def _git(*args: str, timeout: int = 25):
    """Never let git open an interactive prompt: a password box behind a script
    looks like a hang, and a hang has no fix line."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_ASKPASS="echo",
               GCM_INTERACTIVE="never")
    try:
        r = subprocess.run(["git", *args], cwd=HERE, capture_output=True,
                           text=True, timeout=timeout, env=env)
        return r.returncode, (r.stdout + r.stderr).strip()
    except FileNotFoundError:
        return 127, "git is not installed"
    except subprocess.TimeoutExpired:
        return 124, "timed out"


def check_git() -> Item:
    code, out = _git("--version", timeout=15)
    if code != 0:
        return Item(False, "git installed",
                    "The whole session runs out of one shared GitHub repo, so git is not "
                    "optional.\n"
                    "     macOS: xcode-select --install\n"
                    "     Windows: https://git-scm.com/download/win\n"
                    "     Linux: your package manager, e.g. sudo apt install git")
    return Item(True, out.splitlines()[0] if out else "git installed")


def check_git_identity() -> Item:
    code_n, name = _git("config", "user.name", timeout=15)
    code_e, email = _git("config", "user.email", timeout=15)
    if code_n != 0 or not name or code_e != 0 or not email:
        return Item(False, "git identity set",
                    "Your commits would land as nobody, and the pod roster counts committers.\n"
                    "       git config --global user.name \"Your Name\"\n"
                    "       git config --global user.email \"you@yourfirm.com\"")
    return Item(True, "git identity: %s <%s>" % (name, email))


def check_push_path() -> Item:
    """A real reach for a real repo. This is the check that catches the corporate
    proxy that allows browsers and blocks git, which otherwise shows up as a
    dead ten minutes in the first breakout."""
    label = "git can reach GitHub"
    code, out = _git("ls-remote", "--heads", TEMPLATE_URL, timeout=30)
    if code == 0:
        return Item(True, "%s (%s)" % (label, TEMPLATE_URL))
    text = out.lower()
    if "not found" in text or "does not exist" in text or "403" in text or "404" in text:
        # git talked to GitHub and GitHub said no such repo. The path works,
        # which is what this check is for. Advisory: the template repo is
        # published by the owner and may not exist yet.
        return Item(True, label + " (the template repo is not published yet, which is fine)",
                    "", "advisory")
    if "authentication" in text or "could not read username" in text or "permission denied" in text:
        return Item(True, label + " (reached it, offered no credential, which is fine here)",
                    "", "advisory")
    return Item(False, "git can reach GitHub",
                "%s\n"
                "     git could not get to github.com at all. On the day you clone a repo and "
                "push to it,\n"
                "     so this has to work. In order:\n"
                "       1. off the corporate VPN, or on guest wifi, try again\n"
                "       2. behind a proxy? git config --global http.proxy http://your.proxy:port\n"
                "       3. bring it to a facilitator before the session, not during it"
                % last_line_of(out))


def last_line_of(text: str) -> str:
    return text.splitlines()[-1] if text else "no response"


def check_sdk() -> Item:
    try:
        import anthropic
    except ImportError:
        return Item(False, "anthropic SDK installed",
                    "Fix: python3 doctor.py --fix\n"
                    "     or: python3 -m pip install -r requirements.txt")
    version = getattr(anthropic, "__version__", "?")
    return Item(True, "anthropic SDK %s" % version)


def check_network(timeout: float = 6.0) -> Item:
    host = "api.anthropic.com"
    context = ssl.create_default_context()
    try:
        with socket.create_connection((host, 443), timeout=timeout) as raw:
            with context.wrap_socket(raw, server_hostname=host):
                pass
        return Item(True, "TLS reach to %s" % host)
    except ssl.SSLCertVerificationError:
        return Item(False, "TLS reach to %s" % host,
                    "The certificate isn't the real one — your network is inspecting TLS\n"
                    "     (normal on a corporate VPN). Options, in order:\n"
                    "       1. get off the corporate VPN / use guest wifi\n"
                    "       2. ask IT for the proxy CA bundle, then:\n"
                    "          export SSL_CERT_FILE=/path/to/corp-ca.pem\n"
                    "       3. tether to your phone for the session")
    except socket.timeout:
        return Item(False, "TLS reach to %s" % host,
                    "Timed out. A proxy is probably swallowing it.\n"
                    "     Try guest wifi or a phone hotspot. Fix this before the day: every\n"
                    "     block calls the API, and there is no offline path in this pack.")
    except OSError as exc:
        return Item(False, "TLS reach to %s" % host,
                    "%s\n     No route to the API. Try guest wifi or a phone hotspot, and\n"
                    "     bring it to a facilitator before the session if it stays broken."
                    % exc)


def check_credential() -> Item:
    """Advisory only. The live call below is the verdict — an unset API key does
    NOT mean there's no credential (an `ant auth login` profile is invisible here
    on some setups, and federated credentials always are)."""
    from support.client import credential_status
    mode, detail = credential_status()
    if mode == "offline":
        return Item(False, "credential: OFFLINE MODE (%s)" % detail,
                    "LARKSPUR_OFFLINE=1 is set, and there is no offline path in this pack.\n"
                    "     Every block in both days calls the real API, so this setting only\n"
                    "     hides the problem until the room is watching. Unset it:\n"
                    "       unset LARKSPUR_OFFLINE            (and take it out of .env)\n"
                    "     Then get a working credential: an `ant auth login` session or an\n"
                    "     API key in .env. No key yet? Ask now, before the day.")
    if mode == "empty-key":
        return Item(False, "credential: %s" % detail,
                    "An empty key beats every other credential and fails every request.")
    if mode == "unknown":
        return Item(True, "credential: %s" % detail, "", "advisory")
    if "does not start with sk-ant-" in detail or "AWS_REGION is not set" in detail:
        return Item(False, "credential: %s" % detail,
                    "Check for a stray quote, a trailing space, or a truncated paste.")
    return Item(True, "credential: %s" % detail)


def check_live_call() -> Item:
    """Cheapest possible proof that the key actually works."""
    from support.client import MissingCredential, get_client
    if os.environ.get("LARKSPUR_OFFLINE") == "1":
        return Item(False, "live call to Claude",
                    "Skipped, because LARKSPUR_OFFLINE=1 is set. See the credential check "
                    "above:\n     unset it and run again. The live call is the only proof "
                    "that matters here.")
    try:
        client = get_client()
        response = client.messages.create(
            model="claude-sonnet-5", max_tokens=8,
            messages=[{"role": "user", "content": "Say OK"}],
        )
        text = "".join(getattr(b, "text", "") for b in response.content).strip()
        return Item(True, "live call to Claude: %r" % (text or "(empty)"))
    except MissingCredential as exc:
        return Item(False, "live call to Claude", str(exc))
    except Exception as exc:  # noqa: BLE001
        name = type(exc).__name__
        no_credential = (
            "No credential reached the API. Pick whichever you already have:\n"
            "       1. Already sign in to Claude? Use that — no API key needed:\n"
            "            brew install anthropics/tap/ant   (or see the site for Linux/Windows)\n"
            "            ant auth login\n"
            "            ant auth status        # confirms which credential is active\n"
            "       2. Have an API key? cp .env.example .env and paste it in\n"
            "       3. Neither? Ask for one now. Both days call the API in every block."
        )
        if "resolve authentication" in str(exc).lower() or name == "AuthenticationError":
            hint = no_credential
        else:
            hint = {
                "PermissionDeniedError": "That credential is valid but has no access to "
                                         "claude-sonnet-5.",
                "RateLimitError": "Rate limited — everyone hit the API at once. Wait 30s and "
                                  "run this again.",
                "NotFoundError": "Model claude-sonnet-5 not available on this credential/region.",
            }.get(name, "Paste this into Claude Code — it has the repo in context.")
        return Item(False, "live call to Claude", "%s: %s\n     %s" % (name, exc, hint))


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------

def run_checks(quiet: bool = False, live: bool = True) -> List[Item]:
    items = [check_python(), check_isolated(), check_files(), check_writable(),
             check_git(), check_git_identity(), check_push_path(),
             check_sdk(), check_network(), check_credential()]
    if live and all(i.ok for i in items if i.severity == "required"):
        items.append(check_live_call())
    return [i for i in items if i.severity == "required"] if quiet else items


def do_fix() -> int:
    venv = os.path.join(HERE, ".venv")
    python = os.path.join(venv, "Scripts" if os.name == "nt" else "bin", "python")
    if not os.path.exists(python):
        print("creating %s ..." % os.path.relpath(venv, HERE))
        result = subprocess.run([sys.executable, "-m", "venv", venv])
        if result.returncode != 0:
            print("\ncouldn't create a venv with %s" % sys.executable)
            print("try: python3 -m pip install --user virtualenv && python3 -m virtualenv .venv")
            return 1
    print("installing dependencies ...")
    subprocess.run([python, "-m", "pip", "install", "-q", "--upgrade", "pip"])
    result = subprocess.run([python, "-m", "pip", "install", "-q", "-r",
                             os.path.join(HERE, "requirements.txt")])
    if result.returncode != 0:
        print("\ninstall failed. If you're behind a proxy, try:")
        print("  %s -m pip install --proxy http://your.proxy:port -r requirements.txt" % python)
        return 1
    activate = ".venv\\Scripts\\activate" if os.name == "nt" else "source .venv/bin/activate"
    print("\n%s\nDone. Now run these two lines:\n\n  %s\n  python3 doctor.py\n%s"
          % (RULE, activate, RULE))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose this laptop for the exercise.")
    parser.add_argument("--fix", action="store_true", help="create .venv and install dependencies")
    parser.add_argument("--offline", action="store_true",
                        help="(removed) there is no offline path in this pack")
    parser.add_argument("--no-live", action="store_true", help="skip the live API call")
    args = parser.parse_args()

    if args.offline:
        print("\n%s" % RULE)
        print("There is no offline mode in this pack, so --offline does nothing but hide")
        print("the problem. Every block in both days makes a real API call.")
        print("What to do instead:")
        print("  1. python3 doctor.py            and fix the credential check it names")
        print("  2. no key at all? ask for one now, before the day")
        print(RULE)
        return 1
    if args.fix:
        return do_fix()

    print("\n%s\nLARKSPUR DOCTOR  ·  %s %s\n%s"
          % (RULE, platform.system(), platform.release(), RULE))
    items = run_checks(quiet=False, live=not args.no_live)
    for item in items:
        mark = "  ✓" if item.ok else ("  !" if item.severity == "advisory" else "  ✗")
        print("%s %s" % (mark, item.label))
        if not item.ok and item.fix:
            for line in item.fix.splitlines():
                print("      %s" % line)

    blocking = [i for i in items if not i.ok and i.severity == "required"]
    print("\n" + RULE)
    if not blocking:
        print("READY on this laptop. That is the pre-work.")
        print("On the day, Block 2 wires the pod: python3 ready.py --name \"Your Name\"")
        print(RULE)
        return 0
    print("BLOCKED on %d check(s). Fix the ✗ lines above, top to bottom, then re-run." % len(blocking))
    print("Still stuck after two tries? Bring it to the pre-work channel now. Every one of")
    print("these is a ten minute fix at your desk and a lost block in the room.")
    print(RULE)
    return 1


if __name__ == "__main__":
    sys.exit(main())
