from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class PastCompany(BaseModel):
    company: str
    company_type: str
    title: str
    years: float


class Profile(BaseModel):
    id: str
    name: str
    current_title: str
    years_experience: float
    location: str
    current_company: str
    current_company_type: str
    skills: list[str]
    past_companies: list[PastCompany]
    education: str
    summary: str


class ObjectiveFilters(BaseModel):
    required_skills: list[str] = Field(default_factory=list)
    min_years: float | None = None
    max_years: float | None = None
    locations: list[str] = Field(default_factory=list)
    company_types: list[str] = Field(default_factory=list)
    company_history: Literal["current", "past", "any"] = "any"
    skill_match: Literal["all", "any"] = "all"

    @field_validator("min_years", "max_years", mode="before")
    @classmethod
    def empty_years(cls, value: Any) -> Any:
        if value == "" or value is None:
            return None
        return value


class RubricCriterion(BaseModel):
    id: str
    name: str
    description: str
    weight: float = Field(gt=0)


class FitRubric(BaseModel):
    criteria: list[RubricCriterion]


class SearchSpec(BaseModel):
    filters: ObjectiveFilters
    rubric: FitRubric


class Citation(BaseModel):
    field: str
    quote: str


class ScoredCard(BaseModel):
    profile: Profile
    score: int = Field(ge=0, le=100)
    citations: list[Citation]
    reason: str
    concern: str | None = None


class RecruiterFeedback(BaseModel):
    profile_id: str
    verdict: Literal["accept", "reject"]
    reason: str | None = None


class SearchChange(BaseModel):
    change_type: Literal["filter", "rubric"]
    field: str
    old_value: Any = None
    new_value: Any = None
    reason: str


class CardOut(BaseModel):
    position: int
    profile: Profile
    score: int
    citations: list[Citation]
    reason: str
    concern: str | None = None


class SessionView(BaseModel):
    session_id: str
    status: Literal["active", "frozen"]
    original_query: str
    revision: int
    search_spec: SearchSpec
    filtered_count: int
    ranked_count: int
    pool_size: int
    visible: list[CardOut]
    ranked: list[CardOut]
    changes: list[SearchChange]
