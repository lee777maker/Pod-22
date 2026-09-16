"""Larkspur disruption agent. This is the file you build.

It runs right now, and it is wrong in four places. The trace shows each one
before the code does, so read the trace first:

    python3 run.py K7PQ2M --trace

Where you edit:   grep -n '✏' agent.py   (six marks, one per place)
Steps and gates:  https://anthropicpartnerbasecamp.bts.com/
"""
from __future__ import annotations
import re
from typing import Any, Dict, List
from support import (MODEL, SYSTEM_PROMPT, call_local, execute_tool, mcp_client,
                     new_session, next_available_day, record_tool_result,
                     runtime_preamble)

MAX_TOOL_CALLS = 8  # Larkspur's own build capped the loop here; then a human takes over.

# Cost lane, tiered inference: run routine disruptions on the cheap model and reserve the
# capable model (support's MODEL, sonnet-5) for the cases our evals prove the cheap one
# cannot hold: abuse, legal threats, refunds, out-of-scope, ambiguous connections, and
# policy-rule challenges. Fail-safe: any risk word routes to the capable model. A
# production version would swap this heuristic for a trained classifier and add
# mid-conversation escalation when a benign chat turns.
CHEAP_MODEL = "claude-haiku-4-5-20251001"
_CAPABLE_TRIGGERS = re.compile(
    r"\b(lawyer|sue|suing|legal|attorney|useless|ridiculous|disgrace|unacceptable|"
    r"refund|money back|chargeback|"
    r"group|minor|unaccompanied|partner|"
    r"missed (my |the )?connection|missed connection|"
    r"hotel|rule|policy|entitled|owed|compensation|voucher|goodwill)\b", re.I)


def choose_model(message: str) -> str:
    """Pick the model for this conversation. Capable model for risky/judgment-heavy
    messages, cheap model for clear routine disruptions."""
    return MODEL if _CAPABLE_TRIGGERS.search(message or "") else CHEAP_MODEL


def next_available_day_for_party(pnr: str, cabin: str = "") -> Dict[str, Any]:
    """Pod-authored local tool (Build 2). Party-aware sibling of next_available_day:
    that one answers for a single passenger, so on a group booking it can name a date
    that cannot actually seat everyone. This reads the real passenger count and the
    disrupted segment off the booking and only returns a date with seats for the whole
    party."""
    from support import mock_backend as backend
    try:
        booking = backend.get_booking_raw(pnr)
    except backend.NotFound as exc:
        return {"error": str(exc)}
    seg = backend.get_disrupted_segment(booking)
    pax = len(booking["passengers"])
    cab = (cabin or seg["cabin"]).strip().upper()
    found = backend.earliest_alternative_date(seg["origin"], seg["dest"], seg["date"], cab, pax)
    if not found:
        return {"error": "no date with %d seat(s) from %s to %s in cabin %s on or after %s"
                         % (pax, seg["origin"], seg["dest"], cab, seg["date"])}
    return {"pnr": pnr, "pax_count": pax, "origin": seg["origin"], "dest": seg["dest"],
            "cabin": cab, "earliest_date_all_seated": found,
            "note": "earliest date with an open seat for the whole party of %d" % pax}


TONE_ADDENDUM = (                        # ✏️ Build 4, step 4.1, intelligence lane
    "\n\nTone and escalation, on every reply:\n"
    "Stay calm, respectful and firm on boundaries no matter how the customer speaks "
    "to you, and never be retaliatory.\n"
    "If a customer threatens legal action, acknowledge it without debating, never "
    "promise compensation, and escalate to a human using escalate_to_human with a "
    "short summary.\n"
    "If the customer says they missed a connection but lookup_booking does not clearly "
    "identify which connection was missed, ask which inbound and onward flights they "
    "mean and whether the connection is already missed or only at risk. Do not check "
    "policy, search alternatives, hold a seat, or recommend an action until they clarify."
)
EXTRA_TOOLS: List[Dict[str, Any]] = [    # ✏️ Build 2, step 2.1: schemas for the tools you add
    {
        "name": "next_available_day_for_party",
        "description": (
            "Find the earliest date with an open seat for EVERY passenger on the booking, "
            "not just one. Use this instead of next_available_day whenever the booking has "
            "more than one passenger (a family or a group), because next_available_day "
            "answers for a party of one and can name a date that cannot actually seat the "
            "whole party. Give it the PNR; it reads the passenger count and the disrupted "
            "segment from the booking itself. Returns the earliest date that has seats for "
            "the full party."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pnr": {"type": "string"},
                "cabin": {"type": "string", "description": "Optional cabin code (Y or J); defaults to the booked cabin"},
            },
            "required": ["pnr"],
        },
    },
]
LOCAL_TOOLS: Dict[str, Any] = {          # ✏️ Build 2, step 2.1: the functions behind them
    "next_available_day_for_party": next_available_day_for_party,
}
# Build 2, step 2.2: next_available_day is served by the MCP server (support/mcp_server.py),
# so its schema and function are not local here; tool_list() pulls it in over the wire via
# mcp_client.tools(). next_available_day_for_party above stays local, per the guide's rule
# that only one tool moves to MCP.


def text_of(response) -> str:
    """Given. The last non-empty text block, never content[0]."""
    texts = [b.text for b in response.content if getattr(b, "type", None) == "text" and b.text]
    return texts[-1] if texts else ""


def tool_results(response) -> List[Dict[str, Any]]:
    """Given. Runs every tool_use block and packages the results the way the
    API expects them back. A tool can live in three places: the MCP server,
    LOCAL_TOOLS, or support/tools.py."""
    # three branches, no try/except in this file: mcp_client.call_remote() and
    # support.call_local() answer with an error dict instead of raising, and both
    # record what came back on the trace
    results = []
    for block in response.content:
        if getattr(block, "type", None) != "tool_use":
            continue
        if block.name in mcp_client.tool_names:
            output = mcp_client.call_remote(block.name, block.input)
        elif block.name in LOCAL_TOOLS:
            output = call_local(LOCAL_TOOLS[block.name], block.name, block.input)
        else:
            output = execute_tool(block.name, block.input)
        results.append({
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": str(output),
        })
    return results


def run_agent(pnr: str, last_name: str, message: str) -> str:            # ✏️ Build 1, step 1.2
    """Run the tool loop until Claude stops asking for tools. Return its final text."""
    client, tracer = new_session()
    tools = tool_list()
    model = choose_model(message)  # tiered inference: cheap model for routine, capable for risky
    think = {} if "haiku" in model.lower() else {"thinking": {"type": "adaptive"}}  # haiku has no adaptive thinking
    # Cost lane (Build 4, second lever): the tool schemas and the system prompt are
    # byte-identical on every turn, so mark that stable prefix for prompt caching and
    # reuse the same objects across turns. The runtime preamble carries a per-call
    # timestamp, so it lives in its own block AFTER the cache breakpoint, where it can
    # change without busting the cache. Built once, before the loop.
    if tools:
        tools[-1] = {**tools[-1], "cache_control": {"type": "ephemeral"}}  # cache all tool schemas
    system = [
        {"type": "text", "text": SYSTEM_PROMPT + TONE_ADDENDUM,
         "cache_control": {"type": "ephemeral"}},                          # cache tools + this
        {"type": "text", "text": runtime_preamble()},                      # dynamic, uncached
    ]
    messages = [
        {"role": "user", "content": f"PNR {pnr}, last name {last_name}. {message}"},
    ]

    response = client.messages.create(
        model=model, max_tokens=4096, system=system,
        tools=tools, messages=messages, **think,
    )

    turns = 1
    while response.stop_reason == "tool_use" and turns < MAX_TOOL_CALLS:
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results(response)})
        response = client.messages.create(
            model=model, max_tokens=4096, system=system,
            tools=tools, messages=messages, **think,
        )
        turns += 1

    # If the loop stopped because it hit MAX_TOOL_CALLS while Claude was still asking
    # for a tool, the final response is a tool_use turn that may carry no text at all.
    # Create a real handoff rather than return an empty or half-finished reply.
    if response.stop_reason == "tool_use":
        handoff = execute_tool("escalate_to_human", {
            "pnr": pnr,
            "reason": "automatic handling reached its tool-call ceiling",
            "summary_for_human": (
                "The disruption-care agent reached its safety ceiling while handling "
                "this conversation. Review the trace and continue from the gathered results."
            ),
        })
        reference = handoff.get("escalation_id") if isinstance(handoff, dict) else None
        suffix = " Reference: %s." % reference if reference else ""
        return ("I wasn't able to finish this one automatically, so I've handed it to a "
                "human agent who can continue with everything gathered so far." + suffix)

    return text_of(response)


def tool_list() -> List[Dict[str, Any]]:                   # ✏️ Build 2, step 2.2
    """Given. Exactly what Claude is offered on every turn; run.py --show-tools
    prints this list."""
    return build_tools() + EXTRA_TOOLS + mcp_client.tools()


# ──────────────────────────────────────────────────────────────────────────────
# Below this line: what Claude is told about each tool. Step 1.3.
# The functions these describe are written and correct, in support/tools.py.
# ──────────────────────────────────────────────────────────────────────────────
def build_tools() -> List[Dict[str, Any]]:                 # ✏️ Build 1, step 1.3
    """Anthropic-shaped schemas: name, description, input_schema. What Claude is
    told about each of the nine tools, and all it is ever told."""
    return [
        {
            "name": "lookup_booking",
            "description": (
                "Retrieve a Larkspur reservation from Altura by confirmation code (PNR) "
                "and the passenger's last name. Both are required to prevent a lookup on "
                "a guessed PNR. Returns fare family, loyalty tier, the segment that needs "
                "attention, and any group/partner/minor/SSR flags relevant to scope."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"pnr": {"type": "string"}, "last_name": {"type": "string"}},
                "required": ["pnr", "last_name"],
            },
        },
        {
            "name": "get_flight_status",
            "description": (
                "Look up a Larkspur or Larkspur Link flight's current OpsFeed status for "
                "one local date: status, delay minutes, and cause. Use this before telling "
                "a customer anything about a flight's timing; never state it from memory."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "flight_no": {"type": "string"},
                    "date": {"type": "string", "description": "YYYY-MM-DD"},
                },
                "required": ["flight_no", "date"],
            },
        },
        {
            "name": "search_alternatives",
            "description": (
                "Find alternative Larkspur flights to rebook this booking's disrupted "
                "segment. Takes only the PNR; the origin, destination, date and cabin are "
                "read from the affected segment on the booking, not asked of you. Returns a "
                "list of rebooking options, each with an option_id you can pass to hold_seat "
                "or confirm_rebooking. Reach for this once you know the segment is disrupted "
                "and the customer wants to keep traveling."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"pnr": {"type": "string"}},
                "required": ["pnr"],
            },
        },
        {
            "name": "check_policy",
            "description": (
                "Resolve what Larkspur owes this customer for the disruption: rebooking "
                "waiver, refund path, meal/hotel/ground care, goodwill eligibility and cap, "
                "and any escalation triggers. cause_code, delay_minutes and status describe "
                "what get_flight_status told you; fare_family, loyalty_tier and whether this "
                "is overnight are looked up from the booking, not asked of you. Every "
                "response carries a policy_row_id. Cite it if you reference this decision "
                "again."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "pnr": {"type": "string"},
                    "cause_code": {"type": "string", "enum": ["WX", "ATC", "MX", "CREW", "SEC"]},
                    "delay_minutes": {"type": "integer"},
                    "status": {"type": "string", "enum": ["ON_TIME", "DELAYED", "CANCELLED", "DIVERTED"]},
                    "wait_minutes_for_alternative": {"type": "integer"},
                    "chosen_option_id": {"type": "string"},
                },
                "required": ["pnr", "cause_code", "delay_minutes", "status"],
            },
        },
        {
            "name": "hold_seat",
            "description": "Place a 15-minute hold on one alternative. Reversible. It simply expires.",
            "input_schema": {
                "type": "object",
                "properties": {"option_id": {"type": "string"}, "pnr": {"type": "string"}},
                "required": ["option_id", "pnr"],
            },
        },
        {
            "name": "confirm_rebooking",
            "description": (
                "Finalize a held seat. Irreversible. Requires a confirmation_token that "
                "only the customer's own Confirm-click can produce. You cannot supply it "
                "yourself, and 'the customer said yes' in chat does not substitute for it."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"hold_id": {"type": "string"}, "confirmation_token": {"type": "string"}},
                "required": ["hold_id", "confirmation_token"],
            },
        },
        {
            "name": "issue_voucher",
            "description": (
                "Issue a meal, ground, hotel, or goodwill voucher. Auto-approves within the "
                "policy's threshold for that type; above it, returns a pending status for a "
                "human. It does not fail. Always pass the policy_row_id that made it eligible."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "voucher_type": {"type": "string", "enum": ["meal", "ground", "hotel", "goodwill"]},
                    "amount_usd": {"type": "number"},
                    "pnr": {"type": "string"},
                    "policy_row_id": {"type": "string"},
                },
                "required": ["voucher_type", "amount_usd", "pnr", "policy_row_id"],
            },
        },
        {
            "name": "escalate_to_human",
            "description": (
                "Hand this conversation to a human, with your reasoning attached. Use for "
                "groups, partner segments, unaccompanied minors, refunds, or anything else "
                "out of scope. This is the correct outcome for those cases, not a failure."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "pnr": {"type": "string"}, "reason": {"type": "string"},
                    "summary_for_human": {"type": "string"}, "queue": {"type": "string"},
                },
                "required": ["pnr", "reason", "summary_for_human"],
            },
        },
        {
            "name": "send_confirmation",
            "description": "Send the customer a written confirmation of what was just done. Benign.",
            "input_schema": {
                "type": "object",
                "properties": {"pnr": {"type": "string"}, "message": {"type": "string"}},
                "required": ["pnr", "message"],
            },
        },
    ]
