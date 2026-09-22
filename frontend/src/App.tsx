import { useEffect, useState } from "react";
import {
  ApiError,
  createSession,
  editSpec,
  freezeSession,
  refineSession,
  retrySession,
  type RecruiterMark,
} from "./api";
import type { Card, Profile, RubricCriterion, SearchChange, SearchSpec, Session } from "./types";

const COMPANY_TYPES = ["startup", "scaleup", "enterprise", "agency"] as const;
const YEAR_MIN = 0;
const YEAR_MAX = 15;

const FIELD_LABELS: Record<string, string> = {
  required_skills: "Required skills",
  min_years: "Minimum years",
  max_years: "Maximum years",
  locations: "Location",
  company_types: "Company background",
  company_history: "Company history",
  skill_match: "Skill match",
  rubric: "Fit rubric",
};

const EXAMPLES = [
  {
    title: "Backend, Bangalore",
    detail: "RDS, 4–7 years, startup background",
    query: "RDS developers with 4–7 years who have worked at startups, for a role in Bangalore.",
  },
  {
    title: "Frontend, Amsterdam",
    detail: "Senior React, product companies",
    query: "Senior React engineers in Amsterdam who have worked at product companies.",
  },
  {
    title: "DevOps, remote India",
    detail: "Kubernetes, 5 or more years",
    query: "DevOps engineers with Kubernetes and 5 or more years, open to remote India.",
  },
];

type View = "search" | "shortlist" | "messages" | "analytics";
type Activity = "search" | "edit" | "refine" | "freeze" | "retry";

const ACTIVITY_COPY: Record<Activity, { headline: string; steps: string[] }> = {
  search: {
    headline: "Searching for the best candidates for your organization",
    steps: [
      "Reading your brief",
      "Picking skills, years, and location",
      "Checking the candidate pool",
      "Scoring who fits the role",
      "Ranking the strongest matches",
    ],
  },
  edit: {
    headline: "Updating the shortlist",
    steps: ["Checking the filters you changed", "Searching the pool again", "Scoring the updated matches"],
  },
  refine: {
    headline: "Applying your feedback",
    steps: ["Reading what you marked", "Updating the search", "Scoring the revised shortlist"],
  },
  freeze: {
    headline: "Locking this shortlist",
    steps: ["Saving the profiles on screen"],
  },
  retry: {
    headline: "Trying that step again",
    steps: ["Contacting the model", "Scoring the matches"],
  },
};

function cloneSpec(spec: SearchSpec): SearchSpec {
  return JSON.parse(JSON.stringify(spec)) as SearchSpec;
}

function formatValue(value: unknown): string {
  if (value == null || value === "") return "none";
  if (Array.isArray(value)) return value.length ? value.join(", ") : "none";
  return String(value);
}

function fieldLabel(field: string): string {
  if (FIELD_LABELS[field]) return FIELD_LABELS[field];
  return field.replace(/^rubric\./, "").replaceAll(".", " ").replaceAll("_", " ");
}

function initials(name: string): string {
  return name
    .split(" ")
    .slice(0, 2)
    .map((part) => part[0] ?? "")
    .join("")
    .toUpperCase();
}

function sameSpec(left: SearchSpec, right: SearchSpec): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

function skillMatches(skill: string, required: string[]): boolean {
  const value = skill.toLowerCase();
  return required.some((item) => {
    const needle = item.toLowerCase();
    return value.includes(needle) || needle.includes(value);
  });
}

function fitLabel(score: number): string {
  if (score >= 90) return "Excellent match";
  if (score >= 75) return "Great match";
  return "Good match";
}

function Icon({ d, extra }: { d: string; extra?: string }) {
  return (
    <svg className="icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d={d} />
      {extra && <path d={extra} />}
    </svg>
  );
}

export function App() {
  const [view, setView] = useState<View>("search");
  const [query, setQuery] = useState(EXAMPLES[0].query);
  const [session, setSession] = useState<Session | null>(null);
  const [draft, setDraft] = useState<SearchSpec | null>(null);
  const [message, setMessage] = useState("");
  const [marks, setMarks] = useState<Record<string, "accept" | "reject">>({});
  const [activity, setActivity] = useState<Activity | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [toast, setToast] = useState("");
  const [profile, setProfile] = useState<Profile | null>(null);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 2800);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    if (session) setDraft(cloneSpec(session.search_spec));
  }, [session]);

  const frozen = session?.status === "frozen";
  const busy = activity !== null;
  const cards = session ? (frozen ? session.ranked : session.visible) : [];
  const dirty = Boolean(session && draft && !sameSpec(draft, session.search_spec));
  const shortlisted = cards.filter((card) => marks[card.profile.id] === "accept");

  async function run<T>(next: Activity, action: () => Promise<T>, onSuccess: (value: T) => void) {
    setActivity(next);
    setError(null);
    try {
      onSuccess(await action());
    } catch (caught) {
      setError(caught instanceof ApiError ? caught : new ApiError("REQUEST_FAILED", "The request failed.", true));
    } finally {
      setActivity(null);
    }
  }

  function acceptSession(next: Session) {
    setSession(next);
    setMarks({});
    setMessage("");
    setView("search");
  }

  function onSearch() {
    const text = query.trim();
    if (!text) {
      setToast("Enter a search requirement first.");
      return;
    }
    setView("search");
    void run("search", () => createSession(text), acceptSession);
  }

  function onApply() {
    if (!session || !draft) return;
    void run("edit", () => editSpec(session.session_id, draft), acceptSession);
  }

  function onRefine() {
    if (!session) return;
    const feedback: RecruiterMark[] = Object.entries(marks).map(([profile_id, verdict]) => ({
      profile_id,
      verdict,
    }));
    if (!message.trim() && feedback.length === 0) {
      setToast("Mark profiles or describe what to change.");
      return;
    }
    void run("refine", () => refineSession(session.session_id, message.trim(), feedback), acceptSession);
  }

  function onFreeze() {
    if (!session) return;
    void run("freeze", () => freezeSession(session.session_id), (next) => {
      setSession(next);
      setMessage("");
    });
  }

  function onRetry() {
    if (session) {
      void run("retry", () => retrySession(session.session_id), acceptSession);
      return;
    }
    onSearch();
  }

  function toggleMark(profileId: string, verdict: "accept" | "reject") {
    const name = cards.find((card) => card.profile.id === profileId)?.profile.name ?? "This candidate";
    const removing = marks[profileId] === verdict;
    setMarks((current) => {
      const next = { ...current };
      if (next[profileId] === verdict) delete next[profileId];
      else next[profileId] = verdict;
      return next;
    });
    if (verdict === "accept") {
      setToast(removing ? `${name} removed from Shortlisted` : `${name} added to Shortlisted`);
    } else if (!removing) {
      setToast(`${name} marked to reject`);
    }
  }

  return (
    <div className="app-shell">
      <Topbar
        view={view}
        shortlistCount={shortlisted.length}
        onView={setView}
        onHome={() => {
          setView("search");
        }}
      />
      {view === "search" ? (
        <main className="workspace">
          <div className="side">
            <SearchCard query={query} setQuery={setQuery} busy={busy} onSearch={onSearch} />
            {draft && (
              <FiltersCard
                draft={draft}
                setDraft={setDraft}
                frozen={Boolean(frozen) || busy}
                dirty={dirty}
                busy={busy}
                onApply={onApply}
              />
            )}
          </div>
          <ResultsPanel
            query={query}
            setQuery={setQuery}
            session={session}
            cards={cards}
            frozen={Boolean(frozen)}
            busy={busy}
            activity={activity}
            error={error}
            marks={marks}
            message={message}
            setMessage={setMessage}
            onToggle={toggleMark}
            onFreeze={onFreeze}
            onRetry={onRetry}
            onRefine={onRefine}
            onOpen={setProfile}
          />
        </main>
      ) : (
        <SecondaryView
          view={view}
          session={session}
          shortlisted={shortlisted}
          onOpen={setProfile}
          onSearch={() => setView("search")}
        />
      )}
      {profile && <ProfileDialog profile={profile} onClose={() => setProfile(null)} />}
      <div className={`toast ${toast ? "show" : ""}`}>{toast}</div>
    </div>
  );
}

function Topbar({
  view,
  shortlistCount,
  onView,
  onHome,
}: {
  view: View;
  shortlistCount: number;
  onView: (view: View) => void;
  onHome: () => void;
}) {
  const items: { id: View; label: string; icon: string; extra?: string }[] = [
    { id: "search", label: "Search", icon: "M11 19a8 8 0 1 1 0-16 8 8 0 0 1 0 16z", extra: "M21 21l-4.3-4.3" },
    { id: "shortlist", label: "Shortlisted", icon: "M12 3.2l2.4 5.2 5.6.6-4.2 3.8 1.2 5.5L12 15.8 7 18.3l1.2-5.5L4 9l5.6-.6L12 3.2z" },
    { id: "messages", label: "Messages", icon: "M5 6h14a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H9l-4 3v-3H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2z" },
    { id: "analytics", label: "Analytics", icon: "M4 19V5M4 19h16M8 16v-5M12 16V8M16 16v-3" },
  ];
  return (
    <header className="topbar">
      <button type="button" className="brand" onClick={onHome}>
        <span className="brand-mark">F</span>
        <span>Flexiple</span>
        <span className="subbrand">Sourcing</span>
      </button>
      <nav className="nav">
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`nav-btn ${view === item.id ? "active" : ""}`}
            onClick={() => onView(item.id)}
          >
            <Icon d={item.icon} extra={item.extra} />
            {item.label}
            {item.id === "shortlist" && shortlistCount > 0 && <span className="nav-count">{shortlistCount}</span>}
          </button>
        ))}
      </nav>
      <div className="top-actions">
        <button type="button" className="bell" aria-label="Notifications">
          <Icon d="M6 9a6 6 0 1 1 12 0c0 7 3 7 3 7H3s3 0 3-7M10 19a2 2 0 0 0 4 0" />
          <span className="dot" />
        </button>
        <div className="user-chip">
          <span className="avatar">MM</span>
          <span>Manoj M.</span>
          <span className="caret">▾</span>
        </div>
      </div>
    </header>
  );
}

function SearchCard({
  query,
  setQuery,
  busy,
  onSearch,
}: {
  query: string;
  setQuery: (value: string) => void;
  busy: boolean;
  onSearch: () => void;
}) {
  return (
    <section className="panel search-panel">
      <p className="eyebrow">
        <Icon d="M11 19a8 8 0 1 1 0-16 8 8 0 0 1 0 16z" extra="M21 21l-4.3-4.3" />
        Search for talent
      </p>
      <h2>Find the right fit, faster.</h2>
      <p className="lede">Use natural language to describe what you're looking for. We'll handle the rest.</p>
      <textarea
        className="brief"
        value={query}
        disabled={busy}
        onChange={(event) => setQuery(event.target.value)}
        onKeyDown={(event) => {
          if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
            event.preventDefault();
            onSearch();
          }
        }}
      />
      <button className="run-btn" onClick={onSearch} disabled={busy || !query.trim()}>
        {busy ? <span className="spinner spinner-sm" /> : <Icon d="M11 19a8 8 0 1 1 0-16 8 8 0 0 1 0 16z" extra="M21 21l-4.3-4.3" />}
        {busy ? "Hold on" : "Run search"}
      </button>
    </section>
  );
}

function FiltersCard({
  draft,
  setDraft,
  frozen,
  dirty,
  busy,
  onApply,
}: {
  draft: SearchSpec;
  setDraft: (spec: SearchSpec) => void;
  frozen: boolean;
  dirty: boolean;
  busy: boolean;
  onApply: () => void;
}) {
  const filters = draft.filters;

  function update(next: SearchSpec) {
    setDraft(next);
  }

  return (
    <>
      <section className="panel">
        <div className="filters-head">
          <h3>Filters</h3>
          <button
            type="button"
            className="link-btn"
            disabled={frozen}
            onClick={() =>
              update({
                ...draft,
                filters: {
                  ...filters,
                  required_skills: [],
                  min_years: null,
                  max_years: null,
                  locations: [],
                  company_types: [],
                },
              })
            }
          >
            Clear all
          </button>
        </div>
        <ChipEditor
          icon="M12 3l2.2 4.6L19 8.2l-3.5 3.4.8 5L12 14.2 7.7 16.6l.8-5L5 8.2l4.8-.6L12 3z"
          label="Required skills"
          values={filters.required_skills}
          disabled={frozen}
          placeholder="Add a skill"
          onChange={(required_skills) => update({ ...draft, filters: { ...filters, required_skills } })}
        />
        <YearRange
          minYears={filters.min_years}
          maxYears={filters.max_years}
          disabled={frozen}
          onChange={(min_years, max_years) => update({ ...draft, filters: { ...filters, min_years, max_years } })}
        />
        <ChipEditor
          icon="M12 21s7-6.2 7-11a7 7 0 1 0-14 0c0 4.8 7 11 7 11z"
          extra="M12 10.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z"
          label="Location"
          values={filters.locations}
          disabled={frozen}
          placeholder="Add a location"
          onChange={(locations) => update({ ...draft, filters: { ...filters, locations } })}
        />
        <div className="field">
          <p className="field-label">
            <Icon d="M4 20V6l8-3 8 3v14M9 20v-6h6v6" />
            Company background
          </p>
          <div className="type-row">
            {COMPANY_TYPES.map((type) => {
              const active = filters.company_types.includes(type);
              return (
                <button
                  key={type}
                  type="button"
                  className={`pill ${active ? "on" : ""}`}
                  disabled={frozen}
                  onClick={() => {
                    const company_types = active
                      ? filters.company_types.filter((item) => item !== type)
                      : [...filters.company_types, type];
                    update({ ...draft, filters: { ...filters, company_types } });
                  }}
                >
                  {type}
                </button>
              );
            })}
          </div>
          <label className="select-label">
            Where that background counts
            <select
              className="select"
              value={filters.company_history}
              disabled={frozen}
              onChange={(event) =>
                update({
                  ...draft,
                  filters: { ...filters, company_history: event.target.value as SearchSpec["filters"]["company_history"] },
                })
              }
            >
              <option value="any">Current or past company</option>
              <option value="current">Current company only</option>
              <option value="past">Past companies only</option>
            </select>
          </label>
          <label className="select-label">
            Skill match
            <select
              className="select"
              value={filters.skill_match}
              disabled={frozen}
              onChange={(event) =>
                update({
                  ...draft,
                  filters: { ...filters, skill_match: event.target.value as SearchSpec["filters"]["skill_match"] },
                })
              }
            >
              <option value="all">All required skills</option>
              <option value="any">Any required skill</option>
            </select>
          </label>
        </div>
      </section>
      <section className="panel">
        <div className="filters-head">
          <h3>Fit rubric</h3>
        </div>
        <div className="rubric">
          {draft.rubric.criteria.map((criterion, index) => (
            <RubricEditor
              key={criterion.id}
              criterion={criterion}
              disabled={frozen}
              onChange={(next) => {
                const criteria = draft.rubric.criteria.slice();
                criteria[index] = next;
                update({ ...draft, rubric: { criteria } });
              }}
              onRemove={
                draft.rubric.criteria.length > 1
                  ? () => update({ ...draft, rubric: { criteria: draft.rubric.criteria.filter((_, item) => item !== index) } })
                  : undefined
              }
            />
          ))}
        </div>
        {!frozen && (
          <button
            className="ghost-btn block"
            onClick={() =>
              update({
                ...draft,
                rubric: {
                  criteria: [
                    ...draft.rubric.criteria,
                    {
                      id: `c${draft.rubric.criteria.length + 1}`,
                      name: "New criterion",
                      description: "What good looks like.",
                      weight: 10,
                    },
                  ],
                },
              })
            }
          >
            Add criterion
          </button>
        )}
        {dirty && (
          <button className="primary-btn block" onClick={onApply} disabled={busy || frozen}>
            Update results
          </button>
        )}
      </section>
    </>
  );
}

function YearRange({
  minYears,
  maxYears,
  disabled,
  onChange,
}: {
  minYears: number | null;
  maxYears: number | null;
  disabled: boolean;
  onChange: (minYears: number, maxYears: number) => void;
}) {
  const lo = minYears ?? YEAR_MIN;
  const hi = maxYears ?? YEAR_MAX;
  const span = YEAR_MAX - YEAR_MIN;
  const left = ((lo - YEAR_MIN) / span) * 100;
  const width = ((hi - lo) / span) * 100;

  function commit(nextLo: number, nextHi: number) {
    const low = Math.min(nextLo, nextHi);
    const high = Math.max(nextLo, nextHi);
    onChange(low, high);
  }

  return (
    <div className="field">
      <p className="field-label">
        <Icon d="M8 4v16M16 4v16M8 8h8M8 16h8" />
        Experience (years)
      </p>
      <div className="year-row">
        <label className="year-box">
          <input
            type="number"
            min={YEAR_MIN}
            max={YEAR_MAX}
            value={minYears ?? ""}
            disabled={disabled}
            aria-label="Minimum years"
            onChange={(event) => commit(event.target.value === "" ? YEAR_MIN : Number(event.target.value), hi)}
          />
        </label>
        <div className="slider">
          <div className="slider-track" />
          <div className="slider-fill" style={{ left: `${left}%`, width: `${width}%` }} />
          <input
            type="range"
            min={YEAR_MIN}
            max={YEAR_MAX}
            value={lo}
            disabled={disabled}
            aria-label="Minimum years"
            onChange={(event) => commit(Number(event.target.value), hi)}
          />
          <input
            type="range"
            min={YEAR_MIN}
            max={YEAR_MAX}
            value={hi}
            disabled={disabled}
            aria-label="Maximum years"
            onChange={(event) => commit(lo, Number(event.target.value))}
          />
        </div>
        <label className="year-box">
          <input
            type="number"
            min={YEAR_MIN}
            max={YEAR_MAX}
            value={maxYears ?? ""}
            disabled={disabled}
            aria-label="Maximum years"
            onChange={(event) => commit(lo, event.target.value === "" ? YEAR_MAX : Number(event.target.value))}
          />
        </label>
      </div>
    </div>
  );
}

function ChipEditor({
  icon,
  extra,
  label,
  values,
  disabled,
  placeholder,
  onChange,
}: {
  icon: string;
  extra?: string;
  label: string;
  values: string[];
  disabled: boolean;
  placeholder: string;
  onChange: (values: string[]) => void;
}) {
  const [text, setText] = useState("");
  return (
    <div className="field">
      <p className="field-label">
        <Icon d={icon} extra={extra} />
        {label}
      </p>
      <div className="chip-row">
        {values.map((value) => (
          <span className="chip hot" key={value}>
            {value}
            {!disabled && (
              <button type="button" className="chip-x" onClick={() => onChange(values.filter((item) => item !== value))} aria-label={`Remove ${value}`}>
                ×
              </button>
            )}
          </span>
        ))}
      </div>
      {!disabled && (
        <input
          className="adder"
          value={text}
          placeholder={placeholder}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key !== "Enter") return;
            event.preventDefault();
            const next = text.trim();
            if (!next || values.some((item) => item.toLowerCase() === next.toLowerCase())) return;
            onChange([...values, next]);
            setText("");
          }}
        />
      )}
    </div>
  );
}

function RubricEditor({
  criterion,
  disabled,
  onChange,
  onRemove,
}: {
  criterion: RubricCriterion;
  disabled: boolean;
  onChange: (criterion: RubricCriterion) => void;
  onRemove?: () => void;
}) {
  return (
    <div className="rubric-row">
      <input value={criterion.name} disabled={disabled} onChange={(event) => onChange({ ...criterion, name: event.target.value })} />
      <textarea
        value={criterion.description}
        disabled={disabled}
        onChange={(event) => onChange({ ...criterion, description: event.target.value })}
      />
      <div className="rubric-meta">
        <label>
          Weight
          <input
            type="number"
            min={1}
            value={criterion.weight}
            disabled={disabled}
            onChange={(event) => onChange({ ...criterion, weight: Number(event.target.value) || 1 })}
          />
        </label>
        {!disabled && onRemove && (
          <button type="button" className="text-btn" onClick={onRemove}>
            Remove
          </button>
        )}
      </div>
    </div>
  );
}

function ResultsPanel(props: {
  query: string;
  setQuery: (value: string) => void;
  session: Session | null;
  cards: Card[];
  frozen: boolean;
  busy: boolean;
  activity: Activity | null;
  error: ApiError | null;
  marks: Record<string, "accept" | "reject">;
  message: string;
  setMessage: (value: string) => void;
  onToggle: (profileId: string, verdict: "accept" | "reject") => void;
  onFreeze: () => void;
  onRetry: () => void;
  onRefine: () => void;
  onOpen: (profile: Profile) => void;
}) {
  const { session, cards, frozen, busy, activity, error, onFreeze, onRetry } = props;
  const count = cards.length;
  const firstSearch = activity === "search" && !session;
  return (
    <section className="panel results-panel">
      <div className="results-head">
        <div className="results-copy">
          <div className="title-row">
            <h1>{frozen ? "Frozen shortlist" : "Top matches"}</h1>
            {session && (
              <span className="count-pill">
                {count} candidate{count === 1 ? "" : "s"}
              </span>
            )}
          </div>
          <p className="meta">
            {session
              ? `${session.filtered_count} passed filters · ranked by relevance${session.revision > 0 ? ` · revision ${session.revision}` : ""}`
              : "Candidates ranked by relevance to your search."}
          </p>
        </div>
        {session && !frozen && (
          <div className="header-controls">
            <label className="sort-box">
              Sort by
              <select defaultValue="best" aria-label="Sort by">
                <option value="best">Best match</option>
              </select>
            </label>
            <button className="freeze-btn" onClick={onFreeze} disabled={busy}>
              <Icon d="M12 2l2 6 6 2-6 2-2 6-2-6-6-2 6-2 2-6z" />
              Freeze search
            </button>
          </div>
        )}
      </div>
      {activity && <WorkingState activity={activity} keepPrevious={Boolean(session)} />}
      <div className={activity && session ? "dimmed" : undefined}>
      {error && <ErrorBanner error={error} onRetry={onRetry} />}
      {firstSearch ? null : !session ? (
        <div className="stack">
          <div className="empty">
            <strong>Run a search to see ranked profiles.</strong>
            <p>Pick a brief or edit the one on the left. Filters and the fit rubric show up with the first results.</p>
          </div>
          {EXAMPLES.map((example) => (
            <button
              key={example.title}
              type="button"
              className={`example ${props.query === example.query ? "on" : ""}`}
              onClick={() => props.setQuery(example.query)}
            >
              <strong>{example.title}</strong>
              <span>{example.detail}</span>
            </button>
          ))}
        </div>
      ) : session.filtered_count === 0 ? (
        <div className="empty">
          <strong>No profiles passed these filters.</strong>
          <p>Loosen a skill, the year range, or the location, then update the results.</p>
        </div>
      ) : cards.length === 0 ? (
        <div className="empty">
          <strong>Nobody could be cited from the profile fields.</strong>
          <p>Retry the scoring step, or loosen the rubric and update the results.</p>
        </div>
      ) : (
        <div className="candidate-list">
          {cards.map((card) => (
            <CandidateCard
              key={card.profile.id}
              card={card}
              required={session.search_spec.filters.required_skills}
              companyTypes={session.search_spec.filters.company_types}
              frozen={frozen}
              busy={busy}
              mark={props.marks[card.profile.id]}
              onToggle={props.onToggle}
              onOpen={props.onOpen}
            />
          ))}
        </div>
      )}
      {session && session.changes.length > 0 && <ChangeList changes={session.changes} />}
      {session && !frozen && (
        <div className="feedback">
          <textarea
            value={props.message}
            placeholder='Tell the search what to change. Example: "1 is too junior, 2 and 4 are right."'
            disabled={busy}
            onChange={(event) => props.setMessage(event.target.value)}
            onKeyDown={(event) => {
              if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                event.preventDefault();
                props.onRefine();
              }
            }}
          />
          <button className="primary-btn" onClick={props.onRefine} disabled={busy}>
            Refine search
          </button>
        </div>
      )}
      </div>
    </section>
  );
}

function WorkingState({ activity, keepPrevious }: { activity: Activity; keepPrevious: boolean }) {
  const copy = ACTIVITY_COPY[activity];
  const [index, setIndex] = useState(0);

  useEffect(() => {
    setIndex(0);
    if (copy.steps.length < 2) return;
    const timer = window.setInterval(() => {
      setIndex((current) => (current + 1) % copy.steps.length);
    }, 2600);
    return () => window.clearInterval(timer);
  }, [activity, copy.steps.length]);

  return (
    <div className="working" role="status" aria-live="polite">
      <span className="spinner" />
      <p className="working-kicker">Hold on</p>
      <p className="working-line">{copy.headline}</p>
      <p className="working-step" key={copy.steps[index]}>
        {copy.steps[index]}
      </p>
      <div className="working-dots" aria-hidden="true">
        {copy.steps.map((step, position) => (
          <span key={step} className={position === index ? "on" : position < index ? "done" : ""} />
        ))}
      </div>
      <p className="working-note">
        {keepPrevious
          ? "Your current shortlist stays here until this finishes."
          : "This usually takes a moment. The shortlist will appear here."}
      </p>
    </div>
  );
}

function CandidateCard({
  card,
  required,
  companyTypes,
  frozen,
  busy,
  mark,
  onToggle,
  onOpen,
}: {
  card: Card;
  required: string[];
  companyTypes: string[];
  frozen: boolean;
  busy: boolean;
  mark?: "accept" | "reject";
  onToggle: (profileId: string, verdict: "accept" | "reject") => void;
  onOpen: (profile: Profile) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const profile = card.profile;
  const chips = [
    ...profile.skills.map((skill) => ({
      label: skill,
      tone: skillMatches(skill, required) ? "hot" : "green",
    })),
  ];
  if (companyTypes.some((type) => type.toLowerCase() === profile.current_company_type.toLowerCase())) {
    chips.splice(1, 0, { label: profile.current_company_type, tone: "hot" });
  }
  const visible = expanded ? chips : chips.slice(0, 5);
  const hidden = chips.length - visible.length;

  return (
    <article className="candidate">
      <div className="candidate-top">
        <div className="person">
          <div className="rank">{card.position}</div>
          <div className="person-avatar">{initials(profile.name)}</div>
          <div>
            <h3>
              {profile.name}
              {mark === "accept" && <span className="saved-pill">Shortlisted</span>}
            </h3>
            <p>
              {profile.current_title} · {profile.current_company} · {profile.location} · {profile.years_experience} yrs ·{" "}
              {profile.current_company_type}
            </p>
          </div>
        </div>
        <div className="score-col">
          <div className="score">{card.score}</div>
          <div className="score-label">Fit score</div>
          <div className="fit-note">
            <i />
            {fitLabel(card.score)}
          </div>
        </div>
      </div>
      <div className="skill-row">
        {visible.map((chip) => (
          <span className={`chip ${chip.tone}`} key={`${chip.tone}-${chip.label}`}>
            {chip.label}
          </span>
        ))}
        {hidden > 0 && (
          <button type="button" className="chip more" onClick={() => setExpanded(true)}>
            +{hidden} more
          </button>
        )}
      </div>
      <p className="why">{card.reason}</p>
      {card.concern && <p className="concern">{card.concern}</p>}
      <div className="card-actions">
        <button type="button" className="view-btn" onClick={() => onOpen(profile)}>
          View profile
        </button>
        {!frozen && (
          <>
            <button
              type="button"
              className={`reject-btn ${mark === "reject" ? "on" : ""}`}
              disabled={busy}
              onClick={() => onToggle(profile.id, "reject")}
            >
              Reject
            </button>
            <button
              type="button"
              className={`match-btn ${mark === "accept" ? "on" : ""}`}
              disabled={busy}
              aria-pressed={mark === "accept"}
              onClick={() => onToggle(profile.id, "accept")}
            >
              <Icon d="M4 12l5 5L20 6" />
              {mark === "accept" ? "Shortlisted" : "Match"}
            </button>
          </>
        )}
      </div>
    </article>
  );
}

function ChangeList({ changes }: { changes: SearchChange[] }) {
  return (
    <div className="stack">
      <p className="field-label">What changed</p>
      {changes.map((change) => (
        <div className="change-card" key={`${change.field}-${formatValue(change.new_value)}`}>
          <strong>{fieldLabel(change.field)}</strong>
          <p>{change.reason}</p>
          <div className="delta">
            <span className="from">{formatValue(change.old_value)}</span>
            <span>→</span>
            <span className="to">{formatValue(change.new_value)}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function ErrorBanner({ error, onRetry }: { error: ApiError; onRetry: () => void }) {
  return (
    <div className="error-banner">
      <div>
        <strong>{error.code.replaceAll("_", " ")}</strong>
        <p>{error.message}</p>
      </div>
      {error.retryable && (
        <button className="ghost-btn" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}

function SecondaryView({
  view,
  session,
  shortlisted,
  onOpen,
  onSearch,
}: {
  view: View;
  session: Session | null;
  shortlisted: Card[];
  onOpen: (profile: Profile) => void;
  onSearch: () => void;
}) {
  if (view === "shortlist") {
    return (
      <main className="simple-page">
        <section className="panel">
          <div className="title-row">
            <h1>Shortlisted</h1>
            <span className="count-pill">{shortlisted.length}</span>
          </div>
          <p className="meta">Candidates you marked as a match on this search.</p>
          {shortlisted.length === 0 ? (
            <div className="empty">
              <strong>No one is shortlisted yet.</strong>
              <p>Open Search and choose Match on the profiles you want to keep.</p>
              <button className="primary-btn" style={{ marginTop: 12 }} onClick={onSearch}>
                Back to search
              </button>
            </div>
          ) : (
            <div className="candidate-list">
              {shortlisted.map((card) => (
                <CandidateCard
                  key={card.profile.id}
                  card={card}
                  required={session?.search_spec.filters.required_skills ?? []}
                  companyTypes={session?.search_spec.filters.company_types ?? []}
                  frozen
                  busy={false}
                  mark="accept"
                  onToggle={() => undefined}
                  onOpen={onOpen}
                />
              ))}
            </div>
          )}
        </section>
      </main>
    );
  }

  if (view === "messages") {
    return (
      <main className="simple-page">
        <section className="panel">
          <h1>Messages</h1>
          <div className="empty">
            <strong>No messages yet.</strong>
            <p>Feedback you send with Refine search stays on the search, next to the shortlist.</p>
          </div>
        </section>
      </main>
    );
  }

  const top = session?.visible[0]?.score ?? session?.ranked[0]?.score;
  return (
    <main className="simple-page">
      <section className="panel">
        <h1>Analytics</h1>
        <p className="meta">Counts from the current search.</p>
      </section>
      <div className="stat-grid">
        <article className="panel stat">
          <span>Profiles considered</span>
          <strong>{session ? session.pool_size : "—"}</strong>
        </article>
        <article className="panel stat">
          <span>Passed filters</span>
          <strong>{session ? session.filtered_count : "—"}</strong>
        </article>
        <article className="panel stat">
          <span>On the shortlist</span>
          <strong>{session ? (session.status === "frozen" ? session.ranked_count : session.visible.length) : "—"}</strong>
        </article>
        <article className="panel stat">
          <span>Top fit score</span>
          <strong>{top ?? "—"}</strong>
        </article>
      </div>
    </main>
  );
}

function ProfileDialog({ profile, onClose }: { profile: Profile; onClose: () => void }) {
  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="profile-title" onClick={(event) => event.stopPropagation()}>
        <header>
          <div className="person">
            <div className="person-avatar">{initials(profile.name)}</div>
            <div>
              <h2 id="profile-title">{profile.name}</h2>
              <p className="meta">
                {profile.current_title} · {profile.current_company} · {profile.location}
              </p>
            </div>
          </div>
          <button type="button" className="close" onClick={onClose} aria-label="Close profile">
            ×
          </button>
        </header>
        <dl>
          <div>
            <dt>Experience</dt>
            <dd>
              {profile.years_experience} years · {profile.current_company_type}
            </dd>
          </div>
          <div>
            <dt>Education</dt>
            <dd>{profile.education}</dd>
          </div>
          <div>
            <dt>Skills</dt>
            <dd>{profile.skills.join(", ")}</dd>
          </div>
          <div>
            <dt>Summary</dt>
            <dd>{profile.summary}</dd>
          </div>
        </dl>
      </div>
    </div>
  );
}
