export type CompanyHistory = "current" | "past" | "any";
export type SkillMatch = "all" | "any";

export interface RubricCriterion {
  id: string;
  name: string;
  description: string;
  weight: number;
}

export interface SearchSpec {
  filters: {
    required_skills: string[];
    min_years: number | null;
    max_years: number | null;
    locations: string[];
    company_types: string[];
    company_history: CompanyHistory;
    skill_match: SkillMatch;
  };
  rubric: {
    criteria: RubricCriterion[];
  };
}

export interface Profile {
  id: string;
  name: string;
  current_title: string;
  years_experience: number;
  location: string;
  current_company: string;
  current_company_type: string;
  skills: string[];
  education: string;
  summary: string;
}

export interface Card {
  position: number;
  profile: Profile;
  score: number;
  citations: { field: string; quote: string }[];
  reason: string;
  concern: string | null;
}

export interface SearchChange {
  change_type: "filter" | "rubric";
  field: string;
  old_value: unknown;
  new_value: unknown;
  reason: string;
}

export interface Session {
  session_id: string;
  status: "active" | "frozen";
  original_query: string;
  revision: number;
  search_spec: SearchSpec;
  filtered_count: number;
  ranked_count: number;
  pool_size: number;
  visible: Card[];
  ranked: Card[];
  changes: SearchChange[];
}
