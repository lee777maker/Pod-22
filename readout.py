#!/usr/bin/env python3
"""readout.py — one page that says what your agent IS and what it just DID.

    python3 readout.py                          # uses .workshop/last_trace.json
    python3 readout.py --trace path/to.json     # any saved trace
    python3 readout.py --open                   # write it and open in the browser

Two halves, one self-contained HTML file — readout.html at the repo root:

  ARCHITECTURE — read live from your agent.py: every tool and its description
  length, the loop ceiling, the prompt sizes, what you've added beyond the
  given nine. This is the "what we built" half of your pod's submission.

  THE LOOP — your latest wire trace, drawn as the loop it actually was: each
  API turn, what went up, what came back, which tools fired, and where
  stop_reason finally changed. This is the "prove it ran" half.

Pushing readout.html is the submission — there is nothing to upload. It is also
the fastest way to explain your agent to another pod: one page, no code tour.

It writes readout-trace.json beside it (the trace summary alone) and carries a
copy of the same numbers — plus whichever gates this laptop has banked — inside
the page in a <script id="evidence"> block, so the grader can read a cloned repo
that never had a .workshop/ folder.

Given, like the tracer — reading it is the point, editing it is not.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
import time
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

DEFAULT_TRACE = os.path.join(HERE, ".workshop", "last_trace.json")
# The readout is the pod's submission: it lives at the repo ROOT (committed and
# pushed, unlike .workshop/, which is gitignored). Pushing it IS submitting it.
OUT_PATH = os.path.join(HERE, "readout.html")
PROFILE_PATH = os.path.join(HERE, ".workshop", "profile.json")
GIVEN_TOOL_COUNT = 9  # the nine shipped schemas; anything past this is yours


# ---------------------------------------------------------------------------
# gather
# ---------------------------------------------------------------------------

def read_architecture() -> dict:
    """Introspect agent.py defensively: a half-built agent should still get a
    readout that shows exactly how half-built it is."""
    arch = {"error": None, "tools": [], "max_tool_calls": None,
            "system_prompt_chars": None, "tone_addendum_chars": None,
            "extra_tools": 0, "local_tools": []}
    try:
        import agent
    except Exception as exc:  # noqa: BLE001 - the readout must render anyway
        arch["error"] = "%s: %s" % (type(exc).__name__, exc)
        return arch
    try:
        tools = agent.build_tools()
    except Exception as exc:  # noqa: BLE001
        arch["error"] = "build_tools() failed — %s: %s" % (type(exc).__name__, exc)
        tools = []
    extra = list(getattr(agent, "EXTRA_TOOLS", []) or [])
    arch["extra_tools"] = len(extra)
    for i, t in enumerate(tools + extra):
        desc = t.get("description", "") or ""
        arch["tools"].append({
            "name": t.get("name", "?"),
            "desc_chars": len(desc),
            "desc_head": desc[:110],
            "given": i < GIVEN_TOOL_COUNT and t not in extra,
        })
    arch["max_tool_calls"] = getattr(agent, "MAX_TOOL_CALLS", None)
    prompt = getattr(agent, "SYSTEM_PROMPT", None)
    if prompt is None:
        try:
            from support import prompts  # optional; layout varies
            prompt = getattr(prompts, "SYSTEM_PROMPT", None)
        except Exception:  # noqa: BLE001
            prompt = None
    arch["system_prompt_chars"] = len(prompt) if isinstance(prompt, str) else None
    tone = getattr(agent, "TONE_ADDENDUM", None)
    arch["tone_addendum_chars"] = len(tone.strip()) if isinstance(tone, str) else None
    arch["local_tools"] = sorted((getattr(agent, "LOCAL_TOOLS", {}) or {}).keys())
    return arch


def read_trace(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def read_pod() -> str:
    team = os.path.join(HERE, "TEAM.md")
    if os.path.exists(team):
        with open(team) as f:
            for line in f:
                if line.strip().lower().startswith("# pod"):
                    return line.split(":", 1)[-1].strip()
    return ""


def read_banked() -> dict:
    """What this laptop has banked, out of the gitignored profile. The page
    carries a copy because .workshop/ never travels with a clone — without it a
    facilitator grading a pushed repo sees a build with no gates at all."""
    try:
        with open(PROFILE_PATH) as f:
            profile = json.load(f)
    except (OSError, ValueError):
        return {"name": None, "banked": {}}
    return {"name": profile.get("name"),
            "banked": profile.get("banked") or {}}


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------

CSS = """
body { font: 15px/1.5 -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: #faf7f2; color: #262220; margin: 0; padding: 36px 28px 64px; }
.page { max-width: 880px; margin: 0 auto; }
h1 { font-size: 26px; margin: 0 0 2px; } h1 em { color: #b4562e; font-style: italic; }
h2 { font-size: 15px; letter-spacing: .08em; text-transform: uppercase;
  color: #b4562e; margin: 34px 0 12px; }
.sub { color: #75695f; margin: 0 0 8px; }
.strip { display: flex; gap: 10px; flex-wrap: wrap; margin: 18px 0 6px; }
.stat { background: #fff; border: 1.5px solid #e5dccf; border-top: 4px solid #b4562e;
  border-radius: 8px; padding: 10px 16px; min-width: 108px; }
.stat b { display: block; font-size: 24px; font-weight: 800; }
.stat span { color: #75695f; font-size: 12.5px; }
table { border-collapse: collapse; width: 100%; background: #fff;
  border: 1.5px solid #e5dccf; border-radius: 8px; overflow: hidden; }
th, td { text-align: left; padding: 8px 12px; border-bottom: 1px solid #efe8dc;
  font-size: 13.5px; vertical-align: top; }
th { background: #f4eee4; font-size: 12px; letter-spacing: .05em; text-transform: uppercase;
  color: #75695f; }
.yours td { background: #fdf3ec; }
.pill { display: inline-block; background: #f0e7d9; border-radius: 999px;
  padding: 1px 10px; font-family: ui-monospace, Menlo, monospace; font-size: 12px; }
.pill.you { background: #f5dbc9; }
.turn { background: #fff; border: 1.5px solid #e5dccf; border-left: 5px solid #b4562e;
  border-radius: 8px; padding: 12px 16px; margin: 0 0 4px; }
.turn.done { border-left-color: #3d7a52; }
.turn .hd { font-weight: 700; }
.turn .meta { color: #75695f; font-size: 12.5px; margin-top: 2px; }
.tool { font-family: ui-monospace, Menlo, monospace; font-size: 12.5px;
  background: #f4eee4; border-radius: 6px; padding: 4px 10px; margin: 6px 0 0;
  overflow-wrap: anywhere; }
.loopback { color: #b4562e; font-size: 12.5px; margin: 2px 0 6px 18px; }
.stopped { color: #3d7a52; font-weight: 700; }
.warn { background: #fdf3ec; border: 1.5px solid #eac9ae; border-radius: 8px;
  padding: 10px 14px; color: #8a4a22; }
.foot { color: #a2968b; font-size: 12px; margin-top: 40px; }
"""


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def render(arch: dict, trace: dict, pod: str, trace_path: str, evidence: dict) -> str:
    out = ["<!doctype html><meta charset='utf-8'>"]
    out.append("<title>Agent readout%s</title>" % (" — " + esc(pod) if pod else ""))
    out.append("<style>%s</style><div class='page'>" % CSS)
    out.append("<h1>Agent <em>readout.</em></h1>")
    sub = "Pod %s · " % esc(pod) if pod else ""
    out.append("<p class='sub'>%s%s</p>" % (sub, time.strftime("%Y-%m-%d %H:%M")))

    # -- architecture --------------------------------------------------------
    out.append("<h2>Architecture — what the agent is</h2>")
    if arch["error"]:
        out.append("<p class='warn'>agent.py could not be fully read: %s<br>"
                   "The loop half below still renders — fix the import and re-run for "
                   "the full picture.</p>" % esc(arch["error"]))
    n_tools = len(arch["tools"])
    shortest = min((t["desc_chars"] for t in arch["tools"]), default=0)
    out.append("<div class='strip'>")
    for value, label in [
        (n_tools, "tools registered"),
        (arch["extra_tools"], "beyond the given nine"),
        (arch["max_tool_calls"] if arch["max_tool_calls"] is not None else "?", "loop ceiling"),
        (arch["system_prompt_chars"] if arch["system_prompt_chars"] is not None else "?",
         "system prompt chars"),
        (arch["tone_addendum_chars"] if arch["tone_addendum_chars"] is not None else 0,
         "tone addendum chars"),
    ]:
        out.append("<div class='stat'><b>%s</b><span>%s</span></div>" % (esc(value), esc(label)))
    out.append("</div>")
    if arch["tools"]:
        out.append("<table><tr><th>tool</th><th>description</th><th>chars</th><th></th></tr>")
        for t in arch["tools"]:
            yours = "" if t["given"] else " class='yours'"
            tag = "" if t["given"] else "<span class='pill you'>yours</span>"
            flag = " ⚠" if t["desc_chars"] < 40 else ""
            out.append("<tr%s><td><span class='pill'>%s</span></td><td>%s</td>"
                       "<td>%d%s</td><td>%s</td></tr>"
                       % (yours, esc(t["name"]), esc(t["desc_head"]), t["desc_chars"], flag, tag))
        out.append("</table>")
        if shortest < 40:
            out.append("<p class='sub'>⚠ a description under 40 chars — Claude picks tools "
                       "from that string alone.</p>")
    if arch["local_tools"]:
        out.append("<p class='sub'>local dispatch: %s</p>"
                   % ", ".join("<span class='pill you'>%s</span>" % esc(n)
                               for n in arch["local_tools"]))

    # -- the loop -------------------------------------------------------------
    s = trace.get("summary", {})
    tokens = s.get("tokens", {})
    out.append("<h2>The loop — what it just did</h2>")
    out.append("<p class='sub'>trace: %s</p>" % esc(os.path.relpath(trace_path, HERE)))
    out.append("<div class='strip'>")
    for value, label in [
        (s.get("turns", "?"), "API turns"),
        (s.get("tool_calls", "?"), "tool calls"),
        ("{:,}".format(tokens.get("input", 0)), "tokens in"),
        ("{:,}".format(tokens.get("output", 0)), "tokens out"),
        ("%ss" % s.get("elapsed", "?"), "wall clock"),
    ]:
        out.append("<div class='stat'><b>%s</b><span>%s</span></div>" % (esc(value), esc(label)))
    out.append("</div>")

    turns = trace.get("turns", [])
    for i, t in enumerate(turns, start=1):
        stop = t.get("stop_reason")
        done = stop != "tool_use"
        usage = t.get("usage") or [0, 0]
        out.append("<div class='turn%s'>" % (" done" if done else ""))
        out.append("<div class='hd'>Turn %d → messages.%s()</div>" % (i, esc(t.get("kind", "?"))))
        out.append("<div class='meta'>sent: %s msg in context · %s tools offered</div>"
                   % (esc(t.get("n_messages", "?")), len(t.get("tools") or [])))
        if t.get("error"):
            out.append("<div class='meta'>← <b>ERROR</b>: %s</div>" % esc(t["error"]))
        else:
            out.append("<div class='meta'>← stop_reason=<b%s>%s</b> · blocks: %s · "
                       "in %s / out %s · %.1fs</div>"
                       % (" class='stopped'" if done else "", esc(stop),
                          esc(", ".join(t.get("blocks") or []) or "—"),
                          "{:,}".format(usage[0]), "{:,}".format(usage[1]),
                          t.get("elapsed") or 0.0))
        for call in t.get("tool_calls") or []:
            args = json.dumps(call.get("input", {}), default=str)
            args = args if len(args) <= 100 else args[:99] + "…"
            out.append("<div class='tool'>⚙ %s(%s)</div>" % (esc(call.get("name", "?")), esc(args)))
        out.append("</div>")
        if not done and i < len(turns):
            out.append("<div class='loopback'>↺ stop_reason=tool_use → results appended → "
                       "loop continues</div>")
    if turns:
        last_stop = turns[-1].get("stop_reason")
        if last_stop == "tool_use":
            out.append("<p class='warn'>The trace ENDS on stop_reason=tool_use — the loop "
                       "stopped before the model was finished. That is the Build 1 bug, "
                       "visible right here.</p>")

    out.append("<p class='foot'>Generated by readout.py · Larkspur Airlines is a fictional "
               "training scenario · Confidential / do not distribute</p></div>")

    # The machine-readable half, travelling INSIDE the page. .workshop/ is
    # gitignored, so a facilitator who clones the pod repo has no profile.json
    # and no last_trace.json — this block, and readout-trace.json beside it, are
    # the only evidence that survives a push.
    payload = json.dumps({
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "pod": pod or None,
        "banked_by": evidence.get("name"),
        "banked": evidence.get("banked") or {},
        "trace": trace.get("summary") or {},
    }, default=str)
    out.append("<script type=\"application/json\" id=\"evidence\">%s</script>"
               % payload.replace("</", "<\\/"))
    return "\n".join(out)


# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Render the agent architecture + loop readout.")
    parser.add_argument("--trace", default=DEFAULT_TRACE, help="saved trace JSON")
    parser.add_argument("--out", default=OUT_PATH)
    parser.add_argument("--open", action="store_true", help="open the result in a browser")
    args = parser.parse_args()

    if not os.path.exists(args.trace):
        print("No trace at %s" % os.path.relpath(args.trace, HERE))
        print("Run the agent once first:  python3 run.py <PNR> --trace")
        return 1

    arch = read_architecture()
    trace = read_trace(args.trace)
    pod = read_pod()
    evidence = read_banked()
    page = render(arch, trace, pod, args.trace, evidence)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        f.write(page)

    # The same summary, on its own, beside the page — a grader that wants the
    # numbers should not have to parse HTML to get them.
    side = os.path.join(os.path.dirname(os.path.abspath(args.out)) or ".",
                        "readout-trace.json")
    with open(side, "w") as f:
        json.dump(trace.get("summary") or {}, f, indent=2, default=str)

    s = trace.get("summary", {})
    print("wrote %s" % os.path.relpath(args.out, HERE))
    print("wrote %s" % os.path.relpath(side, HERE))
    print("  architecture: %d tools (%d yours), loop ceiling %s"
          % (len(arch["tools"]), arch["extra_tools"], arch["max_tool_calls"]))
    print("  last run: %s turns, %s tool calls, %s in / %s out"
          % (s.get("turns", "?"), s.get("tool_calls", "?"),
             "{:,}".format(s.get("tokens", {}).get("input", 0)),
             "{:,}".format(s.get("tokens", {}).get("output", 0))))
    banked = sorted((evidence.get("banked") or {}).keys())
    print("  embedded evidence: gates %s%s"
          % (", ".join(banked) or "none banked on this laptop",
             " (%s)" % evidence["name"] if evidence.get("name") else ""))
    if args.open:
        webbrowser.open("file://" + os.path.abspath(args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
