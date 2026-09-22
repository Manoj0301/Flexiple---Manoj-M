import json
import secrets
from dataclasses import dataclass, field
from typing import Literal

from app.diff import diff_specs
from app.errors import AppError
from app.evidence import infer_citations, validate_citations
from app.feedback import merge_feedback
from app.filters import filter_profiles, pre_rank
from app.llm import OpenAIClient
from app.llm_schema import LLMParse, LLMRefine, LLMScoreBatch
from app.models import (
    CardOut,
    Citation,
    Profile,
    RecruiterFeedback,
    ScoredCard,
    SearchSpec,
    SessionView,
)
from app.prompts import load_prompt
from app.spec import normalize_spec

VISIBLE_LIMIT = 5
SCORE_LIMIT = 12


@dataclass
class Revision:
    version: int
    spec: SearchSpec
    cards: list[ScoredCard]
    filtered_count: int
    feedback: list[RecruiterFeedback] = field(default_factory=list)
    changes: list = field(default_factory=list)


@dataclass
class FailedOp:
    kind: Literal["edit", "refine"]
    spec: SearchSpec | None = None
    message: str = ""
    feedback: list[RecruiterFeedback] = field(default_factory=list)


@dataclass
class Session:
    id: str
    original_query: str
    status: Literal["active", "frozen"]
    revisions: list[Revision]
    failed: FailedOp | None = None


class SearchService:
    def __init__(self, profiles: list[Profile], llm: OpenAIClient | None = None):
        self.profiles = profiles
        self.llm = llm or OpenAIClient()
        self.sessions: dict[str, Session] = {}

    def _get(self, session_id: str) -> Session:
        session = self.sessions.get(session_id)
        if session is None:
            raise AppError("SESSION_NOT_FOUND", "That search session no longer exists.", False, 404)
        return session

    def _require_active(self, session_id: str) -> Session:
        session = self._get(session_id)
        if session.status == "frozen":
            raise AppError(
                "SESSION_ALREADY_FROZEN",
                "This search is frozen. Filters, rubric, and the shortlist are locked.",
                False,
                409,
            )
        return session

    def view(self, session: Session) -> SessionView:
        revision = session.revisions[-1]
        ranked = [
            CardOut(
                position=index,
                profile=card.profile,
                score=card.score,
                citations=card.citations,
                reason=card.reason,
                concern=card.concern,
            )
            for index, card in enumerate(revision.cards, start=1)
        ]
        return SessionView(
            session_id=session.id,
            status=session.status,
            original_query=session.original_query,
            revision=revision.version,
            search_spec=revision.spec,
            filtered_count=revision.filtered_count,
            ranked_count=len(ranked),
            pool_size=len(self.profiles),
            visible=ranked[:VISIBLE_LIMIT],
            ranked=ranked,
            changes=revision.changes,
        )

    async def _score(self, spec: SearchSpec, force: str | None) -> tuple[int, list[ScoredCard]]:
        filtered = filter_profiles(self.profiles, spec.filters)
        if not filtered:
            return 0, []
        chosen = pre_rank(filtered, spec.filters, SCORE_LIMIT)
        prompt = (
            load_prompt("score_profiles.md")
            + "\n\nINPUT:\n"
            + json.dumps(
                {
                    "rubric": spec.rubric.model_dump(),
                    "profiles": [profile.model_dump() for profile in chosen],
                },
                indent=2,
            )
        )
        batch = await self.llm.generate(prompt, LLMScoreBatch, force)
        by_id = {profile.id: profile for profile in chosen}
        cards: list[ScoredCard] = []
        for item in batch.scores:
            profile = by_id.get(item.profile_id)
            if profile is None:
                continue
            citations = validate_citations(
                profile,
                [Citation(field=citation.field, quote=citation.quote) for citation in item.citations],
            )
            if not citations:
                citations = infer_citations(profile, item.reason)
            if not citations:
                continue
            cards.append(
                ScoredCard(
                    profile=profile,
                    score=max(0, min(100, int(item.score))),
                    citations=citations[:6],
                    reason=item.reason.strip() or _reason_from_citations(profile, citations),
                    concern=(item.concern or "").strip() or None,
                )
            )
        cards.sort(key=lambda card: (-card.score, card.profile.name))
        return len(filtered), cards

    def _commit(
        self,
        session: Session,
        spec: SearchSpec,
        filtered_count: int,
        cards: list[ScoredCard],
        changes: list,
        feedback: list[RecruiterFeedback],
    ) -> SessionView:
        version = len(session.revisions)
        session.revisions.append(
            Revision(
                version=version,
                spec=spec,
                cards=cards,
                filtered_count=filtered_count,
                feedback=feedback,
                changes=changes,
            )
        )
        session.failed = None
        return self.view(session)

    async def create(self, query: str, force: str | None = None) -> SessionView:
        text = query.strip()
        if not text:
            raise AppError("INVALID_REQUEST", "Enter a search requirement.", False, 400)
        parsed = await self.llm.generate(
            load_prompt("parse_search.md") + "\n\nRECRUITER NOTE:\n" + text,
            LLMParse,
            force,
        )
        spec = _spec_from_llm(parsed)
        filtered_count, cards = await self._score(spec, None)
        session = Session(id=f"s_{secrets.token_hex(4)}", original_query=text, status="active", revisions=[])
        self.sessions[session.id] = session
        return self._commit(session, spec, filtered_count, cards, [], [])

    async def edit(self, session_id: str, spec: SearchSpec, force: str | None = None) -> SessionView:
        session = self._require_active(session_id)
        normalized = normalize_spec(spec)
        try:
            filtered_count, cards = await self._score(normalized, force)
        except AppError:
            session.failed = FailedOp(kind="edit", spec=normalized)
            raise
        changes = diff_specs(
            session.revisions[-1].spec,
            normalized,
            default_reason="Edited directly by the recruiter.",
        )
        return self._commit(session, normalized, filtered_count, cards, changes, [])

    async def refine(
        self,
        session_id: str,
        message: str,
        explicit: list[RecruiterFeedback],
        force: str | None = None,
    ) -> SessionView:
        session = self._require_active(session_id)
        current = session.revisions[-1]
        visible = current.cards[:VISIBLE_LIMIT]
        visible_ids = [card.profile.id for card in visible]
        feedback = merge_feedback(explicit, message, visible_ids)
        if not message.strip() and not feedback:
            raise AppError("INVALID_REQUEST", "Add feedback before refining.", False, 400)
        prompt = _refine_prompt(session, current, visible, feedback, message)
        try:
            parsed = await self.llm.generate(prompt, LLMRefine, force)
            spec = _spec_from_llm(parsed)
            filtered_count, cards = await self._score(spec, None)
        except AppError:
            session.failed = FailedOp(kind="refine", message=message, feedback=explicit)
            raise
        reasons = {note.field: note.reason for note in parsed.change_notes}
        changes = diff_specs(current.spec, spec, reasons)
        return self._commit(session, spec, filtered_count, cards, changes, feedback)

    async def retry(self, session_id: str, force: str | None = None) -> SessionView:
        session = self._require_active(session_id)
        failed = session.failed
        if failed is None:
            raise AppError("INVALID_REQUEST", "There is no failed step to retry.", False, 400)
        if failed.kind == "edit" and failed.spec is not None:
            return await self.edit(session_id, failed.spec, force)
        return await self.refine(session_id, failed.message, failed.feedback, force)

    def freeze(self, session_id: str) -> SessionView:
        session = self._get(session_id)
        if not session.revisions:
            raise AppError("INVALID_REQUEST", "This search has no results to freeze.", False, 400)
        session.status = "frozen"
        session.failed = None
        return self.view(session)

    def get(self, session_id: str) -> SessionView:
        return self.view(self._get(session_id))


def _spec_from_llm(parsed: LLMParse | LLMRefine) -> SearchSpec:
    data = {"filters": parsed.filters.model_dump(), "rubric": parsed.rubric.model_dump()}
    history = data["filters"].get("company_history")
    if history not in {"current", "past", "any"}:
        data["filters"]["company_history"] = "any"
    match = data["filters"].get("skill_match")
    if match not in {"all", "any"}:
        data["filters"]["skill_match"] = "all"
    for index, criterion in enumerate(data["rubric"].get("criteria") or [], start=1):
        if not criterion.get("weight") or criterion["weight"] <= 0:
            criterion["weight"] = 1
        if not str(criterion.get("id") or "").strip():
            criterion["id"] = f"c{index}"
    try:
        return normalize_spec(SearchSpec.model_validate(data))
    except AppError as exc:
        exc.retryable = True
        raise


def _reason_from_citations(profile: Profile, citations: list[Citation]) -> str:
    bits = [citation.quote for citation in citations[:3]]
    detail = ", ".join(bits)
    return f"{profile.name} matches on {detail}."


def _refine_prompt(
    session: Session,
    current: Revision,
    visible: list[ScoredCard],
    feedback: list[RecruiterFeedback],
    message: str,
) -> str:
    history = []
    for revision in session.revisions[-3:]:
        history.append(
            {
                "version": revision.version,
                "changes": [change.model_dump() for change in revision.changes],
            }
        )
    payload = {
        "original_query": session.original_query,
        "current_spec": current.spec.model_dump(),
        "visible_candidates": [
            {
                "position": index,
                "profile_id": card.profile.id,
                "name": card.profile.name,
                "current_title": card.profile.current_title,
                "years_experience": card.profile.years_experience,
                "location": card.profile.location,
                "current_company": card.profile.current_company,
                "current_company_type": card.profile.current_company_type,
                "skills": card.profile.skills,
                "score": card.score,
                "reason": card.reason,
            }
            for index, card in enumerate(visible, start=1)
        ],
        "feedback": [item.model_dump() for item in feedback],
        "message": message,
        "recent_changes": history,
    }
    return load_prompt("refine_search.md") + "\n\nINPUT:\n" + json.dumps(payload, indent=2)
