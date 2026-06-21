# RedrankAI — Candidate Intelligence Engine

RedrankAI is an offline-first, high-performance candidate ranking web application built for the **Redrob Data & AI Challenge**. It evaluates and ranks 100,000 candidate profiles against any arbitrary job description in under 3 seconds using a hybrid, multi-signal scoring system.

---

## Features

* **Multi-Signal Ranking:** Evaluates talent objectively across 6 dimensions:
  * **Skills (30%):** Proficiencies, duration, endorsements, and skill assessments.
  * **Career Trajectory (25%):** Job title relevance, job descriptions, industry fit, and tenure recency.
  * **Experience (15%):** Absolute years of experience matched against job description requirements.
  * **Education (10%):** Academic tier, degree levels, and field-of-study match.
  * **Behavioral (12%):** Responsiveness, activity frequency, and GitHub signals.
  * **Availability (8%):** Notice period, open-to-work status, and active applications.
* **Dynamic Location Engine:** Automatically extracts candidate cities from the database on startup. Matches job requirements dynamically using boundary-safe regular expressions and groups regional hubs (e.g., Noida, Gurgaon) into canonical zones (e.g., Delhi NCR) using synonyms.
* **Decoupled Configurations:** Scoring weights, domain terminology synonyms, and city groups are externalized in `data/config.json` for easy tuning without modifying Python files.
* **High-Speed Ingestion & Search:** Normalizes candidate profiles on startup and caches query constants, delivering a 5x search speedup (evaluating 100k records in ~2.5s).
* **Minimalist UI & Insights:** Editorial design layout, live pool stats charts, adjustable weight sliders, per-dimension breakdown bars, and collapsible candidate cards.
* **Mobile Responsive:** Completely responsive grid layout with custom touch-screen adaptations (hiding custom cursor hover loops on tablets and mobile screens).

---

## Architecture

* **Backend (`app.py`, `scoring.py`):** Flask application serving API routes and the modular hybrid scoring engine.
* **Frontend (`static/`):** Vanilla layout (`index.html`), interactive logic (`app.js`), and component stylesheets (`tokens.css`, `layout.css`, `form.css`, `results.css`) imported via `style.css`.
* **Configurations (`data/`):** Houses configuration schema (`config.json`), database (`candidates.jsonl`), and validation files.

---

## Getting Started

### Prerequisites

Install the backend dependencies:
```bash
pip install Flask
```

### Run Locally

1. Start the local server:
   ```bash
   python3 app.py
   ```
2. Navigate to `http://localhost:5050` in your browser.

---

## Configuration (`data/config.json`)

Scoring rules can be tuned dynamically in the config file:
* `default_weights`: Set default influence ratios for the 6 scoring signals.
* `domain_synonyms`: Define term expansions (e.g., `nlp` -> `bert, transformer, llm`) to detect implicit skills.
* `city_synonyms`: Group multiple municipalities under single metropolitan targets (e.g., `gurgaon` -> `delhi ncr`).
