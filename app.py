#!/usr/bin/env python3
"""
RedrankAI — Intelligent Candidate Ranking System
Backend: Flask + API Routes (Optimized & Thread-Safe)
"""

import json
import os
import re
import time
import threading
from datetime import date
from flask import Flask, request, jsonify, send_from_directory

# Import scoring helper routines from our modular engine
from scoring import extract_keywords, score_candidate, normalize

# Load config settings from data/config.json
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "data", "config.json")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    _config = json.load(f)

DEFAULT_WEIGHTS = _config["default_weights"]

app = Flask(__name__, static_folder='static', static_url_path='')

# ──────────────────────────────────────────────────────────────────────────────
# Global state
# ──────────────────────────────────────────────────────────────────────────────
CANDIDATES = []
ALL_CITIES = set()
CANDIDATES_MAP = {}
CANDIDATES_LOCK = threading.Lock()
DATA_LOADED = False
LOAD_PROGRESS = {"loaded": 0, "total": 0, "done": False}

# Candidates data path in the new grouped folder
DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "candidates.jsonl")

# ──────────────────────────────────────────────────────────────────────────────
# Background data loader
# ──────────────────────────────────────────────────────────────────────────────
def load_data_background():
    global DATA_LOADED, CANDIDATES, ALL_CITIES, CANDIDATES_MAP
    try:
        tmp_cities = set()
        tmp_map = {}
        
        # Helper to extract tokens for fast boundary-safe O(1) set lookup
        def get_tokens(text):
            words = re.findall(r"[a-z][a-z0-9\+\#\.\/\-]*", text)
            bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words)-1)]
            return set(words + bigrams)

        if os.path.exists(DATA_PATH):
            print(f"[RedrankAI] Loading main database from {DATA_PATH}...")
            LOAD_PROGRESS["total"] = 100000

            tmp = []
            with open(DATA_PATH, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    line = line.strip()
                    if line:
                        try:
                            c = json.loads(line)
                            
                            # Pre-normalize skills
                            for sk in c.get("skills", []):
                                sk["name_norm"] = normalize(sk.get("name", ""))
                            # Pre-normalize and pre-tokenize career history
                            for job in c.get("career_history", []):
                                job["title_norm"] = tn = normalize(job.get("title", ""))
                                job["description_norm"] = dn = normalize(job.get("description", ""))
                                job["industry_norm"] = in_ = normalize(job.get("industry", ""))
                                job["title_tokens"] = get_tokens(tn)
                                job["desc_tokens"] = get_tokens(dn)
                                job["industry_tokens"] = get_tokens(in_)
                            # Pre-normalize education
                            for edu in c.get("education", []):
                                edu["degree_norm"] = normalize(edu.get("degree", ""))
                                edu["field_norm"] = normalize(edu.get("field_of_study", ""))
                            # Pre-normalize location
                            profile = c.get("profile", {})
                            loc_norm = normalize(profile.get("location", ""))
                            profile["location_norm"] = loc_norm
                            if loc_norm:
                                parts = [p.strip() for p in loc_norm.split(",")]
                                if parts and parts[0]:
                                    tmp_cities.add(parts[0])
                            
                            # Pre-parse last active date to save loop time
                            sig = c.get("redrob_signals", {})
                            last_active_str = sig.get("last_active_date")
                            if last_active_str:
                                try:
                                    sig["last_active_date_obj"] = date.fromisoformat(last_active_str)
                                except Exception:
                                    pass

                            tmp.append(c)
                            tmp_map[c["candidate_id"]] = c
                        except Exception:
                            pass
                        LOAD_PROGRESS["loaded"] = i + 1
        else:
            fallback_path = os.path.join(os.path.dirname(__file__), "data", "sample_candidates.json")
            print(f"[RedrankAI] Main database not found. Loading fallback sample from {fallback_path}...")
            if os.path.exists(fallback_path):
                with open(fallback_path, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                
                # Pre-normalize fallback candidates
                for c in raw_data:
                    for sk in c.get("skills", []):
                        sk["name_norm"] = normalize(sk.get("name", ""))
                    for job in c.get("career_history", []):
                        job["title_norm"] = tn = normalize(job.get("title", ""))
                        job["description_norm"] = dn = normalize(job.get("description", ""))
                        job["industry_norm"] = in_ = normalize(job.get("industry", ""))
                        job["title_tokens"] = get_tokens(tn)
                        job["desc_tokens"] = get_tokens(dn)
                        job["industry_tokens"] = get_tokens(in_)
                    for edu in c.get("education", []):
                        edu["degree_norm"] = normalize(edu.get("degree", ""))
                        edu["field_norm"] = normalize(edu.get("field_of_study", ""))
                    profile = c.get("profile", {})
                    loc_norm = normalize(profile.get("location", ""))
                    profile["location_norm"] = loc_norm
                    if loc_norm:
                         parts = [p.strip() for p in loc_norm.split(",")]
                         if parts and parts[0]:
                             tmp_cities.add(parts[0])
                    
                    # Pre-parse last active date to save loop time
                    sig = c.get("redrob_signals", {})
                    last_active_str = sig.get("last_active_date")
                    if last_active_str:
                        try:
                            sig["last_active_date_obj"] = date.fromisoformat(last_active_str)
                        except Exception:
                            pass
                    
                    tmp_map[c["candidate_id"]] = c
                
                tmp = raw_data
                LOAD_PROGRESS["total"] = len(tmp)
                LOAD_PROGRESS["loaded"] = len(tmp)
            else:
                raise FileNotFoundError("Neither data/candidates.jsonl nor data/sample_candidates.json found.")

        with CANDIDATES_LOCK:
            CANDIDATES = tmp
            ALL_CITIES = tmp_cities
            CANDIDATES_MAP = tmp_map
        DATA_LOADED = True
        LOAD_PROGRESS["done"] = True
        print(f"[RedrankAI] Loaded {len(CANDIDATES):,} candidates (found {len(ALL_CITIES)} unique cities)")
    except Exception as e:
        print(f"[RedrankAI] Load error: {e}")
        LOAD_PROGRESS["done"] = True


# Start loading in background
loader_thread = threading.Thread(target=load_data_background, daemon=True)
loader_thread.start()

# ──────────────────────────────────────────────────────────────────────────────
# API Routes
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/status")
def api_status():
    return jsonify({
        "loaded": DATA_LOADED,
        "progress": LOAD_PROGRESS,
        "candidate_count": len(CANDIDATES),
    })


@app.route("/api/rank", methods=["POST"])
def api_rank():
    data = request.get_json(force=True)
    jd_text = data.get("job_description", "").strip()
    top_n = min(int(data.get("top_n", 20)), 100)
    filters = data.get("filters", {})
    weights_override = data.get("weights", {})

    if not jd_text:
        return jsonify({"error": "job_description is required"}), 400

    if not DATA_LOADED and len(CANDIDATES) < 1000:
        return jsonify({"error": "Data still loading, please wait"}), 503

    # Default weights loaded dynamically
    weights = DEFAULT_WEIGHTS.copy()
    weights.update(weights_override)

    # 1. Precompute query constants outside loop
    today = date.today()
    jd_lower = normalize(jd_text)
    jd_keywords = extract_keywords(jd_text)
    kw_set = set(jd_keywords)
    total_w = sum(weights.values())

    # Exp requirements parsed once
    exp_req = 0
    exp_match = re.search(r'(\d+)\+?\s*(?:years?|yrs?)', jd_lower)
    if exp_match:
        exp_req = int(exp_match.group(1))

    # Target cities compiled dynamically from ALL_CITIES and CITY_SYNONYMS
    from scoring import CITY_SYNONYMS
    target_cities = []
    with CANDIDATES_LOCK:
        cities_snapshot = list(ALL_CITIES)
        
    for city in cities_snapshot:
        canonical = CITY_SYNONYMS.get(city, city)
        
        # Match with word boundaries
        if re.search(r'\b' + re.escape(city) + r'\b', jd_lower):
            target_cities.append(city)
            continue
            
        # Match synonyms
        matched_syn = False
        for syn_key, syn_val in CITY_SYNONYMS.items():
            if syn_val == canonical or syn_key == canonical:
                if re.search(r'\b' + re.escape(syn_key) + r'\b', jd_lower):
                    matched_syn = True
                    break
        if matched_syn:
            target_cities.append(city)

    start = time.time()

    with CANDIDATES_LOCK:
        candidate_pool = CANDIDATES.copy()

    # Apply pre-filters to obtain filtered candidates
    filtered = []
    for c in candidate_pool:
        sig = c.get("redrob_signals", {})
        profile = c.get("profile", {})

        # Work mode filter
        if filters.get("work_mode") and sig.get("preferred_work_mode") != filters["work_mode"]:
            if filters["work_mode"] != "any":
                continue

        # Min experience filter
        min_exp = filters.get("min_experience", 0)
        if profile.get("years_of_experience", 0) < min_exp:
            continue

        # Max experience filter
        max_exp = filters.get("max_experience", 999)
        if profile.get("years_of_experience", 0) > max_exp:
            continue

        # Open to work filter
        if filters.get("open_to_work_only") and not sig.get("open_to_work_flag"):
            continue

        # Notice period filter
        max_notice = filters.get("max_notice_days", 999)
        if sig.get("notice_period_days", 0) > max_notice:
            continue

        filtered.append(c)

    # 2. Score all filtered candidates (highly optimized single-threaded)
    scored = []
    for c in filtered:
        try:
            result = score_candidate(
                c, jd_keywords, kw_set, weights, today, jd_lower, exp_req, target_cities, total_w, simple=True
            )
            scored.append(result)
        except Exception:
            pass

    # Sort by score descending
    scored.sort(key=lambda x: x["score"], reverse=True)

    # Assign ranks and inflate only the top N shortlist candidates
    from scoring import inflate_candidate
    shortlist = []
    with CANDIDATES_LOCK:
        for i, s in enumerate(scored[:top_n]):
            c = CANDIDATES_MAP.get(s["candidate_id"])
            if c:
                inflated = inflate_candidate(c, s)
                inflated["rank"] = i + 1
                shortlist.append(inflated)

    elapsed = time.time() - start

    return jsonify({
        "total_evaluated": len(filtered),
        "total_candidates": len(CANDIDATES),
        "elapsed_seconds": round(elapsed, 2),
        "keywords_extracted": jd_keywords[:30],
        "results": shortlist,
    })


@app.route("/api/candidate/<candidate_id>")
def api_candidate(candidate_id):
    with CANDIDATES_LOCK:
        c = CANDIDATES_MAP.get(candidate_id)
        if c:
            return jsonify(c)
    return jsonify({"error": "Not found"}), 404


@app.route("/api/stats")
def api_stats():
    """Return aggregate statistics about the dataset."""
    with CANDIDATES_LOCK:
        pool = CANDIDATES[:5000]  # Sample for speed

    if not pool:
        return jsonify({"error": "No data yet"})

    titles = {}
    industries = {}
    countries = {}
    yoe_buckets = {"0-2": 0, "3-5": 0, "6-10": 0, "11+": 0}

    for c in pool:
        p = c.get("profile", {})
        title = p.get("current_title", "Unknown")
        titles[title] = titles.get(title, 0) + 1
        ind = p.get("current_industry", "Unknown")
        industries[ind] = industries.get(ind, 0) + 1
        country = p.get("country", "Unknown")
        countries[country] = countries.get(country, 0) + 1
        yoe = p.get("years_of_experience", 0)
        if yoe <= 2:
            yoe_buckets["0-2"] += 1
        elif yoe <= 5:
            yoe_buckets["3-5"] += 1
        elif yoe <= 10:
            yoe_buckets["6-10"] += 1
        else:
            yoe_buckets["11+"] += 1

    # Top 10 of each
    top_titles = sorted(titles.items(), key=lambda x: -x[1])[:10]
    top_industries = sorted(industries.items(), key=lambda x: -x[1])[:8]
    top_countries = sorted(countries.items(), key=lambda x: -x[1])[:8]

    return jsonify({
        "sample_size": len(pool),
        "top_titles": top_titles,
        "top_industries": top_industries,
        "top_countries": top_countries,
        "experience_distribution": yoe_buckets,
    })


if __name__ == "__main__":
    print("[RedrankAI] Starting server on http://localhost:5050")
    app.run(host="0.0.0.0", port=5050, debug=False, threaded=True)
