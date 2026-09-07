#!/usr/bin/env python3
"""run.py: drive your agent and watch what it does.

    python3 run.py K7PQ2M                # the plain tool loop (step 1.2)
    python3 run.py K7PQ2M --trace        # same, with the wire trace
    python3 run.py --show-tools          # step 1.3: what Claude sees about your tools
    python3 run.py --all --trace         # every Stage 1 shape (step 1.4)

--trace prints the wire: every API turn, the parameters you sent, the blocks
that came back, the tools Claude picked, and what it cost. Read it. The trace
is the lesson; the answer is just the by-product.

Every run also writes the trace to .workshop/last_trace.json, with or without
--trace, and under --all it is the LAST of the five that survives. That file is
what `python3 readout.py` turns into the pod's one-page readout, so a run you
never made is a readout you cannot render.

--all additionally writes .workshop/last_run.json: one row per shape plus the
totals, because "it worked on K7PQ2M" and "it worked on all five" are different
claims and only the second one is worth putting on a readout.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import agent  # noqa: E402
from support import DEFAULT_LAST_NAME, DEFAULT_PNR, STAGE1_TASKS  # noqa: E402

DEFAULT_MESSAGE = "My flight was disrupted. Can you help me figure out what happens next?"


def _last_name_for(pnr: str):
    for task in STAGE1_TASKS:
        if task["pnr"] == pnr:
            return task["last_name"]
    return None


def run_one(pnr: str, last_name: str, message: str, trace: bool, shape: str = "") -> dict:
    """Runs one conversation and returns the row --all aggregates. Returns None
    when the agent raised NotImplementedError, which is the unbuilt state and
    not a measurement, and None when the run raised anything else. The run
    broke, so there is no row to aggregate, but the trace up to the break is
    still printed because that is where the answer is."""
    print(f"\n=== {pnr} ({last_name}) ===")
    result, failure = "", None
    try:
        result = agent.run_agent(pnr, last_name, message)
    except NotImplementedError as exc:
        print(f"\n[--] {exc}\n     That's the exercise, not a bug. Build it, then re-run.")
        return None
    except Exception as exc:  # noqa: BLE001
        # A run that raised is still a run that happened, and the tracer already
        # recorded the turn that broke. One line here, then straight on to the
        # trace: the message the API sent back is a statement about the
        # conversation this agent assembled, and the trace is where you read it.
        detail = str(exc)
        if len(detail) > 200:
            detail = detail[:200] + "…"
        failure = f"{type(exc).__name__}: {detail}"
        print(f"\n[!!] {failure}")

    tracer = agent.LAST.tracer
    if failure is not None:
        print(
            "\n  The run stopped on that instead of answering. The trace below ends on the\n"
            "  turn that broke, marked ERROR, and the turns before it are the ones that\n"
            "  set it up. Read the error as a statement about the conversation that went\n"
            "  out, not about your Python."
        )
    elif result:
        print(f"\n{result}")
    else:
        print(
            "\n(nothing)\n\n"
            "  Claude didn't send any text. Read the LAST turn in the trace below.\n"
            "  If it says stop_reason=tool_use, Claude asked for a tool and the\n"
            "  conversation ended before anyone answered it. If it says end_turn, the\n"
            "  conversation did finish, properly, with text, so the question is which\n"
            "  response's text this function handed back."
        )

    if tracer is None:
        return None

    # Saved on EVERY run, traced or not. readout.py reads exactly this file, and
    # under --all the last shape to run is the one that survives here.
    saved, save_error = None, None
    try:
        saved = tracer.save(os.path.join(HERE, ".workshop", "last_trace.json"))
    except OSError as exc:
        save_error = f"{type(exc).__name__}: {exc}"

    s = tracer.summary()
    where = os.path.relpath(saved, HERE) if saved else f"not saved ({save_error})"
    if failure is not None:
        # The wire is the whole point of a broken run, so it prints with or
        # without --trace. Nothing below this is a measurement worth keeping.
        print("\n" + tracer.render())
        print(f"\n  trace → {where}   (python3 readout.py renders this one)")
        return None
    if not trace:
        print(
            f"\n  [{s['turns']} turns · {s['tool_calls']} tool calls · "
            f"{s['tokens']['output']} out tokens · {s['elapsed']}s · trace → {where}]"
            f"  add --trace to see the wire"
        )
    else:
        print("\n" + tracer.render())
        print(f"\n  trace → {where}   (python3 readout.py renders this one)")

    tokens = s.get("tokens") or {}
    return {
        "pnr": pnr,
        "shape": shape,
        "turns": s.get("turns", 0),
        "tool_calls": s.get("tool_calls", 0),
        "tokens_in": tokens.get("input", 0),
        "tokens_out": tokens.get("output", 0),
        "cache_read": tokens.get("cache_read", 0),
        # The last turn's stop_reason is the one that says whether the loop
        # closed or just ran out of road. tool_use here is an unfinished run.
        "stop_reason": tracer.turns[-1].get("stop_reason") if tracer.turns else None,
        "elapsed": s.get("elapsed"),
        "resolved": bool(result),
    }


def run_all(message: str, trace: bool) -> None:
    """Every Stage 1 shape through the same function, then the totals. A loop
    that works on one ticket and nowhere else is a loop tuned to one ticket, and
    the footer is where that stops being an opinion."""
    rows = [r for r in (run_one(t["pnr"], t["last_name"], message, trace, t["shape"])
                        for t in STAGE1_TASKS) if r]
    if not rows:
        return

    totals = {
        "shapes": len(rows),
        "resolved": sum(1 for r in rows if r["resolved"]),
        "turns": sum(r["turns"] for r in rows),
        "tool_calls": sum(r["tool_calls"] for r in rows),
        "tokens_in": sum(r["tokens_in"] for r in rows),
        "tokens_out": sum(r["tokens_out"] for r in rows),
        "cache_read": sum(r["cache_read"] for r in rows),
        "unfinished": [r["pnr"] for r in rows if r["stop_reason"] == "tool_use"],
    }

    path = os.path.join(HERE, ".workshop", "last_run.json")
    where = None
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            json.dump({"generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
                       "shapes": rows, "totals": totals}, fh, indent=2, default=str)
        where = os.path.relpath(path, HERE)
    except OSError as exc:
        where = f"not saved ({type(exc).__name__}: {exc})"

    print("\n" + "=" * 66)
    print("ALL FIVE STAGE 1 SHAPES")
    print("=" * 66)
    print("  %-8s %-30s %5s %5s %9s %9s  %s"
          % ("pnr", "shape", "turns", "tools", "in", "out", "stop_reason"))
    for r in rows:
        print("  %-8s %-30s %5d %5d %9s %9s  %s"
              % (r["pnr"], r["shape"][:30], r["turns"], r["tool_calls"],
                 "{:,}".format(r["tokens_in"]), "{:,}".format(r["tokens_out"]),
                 r["stop_reason"]))
    print("  " + "-" * 64)
    print("  %-8s %-30s %5d %5d %9s %9s  %d/%d returned text"
          % ("TOTAL", "%d shapes" % totals["shapes"], totals["turns"], totals["tool_calls"],
             "{:,}".format(totals["tokens_in"]), "{:,}".format(totals["tokens_out"]),
             totals["resolved"], totals["shapes"]))
    if totals["cache_read"]:
        print("  cache read: %s tokens" % "{:,}".format(totals["cache_read"]))
    if totals["unfinished"]:
        print("  ! ended on stop_reason=tool_use (the loop stopped mid-ask): %s"
              % ", ".join(totals["unfinished"]))
    print("  totals → %s   (python3 readout.py puts these on the page)" % where)
    print("=" * 66)


def show_tools() -> None:
    given = agent.build_tools()
    extra = list(getattr(agent, "EXTRA_TOOLS", []) or [])
    # tool_list() is the list run_agent actually sends, so this print-out cannot
    # drift from the wire. It only reaches the MCP server if the agent's own
    # seam reaches it, which is why nothing here starts a server on day one.
    assemble = getattr(agent, "tool_list", None)
    offered = list(assemble() if callable(assemble) else given + extra)
    # Names that arrived over the wire. Empty until the MCP seam is wired.
    over_mcp = {t["name"] for t in (getattr(agent, "MCP_TOOLS", []) or [])}
    extra_names = {t["name"] for t in extra}
    print("\nWHAT CLAUDE ACTUALLY RECEIVES ABOUT YOUR TOOLS")
    print("=" * 66)
    for t in offered:
        desc = t.get("description", "")
        if t["name"] in over_mcp:
            mine = "  via mcp"
        elif t["name"] in extra_names:
            mine = " + yours"
        else:
            mine = ""
        flag = f"  <-- {len(desc)} characters" if len(desc) < 40 else ""
        print(f"\n{t['name']}{mine}{flag}")
        print(f"  {desc!r}")
    print("\n" + "=" * 66)
    n_mcp = sum(1 for t in offered if t["name"] in over_mcp)
    n_extra = sum(1 for t in offered if t["name"] in extra_names)
    added = []
    if n_extra:
        added.append("%d of yours" % n_extra)
    if n_mcp:
        added.append("%d over MCP" % n_mcp)
    print("%d tool(s) offered on every call: the given nine%s."
          % (len(offered),
             " plus " + " and ".join(added) if added else ", none of yours yet"))
    if n_mcp:
        print("%d of those are served by support/mcp_server.py, a separate program.\n"
              "Claude cannot tell. Same name, same description, same tokens."
              % n_mcp)
    print("Read that back and ask: could you do this job from that briefing?\n"
          "Say the answer out loud first, in your own words, then put it in\n"
          "build_tools() (or EXTRA_TOOLS, for the ones you added).")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("pnr", nargs="?", help="PNR to run, e.g. K7PQ2M")
    parser.add_argument("--last-name", help="required if pnr isn't one of the Stage 1 tasks")
    parser.add_argument("--message", default=DEFAULT_MESSAGE)
    parser.add_argument("--trace", action="store_true")
    parser.add_argument("--show-tools", action="store_true")
    parser.add_argument("--all", action="store_true", help="run all five Stage 1 PNRs")
    parser.add_argument("--offline", action="store_true", help="(removed) there is no offline mode")
    args = parser.parse_args()

    if args.offline:
        print("There is no offline mode in this pack. No network means a raised hand")
        print("and a podmate's screen. Flag it to a facilitator.")
        return 1

    if args.show_tools:
        show_tools()
        return 0

    if args.all:
        run_all(args.message, args.trace)
        return 0

    pnr = args.pnr or DEFAULT_PNR
    last_name = args.last_name or _last_name_for(pnr) or DEFAULT_LAST_NAME
    run_one(pnr, last_name, args.message, args.trace)
    return 0


if __name__ == "__main__":
    sys.exit(main())
