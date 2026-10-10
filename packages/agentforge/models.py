from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

SCENARIOS = ("incident", "sdlc", "knowledge", "workflow", "reliability")
CAPABILITIES = [
    "structured-output",
    "rag",
    "react-planning",
    "mcp",
    "memory",
    "human-approval",
    "model-routing",
    "events",
    "debate",
    "reflection",
    "observability",
    "sdk",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunRequest(StrictModel):
    scenario: Literal["incident", "sdlc", "knowledge", "workflow", "reliability"]
    prompt: str = Field(min_length=5, max_length=4000)
    mode: Literal["demo", "live"] = "demo"
    budget_tokens: int = Field(default=16000, ge=1000, le=64000)


class Citation(StrictModel):
    source_id: str
    quote: str = Field(min_length=1, max_length=1200)


class Proposal(StrictModel):
    summary: str = Field(min_length=1, max_length=2000)
    action: Literal["rollback", "patch", "answer", "purchase", "evaluate"]
    citations: list[Citation] = Field(default_factory=list, max_length=8)
    risk: Literal["low", "medium", "high"]


class Review(StrictModel):
    approved: bool
    reasons: list[str] = Field(min_length=1, max_length=8)


class Approval(StrictModel):
    digest: str = Field(min_length=64, max_length=64)
    approve: bool


class Document(StrictModel):
    title: str = Field(min_length=1, max_length=150)
    text: str = Field(min_length=10, max_length=50000)


class Event(StrictModel):
    event_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    request: RunRequest
