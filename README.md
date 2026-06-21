# RedrankAI — Candidate Intelligence Engine

RedrankAI is an offline-first, high-performance candidate ranking web application built for the **Redrob Data & AI Challenge**. It evaluates and ranks **100,000 candidates** against any job description in under 3 seconds using a multi-signal scoring system.

---

## Features

* **Multi-Signal Ranking:** Scores profiles across 6 dimensions: Skills, Career Trajectory, Experience Fit, Education Quality, Behavioral signals, and Availability.


* **Dynamic Location Resolution:** Matches search target cities dynamically and groups regional hubs (e.g. Noida, Gurgaon) to canonical zones (e.g. Delhi NCR) offline.


* **Performance Optimized:** Uses pre-normalized profile ingestion and cached query constants to evaluate 100k records in ~2.5s.


* **Adjustable Priorities:** Real-time adjustable scoring weight sliders and advanced filters.


* **Fully Responsive UI:** Minimalist, editorial layout adapting to mobile and desktop screens.

---

## Project Structure

```
RedrankAI/
│
├── app.py                      # Flask Server, API Routing, and background dataset caching
├── scoring.py                  # Hybrid scoring calculations, normalizations, and keyword extraction
├── validate_submission.py      # Standalone verification script for challenge requirements
├── Dockerfile                  # Containerization environment script
├── render.yaml                 # Configuration for Render cloud deployments
├── requirements.txt            # Python dependencies (Flask, Gunicorn)
│
├── data/                       # Configs, fallbacks, and databases
│   ├── config.json             # Decoupled default weights, domain vocabulary, and city mappings
│   ├── candidates.jsonl        # The high-scale dataset of 100,000 candidates (Git-ignored)
│   ├── sample_candidates.json  # Fallback demo candidate dataset
│   └── candidate_schema.json   # JSON schema document detailing candidate profiles structure
│
└── static/                     # Web assets (Modular frontend structure)
    ├── index.html              # HTML DOM scaffolding
    ├── app.js                  # Frontend controllers, slider listeners, and asynchronous fetching
    ├── style.css               # CSS entry point importing modular components
    ├── tokens.css              # Reset rules, design tokens (variables), and custom cursor styles
    ├── layout.css              # Navbars, hero sections, footers, and grid boundaries
    ├── form.css                # Textareas, select tags, parameters sliders, and buttons
    └── results.css             # Candidate cards, radial gauges, and stats dashboard layouts
```

---

## Getting Started

### Prerequisites

```bash
pip install Flask
```

### Local Setup

1. Start the server from the project directory:
   ```bash
   python3 app.py
   ```
2. Navigate to `http://localhost:5050` in your web browser.
