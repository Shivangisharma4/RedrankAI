---
title: RedrankAI
emoji: 🎯
colorFrom: yellow
colorTo: red
sdk: docker
app_port: 8080
pinned: false
---

# RedrankAI — Intelligent Candidate Ranking System

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/26vTwB?referralCode=gWEQhe&utm_medium=integration&utm_source=template&utm_campaign=generic)

RedrankAI is an intelligent, high-performance candidate ranking web application built for the **Redrob Data & AI Challenge**. It is designed to rank 100,000 candidates against any job description using a hybrid, multi-signal scoring engine, mirroring the decision-making of a seasoned recruiter rather than simple keyword matching.

---

## Architecture

```
Flask Backend (app.py)          Static Frontend (static/index.html)
─────────────────────           ──────────────────────────────────
/api/status          ←──────→   Live loading progress bar
/api/rank  (POST)    ←──────→   JD input + weight sliders + results
/api/candidate/:id   ←──────→   Full profile view
/api/stats           ←──────→   Dataset statistics
```

- **Backend:** Flask web server + in-memory scoring engine
- **Frontend:** Single-page application with a premium editorial design system
- **Port:** Runs locally on `http://localhost:5050`

---

## Scoring Engine — 6 Signal Dimensions

The algorithm scores candidates across multiple dimensions to determine genuine role fit:

| Dimension | Default Weight | What it measures |
|---|---|---|
| **Skills** | 30% | Semantic skill match × proficiency × endorsements × duration × assessment scores |
| **Career fit** | 25% | JD relevance of each role's title + description + industry, weighted by tenure |
| **Experience** | 15% | Years of experience fit against JD-detected requirements |
| **Education** | 10% | Degree level × institution tier × field relevance |
| **Behavioral** | 12% | Recruiter response rate, platform activity, GitHub score, profile completeness, interview/offer rates |
| **Availability** | 8% | Open-to-work status, notice period, active applications |

### Semantic Expansion
The engine dynamically parses the job description and expands keywords through a domain taxonomy (e.g., "NLP" expands to cover Transformers, BERT, Fine-tuning LLMs, sentiment analysis; "cloud" expands to AWS, GCP, Azure, etc.) to detect implicit expertise.

---

## UI Features

- **Editorial Typography:** Fraunces serif display font paired with Instrument Sans (body) and DM Mono (labels/data).
- **Warm Aesthetic:** Curated warm cream/terracotta color palette with sharp, premium accents.
- **Dynamic UX:** Custom cursor (dot + ring with lag animation) and radial gradient hero with interactive elements.
- **Data Load Indicator:** Live loading progress bar tracking startup loading of the 487 MB database.
- **Interactive Control:** Real-time adjustable scoring weight sliders to custom-tune the ranking priority.
- **Advanced Filters:** Filter by work mode, min/max experience, notice period, and open-to-work status.
- **Sort Modes:** Sort results by Score, Experience, or Most recently active.
- **Rich Visualizations:** SVG stroke-dashoffset score gauges and color-coded per-dimension breakdown bars.
- **Detail Panel:** Expandable full-profile slide-out detailing career history, signal dashboard, and professional summary.

---

## Getting Started

### Prerequisites

Make sure you have Python 3 and Flask installed:

```bash
pip install flask
```

### Installation & Run

1. Clone this repository (or go to the repository directory):
   ```bash
   cd RedrankAI
   ```
2. Run the application:
   ```bash
   python3 app.py
   ```
3. Open [http://localhost:5050](http://localhost:5050) in your web browser.

*Note: On startup, the Flask backend loads the 100,000 candidate profiles into memory (takes ~7-10 seconds) for near-instantaneous search and ranking during API calls.*

---

## Project Structure

- `app.py` — Flask backend, routing, and scoring logic.
- `static/index.html` — Full-featured frontend with responsive layout and interactive dashboard.
- `candidate_schema.json` — JSON schema documentation for the candidates data.
- `sample_candidates.json` — A subset of candidate profiles for quick validation.
- `validate_submission.py` — Validation script to check candidate submission files.
