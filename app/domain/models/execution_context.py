from typing import Any

from pydantic import BaseModel


class ExecutionContext(BaseModel):
    """Ephemeral technical outcome of the most recent graph action.

    It is intentionally separate from the presentation aggregate: a tool
    failure must never be confused with a clinical or business decision.
    """

    last_tool: str | None = None
    tool_output: Any | None = None
    error: str | None = None
