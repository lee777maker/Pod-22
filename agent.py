"""Larkspur disruption agent — THIS is the file you build.

HOW THIS FILE WORKS — read this once, it saves you asking.

Nothing here is a blank page. Every function below **runs right now**, and
each one is **wrong in exactly one way**. Your job each step is the same:

    1. run it            python3 run.py K7PQ2M --trace
    2. read the trace     the wrong thing shows up on the wire, not in the code
    3. find the marker    one ✏️ YOUR TURN block, at the line that's wrong
    4. change it          yourself, or with Claude Code — your call
    5. run it again       and watch the trace change

That last step is the one people skip and the one that teaches. A trace you
can explain is the deliverable; the working agent is a side effect.

You are free to delete any of these functions and rewrite them from scratch.
The verifier checks what happens on the wire, not what your code looks like.

    claude            # start Claude Code in this folder
    /coach             # it works with you, not for you — that's deliberate
"""

from __future__ import annotations

from typing import Any, Dict, List

from support import (MODEL, SYSTEM_PROMPT, Tracer, execute_tool, get_client,
                     reset_call_log, runtime_preamble, wrap)

MAX_TOOL_CALLS = 8  # Larkspur's own week-2 build capped the loop at eight API
                    # turns — after that, a human takes over. Same number, same
                    # reason.

# =============================================================================
# DAY 2 SEAMS — both empty on day 1, and that is correct.
#
# TONE_ADDENDUM is the intelligence lane's authoring target: the given system
# prompt says nothing about what to do when a customer is abusive or threatens
# legal action, and the tone_safety hard gate fails because of it. Writing this
# section — from nothing, in your own words — is how that lane fixes it.
# Concatenated into every system prompt below, so an empty string changes nothing.
#
# EXTRA_TOOLS is Build 2's: schemas for the tools you decided you need, executed
# by LOCAL_TOOLS at the bottom of this file rather than by support/tools.py.
# =============================================================================
TONE_ADDENDUM = ""  # ✏️ YOUR TURN (Block 13, intelligence lane)

EXTRA_TOOLS: List[Dict[str, Any]] = []  # ✏️ YOUR TURN (Block 7, Build 2)


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
    """Given. With adaptive thinking on, content is often [thinking, text] —
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
        if block.name in LOCAL_TOOLS:
            # Build 2 tools live in this file; everything else is support/tools.py
            try:
                output = LOCAL_TOOLS[block.name](**block.input)
            except TypeError as exc:
                output = {"error": "Bad arguments for %s: %s" % (block.name, exc)}
        else:
            output = execute_tool(block.name, block.input)
        results.append({
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": str(output),
        })
    return results


# =============================================================================
# STEP 2 — Tool schemas
#
# RUN IT FIRST:  python3 run.py --show-tools
# It prints exactly what Claude receives about each tool. Read the
# search_alternatives entry. Its description is one word. Claude picks tools
# from that string alone — it cannot see support/tools.py, and it cannot ask
# you what the function actually does.
# =============================================================================
def build_tools() -> List[Dict[str, Any]]:
    """Anthropic-shaped tool schemas — name, description, input_schema. The
    functions these call are already written and correct, in support/tools.py.
    Your job is only the schema: what Claude is told about each tool."""
    return [
        {
            "name": "lookup_booking",
            "description": (
                "Retrieve a Larkspur reservation from Altura by confirmation code (PNR) "
                "and the passenger's last name — both are required to prevent a lookup on "
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
                "one local date — status, delay minutes, and cause. Use this before telling "
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
            # ✏️ YOUR TURN — this description tells Claude nothing about when to
            # call this tool, what it needs, or what comes back. Claude will
            # sometimes skip it, sometimes call it at the wrong moment, and you
            # won't be able to tell why just by reading agent.py — the fix has
            # to happen here, not in support/tools.py, because the function
            # underneath is already correct.
            #
            # Write the description a new hire would need: when to call this,
            # what it needs to already know (hint: it takes only a pnr — origin,
            # destination, date and cabin are all derived from the booking so a
            # search can't be pointed at a route the customer never had), and
            # what a result looks like.
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
                "response carries a policy_row_id — cite it if you reference this decision "
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
            "description": "Place a 15-minute hold on one alternative. Reversible — it simply expires.",
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
                "only the customer's own Confirm-click can produce — you cannot supply it "
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
                "human — it does not fail. Always pass the policy_row_id that made it eligible."
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
                "out of scope — this is the correct outcome for those cases, not a failure."
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
# STEP 3 — The agentic loop
#
# RUN IT FIRST:  python3 run.py K7PQ2M --trace
# It runs. Read the trace: one turn, stop_reason=tool_use, then nothing — the
# function returned before anyone answered the tool call.
#
# Larkspur's own week-2 build hit a version of this: appending only the
# model's text back into the conversation (instead of every content block it
# sent) made the agent lose track of what it had already asked, and it had
# to re-ask for things it already knew — case 7 called search_alternatives
# 11 times before anyone caught it. The lesson is the same either way: the
# loop has to actually continue, and once it does, the assistant turn you
# append must be response.content WHOLE, unmodified — drop or rewrite it and
# you've rebuilt the same bug one level up.
# =============================================================================
def run_agent(pnr: str, last_name: str, message: str) -> str:
    """Run the tool loop until Claude stops asking for tools. Return its final
    text.

    ACCEPTANCE (verify.py 3):
      - the trace shows >= 2 API turns and >= 2 tool calls
      - lookup_booking is called before check_policy
      - the run never exceeds MAX_TOOL_CALLS turns
      - returns a non-empty string
    """
    client, tracer = new_session()
    tools = build_tools() + EXTRA_TOOLS
    messages = [
        {"role": "user", "content": f"PNR {pnr}, last name {last_name}. {message}"},
    ]

    response = client.messages.create(
        model=MODEL, max_tokens=4096, system=runtime_preamble() + SYSTEM_PROMPT + TONE_ADDENDUM,
        thinking={"type": "adaptive"}, tools=tools, messages=messages,
    )

    # ✏️ YOUR TURN — this is a loop with the loop missing.
    #
    # Everything above is correct. What's missing is that when Claude comes
    # back with stop_reason == "tool_use", you have to:
    #     1. append the assistant's response.content to messages — UNCHANGED
    #        (it may contain thinking blocks; dropping them breaks the next call)
    #     2. append tool_results(response) as a user message
    #     3. call the API again
    #     4. keep going until stop_reason is something else, or you hit
    #        MAX_TOOL_CALLS turns — then stop and hand off, don't loop forever
    #
    # tool_results() is written for you above. Use it.

    return text_of(response)


# =============================================================================
# STEP 4 — Prove it generalizes
#
# RUN IT:  python3 run.py --all --trace
# Fixing Step 3 against one clean cancellation is not the same as fixing it.
# This runs all five Stage 1 shapes — clean cancel, a delay too short for any
# waiver, an ambiguous missed connection, an out-of-scope group, an abusive
# message — through the SAME function. No stub here: if your loop is right,
# this just works. If it only works on K7PQ2M, that's real information.
# =============================================================================


# =============================================================================
# BUILD 2 (Block 7) — add the tools you decided you need, then measure them
#
# RUN IT:  python3 verify.py 7
# Teach 2 ends with you arguing for tools. This is where you add them. Define
# the schema in EXTRA_TOOLS above, implement the function here, register it in
# LOCAL_TOOLS, and the loop picks it up — nothing in support/ changes.
#
# One is scaffolded because the backend already answers it and no current tool
# asks: a cancelled customer's first question is "when CAN I fly?", and today
# the agent can only search one day at a time.
#
# Two more the data supports, if your pod argued for them — either instead of
# the scaffolded one, or add it on top once the gate is banked, and measure what
# the eleventh tool costs:
#   - fare_rules(section): the Handbook text behind a policy row, from
#     data/americas/fare_rules_excerpt.md — for "why won't you give me a hotel?"
#   - reopen_stats(shape): how often this disruption shape reopens within 72h,
#     from data/americas/transcripts_sample.jsonl — for the value conversation.
#
# The measurement is not optional. bench before, add the tool, bench after —
# a tool that never gets called is context tax with no return, and the trace
# is how you find out which one you built.
# =============================================================================
def next_available_day(origin: str, dest: str, date: str, cabin: str = "Y"):
    """Given. The earliest date with an open seat — the backend function existed
    all along; nobody had given Claude a way to call it."""
    from support import mock_backend
    return mock_backend.earliest_alternative_date(origin, dest, date, cabin)


# ✏️ YOUR TURN — schema for next_available_day goes in EXTRA_TOOLS above.
# Claude picks tools from the description string alone. Say when to call it,
# what it needs, and what comes back. Then register the function:
LOCAL_TOOLS: Dict[str, Any] = {
    # "next_available_day": next_available_day,
}

