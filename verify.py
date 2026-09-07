#!/usr/bin/env python3
"""verify.py: the gate. Never edit this file; if a check seems wrong, say so
out loud to a facilitator, don't route around it.

    python3 verify.py            # status board: what's banked, what isn't
    python3 verify.py 1.2        # check step 1.2 (Build 1, step 2)
    python3 verify.py 2.1 --name "Your Name"

Steps are named by build: 1.2, 1.3, 1.4 are Build 1; 2.1, 2.2 are Build 2;
3.1 is Build 3; 4.1 is Build 4. The guide uses the same ids.

The verifier checks what happened ON THE WIRE: how many turns, which tools,
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
# Everything this file banks lives here, and nowhere else. .workshop/ is
# per-clone and gitignored: your codes are yours, on your laptop, and nothing
# has to be committed for a gate to count.
PROFILE_PATH = os.path.join(HERE, ".workshop", "profile.json")
# Banked by gate 2.1 so gate 2.2 has a before-number for the same probe. A
# missing file degrades 2.2's comparison; it never blocks it.
BUILD2_TOKENS = os.path.join(HERE, ".workshop", "build2_tokens.json")

# Steps are named by build, in the order they are built. The old integer ids
# (verify.py 2 … 7, the 20 Aug numbering) still resolve through ALIASES so
# nothing that typed them breaks, but every surface (guide, decks, hints)
# speaks the new ids. Evidence codes key on the new ids.
STEP_NAMES = {
    "1.2": "Build 1 · Make the loop hold",
    "1.3": "Build 1 · Make the tools route",
    "1.4": "Build 1 · All five shapes",
    "2.1": "Build 2 · Your own tool",
    "2.2": "Build 2 · The same tool, over MCP",
    "3.1": "Build 3 · Build the proof",
    "4.1": "Build 4 · Pull the lever",
}
STEP_IDS = list(STEP_NAMES)
# Old id → new id. Setup is not a gate any more: setup.py owns it, so the old
# "1" is answered with the command to type instead of a check.
ALIASES = {"2": "1.3", "3": "1.2", "4": "1.4",
           "5": "4.1", "6": "3.1", "7": "2.1"}
# Steps that end a build block: the pod's readout should be fresh at each.
BLOCK_END_STEPS = {"1.4", "2.1", "2.2", "3.1", "4.1"}

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
#
# Every gap in these two is [ \t]* rather than \s*, on purpose: \s matches a
# newline, so `Still broken:` with nothing after it used to swallow the NEXT
# line and read an empty answer as a filled one. A blank line in PITCH.md is
# now unfilled, which is what the shipped template ships as.
LEVER_RE = re.compile(r"^[ \t>*_-]*\**[ \t]*Lever\**[ \t]*:[ \t]*\**[ \t]*(\w+)", re.M | re.I)
STILL_BROKEN_RE = re.compile(
    r"^[ \t>*_-]*\**[ \t]*Still[ _-]?broken\**[ \t]*:[ \t]*\**[ \t]*(\S.*)$", re.M | re.I)
# The shipped PITCH.md carries `Lever: <cost | speed | intelligence>`, which is
# the menu, not a choice. Anything still wearing its angle brackets or still
# offering the alternatives is an unfilled line, and an unfilled line is no
# lane at all.
LEVER_LINE_RE = re.compile(r"^[ \t>*_-]*\**[ \t]*Lever\**[ \t]*:[ \t]*(.*)$", re.M | re.I)


@dataclass
class Check:
    passed: bool
    label: str
    hint: str = ""


@dataclass
class StepContext:
    """What a step is told before it runs. `name` is resolved up front now,
    because gate 3.1 checks whether any eval case carries it."""
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
    """(pod name or None, [member names]) from TEAM.md.

    TEAM.md is two things: `# Pod: <name>` on the first line, then one `- Name`
    per person. Whoever created the repo types it once. Display and attribution
    only, and this never fails: a missing or half-filled file returns empty."""
    pod, members = None, []
    path = os.path.join(HERE, "TEAM.md")
    try:
        with open(path) as fh:
            text = fh.read()
    except OSError:
        text = ""
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"#\s*Pod\s*:\s*(.+)", line, re.I)
        if m:
            pod = pod or m.group(1).strip()
            continue
        if line.startswith("- ") and line[2:].strip():
            members.append(line[2:].strip())
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


_ORDINALS = ("zeroth", "first", "second", "third", "fourth", "fifth", "sixth",
             "seventh", "eighth", "ninth", "tenth", "eleventh", "twelfth",
             "thirteenth", "fourteenth", "fifteenth", "sixteenth", "seventeenth",
             "eighteenth", "nineteenth", "twentieth")


def _ordinal(n: int) -> str:
    """'tenth' for 10. Written out because the gate says it in a sentence, and
    computed because a hardcoded ordinal disagreed with --show-tools."""
    if 0 <= n < len(_ORDINALS):
        return _ORDINALS[n]
    return "%dth" % n


def evidence_code(step: str, name: str) -> str:
    """A speed bump and a telemetry key, not a security boundary. Anyone who
    reads this file can forge a code, and anyone who bothers has already
    learned more than the step teaches."""
    payload = "step:%s|name:%s" % (step, normalize_name(name))
    digest = hmac.new(SHARED_SECRET, payload.encode(), hashlib.sha256).hexdigest().upper()
    return "%s-%s" % (digest[:3], digest[3:6])


def _load_profile() -> dict:
    if os.path.exists(PROFILE_PATH):
        with open(PROFILE_PATH) as f:
            return json.load(f)
    return {"name": None, "banked": {}, "caught_up": [], "banked_from_checkpoint": []}


def _save_profile(profile: dict) -> None:
    """Bank it locally, and only locally. Nothing about a passed gate has to be
    committed or pushed: the code prints on this laptop and stays here."""
    os.makedirs(os.path.dirname(PROFILE_PATH), exist_ok=True)
    with open(PROFILE_PATH, "w") as f:
        json.dump(profile, f, indent=2)


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
            "%s: description is substantive (%d chars, floor is 40), routing is proven "
            "at gate 2.1" % (t["name"], len(desc)),
            hint="The description is the main routing surface, and the field descriptions "
                 "inside input_schema route too. Say when to call it, what it needs, and "
                 "what comes back.",
        ))

    # Length is not routing. A description can clear the floor and still send the
    # wrong argument, and the only place that shows is what the tool ANSWERED.
    # So this gate runs one conversation and reads the results, not the schemas.
    try:
        _text, tracer = call_agent(agent.run_agent, "K7PQ2M", "Marchetti",
                                    "My flight was disrupted. What happens next?")
    except Exception as exc:  # noqa: BLE001: the loop, not the schemas
        raise StepFailure(
            "this gate runs one conversation before it can read any results, and that "
            "conversation stopped on an error:\n\n      %s: %s\n\n"
            "      Gate 1.2 is the one that covers the loop. Clear that first, then "
            "come back to this one." % (type(exc).__name__, exc)
        ) from exc
    if tracer is None:
        raise StepFailure("run_agent() didn't create a tracer. Did you call new_session()?")

    status_calls = [c for c in tracer.tool_calls if c.get("name") == "get_flight_status"]
    refused = [c for c in status_calls if "error" in (c.get("result") or "")]
    checks.append(Check(
        not refused,
        "get_flight_status answered with data, not a refusal (%d of %d call(s) refused)"
        % (len(refused), len(status_calls)),
        hint="the model passed a date the backend refused; what did the field description "
             "tell it? The backend said: %s"
             % (refused[0].get("result") if refused else ""),
    ))
    return checks


def step_3(args) -> List[Check]:
    agent = load_agent()
    try:
        result, tracer = call_agent(agent.run_agent, "K7PQ2M", "Marchetti",
                                     "My flight was disrupted. What happens next?")
    except Exception as exc:  # noqa: BLE001: the API's verdict, handed over whole
        raise StepFailure(
            "the run stopped on an error instead of an answer:\n\n      %s: %s\n\n"
            "      Read that as a statement about the conversation you sent, not about "
            "your Python. It names the message in the list it could not accept and why. "
            "Run python3 run.py K7PQ2M --trace, look at the turn before the one that "
            "failed, and compare what Claude sent on it with what this function put "
            "into messages afterwards." % (type(exc).__name__, exc)
        ) from exc
    if tracer is None:
        raise StepFailure("run_agent() didn't create a tracer. Did you call new_session()?")

    names = tracer.tool_names
    lookup_idx = names.index("lookup_booking") if "lookup_booking" in names else None
    policy_idx = names.index("check_policy") if "check_policy" in names else None
    last_stop = tracer.turns[-1].get("stop_reason") if tracer.turns else None

    return [
        Check(len(tracer.turns) >= 2, "%d API turns (need >= 2)" % len(tracer.turns),
              hint="One turn means the second one never landed. If it came back as a 400 "
                   "saying a tool_result carries a tool_use_id with no matching tool_use in "
                   "the previous message, the API is telling you the two halves of that "
                   "exchange no longer match: you answered a request the transcript you sent "
                   "does not contain. Put what Claude sent on turn 1 next to what this "
                   "function handed back for it and find the difference."),
        Check(len(tracer.tool_calls) >= 2, "%d tool calls (need >= 2)" % len(tracer.tool_calls),
              hint="lookup_booking alone isn't enough. check_policy needs what it returns."),
        Check(lookup_idx is not None and policy_idx is not None and lookup_idx < policy_idx,
              "lookup_booking called before check_policy",
              hint="check_policy resolves entitlements for a booking you haven't looked up yet."),
        Check(len(tracer.turns) <= agent.MAX_TOOL_CALLS,
              "loop stayed within the cap (%d API turns, ceiling %d)"
              % (len(tracer.turns), agent.MAX_TOOL_CALLS),
              hint="MAX_TOOL_CALLS counts API TURNS, not tool calls. One turn can carry "
                   "several calls. Count the turns you take, not the tools you execute, or "
                   "you will cut the loop off early and not know why."),
        Check(last_stop != "tool_use",
              "the loop ran out of tool calls, not out of turns (last stop_reason=%s)"
              % last_stop,
              hint="the trace ends with Claude still asking. Nobody answered the last "
                   "tool call, or the cap cut it off without a handoff."),
        Check(bool(result), "returned a non-empty string",
              hint="Run with --trace and read the LAST turn first. stop_reason=tool_use "
                   "means the conversation never finished. stop_reason=end_turn means it "
                   "did finish, properly, with text. And this function still handed back "
                   "nothing, so what it returned did not come from that turn. Which "
                   "response's text is it returning?"),
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
                "My flight was disrupted. Can you help me figure out what happens next?",
            )
        except Exception as exc:  # noqa: BLE001: surfaced per-ticket, not fatal to the run
            checks.append(Check(False, "%s (%s) ran without an exception" % (task["pnr"], task["shape"]),
                                 hint="%s: %s" % (type(exc).__name__, exc)))
            continue
        good = bool(result) and tracer is not None and len(tracer.tool_calls) >= 1
        if good:
            ok_count += 1
        checks.append(Check(
            good, "%s (%s) resolved with at least one tool call" % (task["pnr"], task["shape"]),
            hint="Empty result or zero tool calls. Read this one with --trace on its own "
                 "PNR. Read what this check asks before you 'fix' anything: the group "
                 "booking escalating is the correct outcome, not a miss.",
        ))
        # DRIFT NOTE: deliberately not asserted: which tool it called, or what
        # it said. That's a model-behaviour question this step doesn't grade;
        # generalizing across five different shapes without crashing or
        # spinning forever is the whole point of step 1.4.

    checks.append(Check(ok_count == len(STAGE1_TASKS),
                         "%d/%d Stage 1 shapes generalized" % (ok_count, len(STAGE1_TASKS)),
                         hint="A loop that works on K7PQ2M and nowhere else is a loop tuned to "
                              "one ticket. Fix the shape that failed above and re-run all five: "
                              "python3 run.py --all --trace."))
    checks.append(Check(True,
                        "(R8KD3F, the abusive-message ticket, comes back calm and helpful with "
                        "no gate on tone at all. That is Build 4's work, not a bug to fix "
                        "here. Fixing it now hides the gap this run exists to show you.)"))
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
    """Read the lever out of PITCH.md. Convention: a line reading 'Lever: cost'.

    Returns None for a line that is still the shipped placeholder, so the gate
    says "no lever declared" rather than picking the first word off the menu.
    """
    path = os.path.join(HERE, "PITCH.md")
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        text = fh.read()
    line = LEVER_LINE_RE.search(text)
    if line is not None:
        value = line.group(1).strip().strip("*").strip()
        # Unfilled: empty, still bracketed, or still listing the alternatives.
        if not value or value.startswith("<") or "|" in value:
            return None
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


def _cost_lane_hint(after: dict) -> str:
    """The cost lane's hint, chosen by what the after-bench actually says about
    caching. Three different states, three different questions:

      cache_hit_pct is None   nothing was ever marked for reuse. bench.py
                              prints `cache  not used on any turn`.
      cache_hit_pct == 0.0    something WAS marked and nothing was ever found.
      anything else           caching is working and the cost is elsewhere.

    None and 0.0 are different facts (support/trace.py is explicit about it),
    and the hint that covers one is nonsense for the other. Symptom only: this
    never names the parameter, the line, or the file to change.
    """
    floor = "Needs a %.0f%% reduction in model cost per contact. " % (MIN_IMPROVEMENT * 100)
    hit = after.get("cache_hit_pct")
    if hit is None:
        return (floor + "Your after-bench says nothing was ever marked for reuse: the cache "
                        "line reads 'not used on any turn', which is not the same fact as a "
                        "0% hit rate. Nothing is being kept between calls yet, so a stable "
                        "prefix has nothing to hit. What would the API have to be told, "
                        "about the part of the request that does not change, before it can "
                        "keep anything between calls?")
    if hit <= 0.0:
        return (floor + "Your after-bench says caching is switched on and reading a 0% hit "
                        "rate: something is being kept and nothing is ever found again. "
                        "Print what goes out at the very top of every request, two calls in "
                        "a row, and ask which characters are not identical.")
    return (floor + "Caching is reading a hit rate of %.0f%%, so the prefix is being reused and "
                    "the rest of the bill is somewhere else: tokens per contact, turns per "
                    "contact, or output length. --compare says which of the three moved." % hit)


def step_5(args) -> List[Check]:
    """Lane-aware. Grades movement on the metric the pod itself declared, and
    refuses to reward a win that broke stage 1."""
    lane = _declared_lane()
    checks = [Check(lane is not None,
                    "PITCH.md: the 'Lever:' line names one lane%s"
                    % (" (%s)" % lane if lane else ""),
                    hint="PITCH.md ships that line as Lever: <cost | speed | intelligence>, "
                         "which is the menu. Replace the whole thing after the colon with "
                         "the one word you picked: Lever: cost. Build 4 is where you pick "
                         "it, and the gate grades the metric that word names.")]
    # No early return on a missing lever. The bench pair either exists or it
    # does not, and a pod that measured well and forgot the line should see that
    # on the same board as the line they forgot.

    before, after = _bench("before"), _bench("after")
    checks.append(Check(before is not None, "a 'before' bench exists",
                        hint="python3 bench.py --label before --stage 1, and it has to be "
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
        guard_hint = ("Stage 1 resolved 5/5 before your change and %.0f%% after. Whatever you "
                      "pulled, it broke a shape that used to work. Read bench-after.json's "
                      "failures list." % after_resolved)
    else:
        guard_hint = ("Stage 1 was already at %.0f%% BEFORE your change, so this is not a "
                      "regression: it is a shape that never worked. Fix that first: a lane "
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
                            hint=_cost_lane_hint(after)))
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
                        hint="Add \"author\": \"%s\" to the case you wrote. This is the one "
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
    # Every case eval_harness attempted, including the ones it marked UNKNOWN
    # because the grader could not read its own judge. UNKNOWN is a case that
    # RAN: it is out of the pass rate, never out of the coverage count.
    ran_ids = [entry["case"]["id"] for entry in report.get("cases", [])]
    checks.append(Check(bool(ran_ids) and set(ran_ids) <= set(ids),
                        "the last eval_harness run was YOUR cases, not the examples",
                        hint="Ran %s; cases.json has %s. Run: python3 eval_harness.py"
                             % (ran_ids, ids)))
    # Deliberately NOT asserted: that the evals passed. A blocked release with a
    # named hard gate is a legitimate, honest outcome for this block, and gating
    # on a green run would teach pods to write cases they know they pass.
    rep = report.get("report", {})
    ran = rep.get("cases", 0)
    unknown = rep.get("unknown") or 0
    scored = rep.get("scored", ran)
    checks.append(Check(ran >= 3,
                        "the run covered at least 3 cases (ran %d of the %d in cases.json, "
                        "%d scored%s, release %s)"
                        % (ran, len(ids), scored,
                           "" if not unknown
                           else ", %d the grader could not read" % unknown,
                           rep.get("release", "?")),
                        hint="This asks about COVERAGE, not about passing. BLOCKED with a named "
                             "hard gate is a legitimate result and is not scored down anywhere "
                             "in this exercise. And if a case fails on behaviour you believe was "
                             "right, suspect the rubric before the agent: read "
                             "evals/GRADER-BUG.md, which is that exact failure from Larkspur's "
                             "own week 8."))

    # Informational, never blocking. The panel reads .workshop/bench-after.json,
    # which Build 4 produces, and Build 4 comes after this gate. A pod that has
    # not benched yet is on schedule, not behind.
    bench_after = _bench("after")
    if bench_after is None:
        checks.append(Check(True,
                            "(no bench pair yet. The evidence panel will show bench numbers "
                            "once Build 4 runs. Nothing required here.)"))
    else:
        checks.append(Check(True, "the evidence panel has numbers to show"))

    pitch = os.path.join(HERE, "PITCH.md")
    claim = ""
    if os.path.exists(pitch):
        with open(pitch) as fh:
            claim = fh.read()
    checks.append(Check(bool(re.search(r"\d", claim)),
                        "PITCH.md, whole file: some line carries a number "
                        "(the 'Number:' line is where it belongs)",
                        hint="One number, its unit, and its denominator. "
                             "'$0.11 per resolved contact, 5 shapes, 3 runs each'."))
    checks.append(Check(len(claim.split()) >= 40,
                        "PITCH.md, whole file: more than the shipped template (%d words, "
                        "floor is 40)" % len(claim.split()),
                        hint="The template ships at 27 words, so this fails until the six "
                             "lines are answered in your own words. Built, Does, Number, "
                             "Guardrail, Next, Still broken."))
    # Sh2, and it is scored, not suggested: a line naming one thing that still
    # does not work. "We did not measure that" is worth more than a number you
    # cannot defend, and this line is where that stops being a slogan.
    broken = STILL_BROKEN_RE.search(claim)
    checks.append(Check(bool(broken),
                        "PITCH.md: the 'Still broken:' line names one thing that still does "
                        "not work",
                        hint="PITCH.md ships that line empty. Answer it on the same line: "
                             "'Still broken: nothing watches tone'. The tone gate you "
                             "measured and left is a legitimate entry. An empty one is not."))
    return checks


def _build2_probe() -> tuple:
    """The pod's own Build 2 probe: (pnr, last_name, message, warning-or-None).

    One customer message the pod's new tool exists to answer, in
    build2_probe.txt at the repo root (three lines: PNR, last name, message).
    It lives at the root, not in .workshop/, because it is a pod artifact. One
    person writes the question and everybody's gate runs it. Writing that
    question IS the spec.

    Gates 2.1 and 2.2 both call this, so the two can never drift onto different
    questions: 2.2's whole claim is that nothing changed except who owns the
    tool, and that claim needs the same probe on both sides.

    Without one, the default probes the scaffolded tool: J5NU8S is two
    passengers stranded at DEN on a cancelled DEN-BOI, and "what is the soonest
    day" is a question about DATES that search_alternatives cannot be pointed at.
    It takes a pnr and nothing else. The fixtures answer it truthfully (the
    earliest open seat is 9 May 2025), which matters: a default probe whose
    honest answer is "nothing in the horizon" would pass on a hallucinated date.
    """
    probe_path = os.path.join(HERE, "build2_probe.txt")
    legacy_path = os.path.join(HERE, ".workshop", "build2_probe.txt")
    source = probe_path if os.path.exists(probe_path) else (
        legacy_path if os.path.exists(legacy_path) else None)
    pnr, last = "J5NU8S", "Calloway"
    msg = ("Our Boise flight was cancelled and we are stuck at Denver overnight. "
           "What is the soonest day you could actually get us out?")
    warning = None
    if source:
        with open(source) as fh:
            lines = [l.strip() for l in fh if l.strip()]
        if len(lines) >= 3:
            pnr, last, msg = lines[0], lines[1], " ".join(lines[2:])
        else:
            warning = Check(False, "%s has three lines" % os.path.relpath(source, HERE),
                            hint="PNR on line 1, last name on line 2, the customer's message "
                                 "on line 3. Found %d non-empty line(s); running the default "
                                 "probe instead." % len(lines))
    return pnr, last, msg, warning


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

    # The pod's own probe, shared with gate 2.2 so the two cannot drift.
    pnr, last, msg, probe_warning = _build2_probe()
    if probe_warning is not None:
        checks.append(probe_warning)

    # Three attempts, first success wins. Whether the model reaches for a tool is
    # a sampled decision, and one refusal is not evidence of a bad description:
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
                        hint="Three attempts, none of them reached for your tool. That is a "
                             "routing result, not bad luck. Two suspects, in order: the "
                             "description, including the field descriptions inside "
                             "input_schema (an over-constrained argument description is a "
                             "routing failure that looks like judgement), then the probe. "
                             "Write the one customer message your tool exists to answer into "
                             "build2_probe.txt at the repo root (three lines: PNR, last name, "
                             "message)."))
    checks.append(Check(bool(result), "returned a non-empty string"))
    summary = tracer.summary() if tracer else {}
    # The ordinal is computed from the list that actually went out, so it can
    # never disagree with what run.py --show-tools prints on the same file.
    assemble = getattr(agent, "tool_list", None)
    offered = list(assemble() or []) if callable(assemble) else tools
    checks.append(Check(True, "(that probe cost %s tokens in across %d tool call(s), the %s "
                              "tool is not free, and this is the number that says what it "
                              "cost)"
                        % ("{:,}".format((summary.get("tokens") or {}).get("input", 0) or 0),
                           summary.get("tool_calls", 0) or 0, _ordinal(len(offered)))))
    # Banked so gate 2.2 can say whether moving the tool onto a server changed
    # what it costs. It does not, and that is the point.
    try:
        os.makedirs(os.path.dirname(BUILD2_TOKENS), exist_ok=True)
        with open(BUILD2_TOKENS, "w") as fh:
            json.dump({"tokens_in": (summary.get("tokens") or {}).get("input", 0) or 0,
                       "tool_calls": summary.get("tool_calls", 0) or 0}, fh)
    except OSError:
        pass  # a missing before-number degrades gate 2.2, it never blocks it
    return checks


def step_2_2(args) -> List[Check]:
    """Build 2, phase two. The tool Claude calls is served by a separate
    program now. The schema did not change, the routing did not change, and the
    token bill did not change. Ownership changed, and that is the only thing
    this gate can see from the outside."""
    agent = load_agent()

    # What the server itself says it has. No credential needed for this part,
    # and a fresh process, so a stale one cannot pass this on the agent's behalf.
    try:
        from support import mcp_client
        mcp_client.close()
        mcp_schemas = mcp_client.discover()
    except Exception as exc:  # noqa: BLE001
        return [Check(False, "the MCP server answers tools/list",
                      hint="Nothing below can pass while the server will not start. "
                           "python3 support/mcp_selftest.py prints the reason on one line. "
                           "(%s: %s)" % (type(exc).__name__, exc))]

    mcp_names = {s["name"] for s in mcp_schemas}
    checks = [Check(bool(mcp_names), "the MCP server answers tools/list (%s)"
                    % (", ".join(sorted(mcp_names)) or "no tools"))]

    # 1. The merge. What the agent offers Claude on every turn is what
    # --show-tools prints, so a participant sees this same list.
    assemble = getattr(agent, "tool_list", None)
    if callable(assemble):
        offered_list = list(assemble() or [])
    else:
        offered_list = list(agent.build_tools()) + list(agent.EXTRA_TOOLS or [])
    offered = [t["name"] for t in offered_list]
    # After the agent has assembled its own list, the client's own record of
    # what came over the wire is the honest answer to "which of these are MCP".
    over_wire = set(getattr(mcp_client, "tool_names", set())) & mcp_names
    merged = sorted(set(offered) & over_wire)
    checks.append(Check(bool(merged),
                        "at least one MCP tool is offered to Claude (%s)"
                        % (", ".join(merged) or "none"),
                        hint="--show-tools lists nine tools and none from the server. The "
                             "server is answering; Claude is never told. The list that goes "
                             "out on every turn is assembled in agent.py, in one line, and "
                             "that line is the seam."))
    if not merged:
        return checks

    # 2. One name, one owner. The N+M point, made checkable.
    doubled = sorted(set(merged) & set(agent.LOCAL_TOOLS or {}))
    twice = sorted({n for n in offered if offered.count(n) > 1})
    clean = not doubled and not twice
    detail = ", ".join(doubled or twice) or "clean"
    checks.append(Check(clean,
                        "no tool name is served twice, once here and once over MCP (%s)"
                        % detail,
                        hint="That name shows up twice: the local copy is still registered. "
                             "Two programs answer to it, and which one runs depends on which "
                             "branch the dispatch reaches first. Pick one owner and delete "
                             "the other."))
    if not clean:
        return checks

    pnr, last, msg, probe_warning = _build2_probe()
    if probe_warning is not None:
        checks.append(probe_warning)

    # 3. It fired. Three attempts, first success wins, same rule as 2.1:
    # whether the model reaches for a tool is a sampled decision, and one
    # refusal is not evidence of a bad description.
    attempts, called, tracer, result = 3, [], None, ""
    for _attempt in range(attempts):
        result, tracer = call_agent(agent.run_agent, pnr, last, msg)
        called = [n for n in (tracer.tool_names if tracer else []) if n in merged]
        if called:
            break
    checks.append(Check(bool(called),
                        "an MCP-discovered tool fired on the pod's probe (%s, attempt %d "
                        "of %d)" % (", ".join(called) or "not called", _attempt + 1, attempts),
                        hint="Three attempts and it never reached for the tool. That is a "
                             "routing result, not bad luck, and it is the same suspect as at "
                             "2.1: the description, including the field descriptions inside "
                             "the input schema. What changed is where that text lives. It is "
                             "in support/mcp_server.py now, not in agent.py. Edit it there, "
                             "restart nothing, re-run."))
    checks.append(Check(bool(result), "returned a non-empty string"))

    # 4. The measurement, and it is a print, not a gate. Same schema, same tax
    # but sampling moves turns around, and a gate that fails on a turn the
    # model chose to take teaches the wrong lesson.
    summary = tracer.summary() if tracer else {}
    after = (summary.get("tokens") or {}).get("input", 0) or 0
    before = None
    try:
        with open(BUILD2_TOKENS) as fh:
            before = json.load(fh).get("tokens_in") or None
    except (OSError, ValueError):
        before = None
    if before:
        delta = after - before
        noise = max(200, int(before * 0.10))
        verdict = "inside" if abs(delta) <= noise else "outside"
        checks.append(Check(True,
                            "(tokens in: %s at 2.1, %s here, %+d: %s the +/- %d noise band. "
                            "Same schema, same tax. A jump up means the tool list GREW "
                            "rather than changed hands; --show-tools says which, in one "
                            "screen.)"
                            % ("{:,}".format(before), "{:,}".format(after), delta,
                               verdict, noise)))
    else:
        checks.append(Check(True, "(no banked token count from 2.1, so the "
                                  "same-schema-same-tax comparison is skipped. This probe "
                                  "cost %s tokens in across %d tool call(s).)"
                            % ("{:,}".format(after), summary.get("tool_calls", 0) or 0)))
    return checks


STEPS = {"1.3": step_2, "1.2": step_3, "1.4": step_4,
         "4.1": step_5, "3.1": step_6, "2.1": step_7, "2.2": step_2_2}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def print_board(profile: dict) -> None:
    try:
        pod, members = read_roster()
    except Exception:  # noqa: BLE001: a header must never take the board down
        pod, members = None, []
    if pod or members:
        head = "POD %s" % pod if pod else "POD: no name in TEAM.md yet"
        if members:
            head += " · %d member%s" % (len(members), "" if len(members) == 1 else "s")
        print("\n" + head)

    print("\nSTATUS")
    next_step = None
    for n, label in STEP_NAMES.items():
        code = profile["banked"].get(n)
        mark = "✓ banked %s" % code if code else "-"
        flag = "  (loaded, not banked)" if n in profile.get("caught_up", []) else ""
        print("  %-4s %-36s %s%s" % (n, label, mark, flag))
        if code is None and next_step is None and n in STEPS:
            next_step = n

    if next_step:
        print("\nNext: python3 verify.py %s" % next_step)
    else:
        print("\nEvery gate on this laptop is banked.")


def _resolve_name(profile: dict, name: Optional[str]) -> str:
    """Up front, before any check runs. Gate 3.1 asks whether an eval case
    carries this name, so it cannot be settled at banking time any more."""
    if name:
        return name.strip()
    if profile.get("name"):
        return profile["name"]
    try:
        return input("Your name, for the evidence code (gate 3.1 also looks for it on your "
                     "eval case): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


def resolve_step(raw: str) -> Optional[str]:
    """'1.2' as typed, or '3' via the old numbering."""
    raw = (raw or "").strip()
    if raw in STEPS:
        return raw
    if raw.lower() in ("setup", "1"):
        print("  Setup is not a gate. One command owns it:\n")
        print("    python3 setup.py\n")
        print("  Run it until it says READY.")
        return None
    if raw in ALIASES and ALIASES[raw] in STEPS:
        print("  (step %s is now called %s; the guide uses the new name)" % (raw, ALIASES[raw]))
        return ALIASES[raw]
    return None


def run_step(raw: str, name: Optional[str]) -> int:
    number = resolve_step(raw)
    if number is None:
        if (raw or "").strip().lower() not in ("setup", "1"):
            print("No such step: %s (have %s)" % (raw, ", ".join(STEP_IDS)))
        return 1
    profile = _load_profile()
    name = _resolve_name(profile, name)
    print("\nStep %s: %s\n" % (number, STEP_NAMES.get(number, "Setup")))
    try:
        checks = STEPS[number](StepContext(name=name))
    except StepFailure as exc:
        print("  ✗ %s" % exc)
        return 1
    except Exception:  # noqa: BLE001: a real bug in the participant's code
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
        print("Re-run with:  python3 verify.py %s --name \"Your Name\"" % number)
        return 1
    profile["name"] = name
    code = evidence_code(number, name)
    profile["banked"][number] = code
    if number in profile.get("caught_up", []):
        profile["caught_up"] = [s for s in profile["caught_up"] if s != number]
        flagged = set(profile.get("banked_from_checkpoint", []))
        flagged.add(number)
        profile["banked_from_checkpoint"] = sorted(flagged)
        print("\n  (This ran on code you loaded with catchup.py. Banked, and recorded as")
        print("   loaded rather than built. That's for the facilitator, not a penalty.)")
    _save_profile(profile)
    print("\nAll checks passed. Evidence code: %s" % code)
    print("That code is your receipt for step %s. Nothing to upload." % number)

    # Non-blocking, and only where a build actually ends: 1.4, 2.1, 2.2, 3.1 and
    # 4.1 are the steps that finish a build, and each is a moment where the pod's
    # one-page readout should not still be describing the previous one.
    if number in BLOCK_END_STEPS and not os.path.exists(os.path.join(HERE, "readout.html")):
        print("\n  Note: the pod's readout is stale. Whoever is committer this block runs")
        print("  python3 readout.py before --push-canon.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", nargs="?", help="1.2, 1.3, 1.4, 2.1, 2.2, 3.1, 4.1")
    parser.add_argument("--name")
    args = parser.parse_args()

    if args.step is None:
        print_board(_load_profile())
        return 0
    return run_step(args.step, args.name)


if __name__ == "__main__":
    sys.exit(main())
