from app.models import SearchChange, SearchSpec
from app.normalize import normalize

_FILTER_FIELDS = (
    "required_skills",
    "min_years",
    "max_years",
    "locations",
    "company_types",
    "company_history",
    "skill_match",
)

_DEFAULT_REASON = "Updated to reflect recruiter feedback."


def diff_specs(
    old: SearchSpec,
    new: SearchSpec,
    reasons: dict[str, str] | None = None,
    default_reason: str = _DEFAULT_REASON,
) -> list[SearchChange]:
    notes = reasons or {}
    changes: list[SearchChange] = []
    for field in _FILTER_FIELDS:
        before = getattr(old.filters, field)
        after = getattr(new.filters, field)
        if before != after:
            changes.append(
                SearchChange(
                    change_type="filter",
                    field=field,
                    old_value=before,
                    new_value=after,
                    reason=notes.get(field, default_reason),
                )
            )

    old_by_name = {normalize(item.name): item for item in old.rubric.criteria}
    new_by_name = {normalize(item.name): item for item in new.rubric.criteria}
    if old_by_name and new_by_name and not (set(old_by_name) & set(new_by_name)):
        changes.append(
            SearchChange(
                change_type="rubric",
                field="rubric",
                old_value=[item.name for item in old.rubric.criteria],
                new_value=[item.name for item in new.rubric.criteria],
                reason=notes.get("rubric", default_reason),
            )
        )
        return changes

    for name, criterion in new_by_name.items():
        previous = old_by_name.get(name)
        if previous is None:
            changes.append(
                SearchChange(
                    change_type="rubric",
                    field=f"rubric.{criterion.name}",
                    old_value=None,
                    new_value=criterion.description,
                    reason=notes.get(f"rubric.{criterion.name}", notes.get("rubric", default_reason)),
                )
            )
            continue
        if abs(previous.weight - criterion.weight) >= 5:
            field = f"rubric.{criterion.name}.weight"
            changes.append(
                SearchChange(
                    change_type="rubric",
                    field=field,
                    old_value=previous.weight,
                    new_value=criterion.weight,
                    reason=notes.get(field, notes.get("rubric", default_reason)),
                )
            )
        if normalize(previous.description) != normalize(criterion.description):
            field = f"rubric.{criterion.name}.description"
            changes.append(
                SearchChange(
                    change_type="rubric",
                    field=field,
                    old_value=previous.description,
                    new_value=criterion.description,
                    reason=notes.get(field, notes.get("rubric", default_reason)),
                )
            )
    for name, criterion in old_by_name.items():
        if name not in new_by_name:
            changes.append(
                SearchChange(
                    change_type="rubric",
                    field=f"rubric.{criterion.name}",
                    old_value=criterion.description,
                    new_value=None,
                    reason=notes.get("rubric", default_reason),
                )
            )
    return changes
