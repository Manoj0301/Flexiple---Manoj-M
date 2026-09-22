import json
from pathlib import Path

from app.models import Profile

_PATH = Path(__file__).resolve().parents[1] / "data" / "profiles.json"


def load_profiles(path: Path = _PATH) -> list[Profile]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Profile.model_validate(item) for item in raw]
