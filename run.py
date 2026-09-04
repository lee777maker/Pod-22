#!/usr/bin/env python3
"""run.py — drive your agent and watch what it does.

    python3 run.py K7PQ2M                # the plain tool loop (Step 3)
    python3 run.py K7PQ2M --trace        # same, with the wire trace
    python3 run.py --show-tools          # Step 2 — what Claude sees about your tools
    python3 run.py --all --trace         # every Stage 1 PNR (Step 4)

--trace prints the wire: every API turn, the parameters you sent, the blocks
that came back, the tools Claude picked, and what it cost. Read it. The trace
is the lesson; the answer is just the by-product.

Every run also writes the trace to .workshop/last_trace.json — with or without
--trace, and under --all it is the LAST of the five that survives. That file is
what `python3 readout.py` turns into the pod's one-page readout, so a run you
never made is a readout you cannot render.
"""

from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import agent  # noqa: E402
from support import DEFAULT_LAST_NAME, DEFAULT_PNR, STAGE1_TASKS  # noqa: E402

DEFAULT_MESSAGE = "My flight was disrupted — can you help me figure out what happens next?"


def _last_name_for(pnr: str):
    for task in STAGE1_TASKS:
        if task["pnr"] == pnr:
            return task["last_name"]
    return None


def run_one(pnr: str, last_name: str, message: str, trace: bool) -> None:
    print(f"\n=== {pnr} ({last_name}) ===")
    try:
        result = agent.run_agent(pnr, last_name, message)
    except NotImplementedError as exc:
        print(f"\n[--] {exc}\n     That's the exercise, not a bug. Build it, then re-run.")
        return

    tracer = agent.LAST.tracer
    if result:
        print(f"\n{result}")
    else:
        print(
            "\n(nothing)\n\n"
            "  Claude didn't send any text. Read the trace below: if the last turn says\n"
            "  stop_reason=tool_use, it asked for a tool and the conversation ended before\n"
            "  anyone answered. That's the thing you're fixing."
        )

    if tracer is None:
        return

    # Saved on EVERY run, traced or not. readout.py reads exactly this file, and
    # under --all the last shape to run is the one that survives here.
    saved, save_error = None, None
    try:
        saved = tracer.save(os.path.join(HERE, ".workshop", "last_trace.json"))
    except OSError as exc:
        save_error = f"{type(exc).__name__}: {exc}"

    s = tracer.summary()
    where = os.path.relpath(saved, HERE) if saved else f"not saved ({save_error})"
    if not trace:
        print(
            f"\n  [{s['turns']} turns · {s['tool_calls']} tool calls · "
            f"{s['tokens']['output']} out tokens · {s['elapsed']}s · trace → {where}]"
            f"  add --trace to see the wire"
        )
    else:
        print("\n" + tracer.render())
        print(f"\n  trace → {where}   (python3 readout.py renders this one)")


def show_tools() -> None:
    tools = agent.build_tools()
    print("\nWHAT CLAUDE ACTUALLY RECEIVES ABOUT YOUR TOOLS")
    print("=" * 66)
    for t in tools:
        desc = t.get("description", "")
        flag = f"  <-- {len(desc)} characters" if len(desc) < 40 else ""
        print(f"\n{t['name']}{flag}")
        print(f"  {desc!r}")
    print("\n" + "=" * 66)
    print("Read that back and ask: could you do this job from that briefing?\n"
          "Write the answer in SPEC.md first, then put it in build_tools().")


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
        print("and a podmate's screen — flag it to a facilitator.")
        return 1

    if args.show_tools:
        show_tools()
        return 0

    if args.all:
        for task in STAGE1_TASKS:
            run_one(task["pnr"], task["last_name"], args.message, args.trace)
        return 0

    pnr = args.pnr or DEFAULT_PNR
    last_name = args.last_name or _last_name_for(pnr) or DEFAULT_LAST_NAME
    run_one(pnr, last_name, args.message, args.trace)
    return 0


if __name__ == "__main__":
    sys.exit(main())
