import asyncio
import json

import pytest

from app.errors import AppError
from app.llm_schema import (
    LLMChangeNote,
    LLMCitation,
    LLMCriterion,
    LLMFilters,
    LLMParse,
    LLMRefine,
    LLMRubric,
    LLMScore,
    LLMScoreBatch,
)
from app.profiles import load_profiles
from app.service import SearchService


class FakeLLM:
    async def generate(self, prompt: str, schema: type, force: str | None = None):
        if force == "timeout":
            raise AppError("LLM_TIMEOUT", "The AI service timed out. Your last results are unchanged.", True, 504)
        if force == "malformed":
            raise AppError("LLM_INVALID_OUTPUT", "The model returned malformed JSON. Your last results are unchanged.", True, 502)
        if schema is LLMParse:
            return LLMParse(
                filters=LLMFilters(
                    required_skills=["RDS"],
                    min_years=4,
                    max_years=7,
                    locations=["Bengaluru"],
                    company_types=["startup"],
                    company_history="any",
                    skill_match="all",
                ),
                rubric=LLMRubric(
                    criteria=[
                        LLMCriterion(id="db", name="Database depth", description="Practical AWS RDS work.", weight=3),
                        LLMCriterion(id="exp", name="Experience", description="Mid-level scope.", weight=1),
                    ]
                ),
            )
        if schema is LLMScoreBatch:
            payload = json.loads(prompt.split("INPUT:\n", 1)[1])
            return LLMScoreBatch(
                scores=[
                    LLMScore(
                        profile_id=profile["id"],
                        score=70 + len(profile["skills"]),
                        citations=[
                            LLMCitation(field="skills", quote=profile["skills"][0]),
                            LLMCitation(field="location", quote=profile["location"]),
                        ],
                        reason=f"{profile['name']} lists {profile['skills'][0]} in {profile['location']}.",
                        concern=None,
                    )
                    for profile in payload["profiles"]
                ]
            )
        if schema is LLMRefine:
            return LLMRefine(
                filters=LLMFilters(
                    required_skills=["AWS RDS"],
                    min_years=5,
                    max_years=7,
                    locations=["Bangalore"],
                    company_types=["startup"],
                    company_history="any",
                    skill_match="all",
                ),
                rubric=LLMRubric(
                    criteria=[
                        LLMCriterion(id="db", name="Database depth", description="Practical AWS RDS work.", weight=40),
                        LLMCriterion(id="exp", name="Experience", description="Stronger seniority.", weight=60),
                    ]
                ),
                change_notes=[LLMChangeNote(field="min_years", reason="Candidate 1 was too junior.")],
            )
        raise AssertionError(schema)


@pytest.fixture
def service() -> SearchService:
    return SearchService(load_profiles(), FakeLLM())


def test_loop_commits_only_after_success(service: SearchService):
    asyncio.run(_loop(service))


async def _loop(service: SearchService):
    created = await service.create("RDS developers with 4-7 years at startups in Bangalore")
    assert created.filtered_count > 0
    assert 1 <= len(created.visible) <= 5
    assert created.visible[0].position == 1
    assert created.search_spec.filters.required_skills == ["RDS"]
    assert created.search_spec.rubric.criteria[0].weight + created.search_spec.rubric.criteria[1].weight == 100
    assert any(item.quote for item in created.visible[0].citations)

    with pytest.raises(AppError) as caught:
        await service.edit(created.session_id, created.search_spec, force="timeout")
    assert caught.value.code == "LLM_TIMEOUT"
    assert service.get(created.session_id).revision == 0

    retried = await service.retry(created.session_id)
    assert retried.revision == 1

    first_id = retried.visible[0].profile.id
    refined = await service.refine(created.session_id, "1 is too junior, 2 and 4 are right", [])
    years = next(change for change in refined.changes if change.field == "min_years")
    assert years.old_value == 4
    assert years.new_value == 5
    assert years.reason == "Candidate 1 was too junior."
    feedback = {item.profile_id: item.verdict for item in service.sessions[created.session_id].revisions[-1].feedback}
    assert feedback[first_id] == "reject"

    frozen = service.freeze(created.session_id)
    assert frozen.status == "frozen"
    assert len(frozen.ranked) >= len(frozen.visible)
    with pytest.raises(AppError) as frozen_error:
        await service.refine(created.session_id, "change it again", [])
    assert frozen_error.value.code == "SESSION_ALREADY_FROZEN"
