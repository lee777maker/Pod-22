#!/usr/bin/env python3
"""verify.py — the gate. Never edit this file; if a check seems wrong, say so
out loud to a facilitator, don't route around it.

    python3 verify.py            # status board — what's banked, what isn't
    python3 verify.py 2          # check step 2
    python3 verify.py 3 --name "Your Name"

The verifier checks what happened ON THE WIRE — how many turns, which tools,
in which order. It does not read your code and does not care what your code
looks like. Any implementation that behaves correctly passes.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import importlib
import json
import os
import re
import sys
import traceback
from dataclasses import dataclass, field
from typing import Callable, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

SHARED_SECRET = b"larkspur-basecamp-reference-architecture"
PROFILE_PATH = os.path.join(HERE, ".workshop", "profile.json")
# .workshop/ is per-clone and gitignored. evidence/ is the half that TRAVELS:
# one committed file per member, so a pod repo can show who banked what without
# six people reading out codes.
EVIDENCE_DIR = os.path.join(HERE, "evidence")

STEP_NAMES = {1: "Setup — laptop, pod, session", 2: "Tool schemas",
              3: "The agentic loop", 4: "Prove it generalizes",
              5: "Pull your lever", 6: "The proof surface",
              7: "Build 2: the tools you chose"}
# Step 7 is numbered out of day order (Build 2 sits between 4 and 5 on the
# clock) because 5 and 6 had already shipped as day 2's gates and evidence
# codes key on the step number. Numbering is cheap; re-keying codes is not.

# Day 2 conventions, in one place because three files depend on them.
#   Every lane benches stage 1 as 'before' and 'after'. That is the regression
#   guard: whatever you pulled, stage 1 has to still resolve.
#   The intelligence lane ALSO benches stage 2 as 's2-before' and 's2-after',
#   because its metric is the wire-rule count and that only exists on stage 2.
LANES = ("intelligence", "cost", "speed")
MIN_IMPROVEMENT = 0.10  # 10%, so noise does not read as a win

# Both anchors are deliberately loose about markdown. People write `**Lever:**
# cost` and `- Still broken: the tone gate`, and a gate that fails on a pair of
# asterisks teaches nothing about measurement.
LEVER_RE = re.compile(r"^[\s>*_-]*\**\s*Lever\**\s*:\s*\**\s*(\w+)", re.M | re.I)
STILL_BROKEN_RE = re.compile(r"^[\s>*_-]*\**\s*Still[ _-]?broken\**\s*:\s*\**\s*(\S.*)$",
                             re.M | re.I)


@dataclass
class Check:
    passed: bool
    label: str
    hint: str = ""


@dataclass
class StepContext:
    """What a step is told before it runs. `name` is resolved up front now,
    because gate 6 checks whether any eval case carries it."""
    name: str = ""


class StepFailure(Exception):
    pass


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip()).lower()


def slug(name: str) -> str:
    """A filename for a person. Stable across runs, boring on purpose."""
    out = re.sub(r"[^a-z0-9]+", "-", normalize_name(name)).strip("-")
    return out or "unnamed"


def read_roster() -> tuple:
    """(pod name or None, [member names]) from TEAM.md, and from team/*.md if the
    pod keeps one file per member. Display and attribution only — pod_doctor.py
    owns the version that actually gates anything, and this one never fails."""
    pod, members = None, []
    paths = [os.path.join(HERE, "TEAM.md")]
    team_dir = os.path.join(HERE, "team")
    if os.path.isdir(team_dir):
        paths += sorted(os.path.join(team_dir, f) for f in os.listdir(team_dir)
                        if f.endswith(".md"))
    for path in paths:
        if not os.path.exists(path):
            continue
        try:
            with open(path) as fh:
                text = fh.read()
        except OSError:
            continue
        found_here = []
        heading = None
        for line in text.splitlines():
            line = line.strip()
            m = re.match(r"#\s*Pod\s*:\s*(.+)", line, re.I)
            if m:
                pod = pod or m.group(1).strip()
                continue
            if line.startswith("#") and heading is None:
                heading = line.lstrip("#").strip()
            elif line.startswith("- ") and line[2:].strip():
                found_here.append(line[2:].strip())
        if found_here:
            members += found_here
        elif os.path.dirname(path) == team_dir:
            # one file per member, no bullet list: the file itself is the member
            members.append(heading or os.path.splitext(os.path.basename(path))[0])
    seen, unique = set(), []
    for m in members:
        key = normalize_name(m)
        if key and key not in seen and not _placeholder(m):
            seen.add(key)
            unique.append(m)
    return (None if (pod and _placeholder(pod)) else pod), unique


def _placeholder(value: str) -> bool:
    """`# Pod: <your pod name>` is the shipped template, not a pod."""
    return bool(re.match(r"^<.*>$", value.strip()))


def evidence_code(step: int, name: str) -> str:
    """A speed bump and a telemetry key, not a security boundary — anyone who
    reads this file can forge a code, and anyone who bothers has already
    learned more than the step teaches."""
    payload = "step:%d|name:%s" % (step, normalize_name(name))
    digest = hmac.new(SHARED_SECRET, payload.encode(), hashlib.sha256).hexdigest().upper()
    return "%s-%s" % (digest[:3], digest[3:6])


def _load_profile() -> dict:
    if os.path.exists(PROFILE_PATH):
        with open(PROFILE_PATH) as f:
            return json.load(f)
    return {"name": None, "banked": {}, "caught_up": [], "banked_from_checkpoint": []}


def _save_profile(profile: dict) -> Optional[str]:
    """Returns the evidence path if the committed copy was written, else None."""
    os.makedirs(os.path.dirname(PROFILE_PATH), exist_ok=True)
    with open(PROFILE_PATH, "w") as f:
        json.dump(profile, f, indent=2)
    return _write_evidence(profile)


def _write_evidence(profile: dict) -> Optional[str]:
    """The committed twin of profile.json.

    .workshop/ is gitignored, so nothing in it survives a clone: a facilitator
    who pulls the pod repo would see a build with no gates banked by anyone.
    evidence/<you>.json is one file per member, added to the repo by that
    member, and it is what makes 'six people banked something' checkable rather
    than claimed. Never blocks a bank — a read-only checkout still gets its
    code."""
    name = profile.get("name")
    if not name:
        return None
    pod, _members = read_roster()
    payload = {"name": name, "pod": pod, "banked": profile.get("banked") or {}}
    path = os.path.join(EVIDENCE_DIR, "%s.json" % slug(name))
    try:
        os.makedirs(EVIDENCE_DIR, exist_ok=True)
        with open(path, "w") as f:
            json.dump(payload, f, indent=2)
    except OSError as exc:
        print("  (could not write evidence/%s.json — %s. Banked locally anyway, but your pod "
              "cannot see it until that file exists.)" % (slug(name), exc))
        return None
    return path


def load_agent():
    """Purge and re-import agent + support so an edit mid-session is picked up."""
    for name in list(sys.modules):
        if name == "agent" or name.startswith("support"):
            del sys.modules[name]
    try:
        import agent
        return agent
    except SyntaxError as exc:
        raise StepFailure(
            "agent.py has a syntax error at line %s: %s" % (exc.lineno, exc.msg)
        ) from exc


def call_agent(fn: Callable, *args, **kwargs):
    result = fn(*args, **kwargs)
    agent_module = sys.modules.get("agent")
    tracer = agent_module.LAST.tracer if agent_module else None
    return result, tracer


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------
def step_1(args) -> List[Check]:
    """Setup is the whole seat, not just this laptop: laptop, pod wiring, and
    the forward checks both sessions need. A pod that finds out at 16:55
    that one member cannot push loses the end of the day, not five minutes."""
    try:
        import ready  # lazy, so an older clone without ready.py still gates
    except ImportError:
        import doctor
        checks = [Check(item.ok, item.label, item.fix)
                  for item in doctor.run_checks(quiet=True)]
        checks.append(Check(True, "(ready.py is not in this clone, so this checked the LAPTOP "
                                  "only — pod wiring and the day-2 forward checks were "
                                  "skipped. Pull the pod repo to get them.)"))
        return checks

    items = ready.all_checks(live=True)
    checks = [Check(item.ok, "%s · %s" % (section, item.label), item.fix)
              for section, item in items if item.severity == "required"]
    advisory_failed = [item.label for _s, item in items
                       if item.severity != "required" and not item.ok]
    if advisory_failed:
        checks.append(Check(True, "(advisory, not gating: %s)" % "; ".join(advisory_failed)))
    return checks


def step_2(args) -> List[Check]:
    agent = load_agent()
    tools = agent.build_tools()
    names = {t["name"] for t in tools}
    expected = {"lookup_booking", "get_flight_status", "search_alternatives", "check_policy",
                "hold_seat", "confirm_rebooking", "issue_voucher", "escalate_to_human",
                "send_confirmation"}
    checks = [Check(names == expected, "all 9 tools present, none renamed",
                     hint="missing: %s | unexpected: %s"
                          % (", ".join(sorted(expected - names)) or "none",
                             ", ".join(sorted(names - expected)) or "none"))]
    for t in tools:
        desc = t.get("description", "")
        checks.append(Check(
            len(desc) >= 40,
            "%s: description is substantive (%d chars, floor is 40) — routing is proven "
            "at gate 7" % (t["name"], len(desc)),
            hint="The description is the main routing surface, and the field descriptions "
                 "inside input_schema route too. Say when to call it, what it needs, and "
                 "what comes back.",
        ))
    return checks


def step_3(args) -> List[Check]:
    agent = load_agent()
    result, tracer = call_agent(agent.run_agent, "K7PQ2M", "Marchetti",
                                 "My flight was disrupted — what happens next?")
    if tracer is None:
        raise StepFailure("run_agent() didn't create a tracer — did you call new_session()?")

    names = tracer.tool_names
    lookup_idx = names.index("lookup_booking") if "lookup_booking" in names else None
    policy_idx = names.index("check_policy") if "check_policy" in names else None
    last_stop = tracer.turns[-1].get("stop_reason") if tracer.turns else None

    return [
        Check(len(tracer.turns) >= 2, "%d API turns (need >= 2)" % len(tracer.turns),
              hint="response.content has to go back WHOLE and unmodified, thinking blocks "
                   "included, as the assistant turn — then tool_results(response) as a user "
                   "turn — then you call again, while response.stop_reason == 'tool_use'. "
                   "One turn means that never happened."),
        Check(len(tracer.tool_calls) >= 2, "%d tool calls (need >= 2)" % len(tracer.tool_calls),
              hint="lookup_booking alone isn't enough — check_policy needs what it returns."),
        Check(lookup_idx is not None and policy_idx is not None and lookup_idx < policy_idx,
              "lookup_booking called before check_policy",
              hint="check_policy resolves entitlements for a booking you haven't looked up yet."),
        Check(len(tracer.turns) <= agent.MAX_TOOL_CALLS,
              "loop stayed within the cap (%d API turns, ceiling %d)"
              % (len(tracer.turns), agent.MAX_TOOL_CALLS),
              hint="MAX_TOOL_CALLS counts API TURNS, not tool calls — one turn can carry "
                   "several calls. Count the turns you take, not the tools you execute, or "
                   "you will cut the loop off early and not know why."),
        Check(last_stop != "tool_use",
              "the loop ran out of tool calls, not out of turns (last stop_reason=%s)"
              % last_stop,
              hint="the trace ends with Claude still asking — nobody answered the last "
                   "tool call, or the cap cut it off without a handoff."),
        Check(bool(result), "returned a non-empty string",
              hint="Run with --trace. If the last turn is stop_reason=tool_use, nobody "
                   "answered Claude's last tool call."),
    ]


def step_4(args) -> List[Check]:
    agent = load_agent()
    from support import STAGE1_TASKS

    checks = []
    ok_count = 0
    for task in STAGE1_TASKS:
        try:
            result, tracer = call_agent(
                agent.run_agent, task["pnr"], task["last_name"],
                "My flight was disrupted — can you help me figure out what happens next?",
            )
        except Exception as exc:  # noqa: BLE001 — surfaced per-ticket, not fatal to the run
            checks.append(Check(False, "%s (%s) ran without an exception" % (task["pnr"], task["shape"]),
                                 hint="%s: %s" % (type(exc).__name__, exc)))
            continue
        good = bool(result) and tracer is not None and len(tracer.tool_calls) >= 1
        if good:
            ok_count += 1
        checks.append(Check(
            good, "%s (%s) resolved with at least one tool call" % (task["pnr"], task["shape"]),
            hint="Empty result or zero tool calls — read this one with --trace on its own "
                 "PNR. Read what this check asks before you 'fix' anything: the group "
                 "booking escalating is the correct outcome, not a miss.",
        ))
        # DRIFT NOTE — deliberately not asserted: which tool it called, or what
        # it said. That's a model-behaviour question this step doesn't grade;
        # generalizing across five different shapes without crashing or
        # spinning forever is the whole point of Step 4.

    checks.append(Check(ok_count == len(STAGE1_TASKS),
                         "%d/%d Stage 1 shapes generalized" % (ok_count, len(STAGE1_TASKS)),
                         hint="A loop that works on K7PQ2M and nowhere else is a loop tuned to "
                              "one ticket. Fix the shape that failed above and re-run all five: "
                              "python3 run.py --all --trace."))
    checks.append(Check(True,
                        "(R8KD3F, the abusive-message ticket, comes back calm and helpful with "
                        "no gate on tone at all. That is Block 15's work, not a bug to fix "
                        "here — fixing it now hides the gap this run exists to show you.)"))
    return checks


# ---------------------------------------------------------------------------
# Day 2
# ---------------------------------------------------------------------------
def _bench(label: str) -> Optional[dict]:
    path = os.path.join(HERE, ".workshop", "bench-%s.json" % label)
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        return json.load(fh)["summary"]


def _declared_lane() -> Optional[str]:
    """Read the lever out of PITCH.md. Convention: a line reading 'Lever: cost'."""
    path = os.path.join(HERE, "PITCH.md")
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        text = fh.read()
    match = LEVER_RE.search(text)
    if not match:
        return None
    lane = match.group(1).lower()
    return lane if lane in LANES else None


def _moved(before, after, key, lower_is_better) -> tuple:
    """(improved, message). Returns the percentage move either way."""
    a, b = before.get(key), after.get(key)
    if a is None or b is None:
        return False, "%s missing from one of the two runs" % key
    if not a:
        return False, "%s was 0 before, nothing to improve on" % key
    delta = (b - a) / abs(a)
    move = -delta if lower_is_better else delta
    return move >= MIN_IMPROVEMENT, "%s %.4g → %.4g (%+.0f%%)" % (key, a, b, delta * 100)


def step_5(args) -> List[Check]:
    """Lane-aware. Grades movement on the metric the pod itself declared, and
    refuses to reward a win that broke stage 1."""
    lane = _declared_lane()
    checks = [Check(lane is not None,
                    "PITCH.md declares a lever%s" % (" (%s)" % lane if lane else ""),
                    hint="Add a line to PITCH.md reading exactly: Lever: cost "
                         "(or speed, or intelligence). Block 15 is where you pick it.")]
    # No early return on a missing lever. The bench pair either exists or it
    # does not, and a pod that measured well and forgot the line should see that
    # on the same board as the line they forgot.

    before, after = _bench("before"), _bench("after")
    checks.append(Check(before is not None, "a 'before' bench exists",
                        hint="python3 bench.py --label before --stage 1 — and it has to be "
                             "BEFORE you tune. There is no way to reconstruct it after. Note "
                             "that .workshop/ is gitignored, so a podmate's before number "
                             "never arrives with a pull; it has to be benched on this laptop. "
                             "If you have already tuned: git stash, bench --label before, "
                             "git stash pop, bench --label after."))
    checks.append(Check(after is not None, "an 'after' bench exists",
                        hint="python3 bench.py --label after --stage 1"))
    if not (before and after):
        return checks

    # The intelligence lane's lever IS the model swap, benched either side, so a
    # model mismatch is the expected shape there. Every other lane must hold the
    # model still or the movement measures the swap, not the thing they pulled.
    model_ok = (before.get("model") == after.get("model")
                or lane == "intelligence")
    comparable = (before.get("stage") == after.get("stage")
                  and before.get("runs_per_shape") == after.get("runs_per_shape")
                  and model_ok)
    checks.append(Check(comparable, "the two runs are comparable",
                        hint="Same stage and same --runs on both sides, and the same model "
                             "unless your declared lane is intelligence, where the model swap "
                             "is the lever. Stage %s/%s, runs %s/%s, model %s/%s. On a cost or "
                             "speed claim, benching across different models measures the swap, "
                             "not the thing you pulled."
                             % (before.get("stage"), after.get("stage"),
                                before.get("runs_per_shape"), after.get("runs_per_shape"),
                                before.get("model"), after.get("model"))))

    # The regression guard, for every lane. A cheaper agent that stopped working
    # is not a win, and this is the check that says so. The hint depends on the
    # BEFORE number: a shape that never worked is not something you broke.
    before_resolved, after_resolved = before.get("resolved_pct"), after.get("resolved_pct") or 0
    if before_resolved is None:
        guard_hint = ("bench-before.json has no resolved_pct, so there is nothing to compare "
                      "this against. Re-bench the baseline.")
    elif before_resolved >= 100.0:
        guard_hint = ("Stage 1 resolved 5/5 before your change and %.0f%% after — whatever you "
                      "pulled, it broke a shape that used to work. Read bench-after.json's "
                      "failures list." % after_resolved)
    else:
        guard_hint = ("Stage 1 was already at %.0f%% BEFORE your change, so this is not a "
                      "regression — it is a shape that never worked. Fix that first: a lane "
                      "win measured on a broken baseline is not a win."
                      % before_resolved)
    checks.append(Check(after_resolved == 100.0,
                        "stage 1 still resolves 5/5 after your change (%.0f%%)" % after_resolved,
                        hint=guard_hint))

    if lane is None:
        return checks

    if lane == "cost":
        ok, msg = _moved(before, after, "model_cost_per_contact", lower_is_better=True)
        checks.append(Check(ok, "cost lane: %s" % msg,
                            hint="Needs a %.0f%% reduction. If caching reports a 0%% hit "
                                 "rate, something in the cached prefix changes every call."
                                 % (MIN_IMPROVEMENT * 100)))
    elif lane == "speed":
        ok, msg = _moved(before, after, "p95_s", lower_is_better=True)
        checks.append(Check(ok, "speed lane: %s" % msg,
                            hint="Needs a %.0f%% reduction in p95. With 5 conversations p95 "
                                 "is the slowest one, so use --runs 3 for a number you can "
                                 "defend." % (MIN_IMPROVEMENT * 100)))
    else:
        s2b, s2a = _bench("s2-before"), _bench("s2-after")
        checks.append(Check(s2b is not None and s2a is not None,
                            "stage 2 benched before and after",
                            hint="The intelligence lane's metric is the wire-rule count, "
                                 "which only exists on stage 2: python3 bench.py "
                                 "--label s2-before --stage 2 (then s2-after)."))
        if s2b and s2a:
            gained = (s2a.get("rules_passed") or 0) - (s2b.get("rules_passed") or 0)
            checks.append(Check(gained >= 1,
                                "intelligence lane: wire rules %s → %s passed"
                                % (s2b.get("rules_passed"), s2a.get("rules_passed")),
                                hint="At least one more Stage 2 case has to satisfy its "
                                     "rules. bench --stage 2 names the failing hard gate."))
    return checks


def step_6(args) -> List[Check]:
    """The proof surface: their own eval cases, actually run, and a claim sized
    to what came back."""
    checks = []
    cases_path = os.path.join(HERE, "evals", "cases.json")
    if not os.path.exists(cases_path):
        return [Check(False, "evals/cases.json exists",
                      hint="cp evals/cases.example.json evals/cases.json, then make them "
                           "yours. The examples are worked examples, not your cases.")]

    with open(cases_path) as fh:
        cases = json.load(fh).get("cases", [])
    ids = [c.get("id") for c in cases]
    hard = [c for c in cases if c.get("hard_gate")]
    checks.append(Check(len(cases) >= 3, "at least 3 eval cases (%d)" % len(cases)))
    checks.append(Check(len(hard) >= 2, "at least 2 of them are hard gates (%d)" % len(hard),
                        hint="A hard gate is a case whose failure blocks a release on its "
                             "own. If everything is soft, nothing is gated."))
    checks.append(Check(all(c.get("expect") for c in cases),
                        "every case says what it expects",
                        hint="A case with no `expect` cannot be judged, only run."))

    # Attribution. A pod of six can ship six cases with one person's judgement
    # in all of them, and nothing else in the day would notice.
    me = normalize_name(getattr(args, "name", "") or "")
    authors = sorted({(c.get("author") or "").strip() for c in cases if (c.get("author") or "").strip()})
    checks.append(Check(bool(me) and me in {normalize_name(a) for a in authors},
                        "at least one case is authored by you (%s)"
                        % (getattr(args, "name", "") or "no name given"),
                        hint="Add \"author\": \"%s\" to the case you wrote — this is the one "
                             "artifact today that carries your name. Authors on file: %s."
                             % (getattr(args, "name", "") or "Your Name",
                                ", ".join(authors) or "none")))

    evals_path = os.path.join(HERE, ".workshop", "evals.json")
    if not os.path.exists(evals_path):
        checks.append(Check(False, "the harness has been run",
                            hint="python3 eval_harness.py"))
        return checks
    with open(evals_path) as fh:
        report = json.load(fh)
    ran_ids = [entry["case"]["id"] for entry in report.get("cases", [])]
    checks.append(Check(bool(ran_ids) and set(ran_ids) <= set(ids),
                        "the last run was YOUR cases, not the examples",
                        hint="Ran %s; cases.json has %s. Run: python3 eval_harness.py"
                             % (ran_ids, ids)))
    # Deliberately NOT asserted: that the evals passed. A blocked release with a
    # named hard gate is a legitimate, honest outcome for this block, and gating
    # on a green run would teach pods to write cases they know they pass.
    rep = report.get("report", {})
    checks.append(Check(rep.get("cases", 0) >= 3,
                        "the run covered at least 3 cases (%d, release %s)"
                        % (rep.get("cases", 0), rep.get("release", "?")),
                        hint="This asks about COVERAGE, not about passing. BLOCKED with a named "
                             "hard gate is a legitimate result and is not scored down anywhere "
                             "in this exercise. And if a case fails on behaviour you believe was "
                             "right, suspect the rubric before the agent — read "
                             "evals/GRADER-BUG.md, which is that exact failure from Larkspur's "
                             "own week 8."))

    # Informational, never blocking. The panel reads .workshop/bench-after.json,
    # which Build 4 produces — and Build 4 comes after this gate. A pod that has
    # not benched yet is on schedule, not behind.
    bench_after = _bench("after")
    if bench_after is None:
        checks.append(Check(True,
                            "(no bench pair yet — the evidence panel will show bench numbers "
                            "once Build 4 runs. Nothing required here.)"))
    else:
        checks.append(Check(True, "the evidence panel has numbers to show"))

    pitch = os.path.join(HERE, "PITCH.md")
    claim = ""
    if os.path.exists(pitch):
        with open(pitch) as fh:
            claim = fh.read()
    checks.append(Check(bool(re.search(r"\d", claim)),
                        "PITCH.md states a claim with a number in it",
                        hint="One number, its unit, and its denominator. "
                             "'$0.11 per resolved contact, 5 shapes, 3 runs each'."))
    checks.append(Check(len(claim.split()) >= 40,
                        "PITCH.md is more than a placeholder (%d words)" % len(claim.split()),
                        hint="Six lines. Five is what you deliberately did not do; six is what "
                             "still does not work."))
    # Sh2, and it is scored, not suggested: a line naming one thing that still
    # does not work. "We did not measure that" is worth more than a number you
    # cannot defend, and this line is where that stops being a slogan.
    broken = STILL_BROKEN_RE.search(claim)
    checks.append(Check(bool(broken),
                        "PITCH.md names one thing that still does not work",
                        hint="Add a line: 'Still broken: <the thing>'. The tone gate you "
                             "measured and left is a legitimate entry. An empty one is not."))
    return checks


def step_7(args) -> List[Check]:
    """Build 2, on the wire: at least one tool that is NOT one of the nine
    given ones, defined, dispatched locally, and actually chosen by the model
    on a conversation that needs it."""
    agent = load_agent()
    given = {"lookup_booking", "get_flight_status", "search_alternatives", "check_policy",
             "hold_seat", "confirm_rebooking", "issue_voucher", "escalate_to_human",
             "send_confirmation"}
    tools = agent.build_tools() + agent.EXTRA_TOOLS
    new_names = {t["name"] for t in tools} - given
    checks = [Check(bool(new_names), "at least one tool beyond the given nine (%s)"
                    % (", ".join(sorted(new_names)) or "none"),
                    hint="Schema in EXTRA_TOOLS, function in LOCAL_TOOLS. The scaffolded "
                         "one is next_available_day."),
              Check(bool(new_names & set(agent.LOCAL_TOOLS)),
                    "the new tool is registered in LOCAL_TOOLS",
                    hint="A schema with no function errors on every call.")]
    for t in tools:
        if t["name"] in new_names:
            desc = t.get("description", "")
            checks.append(Check(len(desc) >= 40,
                                "%s description is >= 40 characters (%d)" % (t["name"], len(desc)),
                                hint="Same bar as the given nine: when to call it, what it "
                                     "needs, what comes back."))
    if not new_names:
        return checks

    # The probe is the pod's own: one customer message their new tool exists to
    # answer, in build2_probe.txt at the repo root (three lines: PNR, last name,
    # message). It lives at the root, not in .workshop/, because it is a pod
    # artifact — one person writes the question and everybody's gate runs it.
    # Writing that question IS the spec.
    #
    # Without one, the default probes the scaffolded tool: J5NU8S is two
    # passengers stranded at DEN on a cancelled DEN-BOI, and "what is the
    # soonest day" is a question about DATES that search_alternatives cannot be
    # pointed at — it takes a pnr and nothing else. The fixtures answer it
    # truthfully (the earliest open seat is 9 May 2025), which matters: a
    # default probe whose honest answer is "nothing in the horizon" would pass
    # this gate on a hallucinated date.
    probe_path = os.path.join(HERE, "build2_probe.txt")
    legacy_path = os.path.join(HERE, ".workshop", "build2_probe.txt")
    source = probe_path if os.path.exists(probe_path) else (
        legacy_path if os.path.exists(legacy_path) else None)
    pnr, last = "J5NU8S", "Calloway"
    msg = ("Our Boise flight was cancelled and we are stuck at Denver overnight. "
           "What is the soonest day you could actually get us out?")
    if source:
        with open(source) as fh:
            lines = [l.strip() for l in fh if l.strip()]
        if len(lines) >= 3:
            pnr, last, msg = lines[0], lines[1], " ".join(lines[2:])
        else:
            checks.append(Check(False, "%s has three lines" % os.path.relpath(source, HERE),
                                hint="PNR on line 1, last name on line 2, the customer's message "
                                     "on line 3. Found %d non-empty line(s); running the default "
                                     "probe instead." % len(lines)))

    # Three attempts, first success wins. Whether the model reaches for a tool is
    # a sampled decision, and one refusal is not evidence of a bad description —
    # three in a row is.
    attempts, called_new, tracer, result = 3, [], None, ""
    for _attempt in range(attempts):
        result, tracer = call_agent(agent.run_agent, pnr, last, msg)
        called_new = [n for n in (tracer.tool_names if tracer else []) if n in new_names]
        if called_new:
            break
    used = _attempt + 1
    checks.append(Check(bool(called_new),
                        "the model chose a new tool on a conversation that needs it (%s, "
                        "attempt %d of %d)" % (", ".join(called_new) or "not called",
                                               used, attempts),
                        hint="Three attempts, none of them reached for your tool — that is a "
                             "routing result, not bad luck. Two suspects, in order: the "
                             "description, including the field descriptions inside "
                             "input_schema (an over-constrained argument description is a "
                             "routing failure that looks like judgement), then the probe. "
                             "Write the one customer message your tool exists to answer into "
                             "build2_probe.txt at the repo root (three lines: PNR, last name, "
                             "message)."))
    checks.append(Check(bool(result), "returned a non-empty string"))
    summary = tracer.summary() if tracer else {}
    checks.append(Check(True, "(that probe cost %s tokens in across %d tool call(s) — the "
                              "eleventh tool is not free, and this is the number that says "
                              "what it cost)"
                        % ("{:,}".format((summary.get("tokens") or {}).get("input", 0) or 0),
                           summary.get("tool_calls", 0) or 0)))
    return checks


STEPS = {1: step_1, 2: step_2, 3: step_3, 4: step_4, 5: step_5, 6: step_6, 7: step_7}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def print_board(profile: dict) -> None:
    try:
        pod, members = read_roster()
    except Exception:  # noqa: BLE001 — a header must never take the board down
        pod, members = None, []
    if pod or members:
        head = "POD %s" % pod if pod else "POD — no name in TEAM.md yet"
        if members:
            head += " · %d member%s" % (len(members), "" if len(members) == 1 else "s")
        print("\n" + head)

    print("\nSTATUS")
    for n, label in STEP_NAMES.items():
        code = profile["banked"].get(str(n))
        mark = "✓ banked %s" % code if code else "—"
        flag = "  (loaded, not banked)" if n in profile.get("caught_up", []) else ""
        print("  %d. %-28s %s%s" % (n, label, mark, flag))


def _resolve_name(profile: dict, name: Optional[str]) -> str:
    """Up front, before any check runs — gate 6 asks whether an eval case
    carries this name, so it cannot be settled at banking time any more."""
    if name:
        return name.strip()
    if profile.get("name"):
        return profile["name"]
    try:
        return input("Your name, for the evidence code (gate 6 also looks for it on your "
                     "eval case): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


def run_step(number: int, name: Optional[str]) -> int:
    if number not in STEPS:
        print("No such step: %d (have 1-%d)" % (number, max(STEPS)))
        return 1
    profile = _load_profile()
    name = _resolve_name(profile, name)
    print("\nStep %d — %s\n" % (number, STEP_NAMES[number]))
    try:
        checks = STEPS[number](StepContext(name=name))
    except StepFailure as exc:
        print("  ✗ %s" % exc)
        return 1
    except Exception:  # noqa: BLE001 — a real bug in the participant's code
        print("  ✗ crashed while checking this step:\n")
        traceback.print_exc()
        return 1

    failed = [c for c in checks if not c.passed]
    for c in checks:
        print("  %s %s" % ("✓" if c.passed else "✗", c.label))
        if not c.passed and c.hint:
            print("      → %s" % c.hint)

    if failed:
        print("\n%d/%d checks failed. Fix the ✗ lines above, then re-run." % (len(failed), len(checks)))
        return 1

    if not name:
        print("\nAll checks passed, but there is no name to bank them under.")
        print("Re-run with:  python3 verify.py %d --name \"Your Name\"" % number)
        return 1
    profile["name"] = name
    code = evidence_code(number, name)
    profile["banked"][str(number)] = code
    if number in profile.get("caught_up", []):
        profile["caught_up"] = [s for s in profile["caught_up"] if s != number]
        flagged = set(profile.get("banked_from_checkpoint", []))
        flagged.add(number)
        profile["banked_from_checkpoint"] = sorted(flagged)
        print("\n  (This ran on code you loaded with catchup.py. Banked, and recorded as")
        print("   loaded rather than built — that's for the facilitator, not a penalty.)")
    evidence_path = _save_profile(profile)
    print("\nAll checks passed. Evidence code: %s" % code)
    print("Type it into the site to bank step %d." % number)
    if evidence_path:
        print("Also written: %s — push it so your pod can see it:\n"
              "  git add evidence/ && git commit -m \"evidence\" && git push origin HEAD\n"
              "  (your own file, nobody else touches it — safe to push mid-block)"
              % os.path.relpath(evidence_path, HERE))

    # Non-blocking, and only where a block actually ends: gates 4, 6 and 7 are
    # the three that finish a build block, and each is a moment where the pod's
    # one-page readout should not still be describing the previous one.
    if number in (4, 6, 7) and not os.path.exists(os.path.join(HERE, "readout.html")):
        print("\n  Note: the pod's readout is stale — whoever is committer this block runs")
        print("  python3 readout.py before --push-canon.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", nargs="?", type=int)
    parser.add_argument("--name")
    args = parser.parse_args()

    if args.step is None:
        print_board(_load_profile())
        return 0
    return run_step(args.step, args.name)


if __name__ == "__main__":
    sys.exit(main())
