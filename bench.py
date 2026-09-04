#!/usr/bin/env python3
"""bench.py — measure your agent. GIVEN; you should not need to edit this.

    python3 bench.py --label before               # 5 Stage 1 shapes, 1 run each
    python3 bench.py --label before --runs 3      # 3 runs each, for a real p95
    python3 bench.py --label after --stage 2      # the harder shapes
    python3 bench.py --compare before after       # what your lever actually did

Every lane measures with this. The cost lane reads the token and cache columns,
the speed lane reads p50/p95, the intelligence lane reads the resolved count on
stage 2. One harness, so a pod never has to argue about whose numbers are whose.

Results land in .workshop/bench-<label>.json. The gate (verify.py 5) reads two
of those files, so a pod that tunes before it measures has nothing to show.

On the modelled cost: it is a model of MODEL's published per-token price applied
to what your run actually consumed, and it is the *model* cost only. Larkspur's
loaded cost per resolved contact was about $0.14 against a model cost of $0.087,
so roughly 40% of the real number is infrastructure and evals rather than
inference. Report it as model cost or say "loaded, estimated". Do not quietly
call it the loaded number.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

WORKSHOP = os.path.join(HERE, ".workshop")

# Larkspur's disruption chat volume, for the at-volume line. ~19M pax/yr with
# disruption at 31% of contacts works out to roughly this many disruption chats
# a week. Swap in the client's own number — the point is that per-contact cost
# means nothing to a sponsor until it is multiplied by THEIR week.
WEEKLY_VOLUME = 13_700
HUMAN_COST = 6.90

# Per-million-token prices for the model the exercise ships with. Cache reads
# are cheaper than fresh input and cache writes cost a little more; that spread
# is the entire economic argument for caching, so it is modelled rather than
# ignored.
PRICES = {
    "claude-sonnet-5": {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75},
    "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00, "cache_read": 0.10, "cache_write": 1.25},
}
DEFAULT_PRICE = PRICES["claude-sonnet-5"]


def price_for(model: str) -> dict:
    if model in PRICES:
        return PRICES[model]
    for known, table in PRICES.items():
        if model and (model.endswith(known) or known in model):
            return table
    return DEFAULT_PRICE


def load_agent():
    for name in list(sys.modules):
        if name == "agent" or name.startswith("support"):
            del sys.modules[name]
    import agent
    return agent


def run_one(agent, task) -> dict:
    """One conversation. Never raises: a shape that blows up is a data point.

    `resolved` below means the agent returned text without raising. It does NOT
    mean the answer was right, and nothing in this file can tell you that —
    `rules_pass` is the closest thing, and it only reads the wire. Say
    "resolved" out loud in a pitch and somebody will hear "handled correctly".
    """
    from support import DEFAULT_MESSAGE
    t0 = time.time()
    try:
        reply = agent.run_agent(
            task["pnr"], task["last_name"],
            task.get("message") or DEFAULT_MESSAGE,
        )
        error = None
    except Exception as exc:  # noqa: BLE001 — a crashed shape is a measurement
        reply, error = "", "%s: %s" % (type(exc).__name__, exc)

    wall = time.time() - t0
    tracer = getattr(getattr(agent, "LAST", None), "tracer", None)
    summary = tracer.summary() if tracer else {}
    tokens = summary.get("tokens") or {}

    return {
        "pnr": task["pnr"],
        "shape": task["shape"],
        "resolved": bool(reply) and error is None,
        "error": error,
        "wall": round(wall, 2),
        "turns": summary.get("turns", 0),
        "tool_calls": summary.get("tool_calls", 0),
        "input": tokens.get("input", 0),
        "output": tokens.get("output", 0),
        "cache_read": tokens.get("cache_read", 0),
        "cache_write": tokens.get("cache_write", 0),
        "reply_chars": len(reply or ""),
        "reply": reply or "",
        # Deterministic wire check, from the task's own `rules`. Free, no judge,
        # and independent of the Block 13 eval suite, so a Block 15 bench stands
        # on its own. It catches the tone gate (never called escalate_to_human)
        # which "resolved" cannot.
        "rules_pass": rules_verdict(task, tracer.tool_names if tracer else []),
        "suite": task.get("suite"),
        "hard_gate": bool(task.get("hard_gate")),
    }


def rules_verdict(task, called):
    """None when the task carries no rules (all of Stage 1)."""
    rules = task.get("rules")
    if not rules:
        return None
    for name in rules.get("must_call", []):
        if name not in called:
            return False
    for name in rules.get("must_not_call", []):
        if name in called:
            return False
    return True


def cost_of(rows, model) -> float:
    """Modelled model-cost per RESOLVED contact. Unresolved runs still cost
    tokens, so they stay in the numerator and out of the denominator — which is
    the honest direction, and it means a agent that fails half its shapes looks
    expensive rather than cheap."""
    p = price_for(model)
    total = sum(
        r["input"] * p["input"] / 1e6
        + r["output"] * p["output"] / 1e6
        + r["cache_read"] * p["cache_read"] / 1e6
        + r["cache_write"] * p["cache_write"] / 1e6
        for r in rows
    )
    resolved = sum(1 for r in rows if r["resolved"]) or 1
    return total / resolved


def percentile(values, q) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return round(values[0], 2)
    ordered = sorted(values)
    # Nearest-rank, which is what an SLA conversation means by p95 and does not
    # interpolate a latency that never happened.
    idx = min(len(ordered) - 1, max(0, int(round(q * len(ordered) + 0.5)) - 1))
    return round(ordered[idx], 2)


def aggregate(rows, model, stage, runs) -> dict:
    walls = [r["wall"] for r in rows]
    resolved = [r for r in rows if r["resolved"]]
    cache_read = sum(r["cache_read"] for r in rows)
    cache_write = sum(r["cache_write"] for r in rows)
    fresh_input = sum(r["input"] for r in rows)
    offered = cache_read + cache_write

    return {
        "model": model,
        "stage": stage,
        "runs_per_shape": runs,
        "n": len(rows),
        "resolved": len(resolved),
        "resolved_pct": round(100.0 * len(resolved) / (len(rows) or 1), 1),
        "p50_s": percentile(walls, 0.50),
        "p95_s": percentile(walls, 0.95),
        "mean_s": round(statistics.fmean(walls), 2) if walls else 0.0,
        "turns_mean": round(statistics.fmean([r["turns"] for r in rows]), 2) if rows else 0,
        "tool_calls_mean": round(statistics.fmean([r["tool_calls"] for r in rows]), 2) if rows else 0,
        "input_per_contact": round(fresh_input / (len(resolved) or 1)),
        "output_per_contact": round(sum(r["output"] for r in rows) / (len(resolved) or 1)),
        "cache_read": cache_read,
        "cache_write": cache_write,
        # None means caching was never switched on, which is a different fact
        # from a 0% hit rate. Do not collapse them.
        "cache_hit_pct": (None if not offered
                          else round(100.0 * cache_read / ((cache_read + fresh_input) or 1), 1)),
        "model_cost_per_contact": round(cost_of(rows, model), 4),
        "rules_checked": sum(1 for r in rows if r.get("rules_pass") is not None),
        "rules_passed": sum(1 for r in rows if r.get("rules_pass") is True),
        "hard_gate_failures": sorted({r["suite"] for r in rows
                                      if r.get("hard_gate") and r.get("rules_pass") is False}),
        "failures": [{"pnr": r["pnr"], "shape": r["shape"], "error": r["error"]}
                     for r in rows if not r["resolved"]],
    }


def render(agg, label) -> str:
    L = ["", "─" * 68, "BENCH  %s   stage %s   %d runs x %d shapes"
         % (label, agg["stage"], agg["runs_per_shape"], agg["n"] // (agg["runs_per_shape"] or 1)),
         "─" * 68,
         "  resolved            %d/%d  (%.0f%%)   returned text and the loop closed — not "
         "\"handled correctly\"" % (agg["resolved"], agg["n"], agg["resolved_pct"]),
         "  latency             p50 %.2fs   p95 %.2fs   mean %.2fs"
         % (agg["p50_s"], agg["p95_s"], agg["mean_s"]),
         "  turns / tool calls  %.2f / %.2f  mean" % (agg["turns_mean"], agg["tool_calls_mean"]),
         "  tokens per contact  %d in   %d out" % (agg["input_per_contact"], agg["output_per_contact"])]
    if agg["cache_hit_pct"] is None:
        L.append("  cache               not used on any turn")
    else:
        L.append("  cache               %d read / %d written   hit %.0f%%"
                 % (agg["cache_read"], agg["cache_write"], agg["cache_hit_pct"]))
    L.append("  model cost/contact  $%.4f   (model only, not loaded)" % agg["model_cost_per_contact"])
    L.append("  at Larkspur volume  $%s/week vs $%s human   (x %s chats/week)"
             % (format(round(agg["model_cost_per_contact"] * WEEKLY_VOLUME), ","),
                format(round(HUMAN_COST * WEEKLY_VOLUME), ","), format(WEEKLY_VOLUME, ",")))
    if agg.get("rules_checked"):
        L.append("  wire rules          %d/%d passed" % (agg["rules_passed"], agg["rules_checked"]))
        if agg["hard_gate_failures"]:
            L.append("  hard gates FAILED   %s" % ", ".join(agg["hard_gate_failures"]))
    if agg["failures"]:
        L.append("")
        L.append("  did not resolve:")
        for f in agg["failures"]:
            L.append("    %s  %-32s %s" % (f["pnr"], f["shape"], f["error"] or "empty reply"))
    L += ["─" * 68, ""]
    return "\n".join(L)


ARROWS = {"down_good": ("better", "worse"), "up_good": ("better", "worse")}


def compare(a_label, b_label) -> int:
    paths = [os.path.join(WORKSHOP, "bench-%s.json" % lbl) for lbl in (a_label, b_label)]
    for p, lbl in zip(paths, (a_label, b_label)):
        if not os.path.exists(p):
            print("No bench file for '%s'. Run: python3 bench.py --label %s" % (lbl, lbl))
            return 1
    a = json.load(open(paths[0]))["summary"]
    b = json.load(open(paths[1]))["summary"]

    # (key, label, lower_is_better, format)
    rows = [
        ("resolved_pct", "resolved", False, "%.0f%%"),
        ("p50_s", "p50 latency", True, "%.2fs"),
        ("p95_s", "p95 latency", True, "%.2fs"),
        ("turns_mean", "turns (mean)", True, "%.2f"),
        ("input_per_contact", "input tokens / contact", True, "%d"),
        ("output_per_contact", "output tokens / contact", True, "%d"),
        ("cache_hit_pct", "cache hit", False, "%.0f%%"),
        ("model_cost_per_contact", "model $ / contact", True, "$%.4f"),
        ("rules_passed", "wire rules passed", False, "%d"),
    ]

    print("")
    print("─" * 74)
    print("COMPARE   %s  →  %s" % (a_label, b_label))
    print("─" * 74)
    print("  %-26s %12s %12s" % ("", a_label, b_label))
    for key, name, lower_better, fmt in rows:
        av, bv = a.get(key), b.get(key)
        if av is None and bv is None:
            print("  %-26s %12s %12s" % (name, "—", "—"))
            continue
        if av is None:
            print("  %-26s %12s %12s   cache turned on" % (name, "off", fmt % bv))
            continue
        if bv is None:
            print("  %-26s %12s %12s   cache turned off" % (name, fmt % av, "off"))
            continue
        delta = bv - av
        if abs(delta) < 1e-9:
            verdict = "no change"
        else:
            improved = (delta < 0) if lower_better else (delta > 0)
            pct = (abs(delta) / abs(av) * 100) if av else 0
            verdict = "%s %s%.0f%%" % ("better" if improved else "worse",
                                        "-" if delta < 0 else "+", pct)
        print("  %-26s %12s %12s   %s" % (name, fmt % av, fmt % bv, verdict))
    print("─" * 74)
    print("  Both runs: stage %s, %s runs per shape."
          % (a.get("stage"), a.get("runs_per_shape")))
    if a.get("stage") != b.get("stage") or a.get("runs_per_shape") != b.get("runs_per_shape"):
        print("  ! These two runs are not comparable: stage %s/%s, runs %s/%s."
              % (a.get("stage"), b.get("stage"), a.get("runs_per_shape"), b.get("runs_per_shape")))
        print("    Re-run so both sides used the same shapes the same number of times.")
    print("")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label", help="name this run, e.g. before / after")
    ap.add_argument("--stage", type=int, default=1, choices=(1, 2), help="which task set")
    ap.add_argument("--runs", type=int, default=1, help="runs per shape (3 for a real p95)")
    ap.add_argument("--compare", nargs=2, metavar=("A", "B"), help="diff two labels")
    args = ap.parse_args()

    if args.compare:
        return compare(*args.compare)
    if not args.label:
        ap.error("--label is required (or use --compare A B)")

    agent = load_agent()
    from support import STAGE1_TASKS, STAGE2_TASKS
    tasks = STAGE1_TASKS if args.stage == 1 else STAGE2_TASKS

    print("\nBenching '%s': stage %d, %d shapes x %d run(s) = %d conversations."
          % (args.label, args.stage, len(tasks), args.runs, len(tasks) * args.runs))
    print("Model: %s\n" % agent.MODEL)

    rows = []
    for run in range(args.runs):
        for task in tasks:
            sys.stdout.write("  %s %-32s " % (task["pnr"], task["shape"]))
            sys.stdout.flush()
            row = run_one(agent, task)
            rows.append(row)
            sys.stdout.write("%5.2fs  %d turns  %s\n"
                             % (row["wall"], row["turns"],
                                "ok" if row["resolved"] else "FAILED"))

    agg = aggregate(rows, agent.MODEL, args.stage, args.runs)
    print(render(agg, args.label))

    os.makedirs(WORKSHOP, exist_ok=True)
    out = os.path.join(WORKSHOP, "bench-%s.json" % args.label)
    with open(out, "w") as fh:
        json.dump({"label": args.label, "summary": agg, "rows": rows}, fh, indent=2)
    print("Saved %s" % os.path.relpath(out, HERE))
    return 0


if __name__ == "__main__":
    sys.exit(main())
