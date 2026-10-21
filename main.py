import re
import unicodedata

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI()

# ---------------------------------------------------------------------------
# Pattern-rule guardrail families
# ---------------------------------------------------------------------------

RULES: list[tuple[str, list[re.Pattern[str]]]] = [
    (
        "instruction_override",
        [
            # Disregard / Ignore / Forget instruction directives
            re.compile(
                r"(ignore|disregard|forget|drop|bypass)\s+.*(instructions?|rules?|constraints?|policy|guardrails?|limits?)"
            ),
            re.compile(r"ignora\s+(todas\s+)?(las\s+)?instrucciones"),
            re.compile(r"disregard\s+(everything|all)(\s+above)?"),
            re.compile(r"forget\s+(your\s+)?rules"),
            # Restriction lifting assertions
            re.compile(
                r"(restrictions?|constraints?|limits?)\s+(have\s+been|are)?\s*(lifted|void|removed|disabled)"
            ),
            re.compile(r"no\s+(restrictions|subject\s+limits)"),
            # Role, mode, and persona reassignments
            re.compile(r"developer\s+mode"),
            re.compile(r"tutorbot-unlocked"),
            re.compile(r"\b(dan|jailbreak)\b"),
            re.compile(
                r"(you\s+are|you're|from\s+now\s+on\s+you\s+are)\s+(now\s+)?(a\s+|an\s+|my\s+)?(personal\s+assistant|general\s+purpose|unrestricted|not\s+a\s+tutor)"
            ),
            re.compile(r"you\s+are\s+no\s+longer\s+a\s+study\s+helper"),
            re.compile(r"pretend\s+(you\s+are|you're|this\s+is\s+for)"),
            re.compile(
                r"act\s+as\s+(a\s+)?(travel\s+agent|chatbot|unrestricted|personal\s+assistant)"
            ),
            re.compile(r"new\s+role\s*="),
            re.compile(r"stay\s+in\s+character"),
        ],
    ),
    (
        "system_prompt_reveal",
        [
            # System prompt / message extraction (attributed to system / AI)
            re.compile(r"system\s+(prompt|message)"),
            re.compile(r"(?:your|system|initial|hidden|original)\s+prompts?"),
            re.compile(r"whats?\s+your\s+pr[oо]mpt"),
            re.compile(
                r"what\s+were\s+(you\s+told|your\s+(?:original|initial|system)?\s*instructions)"
            ),
            re.compile(
                r"what\s+(guidelines|instructions)\s+(did\s+[a-z]+\s+give|were\s+you\s+given)"
            ),
            re.compile(r"(original|initial)\s+instructions"),
            # Bounded distance + attributed targets:
            re.compile(
                r"(reveal|show|print|output|dump|paste|list|translate|summarise|summarize|tell\s+me)\s+(?:\w+\s+){0,4}(?:your\s+(?:rules?|instructions?|guidelines?|prompts?)|(?:all\s+|full\s+|hidden\s+|system\s+)?(?:instructions?|rules?|prompts?|guidelines?)\s+you\s+were\s+(?:given|configured\s+with)|(?:rules?|prompts?|instructions?|guidelines?)\s+you\s+(?:were|are)\s+configured|hidden\s+(?:text|instructions?|rules?|prompts?)|initialization\s+text|configuration\s+message|setup\s+text)"
            ),
            re.compile(r"repeat\s+(your\s+instructions|the\s+text\s+above)"),
            re.compile(r"text\s+above\s+starting\s+with"),
            re.compile(r"message\s+that\s+sets\s+you\s+up"),
            re.compile(r"start\s+of\s+this\s+conversation\s+and\s+my\s+message"),
            re.compile(r"hidden\s+text\s+that\s+came\s+before"),
            re.compile(r"configuration\s+message"),
            re.compile(r"initialization\s+text"),
            re.compile(r"setup\s+text"),
        ],
    ),
    (
        "off_task_writing",
        [
            # Career, job, and employment documents
            re.compile(r"cover\s+letter"),
            re.compile(r"(introductory|recommendation|resignation)\s+letter"),
            re.compile(r"letter\s+of\s+(recommendation|intent|resignation)"),
            re.compile(r"two-?week\s+notice"),
            re.compile(r"(resume|cv|curriculum\s+vitae)"),
            re.compile(r"professional\s+bio"),
            re.compile(r"linkedin\s+(summary|profile|about|bio|section)"),
            re.compile(r"job\s+application\s+(answer|response|essay|letter)"),
            re.compile(r"interview\s+(question|answer|response)"),
            re.compile(
                r"(draft|write)\s+(an?\s+)?(email|message|note|letter)\s+(to|from)\s+(a\s+|my\s+)?(professor|manager|boss|recruiter|teacher|supervisor)"
            ),
            re.compile(r"(reach|reaching)\s+out\s+to\s+(a\s+|my\s+)?recruiter"),
            # Admissions, applications, and scholarship writing
            re.compile(
                r"(college|transfer|common\s+app|supplemental|scholarship|personal|admissions?|application)\s+(essay|statement|story)"
            ),
            re.compile(r"personal\s+statement"),
            re.compile(r"why\s+this\s+college"),
            re.compile(r"write\s+me\s+an\s+essay"),
            re.compile(r"resignation\s+(email|letter|note)"),
            re.compile(r"(graduate\s+school|grad\s+school|job)\s+application"),
            re.compile(r"funding\s+for\s+college\s+tuition"),
        ],
    ),
]

BLOCKED_REPLY = (
    "I can only help with study questions, "
    "so send me a homework problem and we will work through it."
)

# Cyrillic lookalikes map for homoglyph de-obfuscation
CYRILLIC_LOOKALIKES = str.maketrans("асеорхуАВЕКМНОРСТХ", "aceopxyABEKMHOPCTX")


def _normalise(text: str) -> str:
    """
    De-obfuscate and normalise text:
    1. Unicode NFKC normalisation
    2. Cyrillic homoglyph translation
    3. Lowercase
    4. Squeeze spaced-out single letters (e.g. 'i g n o r e' -> 'ignore')
    5. Collapse whitespace runs
    """
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(CYRILLIC_LOOKALIKES)
    text = text.lower()
    text = re.sub(
        r"\b[a-z](\s+[a-z]){2,}\b", lambda m: re.sub(r"\s+", "", m.group(0)), text
    )
    return re.sub(r"\s+", " ", text).strip()


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
