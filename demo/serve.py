#!/usr/bin/env python3
"""demo/serve.py: the client-facing surface. GIVEN.

    python3 demo/serve.py            # then open http://localhost:4390

Two panes. On the left, the chat a customer would see. On the right, the evidence
a sponsor would ask for: your bench numbers, your eval gates, your guardrail.

Why this is given rather than built: a terminal is not a demo, and writing a web
app is not what this half-day is about. You have the first 10 minutes of Build 3 and the
evidence is the work. Making the surface yours is the stretch, not the task.

It calls YOUR run_agent(pnr, last_name, message). Nothing here knows or cares how
you implemented it, so it works with whatever you built.

Endpoints, all stdlib, no dependencies:

    POST /api/chat      {pnr, last_name, message} -> reply + this turn's trace
    GET  /api/evidence  reads .workshop/ and tells the panel what is true
    POST /api/confirm   {hold_id} -> the customer's own click, and a real token

That last one is the guardrail, live in a browser. hold_seat is reversible so the
agent may call it. confirm_rebooking is not, so it needs a token only the
customer's click can produce, and this endpoint is that click. Try it with a
made-up token and watch it refuse.
"""

from __future__ import annotations

import functools
import http.server
import json
import os
import socketserver
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 4390
WORKSHOP = os.path.join(ROOT, ".workshop")


def load_agent():
    """Re-imported per request so an edit shows up without a restart."""
    for name in list(sys.modules):
        if name == "agent" or name.startswith("support"):
            del sys.modules[name]
    import agent
    return agent


def read_json(path, default=None):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return default


def evidence() -> dict:
    """Everything the panel shows, assembled from artifacts the pod actually
    produced. Anything missing is reported as missing rather than faked, because
    a panel with invented numbers on it is worse than an empty one."""
    labels = {}
    if os.path.isdir(WORKSHOP):
        for name in sorted(os.listdir(WORKSHOP)):
            if name.startswith("bench-") and name.endswith(".json"):
                doc = read_json(os.path.join(WORKSHOP, name))
                if doc:
                    labels[doc.get("label") or name[6:-5]] = doc.get("summary")

    evals = read_json(os.path.join(WORKSHOP, "evals.json"))
    profile = read_json(os.path.join(WORKSHOP, "profile.json"), {}) or {}

    pitch_path = os.path.join(ROOT, "PITCH.md")
    pitch = ""
    if os.path.exists(pitch_path):
        with open(pitch_path) as fh:
            pitch = fh.read()

    before = labels.get("before")
    after = labels.get("after")
    deltas = []
    if before and after:
        for key, name, unit, lower_better in (
            ("model_cost_per_contact", "Model cost per resolved contact", "$", True),
            ("p95_s", "p95 latency", "s", True),
            ("input_per_contact", "Input tokens per contact", "", True),
            ("cache_hit_pct", "Cache hit rate", "%", False),
            ("resolved_pct", "Shapes resolved", "%", False),
        ):
            a, b = before.get(key), after.get(key)
            if a is None and b is None:
                continue
            improved = None
            if a not in (None, 0) and b is not None:
                delta = (b - a) / abs(a)
                # A metric that did not move is neither better nor worse. Left as
                # None so the panel shows a neutral dash rather than calling an
                # unchanged 100% resolution rate a regression.
                if abs(delta) > 1e-9:
                    improved = (delta < 0) if lower_better else (delta > 0)
            deltas.append({"key": key, "name": name, "unit": unit,
                           "before": a, "after": b, "improved": improved})

    return {
        "labels": sorted(labels),
        "before": before,
        "after": after,
        "deltas": deltas,
        "evals": (evals or {}).get("report"),
        "eval_cases": [
            {"id": e["case"]["id"], "suite": e["case"].get("suite"),
             "hard_gate": bool(e["case"].get("hard_gate")), "passed": e["result"]["passed"],
             # PASS / FAIL / UNKNOWN. UNKNOWN means the grader could not read
             # its own judge, so the panel shows it as not scored rather than
             # as a failure of the agent.
             "status": e["result"].get("status")
                       or ("PASS" if e["result"]["passed"] else "FAIL")}
            for e in (evals or {}).get("cases", [])
        ],
        "gates_banked": sorted((profile.get("banked") or {}).keys()),
        "name": profile.get("name"),
        "pitch": pitch,
    }


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=HERE, **kw)

    def _send(self, payload, code=200):
        body = json.dumps(payload, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            return {}

    def do_GET(self):  # noqa: N802
        if self.path.split("?")[0] == "/api/evidence":
            try:
                return self._send(evidence())
            except Exception:  # noqa: BLE001
                return self._send({"error": traceback.format_exc()}, 500)
        return super().do_GET()

    def do_POST(self):  # noqa: N802
        path = self.path.split("?")[0]
        body = self._body()

        if path == "/api/chat":
            t0 = time.time()
            try:
                agent = load_agent()
                reply = agent.run_agent(
                    body.get("pnr", ""), body.get("last_name", ""), body.get("message", ""))
                tracer = getattr(getattr(agent, "LAST", None), "tracer", None)
                summary = tracer.summary() if tracer else {}
                # The hold_id comes back in the tool RESULT, not the tool input,
                # so this reads CALL_LOG rather than the tracer. The tracer sees
                # what Claude asked for; CALL_LOG sees what the backend answered.
                from support import CALL_LOG
                holds = [c for c in CALL_LOG
                         if c["name"] == "hold_seat" and isinstance(c.get("result"), dict)
                         and c["result"].get("hold_id")]
                return self._send({
                    "reply": reply,
                    "wall": round(time.time() - t0, 2),
                    "turns": summary.get("turns"),
                    "tool_names": summary.get("tool_names") or [],
                    "tokens": summary.get("tokens") or {},
                    "cache_hit_ratio": summary.get("cache_hit_ratio"),
                    # Surfaced so the browser can offer a real Confirm button.
                    "held": ({"hold_id": holds[-1]["result"]["hold_id"],
                              "option_id": holds[-1]["input"].get("option_id"),
                              "expires_in_minutes": holds[-1]["result"].get("expires_in_minutes")}
                             if holds else None),
                })
            except Exception:  # noqa: BLE001: the panel shows the traceback
                return self._send({"error": traceback.format_exc(),
                                   "wall": round(time.time() - t0, 2)}, 500)

        if path == "/api/confirm":
            # The customer's own click. This is the ONLY thing that mints a
            # confirmation token, which is the whole point of the guardrail.
            try:
                from support import mock_backend as backend
                from support import tools
                hold_id = body.get("hold_id")
                if not hold_id:
                    return self._send({"error": "no hold_id"}, 400)
                if body.get("forge"):
                    result = tools.confirm_rebooking(hold_id, "not-a-real-token")
                    return self._send({"forged": True, "result": result})
                token = backend.simulate_customer_confirm_click(hold_id)
                result = tools.confirm_rebooking(hold_id, token)
                return self._send({"forged": False, "token": token, "result": result})
            except Exception:  # noqa: BLE001
                return self._send({"error": traceback.format_exc()}, 500)

        return self._send({"error": "no such endpoint: %s" % path}, 404)

    def log_message(self, fmt, *args):
        if "/api/" in (self.path or ""):
            sys.stderr.write("  %s %s\n" % (self.command, self.path))


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print("\n  Larkspur demo  ->  http://localhost:%d" % PORT)
        print("  chat on the left, your evidence on the right")
        print("  serving %s, calling agent.run_agent from %s\n"
              % (os.path.relpath(HERE, ROOT), os.path.basename(ROOT)))
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  stopped")
