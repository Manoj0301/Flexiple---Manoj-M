from app.feedback import merge_feedback, parse_positional_feedback
from app.models import RecruiterFeedback


VISIBLE = ["p01", "p02", "p03", "p04"]


def test_maps_positions_in_display_order():
    found = parse_positional_feedback("1 is too junior, 2 and 4 are right", VISIBLE)
    by_id = {item.profile_id: item.verdict for item in found}
    assert by_id == {"p01": "reject", "p02": "accept", "p04": "accept"}


def test_explicit_feedback_overrides_message():
    explicit = [RecruiterFeedback(profile_id="p01", verdict="accept", reason="button")]
    merged = merge_feedback(explicit, "1 is too junior", VISIBLE)
    assert merged[0].verdict == "accept"
    assert merged[0].profile_id == "p01"


def test_ignores_positions_outside_the_visible_set():
    found = parse_positional_feedback("9 is wrong", VISIBLE)
    assert found == []
