from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class CheckRequest(BaseModel):
    message: str


class CheckResponse(BaseModel):
    reply: str


@app.post("/check", response_model=CheckResponse)
async def check(request: CheckRequest) -> CheckResponse:
    """Receive a message and return a reply."""
    return CheckResponse(reply=f"Received: {request.message}")
