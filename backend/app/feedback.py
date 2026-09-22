import re

from app.models import RecruiterFeedback

_REJECT = ("junior", "reject", "wrong", "overqualified", "underqualified", "not a fit", "too ")
_ACCEPT = ("right", "yes", "match", "good", "perfect", "keep", "fits", "fit")


def parse_positional_feedback(message: str, visible_ids: list[str]) -> list[RecruiterFeedback]:
    feedback: list[RecruiterFeedback] = []
    seen: set[str] = set()
    clauses = re.split(r"[,;\n]", message)
    for clause in clauses:
        numbers = [int(item) for item in re.findall(r"\b([1-9])\b", clause)]
        if not numbers:
            continue
        lowered = clause.lower()
        if any(word in lowered for word in _REJECT) or re.search(r"\b(no|not)\b", lowered):
            verdict = "reject"
        elif any(word in lowered for word in _ACCEPT):
            verdict = "accept"
        else:
            continue
        for number in numbers:
            if number < 1 or number > len(visible_ids):
                continue
            profile_id = visible_ids[number - 1]
            if profile_id in seen:
                continue
            seen.add(profile_id)
            feedback.append(
                RecruiterFeedback(profile_id=profile_id, verdict=verdict, reason=clause.strip())
            )
    return feedback


def merge_feedback(
    explicit: list[RecruiterFeedback],
    message: str,
    visible_ids: list[str],
) -> list[RecruiterFeedback]:
    merged: dict[str, RecruiterFeedback] = {}
    for item in parse_positional_feedback(message, visible_ids):
        merged[item.profile_id] = item
    for item in explicit:
        if item.profile_id in visible_ids:
            merged[item.profile_id] = item
    return list(merged.values())
