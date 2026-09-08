"""Larkspur disruption agent: THIS is the file you build.

HOW THIS FILE WORKS: read this once, it saves you asking.

Nothing here is a blank page. Every function below **runs right now**, and
each one is **wrong**. Your job each step is the same:

    1. run it            python3 run.py K7PQ2M --trace
    2. read the trace     the wrong thing shows up on the wire, not in the code
    3. find the fault     the trace tells you which function, you find the line
    4. change it          yourself, or with Claude Code, your call
    5. run it again       and watch the trace change

That last step is the one people skip and the one that teaches. A trace you
can explain is the deliverable; the working agent is a side effect.

You are free to delete any of these functions and rewrite them from scratch.
The verifier checks what happens on the wire, not what your code looks like.

    claude            # start Claude Code in this folder
    /coach             # it works with you, not for you. That's deliberate
"""

from __future__ import annotations

from typing import Any, Dict, List

from support import (MODEL, SYSTEM_PROMPT, Tracer, execute_tool, get_client,
                     record_tool_result, reset_call_log, runtime_preamble, wrap)
# Used by tool_results() below and by the 2.2 seam at the bottom. Imported here
# so this file reads top to bottom; it starts no server until something asks it.
from support import mcp_client

MAX_TOOL_CALLS = 8  # Larkspur's own week-2 build capped the loop at eight API
                    # turns. After that, a human takes over. Same number, same
                    # reason.

# =============================================================================
# LATER SEAMS: both empty on day one, and that is correct.
#
# TONE_ADDENDUM is the intelligence lane's authoring target: the given system
# prompt says nothing about what to do when a customer is abusive or threatens
# legal action, and the tone_safety hard gate fails because of it. Writing this
# section (from nothing, in your own words) is how that lane fixes it.
# Concatenated into every system prompt below, so an empty string changes nothing.
#
# EXTRA_TOOLS is Build 2's: schemas for the tools you decided you need, executed
# by LOCAL_TOOLS at the bottom of this file rather than by support/tools.py.
# =============================================================================
TONE_ADDENDUM = ""  # ✏️ YOUR TURN (Build 4, intelligence lane)

EXTRA_TOOLS: List[Dict[str, Any]] = []  # ✏️ YOUR TURN (Build 2, step 2.1)


class LAST:
    """Holds the most recent tracer so run.py can print it after the call."""
    tracer: Tracer | None = None


def new_session():
    """Given. A fresh client + tracer, wired together."""
    reset_call_log()
    tracer = Tracer()
    client = wrap(get_client(), tracer)
    LAST.tracer = tracer
    return client, tracer


def text_of(response) -> str:
    """Given. With adaptive thinking on, content is often [thinking, text].
    take the LAST non-empty text block, never content[0]."""
    texts = [b.text for b in response.content if getattr(b, "type", None) == "text" and b.text]
    return texts[-1] if texts else ""


def tool_results(response) -> List[Dict[str, Any]]:
    """Given. Executes every tool_use block Claude sent and packages the
    results the way the API expects them back: a list of tool_result blocks,
    each keyed to the tool_use_id it answers."""
    results = []
    for block in response.content:
        if getattr(block, "type", None) != "tool_use":
            continue
        if block.name in mcp_client.tool_names:
            # Given, for step 2.2. This tool runs in the SERVER, not in this
            # process. The only difference you can see from here is which
            # function answers. The set is empty until something discovers, so
            # this branch is inert on day one and inert at 2.1.
            try:
                output = mcp_client.call(block.name, block.input)
            except Exception as exc:  # noqa: BLE001
                # A protocol failure is an integration bug, not something the
                # model can fix. It still has to come back as a tool result, or
                # the loop stalls on an unanswered tool_use id.
                output = {"error": "mcp call failed for %s: %s: %s"
                                   % (block.name, type(exc).__name__, exc)}
            # Same call the local branch below makes, for the same reason.
            record_tool_result(block.name, output)
        elif block.name in LOCAL_TOOLS:
            # Build 2 tools live in this file; everything else is support/tools.py
            try:
                output = LOCAL_TOOLS[block.name](**block.input)
            except TypeError as exc:
                output = {"error": "Bad arguments for %s: %s" % (block.name, exc)}
            # execute_tool does this for the given nine. Do it here too, so the
            # trace (and the eval judge reading it) sees what YOUR tool answered.
            record_tool_result(block.name, output)
        else:
            output = execute_tool(block.name, block.input)
        results.append({
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": str(output),
        })
    return results


# =============================================================================
# STEP 1.1: Read the trace
#
# RUN IT FIRST:  python3 run.py K7PQ2M --trace
#
# Four things in this file are wrong. Each one runs. Each one is wrong in
# exactly one way, and every one of them shows on the wire before it shows in
# the code. So you read the trace first and the code second.
#
# Your first run cannot show you four. One of them stops the run, and while it
# does, the ones downstream of it have no way to appear. So the deliverable is
# two columns, not four rows:
#
#   SEEN        what this run actually shows you, and which function owns it
#   PREDICTED   what you think is hiding behind the one that stopped the run
#
# The prediction is the point. It is a claim about a dependency you cannot see
# yet, and step 1.2 is where you find out whether you were right. Being wrong
# there is worth more than a list that was copied off a comment.
#
# No gate here. The two columns are the deliverable.
# =============================================================================


# =============================================================================
# STEP 1.2: Make the loop hold
#
# RUN IT:  python3 run.py K7PQ2M --trace
# Then read every TURN line in order. Where does the run stop, and does it
# stop because Claude was finished or because something broke?
# =============================================================================
def run_agent(pnr: str, last_name: str, message: str) -> str:
    """Run the tool loop until Claude stops asking for tools. Return its final
    text.

    ACCEPTANCE (verify.py 1.2):
      - the trace shows >= 2 API turns and >= 2 tool calls
      - lookup_booking is called before check_policy
      - the run never exceeds MAX_TOOL_CALLS turns
      - returns a non-empty string
    """
    # ✏️ YOUR TURN: two things in this function are wrong, and the trace says
    # both out loud before you say anything about the code.
    #
    # One: a turn comes back as an error instead of a response. Read the error
    # verbatim, then read the message list this function hands the model on
    # that turn. Is what went back what Claude actually sent?
    #
    # Two: when the run does finish clean, look at what run.py prints above the
    # trace. The trace says the conversation ended properly. Does the string
    # this function returns come from the turn that ended it?

    client, tracer = new_session()
    tools = tool_list()
    messages = [
        {"role": "user", "content": f"PNR {pnr}, last name {last_name}. {message}"},
    ]

    response = client.messages.create(
        model=MODEL, max_tokens=4096, system=runtime_preamble() + SYSTEM_PROMPT + TONE_ADDENDUM,
        thinking={"type": "adaptive"}, tools=tools, messages=messages,
    )

    answer = ""
    turns = 1
    while response.stop_reason == "tool_use" and turns < MAX_TOOL_CALLS:
        messages.append({"role": "assistant", "content": text_of(response)})
        messages.append({"role": "user", "content": tool_results(response)})
        answer = text_of(response)
        response = client.messages.create(
            model=MODEL, max_tokens=4096, system=runtime_preamble() + SYSTEM_PROMPT + TONE_ADDENDUM,
            thinking={"type": "adaptive"}, tools=tools, messages=messages,
        )
        turns += 1

    return answer


# =============================================================================
# STEP 1.3: Make the tools route
#
# RUN IT:  python3 run.py --show-tools
# It prints exactly what Claude receives about each tool, and that print-out is
# the whole briefing: Claude cannot see support/tools.py and cannot ask you what
# a function really does. The description drives which tool gets picked, and the
# field descriptions inside input_schema drive what gets sent as arguments.
#
# Two tools are briefed wrong. One you can see in the print-out. The other only
# shows on the wire, in the arguments Claude sent and what came back. Run with
# --trace for that one.
# =============================================================================
def build_tools() -> List[Dict[str, Any]]:
    """Anthropic-shaped tool schemas: name, description, input_schema. The
    functions these call are already written and correct, in support/tools.py.
    Your job is only the schema: what Claude is told about each tool."""
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
            # ✏️ YOUR TURN: the description on this tool is fine. One line
            # inside input_schema is not. Run with --trace. This tool gets
            # called twice about one segment, and the arguments are not the
            # same both times. Who told Claude to send the first shape, and
            # which of the two did OpsFeed accept?
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
                    "date": {"type": "string", "description": "MM/DD/YYYY"},
                },
                "required": ["flight_no", "date"],
            },
        },
        {
            # ✏️ YOUR TURN: read this description back to yourself as if you
            # were the new hire being briefed with it. Could you do the job?
            # When would you call this tool, what do you need to know before
            # you can, and what does a result look like? Claude gets nothing
            # else. The function underneath is already correct, so nothing you
            # do in support/tools.py will fix a briefing this thin.
            "name": "search_alternatives",
            "description": "search",
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


# =============================================================================
# STEP 1.4: All five shapes
#
# RUN IT:  python3 run.py --all --trace
# Fixing the loop against one clean cancellation is not the same as fixing it.
# This runs all five Stage 1 shapes: clean cancel, a delay too short for any
# waiver, an ambiguous missed connection, an out-of-scope group, an abusive
# message, through the SAME function. No stub here: if your loop is right,
# this just works. If it only works on K7PQ2M, that's real information.
#
# Read the totals footer and write the numbers down. Turns, tool calls, tokens
# in and out. Those are the numbers every later step is measured against.
# =============================================================================


# =============================================================================
# BUILD 2 (2.1): add the tools you decided you need, then measure them
#
# RUN IT:  python3 verify.py 2.1
# Build 2 opens with you arguing for the tools this agent is missing. This is
# where you add them. Define the schema in EXTRA_TOOLS above, implement the
# function here, register it in LOCAL_TOOLS, and the loop picks it up.
# nothing in support/ changes.
#
# One is scaffolded because the backend already answers it and no current tool
# asks: a cancelled customer's first question is "when CAN I fly?", and today
# the agent can only search one day at a time.
#
# Two more the data supports, if your pod argued for them: either instead of
# the scaffolded one, or add it on top once the gate is banked, and measure what
# the eleventh tool costs:
#   - fare_rules(section): the Handbook text behind a policy row, from
#     data/americas/fare_rules_excerpt.md: for "why won't you give me a hotel?"
#   - reopen_stats(shape): how often this disruption shape reopens within 72h,
#     from data/americas/transcripts_sample.jsonl: for the value conversation.
#
# The measurement is not optional. bench before, add the tool, bench after.
# a tool that never gets called is context tax with no return, and the trace
# is how you find out which one you built.
# =============================================================================
def next_available_day(origin: str, dest: str, date: str, cabin: str = "Y"):
    """Given. The earliest date with an open seat. The backend function existed
    all along; nobody had given Claude a way to call it.

    pax_count never crosses this wrapper on purpose: the backend then answers
    for a party of one, and finding that gap is Build 3's capacity case.
    """
    from support import mock_backend
    return mock_backend.earliest_alternative_date(origin, dest, date, cabin)


# ✏️ YOUR TURN: schema for next_available_day goes in EXTRA_TOOLS above.
# The description is the main routing surface, and the field descriptions
# inside input_schema route too. Say when to call it, what it needs, and what
# comes back. Then register the function:
LOCAL_TOOLS: Dict[str, Any] = {
    # "next_available_day": next_available_day,
}


# =============================================================================
# BUILD 2 (2.2): the same tool, over MCP. 2.2 lands here.
#
# RUN IT FIRST:  python3 support/mcp_selftest.py
# THEN READ IT:  MCP_TRACE=1 python3 support/mcp_client.py
#
# support/mcp_server.py is a separate program. It serves next_available_day and
# fare_rules, it reads the same backend this file reads, and it has never heard
# of Claude. mcp_tools() asks it what it has and hands back schemas in the same
# shape build_tools() returns: name, description, input_schema.
#
# Nothing about the model's job changes. Same name, same description, same
# input schema, same token bill. What changes is who owns the tool, and how
# many places you have to edit to change it.
#
# The dispatch is already wired for you, up in tool_results(): any name the
# client knows about goes over the wire instead of into LOCAL_TOOLS. It stays
# inert until something discovers.
# =============================================================================

# Private on purpose. mcp_tools() is the only name worth reaching for: the
# cache is empty until the first discovery, so a list that reads it directly
# looks correct, type-checks, and hands back nothing.
_MCP_CACHE: List[Dict[str, Any]] = []


def mcp_tools() -> List[Dict[str, Any]]:
    """Given. tools/list over the wire, once per process, cached.

    Nothing starts the server until something calls this, so a file that has
    not been wired never spawns it. A server that will not start returns an
    empty list and says why, so a broken server costs you a message and two
    tools rather than a crash halfway through a customer conversation.
    """
    global _MCP_CACHE
    if _MCP_CACHE:
        return _MCP_CACHE
    try:
        _MCP_CACHE = mcp_client.discover()
    except Exception as exc:  # noqa: BLE001 - a dead server is not a stack trace
        print("  [mcp] no tools discovered: %s: %s" % (type(exc).__name__, exc))
        print("  [mcp] python3 support/mcp_selftest.py says why on one line.")
        _MCP_CACHE = []
    return _MCP_CACHE


def tool_list() -> List[Dict[str, Any]]:
    """Given. The exact list of schemas that goes out on every turn, and the
    same list python3 run.py --show-tools prints. run_agent() sends this."""
    # ✏️ YOUR TURN: the server serves next_available_day. So does this file.
    # Two programs, one tool name, and this one line decides what Claude is
    # offered on every turn. Look at what --show-tools prints now and at what
    # it should print. What goes into this list, and what has to leave the file
    # before it can?
    return build_tools() + EXTRA_TOOLS
