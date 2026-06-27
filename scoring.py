import os
import json
import re
import math
from datetime import date

# Decouple configuration from logic: load from data/config.json on startup
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "data", "config.json")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    _config = json.load(f)

DOMAIN_SYNONYMS = _config["domain_synonyms"]
PROFICIENCY_WEIGHT = _config["proficiency_weight"]
EDU_TIER_WEIGHT = _config["edu_tier_weight"]
DEGREE_WEIGHT = _config["degree_weight"]
CITY_SYNONYMS = _config["city_synonyms"]

DEGREE_PATTERNS = {
    k: re.compile(r'\b' + re.escape(k) + r'\b') for k in DEGREE_WEIGHT
}

# ── Consistency / honeypot-detection thresholds ─────────────────────────────
# The challenge dataset includes ~80 honeypot candidates with internally
# impossible profiles (e.g. "expert" proficiency claimed with 0 months of
# actual use, or years_of_experience that doesn't square with career_history).
# These thresholds are intentionally conservative (only fire on clear
# contradictions) so we don't accidentally penalize honest candidates with
# slightly messy data entry.
CONSISTENCY_RULES = {
    "expert_min_duration_months": 3,      # "expert"/"advanced" with <= this many months used = suspicious
    "expert_penalty": 0.55,
    "experience_mismatch_ratio": 1.8,     # yoe vs sum(career duration) off by more than this ratio = suspicious
    "experience_mismatch_penalty": 0.55,
    "date_duration_tolerance_months": 6,  # declared duration_months vs (end-start) computed months
    "date_duration_penalty": 0.75,
    "education_timeline_penalty": 0.5,
    "min_multiplier_floor": 0.03,         # never literally zero (keeps tie-break logic sane), but pushes to the bottom
}


def normalize(text: str) -> str:
    return re.sub(r'\s+', ' ', text.lower().strip())


def extract_keywords(jd_text: str) -> list[str]:
    """Extract meaningful keywords from JD with semantic expansion."""
    text = normalize(jd_text)
    # Remove stop words
    stop = {"the", "a", "an", "and", "or", "for", "to", "of", "in", "on",
             "at", "is", "are", "was", "will", "be", "with", "by", "as",
             "that", "this", "we", "you", "your", "our", "their"}
    # Extract words + bigrams
    words = [w for w in re.findall(r"[a-z][a-z0-9\+\#\.\/\-]*", text) if w not in stop and len(w) > 1]
    bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words)-1)]
    raw_kws = list(dict.fromkeys(words + bigrams))

    # Semantic expansion
    expanded = set(raw_kws)
    for primary, synonyms in DOMAIN_SYNONYMS.items():
        if re.search(r'\b' + re.escape(primary) + r'\b', text) or any(re.search(r'\b' + re.escape(s) + r'\b', text) for s in synonyms):
            expanded.add(primary)
            expanded.update(synonyms)

    return list(expanded)


def compute_consistency_signal(candidate: dict, today: date) -> tuple[float, list[str]]:
    """
    Detects internally-inconsistent ("honeypot-style") profiles: claims that
    can't logically be true given the rest of the profile. Returns a
    multiplier in (0, 1] to apply to the final score, plus human-readable
    flags (used in the reasoning column and for your own QA pass before
    submitting). Independent inconsistencies compound rather than capping
    at a single penalty, since a profile with three contradictions is worse
    than one with a single typo.

    This does not special-case the specific honeypots in the dataset; it
    checks for the general patterns the challenge spec calls out (expert
    proficiency with ~0 usage, experience that doesn't square with career
    history) so it should generalize to honeypot variants we haven't seen.
    """
    R = CONSISTENCY_RULES
    profile = candidate.get("profile", {})
    skills = candidate.get("skills", [])
    career = candidate.get("career_history", [])
    education = candidate.get("education", [])

    flags = []
    multiplier = 1.0

    # 1. "Expert"/"advanced" proficiency claimed with almost no hands-on time.
    for sk in skills:
        prof = sk.get("proficiency", "beginner")
        dur = sk.get("duration_months", 0)
        if prof in ("expert", "advanced") and dur <= R["expert_min_duration_months"]:
            flags.append(f"'{prof}' proficiency in {sk.get('name', 'a skill')} with only {dur} month(s) used")
            multiplier *= R["expert_penalty"]

    # 2. Total years_of_experience vs what career_history actually sums to.
    yoe = profile.get("years_of_experience", 0)
    total_career_months = sum(j.get("duration_months", 0) for j in career)
    claimed_months = yoe * 12
    if claimed_months > 0 and total_career_months > 0:
        ratio = max(claimed_months, total_career_months) / max(min(claimed_months, total_career_months), 1)
        if ratio > R["experience_mismatch_ratio"]:
            flags.append(
                f"years_of_experience ({yoe:.1f}) doesn't square with career_history total "
                f"({total_career_months / 12:.1f} yrs)"
            )
            multiplier *= R["experience_mismatch_penalty"]

    # 3. Declared duration_months vs what the start/end dates actually compute to.
    for j in career:
        sd, ed, dm = j.get("start_date"), j.get("end_date"), j.get("duration_months")
        if not sd or dm is None:
            continue
        try:
            start = date.fromisoformat(sd)
            end = date.fromisoformat(ed) if ed else today
            computed_months = (end.year - start.year) * 12 + (end.month - start.month)
            if abs(computed_months - dm) > R["date_duration_tolerance_months"]:
                flags.append(
                    f"{j.get('title', 'a role')} at {j.get('company', '?')}: declared {dm} months "
                    f"but dates imply ~{computed_months}"
                )
                multiplier *= R["date_duration_penalty"]
        except (ValueError, TypeError):
            continue

    # 4. Education timeline that can't be true (graduated before enrolling).
    for edu in education:
        sy, ey = edu.get("start_year"), edu.get("end_year")
        if sy is not None and ey is not None and ey < sy:
            flags.append(f"education end_year ({ey}) before start_year ({sy})")
            multiplier *= R["education_timeline_penalty"]

    multiplier = max(multiplier, R["min_multiplier_floor"])
    return multiplier, flags


def score_candidate(candidate: dict, jd_keywords: list[str], kw_set: set[str], weights: dict,
                    today: date, jd_lower: str, exp_req: int, target_cities: list[str], total_w: float, simple: bool = False) -> dict:
    """
    Multi-signal hybrid scoring (decoupled from weights and city lookups):
    1. Skills match (semantic + proficiency + endorsements + duration)
    2. Career trajectory (title match, industry relevance, progression)
    3. Experience fit (years, seniority)
    4. Education signal
    5. Behavioral signals (responsiveness, activity, platform trust)
    6. Availability & practicality
    """
    profile = candidate["profile"]
    signals = candidate.get("redrob_signals", {})
    skills = candidate.get("skills", [])
    career = candidate.get("career_history", [])
    education = candidate.get("education", [])

    # ── 1. Skills Score ──────────────────────────────────────────────────────
    skill_scores = []
    matched_skills = []
    noise_skills = {"looking", "expertise", "engineer", "engineering", "software", "developer", "with", "for", "role", "need", "want", "required", "years", "experience", "and", "in"}
    for sk in skills:
        sk_name_lower = sk["name_norm"]
        # Direct or semantic match
        match_strength = 0.0
        if sk_name_lower in kw_set:
            if sk_name_lower not in noise_skills:
                match_strength = 1.0
        else:
            for kw in jd_keywords:
                if kw in noise_skills:
                    continue
                # Boundary-safe match
                if (sk_name_lower in kw or kw in sk_name_lower) and (re.search(r'\b' + re.escape(sk_name_lower) + r'\b', kw) or re.search(r'\b' + re.escape(kw) + r'\b', sk_name_lower)):
                    match_strength = 0.7
                    break

        if match_strength > 0:
            prof = PROFICIENCY_WEIGHT.get(sk.get("proficiency", "beginner"), 0.25)
            # Endorsement signal (diminishing returns after 30)
            endorse_score = math.log1p(min(sk.get("endorsements", 0), 50)) / math.log1p(50)
            # Duration signal
            dur_months = sk.get("duration_months", 0)
            dur_score = min(dur_months / 48.0, 1.0)
            # Assessment score bonus if available
            assessment_bonus = 0.0
            assessment_scores = signals.get("skill_assessment_scores", {})
            for ak, av in assessment_scores.items():
                ak_norm = normalize(ak)
                if (ak_norm in sk_name_lower or sk_name_lower in ak_norm) and (re.search(r'\b' + re.escape(ak_norm) + r'\b', sk_name_lower) or re.search(r'\b' + re.escape(sk_name_lower) + r'\b', ak_norm)):
                    assessment_bonus = (av / 100.0) * 0.3
                    break
            sk_total = match_strength * (
                0.40 * prof + 0.25 * endorse_score + 0.20 * dur_score + 0.15
            ) + assessment_bonus
            skill_scores.append(sk_total)
            matched_skills.append(sk["name"])

    skills_score = min(sum(skill_scores), 3.0) / 3.0 if skill_scores else 0.0

    # ── 2. Career Trajectory Score ───────────────────────────────────────────
    career_score = 0.0
    for job in career:
        job_title = job["title_norm"]
        job_desc = job["description_norm"]
        job_industry = job["industry_norm"]
        job_months = job.get("duration_months", 0)

        # Title relevance: O(1) set lookup with O(N) regex fallback
        if "title_tokens" in job:
            title_rel = sum(1 for kw in jd_keywords if kw in job["title_tokens"]) / max(len(jd_keywords), 1)
        else:
            title_rel = sum(1 for kw in jd_keywords if (kw in job_title) and re.search(r'\b' + re.escape(kw) + r'\b', job_title)) / max(len(jd_keywords), 1)

        # Description relevance
        if "desc_tokens" in job:
            desc_kw_hits = sum(1 for kw in jd_keywords if kw in job["desc_tokens"])
        else:
            desc_kw_hits = sum(1 for kw in jd_keywords if (kw in job_desc) and re.search(r'\b' + re.escape(kw) + r'\b', job_desc))
        desc_rel = min(desc_kw_hits / 10.0, 1.0)

        # Industry relevance
        if "industry_tokens" in job:
            ind_rel = sum(1 for kw in jd_keywords if kw in job["industry_tokens"]) / max(len(jd_keywords), 1)
        else:
            ind_rel = sum(1 for kw in jd_keywords if (kw in job_industry) and re.search(r'\b' + re.escape(kw) + r'\b', job_industry)) / max(len(jd_keywords), 1)

        job_rel = 0.5 * desc_rel + 0.35 * title_rel + 0.15 * ind_rel
        if job.get("is_current"):
            job_rel *= 1.2  # Recency bonus

        # Company size signal
        size = job.get("company_size", "")
        size_bonus = {"10001+": 0.1, "5001-10000": 0.08, "1001-5000": 0.06,
                      "501-1000": 0.04, "201-500": 0.02}.get(size, 0)
        job_rel += size_bonus

        career_score += job_rel * min(job_months / 60.0, 1.0)

    career_score = min(career_score / len(career), 1.0) if career else 0.0

    # ── 3. Experience Fit ────────────────────────────────────────────────────
    yoe = profile.get("years_of_experience", 0)
    if exp_req > 0:
        if yoe < exp_req * 0.5:
            exp_score = 0.2
        elif yoe < exp_req:
            exp_score = 0.5 + 0.5 * (yoe / exp_req)
        elif yoe <= exp_req * 2.5:
            exp_score = 1.0
        else:
            exp_score = max(0.6, 1.0 - (yoe - exp_req * 2.5) * 0.02)
    else:
        # No explicit requirement: reward moderate-to-high experience
        if yoe < 1:
            exp_score = 0.3
        elif yoe < 3:
            exp_score = 0.6
        elif yoe < 7:
            exp_score = 0.85
        elif yoe < 12:
            exp_score = 1.0
        else:
            exp_score = 0.9

    # ── 4. Education Score ───────────────────────────────────────────────────
    edu_score = 0.0
    if education:
        best_edu = 0.0
        for edu in education:
            degree = edu["degree_norm"]
            tier = edu.get("tier", "unknown")
            field = edu["field_norm"]

            deg_w = max((DEGREE_WEIGHT[k] for k, pattern in DEGREE_PATTERNS.items() if k in degree and pattern.search(degree)), default=0.3)
            tier_w = EDU_TIER_WEIGHT.get(tier, 0.2)

            # Field relevance to JD
            field_rel = sum(1 for kw in jd_keywords if kw in field and re.search(r'\b' + re.escape(kw) + r'\b', field)) / max(len(jd_keywords), 1)
            field_rel = min(field_rel * 20, 1.0)  # Amplify

            edu_val = 0.5 * deg_w + 0.3 * tier_w + 0.2 * field_rel
            best_edu = max(best_edu, edu_val)
        edu_score = best_edu
    else:
        edu_score = 0.1

    # ── 5. Behavioral / Platform Signals ────────────────────────────────────
    # Responsiveness
    resp_rate = signals.get("recruiter_response_rate", 0)
    avg_resp_hours = signals.get("avg_response_time_hours", 999)
    resp_time_score = max(0, 1.0 - avg_resp_hours / 200.0)
    responsiveness = 0.6 * resp_rate + 0.4 * resp_time_score

    # Engagement / activity
    last_active = signals.get("last_active_date_obj")
    if not last_active:
        last_active_str = signals.get("last_active_date", "2020-01-01")
        try:
            last_active = date.fromisoformat(last_active_str)
        except Exception:
            last_active = None
    if last_active:
        days_inactive = (today - last_active).days
        activity_score = max(0, 1.0 - days_inactive / 365.0)
    else:
        activity_score = 0.0

    # Profile quality
    completeness = signals.get("profile_completeness_score", 50) / 100.0
    github_score = signals.get("github_activity_score", -1)
    github_signal = max(github_score, 0) / 100.0 if github_score >= 0 else 0.0
    verified = (
        (0.4 if signals.get("verified_email") else 0) +
        (0.4 if signals.get("verified_phone") else 0) +
        (0.2 if signals.get("linkedin_connected") else 0)
    )

    # Interview & offer quality
    icr = signals.get("interview_completion_rate", 0.5)
    oar = max(signals.get("offer_acceptance_rate", 0), 0)  # -1 = no history

    # Platform popularity signals
    saves_30d = min(signals.get("saved_by_recruiters_30d", 0), 30) / 30.0
    search_30d = min(signals.get("search_appearance_30d", 0), 500) / 500.0

    behavioral_score = (
        0.25 * responsiveness +
        0.20 * activity_score +
        0.15 * completeness +
        0.10 * github_signal +
        0.10 * verified +
        0.10 * icr +
        0.05 * oar +
        0.05 * saves_30d
    )

    # ── 6. Availability / Practicality ───────────────────────────────────────
    open_to_work = 1.0 if signals.get("open_to_work_flag") else 0.3
    notice_days = signals.get("notice_period_days", 90)
    notice_score = max(0, 1.0 - notice_days / 180.0)
    applications_30d = min(signals.get("applications_submitted_30d", 0), 10) / 10.0  # active seeker signal

    availability_score = 0.50 * open_to_work + 0.35 * notice_score + 0.15 * applications_30d

    # ── Weighted Composite ───────────────────────────────────────────────────
    w = weights
    raw_score = (
        w["skills"] * skills_score +
        w["career"] * career_score +
        w["experience"] * exp_score +
        w["education"] * edu_score +
        w["behavioral"] * behavioral_score +
        w["availability"] * availability_score
    )

    # Normalise to 0-1
    final_score = min(raw_score / total_w, 1.0)

    # Location constraint matching (target_cities passed dynamically)
    location_multiplier = 1.0
    outside_reason = None
    if target_cities:
        cand_loc = profile["location_norm"]
        matched_location = False
        
        for city in target_cities:
            syn = CITY_SYNONYMS.get(city, city)
            # Match normalized candidate location with normalized target city (or its resolved synonym)
            if (city in cand_loc or syn in cand_loc) and (re.search(r'\b' + re.escape(city) + r'\b', cand_loc) or re.search(r'\b' + re.escape(syn) + r'\b', cand_loc)):
                matched_location = True
                break
        
        if not matched_location:
            if signals.get("willing_to_relocate"):
                location_multiplier = 0.5
                outside_reason = "Outside requested location (willing to relocate)"
            else:
                location_multiplier = 0.05
                outside_reason = "Outside requested location"

    final_score *= location_multiplier

    # Consistency / honeypot check — applied after location so an inconsistent
    # profile can't escape the penalty by also being in the right city.
    consistency_multiplier, consistency_flags = compute_consistency_signal(candidate, today)
    final_score *= consistency_multiplier

    # Build human-readable reasoning
    reasons = []
    if consistency_flags:
        first = consistency_flags[0]
        extra = f" (+{len(consistency_flags) - 1} more)" if len(consistency_flags) > 1 else ""
        reasons.append(f"Profile inconsistency: {first}{extra}")
    if outside_reason:
        reasons.append(outside_reason)
    if matched_skills:
        reasons.append(f"{len(matched_skills)} matching skill{'s' if len(matched_skills)>1 else ''}: {', '.join(matched_skills[:4])}")
    if profile.get("years_of_experience"):
        reasons.append(f"{yoe:.1f} yrs experience")
    if signals.get("recruiter_response_rate", 0) > 0.5:
        reasons.append(f"High recruiter response rate ({resp_rate:.0%})")
    if signals.get("open_to_work_flag"):
        reasons.append("Open to work")
    if github_score > 50:
        reasons.append(f"Strong GitHub activity (score {github_score:.0f})")
    if not reasons:
        reasons.append("General profile match")

    result = {
        "candidate_id": candidate["candidate_id"],
        "score": round(final_score, 4),
        "component_scores": {
            "skills": round(skills_score, 3),
            "career": round(career_score, 3),
            "experience": round(exp_score, 3),
            "education": round(edu_score, 3),
            "behavioral": round(behavioral_score, 3),
            "availability": round(availability_score, 3),
        },
        "matched_skills": matched_skills[:8],
        "reasoning": "; ".join(reasons),
        "consistency_flags": consistency_flags,
    }

    if simple:
        return result

    return inflate_candidate(candidate, result)


def inflate_candidate(candidate: dict, score_result: dict) -> dict:
    profile = candidate["profile"]
    signals = candidate.get("redrob_signals", {})
    skills = candidate.get("skills", [])
    career = candidate.get("career_history", [])
    education = candidate.get("education", [])
    yoe = profile.get("years_of_experience", 0)

    salRange = signals.get("expected_salary_range_inr_lpa", {})

    return {
        "candidate_id": score_result["candidate_id"],
        "score": score_result["score"],
        "component_scores": score_result["component_scores"],
        "matched_skills": score_result["matched_skills"],
        "reasoning": score_result["reasoning"],
        "consistency_flags": score_result.get("consistency_flags", []),
        "profile": {
            "name": profile.get("anonymized_name", "Unknown"),
            "headline": profile.get("headline", ""),
            "summary": profile.get("summary", ""),
            "location": profile.get("location", ""),
            "country": profile.get("country", ""),
            "years_of_experience": yoe,
            "current_title": profile.get("current_title", ""),
            "current_company": profile.get("current_company", ""),
            "current_company_size": profile.get("current_company_size", ""),
            "current_industry": profile.get("current_industry", ""),
        },
        "skills": skills[:12],
        "education": education,
        "certifications": candidate.get("certifications", []),
        "career_history": [
            {k: v for k, v in job.items() if not k.endswith("_tokens")}
            for job in career
        ],
        "signals": {
            "open_to_work": signals.get("open_to_work_flag", False),
            "notice_period_days": signals.get("notice_period_days", 0),
            "profile_completeness": signals.get("profile_completeness_score", 0),
            "github_activity_score": signals.get("github_activity_score", -1),
            "recruiter_response_rate": signals.get("recruiter_response_rate", 0),
            "last_active_date": signals.get("last_active_date", ""),
            "expected_salary_range_inr_lpa": salRange,
            "preferred_work_mode": signals.get("preferred_work_mode", ""),
            "willing_to_relocate": signals.get("willing_to_relocate", False),
            "verified_email": signals.get("verified_email", False),
            "verified_phone": signals.get("verified_phone", False),
            "linkedin_connected": signals.get("linkedin_connected", False),
            "connection_count": signals.get("connection_count", 0),
            "interview_completion_rate": signals.get("interview_completion_rate", 0),
            "offer_acceptance_rate": signals.get("offer_acceptance_rate", -1),
            "saved_by_recruiters_30d": signals.get("saved_by_recruiters_30d", 0),
            "search_appearance_30d": signals.get("search_appearance_30d", 0),
        }
    }