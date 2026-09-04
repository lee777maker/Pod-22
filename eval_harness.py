#!/usr/bin/env python3
"""eval_harness.py — run your eval cases against your agent. GIVEN.

    python3 eval_harness.py                  # run evals/cases.json
    python3 eval_harness.py --example        # run the 5 given examples instead
    python3 eval_harness.py --cases p.json   # run some other case file
    python3 eval_harness.py --case tone-0101 # one case
    python3 eval_harness.py --show           # what's in your case file, no API calls

You write the cases. This runs them, grades them, and applies the gates.

The contract is Larkspur's own, from the engagement (case study, beat 6):

    one call per transcript per suite
    evidence quoted per criterion BEFORE any verdict
    verdict is PASS | FAIL | UNKNOWN, schema-enforced
    UNKNOWN counts as FAIL and queues for the human panel
    one FAIL in a hard-gate suite blocks the release candidate

That last line is the whole point. A release does not ship on an average. It
ships when no hard gate failed.

Three grader types, and a case may carry more than one. ALL of a case's graders
must pass for the case to pass:

    rules    — deterministic, on the wire. must_call / must_not_call.
               Free, instant, and the right grader for an irreversible action.
    lexicon  — deterministic, on the text. must_contain / must_not_contain.
               Cheap. Brittle if you use it for anything subtle.
    judge    — a model call against the case's `expect` prose.
               The only one that can read intent, and the only one that can
               itself be wrong. Version your rubric.

Larkspur's week 8: one suite fell to 37 of 48 overnight and nine of eleven
failures were the grader, not the agent. Fixed in 40 minutes, no rollback. That
is why the judge here reports its own evidence: so you can tell those apart.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

WORKSHOP = os.path.join(HERE, ".workshop")
CASES_PATH = os.path.join(HERE, "evals", "cases.json")
EXAMPLE_PATH = os.path.join(HERE, "evals", "cases.example.json")

JUDGE_MODEL = os.environ.get("LARKSPUR_JUDGE_MODEL", "claude-sonnet-5")
RUBRIC_VERSION = "v2"   # v1 over-specified grnd-0101; see evals/GRADER-BUG.md

VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "evidence": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Verbatim quotes from the transcript. Quote before you judge.",
        },
        "verdict": {"type": "string", "enum": ["PASS", "FAIL", "UNKNOWN"]},
        "why": {"type": "string", "description": "One sentence, referring to the evidence."},
    },
    "required": ["evidence", "verdict", "why"],
    "additionalProperties": False,
}

JUDGE_SYSTEM = """You grade one transcript from an airline disruption-care agent
against one written expectation. You are strict and you are literal.

Rules you follow without exception:

1. Quote the evidence first. Every quote must be verbatim from the transcript.
2. Then give the verdict. PASS only if the expectation is met as written.
3. If the transcript is ambiguous, or the expectation does not clearly apply,
   return UNKNOWN. Do not guess. UNKNOWN is counted as a failure and sent to a
   human panel, which is the correct outcome for a case you cannot call.
4. You are grading against the expectation, not against your own taste. A reply
   you would have written differently still passes if it meets the expectation.
5. Absence matters. If the expectation says the agent must escalate and the
   transcript never escalates, that is a FAIL even if everything said was true."""


# ---------------------------------------------------------------------------
# Graders
# ---------------------------------------------------------------------------
def grade_rules(spec, transcript) -> dict:
    called = transcript["tool_names"]
    problems = []
    for name in spec.get("must_call", []):
        if name not in called:
            problems.append("never called %s" % name)
    for name in spec.get("must_not_call", []):
        if name in called:
            problems.append("called %s, which this case forbids" % name)
    return {
        "grader": "rules",
        "verdict": "FAIL" if problems else "PASS",
        "why": "; ".join(problems) or "tool calls matched the rule",
        "evidence": ["tools called: %s" % (", ".join(called) or "none")],
    }


def grade_lexicon(spec, transcript) -> dict:
    text = (transcript["reply"] or "").lower()
    problems, hits = [], []
    for phrase in spec.get("must_contain", []):
        if phrase.lower() in text:
            hits.append("found '%s'" % phrase)
        else:
            problems.append("missing '%s'" % phrase)
    for phrase in spec.get("must_not_contain", []):
        if phrase.lower() in text:
            problems.append("contains '%s', which this case forbids" % phrase)
    return {
        "grader": "lexicon",
        "verdict": "FAIL" if problems else "PASS",
        "why": "; ".join(problems) or "; ".join(hits) or "no lexicon constraints",
        "evidence": hits,
    }


def grade_judge(spec, transcript, case, client) -> dict:
    prompt = (
        "EXPECTATION\n%s\n\n"
        "WHAT THE CUSTOMER SAID\n%s\n\n"
        "TOOLS THE AGENT CALLED, IN ORDER\n%s\n\n"
        "WHAT THE AGENT REPLIED\n%s\n"
        % (case.get("expect", "(no expectation written)"),
           case.get("message", ""),
           ", ".join(transcript["tool_names"]) or "none",
           transcript["reply"] or "(empty reply)")
    )
    try:
        response = client.messages.create(
            model=JUDGE_MODEL, max_tokens=1500, system=JUDGE_SYSTEM,
            output_config={"format": {"type": "json_schema", "schema": VERDICT_SCHEMA}},
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:  # noqa: BLE001 — a judge that errors is UNKNOWN, not PASS
        return {"grader": "judge", "verdict": "UNKNOWN", "evidence": [],
                "why": "judge call failed: %s: %s" % (type(exc).__name__, exc)}

    text = "".join(b.text for b in response.content if getattr(b, "type", None) == "text")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"grader": "judge", "verdict": "UNKNOWN", "evidence": [],
                "why": "judge did not return parseable JSON"}
    payload["grader"] = "judge"
    payload.setdefault("verdict", "UNKNOWN")
    return payload


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------
def load_agent():
    for name in list(sys.modules):
        if name == "agent" or name.startswith("support"):
            del sys.modules[name]
    import agent
    return agent


def run_case(agent, case) -> dict:
    t0 = time.time()
    try:
        reply = agent.run_agent(case["pnr"], case["last_name"], case["message"])
        error = None
    except Exception as exc:  # noqa: BLE001
        reply, error = "", "%s: %s" % (type(exc).__name__, exc)
    tracer = getattr(getattr(agent, "LAST", None), "tracer", None)
    return {
        "reply": reply,
        "error": error,
        "tool_names": tracer.tool_names if tracer else [],
        "turns": len(tracer.turns) if tracer else 0,
        "wall": round(time.time() - t0, 2),
    }


def grade_case(case, transcript, client) -> dict:
    graders = case.get("graders") or [{"type": "judge"}]
    results = []
    for spec in graders:
        kind = spec.get("type")
        if kind == "rules":
            results.append(grade_rules(spec, transcript))
        elif kind == "lexicon":
            results.append(grade_lexicon(spec, transcript))
        elif kind == "judge":
            results.append(grade_judge(spec, transcript, case, client))
        else:
            results.append({"grader": kind or "?", "verdict": "UNKNOWN", "evidence": [],
                            "why": "unknown grader type %r" % kind})

    # UNKNOWN counts as FAIL, and every grader must pass.
    passed = all(r["verdict"] == "PASS" for r in results)
    if transcript["error"]:
        passed = False
        results.append({"grader": "run", "verdict": "FAIL", "evidence": [],
                        "why": "the agent raised: %s" % transcript["error"]})
    return {"passed": passed, "graders": results}


def gate_report(cases, results) -> dict:
    suites = {}
    for case, res in zip(cases, results):
        s = suites.setdefault(case.get("suite", "unsuited"),
                              {"passed": 0, "failed": 0, "hard_gate": False, "failures": []})
        s["hard_gate"] = s["hard_gate"] or bool(case.get("hard_gate"))
        if res["passed"]:
            s["passed"] += 1
        else:
            s["failed"] += 1
            s["failures"].append(case["id"])

    blocking = [name for name, s in suites.items() if s["hard_gate"] and s["failed"]]
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    return {
        "rubric_version": RUBRIC_VERSION,
        "judge_model": JUDGE_MODEL,
        "cases": total,
        "passed": passed,
        "pass_rate": round(100.0 * passed / (total or 1), 1),
        "suites": suites,
        "blocking_suites": blocking,
        "release": "BLOCKED" if blocking else "CLEAR",
    }


def render(cases, results, report) -> str:
    L = ["", "─" * 74, "EVALS   rubric %s   judge %s" % (report["rubric_version"], report["judge_model"]),
         "─" * 74]
    for case, res in zip(cases, results):
        mark = "PASS" if res["passed"] else "FAIL"
        gate = " [hard gate]" if case.get("hard_gate") else ""
        L.append("  %-4s %-14s %-13s %s%s" % (mark, case["id"], case.get("suite", "-"),
                                               case.get("shape", ""), gate))
        if not res["passed"]:
            for g in res["graders"]:
                if g["verdict"] != "PASS":
                    L.append("         %s → %s: %s" % (g["grader"], g["verdict"], g["why"]))
                    for quote in (g.get("evidence") or [])[:2]:
                        L.append("           \"%s\"" % str(quote)[:96])
    L += ["─" * 74,
          "  %d/%d cases passed  (%.0f%%)" % (report["passed"], report["cases"], report["pass_rate"])]
    for name, s in sorted(report["suites"].items()):
        flag = "  HARD GATE" if s["hard_gate"] else ""
        L.append("  %-16s %d passed  %d failed%s" % (name, s["passed"], s["failed"], flag))
    L.append("")
    if report["blocking_suites"]:
        L.append("  RELEASE BLOCKED by: %s" % ", ".join(report["blocking_suites"]))
        L.append("  One failure in a hard-gate suite blocks a release. Not an average.")
    else:
        L.append("  RELEASE CLEAR — no hard gate failed.")
    L += ["─" * 74, ""]
    return "\n".join(L)


def _shown(path: str) -> str:
    """Relative inside the exercise, as given anywhere else — `--cases` can point
    at another pod's clone, and eleven `../` are not a helpful error message."""
    rel = os.path.relpath(path, HERE)
    return path if rel.startswith("..") else rel


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--example", action="store_true", help="run the given examples")
    ap.add_argument("--cases", metavar="PATH",
                    help="run a different case file — the Block 16 swap (grade another pod's "
                         "cases against your agent) and the Build 4 stretch both need this")
    ap.add_argument("--case", help="run one case by id")
    ap.add_argument("--show", action="store_true", help="list cases, make no API calls")
    args = ap.parse_args()

    path = args.cases or (EXAMPLE_PATH if args.example else CASES_PATH)
    if not os.path.exists(path):
        print("No case file at %s" % _shown(path))
        if not (args.example or args.cases):
            print("\nStart from the examples:")
            print("  cp evals/cases.example.json evals/cases.json")
            print("\nThen make them yours. Three cases, at least two hard gates.")
        return 1

    cases = json.load(open(path))["cases"]
    if args.case:
        cases = [c for c in cases if c["id"] == args.case]
        if not cases:
            print("No case with id %r" % args.case)
            return 1

    if args.show:
        print("\n%-14s %-14s %-7s %s" % ("ID", "SUITE", "GATE", "GRADERS"))
        for c in cases:
            print("%-14s %-14s %-7s %s" % (
                c["id"], c.get("suite", "-"), "hard" if c.get("hard_gate") else "soft",
                ", ".join(g.get("type", "?") for g in (c.get("graders") or [{"type": "judge"}]))))
        print("\n%d cases, %d hard gates.\n"
              % (len(cases), sum(1 for c in cases if c.get("hard_gate"))))
        return 0

    agent = load_agent()
    from support import get_client
    client = get_client()

    print("\nRunning %d case(s) against your agent.\n" % len(cases))
    results = []
    for case in cases:
        sys.stdout.write("  %-14s %-13s " % (case["id"], case.get("suite", "-")))
        sys.stdout.flush()
        transcript = run_case(agent, case)
        result = grade_case(case, transcript, client)
        result["transcript"] = transcript
        results.append(result)
        sys.stdout.write("%s  (%.1fs)\n" % ("PASS" if result["passed"] else "FAIL",
                                             transcript["wall"]))

    report = gate_report(cases, results)
    print(render(cases, results, report))

    os.makedirs(WORKSHOP, exist_ok=True)
    out = os.path.join(WORKSHOP, "evals.json")
    with open(out, "w") as fh:
        json.dump({"report": report,
                   "case_file": _shown(path),
                   "cases": [{"case": c, "result": r} for c, r in zip(cases, results)]},
                  fh, indent=2, default=str)
    print("Saved %s" % os.path.relpath(out, HERE))
    return 0 if not report["blocking_suites"] else 2


if __name__ == "__main__":
    sys.exit(main())
