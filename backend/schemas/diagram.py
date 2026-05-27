"""Pydantic schemas for the diagram JSON the LLM emits.

Stricter than the diagram-service's runtime guards: catches malformed shapes
before they reach React Flow, so the user sees no diagram instead of a broken
one.
"""
from typing import Literal
from pydantic import BaseModel, Field


class DiagramEntity(BaseModel):
    type: Literal["individual", "trust", "company"]
    label: str = Field(min_length=1)
    jurisdiction: str | None = None
    role: str | None = None
    tax_treatment: str | None = None
    rationale: str | None = None
    source: str | None = None


class DiagramEdge(BaseModel):
    source: int = Field(ge=0)
    target: int = Field(ge=0)
    label: str = ""


class Diagram(BaseModel):
    entities: list[DiagramEntity]
    edges: list[DiagramEdge] = []
