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
        if primary in text or any(s in text for s in synonyms):
            expanded.add(primary)
            expanded.update(synonyms)

    return list(expanded)


def score_candidate(candidate: dict, jd_keywords: list[str], kw_set: set[str], weights: dict,
                    today: date, jd_lower: str, exp_req: int, target_cities: list[str], total_w: float) -> dict:
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
                if sk_name_lower in kw or kw in sk_name_lower:
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
                if normalize(ak) in sk_name_lower or sk_name_lower in normalize(ak):
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

        # Title relevance
        title_rel = sum(1 for kw in jd_keywords if kw in job_title) / max(len(jd_keywords), 1)
        # Description relevance
        desc_kw_hits = sum(1 for kw in jd_keywords if kw in job_desc)
        desc_rel = min(desc_kw_hits / 10.0, 1.0)
        # Industry relevance
        ind_rel = sum(1 for kw in jd_keywords if kw in job_industry) / max(len(jd_keywords), 1)

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

            deg_w = max(DEGREE_WEIGHT.get(k, 0) for k in DEGREE_WEIGHT if k in degree) if any(k in degree for k in DEGREE_WEIGHT) else 0.3
            tier_w = EDU_TIER_WEIGHT.get(tier, 0.2)

            # Field relevance to JD
            field_rel = sum(1 for kw in jd_keywords if kw in field) / max(len(jd_keywords), 1)
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
    last_active_str = signals.get("last_active_date", "2020-01-01")
    try:
        last_active = date.fromisoformat(last_active_str)
        days_inactive = (today - last_active).days
        activity_score = max(0, 1.0 - days_inactive / 365.0)
    except Exception:
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
            if city in cand_loc or syn in cand_loc:
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

    # Build human-readable reasoning
    reasons = []
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

    return {
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
        "career_history": career,
        "signals": {
            "open_to_work": signals.get("open_to_work_flag", False),
            "notice_period_days": signals.get("notice_period_days", 0),
            "profile_completeness": signals.get("profile_completeness_score", 0),
            "github_activity_score": signals.get("github_activity_score", -1),
            "recruiter_response_rate": signals.get("recruiter_response_rate", 0),
            "last_active_date": signals.get("last_active_date", ""),
            "expected_salary_range_inr_lpa": signals.get("expected_salary_range_inr_lpa", {}),
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
