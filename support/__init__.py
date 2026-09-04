"""Given scaffolding for the Larkspur disruption-agent build.

You will not need to edit anything in this package. If you find yourself
wanting to, that's a signal worth raising with a facilitator — it usually
means the exercise wording is wrong, not you.
"""

from .client import MissingCredential, credential_status, get_client
from .data import (DEFAULT_LAST_NAME, DEFAULT_MESSAGE, DEFAULT_PNR, MODEL,
                   STAGE1_TASKS, STAGE2_TASKS, SYSTEM_PROMPT, runtime_preamble)
from .tools import CALL_LOG, TOOL_FUNCTIONS, execute_tool, reset_call_log
from .trace import Tracer, record_tool_result, wrap

__all__ = [
    "CALL_LOG", "DEFAULT_LAST_NAME", "DEFAULT_MESSAGE", "DEFAULT_PNR", "MODEL",
    "MissingCredential",
    "STAGE1_TASKS", "STAGE2_TASKS", "SYSTEM_PROMPT", "TOOL_FUNCTIONS", "Tracer",
    "credential_status", "execute_tool", "get_client", "record_tool_result",
    "reset_call_log", "runtime_preamble", "wrap",
]
