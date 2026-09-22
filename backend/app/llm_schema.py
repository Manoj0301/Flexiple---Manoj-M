from pydantic import BaseModel, Field


class LLMFilters(BaseModel):
    required_skills: list[str] = Field(default_factory=list)
    min_years: float | None = None
    max_years: float | None = None
    locations: list[str] = Field(default_factory=list)
    company_types: list[str] = Field(default_factory=list)
    company_history: str = "any"
    skill_match: str = "all"


class LLMCriterion(BaseModel):
    id: str
    name: str
    description: str
    weight: float = 1


class LLMRubric(BaseModel):
    criteria: list[LLMCriterion] = Field(default_factory=list)


class LLMParse(BaseModel):
    filters: LLMFilters
    rubric: LLMRubric


class LLMCitation(BaseModel):
    field: str
    quote: str


class LLMScore(BaseModel):
    profile_id: str
    score: int = 0
    citations: list[LLMCitation] = Field(default_factory=list)
    reason: str = ""
    concern: str | None = None


class LLMScoreBatch(BaseModel):
    scores: list[LLMScore] = Field(default_factory=list)


class LLMChangeNote(BaseModel):
    field: str
    reason: str


class LLMRefine(BaseModel):
    filters: LLMFilters
    rubric: LLMRubric
    change_notes: list[LLMChangeNote] = Field(default_factory=list)
