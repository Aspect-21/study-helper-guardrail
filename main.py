import re

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI()

# ---------------------------------------------------------------------------
# Pattern-rule guardrail
# ---------------------------------------------------------------------------

# Each group is a list of compiled regexes applied to the normalised message.
RULES: list[tuple[str, list[re.Pattern[str]]]] = [
    (
        "instruction_override",
        [
            re.compile(r"ignore previous instructions"),
            re.compile(r"you are now"),
            re.compile(r"pretend you are"),
            re.compile(r"developer mode"),
        ],
    ),
    (
        "system_prompt_reveal",
        [
            re.compile(r"system prompt"),
            re.compile(r"system message"),
            re.compile(r"what were you told"),
            re.compile(r"repeat your instructions"),
        ],
    ),
    (
        "off_task_writing",
        [
            re.compile(r"cover letter"),
            re.compile(r"college essay"),
            re.compile(r"write me an essay"),
            re.compile(r"personal statement"),
        ],
    ),
]

BLOCKED_REPLY = (
    "I can only help with study questions, "
    "so send me a homework problem and we will work through it."
)


def _normalise(text: str) -> str:
    """Lowercase and squeeze whitespace runs into a single space."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def _check_message(message: str) -> str | None:
    """Return the matched rule group name, or None if the message is clean."""
    normalised = _normalise(message)
    for group_name, patterns in RULES:
        for pattern in patterns:
            if pattern.search(normalised):
                return group_name
    return None


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class CheckRequest(BaseModel):
    message: str


class BlockedResponse(BaseModel):
    blocked: bool = True
    reason: str
    reply: str


class AllowedResponse(BaseModel):
    allowed: bool = True


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@app.post("/check")
async def check(request: CheckRequest):
    """Check a message against the guardrail rules."""
    matched_group = _check_message(request.message)

    if matched_group is not None:
        return JSONResponse(
            status_code=400,
            content=BlockedResponse(
                reason=matched_group,
                reply=BLOCKED_REPLY,
            ).model_dump(),
        )

    return AllowedResponse()
