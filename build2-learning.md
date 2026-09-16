# Build 2 — Learning Notes

## What Build 2 did

Added a tenth tool (`next_available_day`) to the agent, first as a local function,
then via an MCP server. Both routes give Claude the same capability; the transport changes.

---

## Step 2.1 — Your own tool (local)

### The gap it closes

After Build 1, the agent could look up a booking, check flight status, check policy, and
tell the customer what they're owed. But if a customer asked "when can I actually fly
next?", the agent had no way to answer — it would have had to guess or ask the customer.

`next_available_day` closes that gap: it searches forward from the disrupted date and
returns the first date with an open seat.

### Where the code lives

| Place | What you put there |
|---|---|
| `EXTRA_TOOLS` | The tool's **schema** — the name, description, and input fields Claude reads to decide *when* to call it |
| `LOCAL_TOOLS` | A dict mapping the tool name to the **Python function** that runs when Claude calls it |

The dispatch in `tool_results()` checks `LOCAL_TOOLS` by name and calls the function for you.

### Why descriptions matter

The description is the **only routing signal**. Claude never reads your source code.
If the description is vague ("does date stuff"), Claude won't know to call it when a
customer asks about rebooking availability. A good description answers:
- *When* should I call this? ("when a customer asks when they can next travel after a disruption")
- *What does it need to know?* (origin, dest, date)
- *What does it give back?* ("the first date with availability")

---

## Step 2.2 — The same tool, over MCP

### What MCP is

MCP (Model Context Protocol) is a standard way to run tools in a **separate process**
that Claude talks to over a protocol, rather than calling Python functions directly.
The benefit: tools can live anywhere — another process, another machine, a vendor API —
and the agent doesn't change.

### What changed

One line in `tool_list()`:

```python
# Before (2.1):
return build_tools() + EXTRA_TOOLS

# After (2.2):
return build_tools() + EXTRA_TOOLS + mcp_client.tools()
```

`mcp_client.tools()` starts the MCP server (`support/mcp_server.py`), discovers its
tools, and returns Anthropic-shaped schemas — the same format `build_tools()` returns.
Claude never knows whether a tool is local or remote; it just calls it by name.

### Two tools the server provides

| Tool | What it does |
|---|---|
| `next_available_day` | Earliest open seat date on a route (same as the local one in 2.1) |
| `fare_rules` | Returns Larkspur's published fare rules text for a given section |

### Dispatch order in `tool_results()`

```python
if block.name in mcp_client.tool_names:       # 1. MCP wins
    output = mcp_client.call_remote(...)
elif block.name in LOCAL_TOOLS:               # 2. then local
    output = call_local(...)
else:                                         # 3. then the given nine
    output = execute_tool(...)
```

After switching to MCP, `next_available_day` is no longer in `EXTRA_TOOLS` or `LOCAL_TOOLS`
— the MCP server owns it and the dispatch routes there automatically.

### Token cost is real

Every tool schema goes to the API on **every turn**, whether Claude uses it or not.
The verifier printed the token counts:
- 9 tools (Build 1): baseline
- +1 local tool (2.1): +502 tokens per turn
- +MCP tools (2.2, adds `fare_rules`): +502 more tokens per turn

Tools are not free. A tool whose description is too vague to route correctly costs
tokens without returning value.

---

## Evidence codes

| Step | Code |
|---|---|
| 2.1 | `313-3E8` |
| 2.2 | `7D3-43C` |

Bank both at https://anthropicpartnerbasecamp.bts.com/
