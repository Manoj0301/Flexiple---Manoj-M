from app.errors import AppError
from app.models import FitRubric, ObjectiveFilters, RubricCriterion, SearchSpec
from app.normalize import coerce_company_type, normalize


def _unique(values: list[str], limit: int) -> list[str]:
    kept: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = " ".join(value.strip().split())
        key = normalize(text)
        if not key or key in seen:
            continue
        seen.add(key)
        kept.append(text)
        if len(kept) >= limit:
            break
    return kept


def _normalize_weights(criteria: list[RubricCriterion]) -> list[RubricCriterion]:
    total = sum(item.weight for item in criteria)
    if total <= 0:
        raise AppError("INVALID_SEARCH_SPEC", "Rubric weights must be positive.", False, 422)
    raw = [max(1, round(item.weight / total * 100)) for item in criteria]
    drift = 100 - sum(raw)
    raw[-1] += drift
    if raw[-1] < 1:
        raw[-1] = 1
        excess = sum(raw) - 100
        largest = max(range(len(raw)), key=lambda index: raw[index])
        raw[largest] = max(1, raw[largest] - excess)
    return [
        criterion.model_copy(update={"weight": weight})
        for criterion, weight in zip(criteria, raw, strict=True)
    ]


def normalize_spec(spec: SearchSpec) -> SearchSpec:
    filters = spec.filters
    company_types: list[str] = []
    for value in filters.company_types:
        coerced = coerce_company_type(value)
        if coerced is None:
            raise AppError(
                "INVALID_SEARCH_SPEC",
                f"Unknown company type '{value}'. Use startup, scaleup, enterprise, or agency.",
                False,
                422,
            )
        if coerced not in company_types:
            company_types.append(coerced)
    if filters.min_years is not None and filters.max_years is not None and filters.min_years > filters.max_years:
        raise AppError(
            "INVALID_SEARCH_SPEC",
            "Minimum years cannot exceed maximum years.",
            False,
            422,
        )
    if filters.company_history not in {"current", "past", "any"}:
        raise AppError("INVALID_SEARCH_SPEC", "Company history must be current, past, or any.", False, 422)

    criteria = spec.rubric.criteria[:6]
    if not criteria:
        raise AppError("INVALID_SEARCH_SPEC", "The fit rubric needs at least one criterion.", False, 422)
    seen_ids: set[str] = set()
    rewritten: list[RubricCriterion] = []
    for index, criterion in enumerate(criteria, start=1):
        name = " ".join(criterion.name.strip().split())
        description = " ".join(criterion.description.strip().split())
        if not name or not description:
            raise AppError("INVALID_SEARCH_SPEC", "Each rubric criterion needs a name and description.", False, 422)
        criterion_id = criterion.id.strip() or f"c{index}"
        if criterion_id in seen_ids:
            criterion_id = f"{criterion_id}_{index}"
        seen_ids.add(criterion_id)
        rewritten.append(
            criterion.model_copy(update={"id": criterion_id, "name": name, "description": description})
        )

    return SearchSpec(
        filters=ObjectiveFilters(
            required_skills=_unique(filters.required_skills, 8),
            min_years=filters.min_years,
            max_years=filters.max_years,
            locations=_unique(filters.locations, 5),
            company_types=company_types,
            company_history=filters.company_history,
            skill_match=filters.skill_match,
        ),
        rubric=FitRubric(criteria=_normalize_weights(rewritten)),
    )
