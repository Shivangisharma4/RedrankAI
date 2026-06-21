# RedrankAI — Candidate Intelligence Engine

RedrankAI is an intelligent, high-performance candidate ranking web application designed for the **Redrob Data & AI Challenge**. It evaluates and ranks **100,000 candidates** against any job description in **under 3 seconds** using a hybrid, multi-signal scoring system that thinks like a seasoned recruiter rather than a simple keyword filter.

---

## 1. The Core Problem & Our Design Philosophy

### The Pitfalls of Traditional ATS Keyword Filtering
Traditional Applicant Tracking Systems (ATS) rely on exact keyword matching. A recruiter searching for "Python" might miss a world-class software engineer who listed "PySpark, Django, and NumPy" but omitted the raw word "Python". Similarly, keyword matching cannot assess:
* **Tenure & Growth:** A candidate with 5 years of progressive responsibility is rated the same as one with 5 years of stagnant tenure.
* **Platform Activity:** A candidate who replies to recruiters immediately and is actively seeking work is scored the same as an inactive profile.
* **Credentials Quality:** It ignores the correlation between degree tiers and professional growth.

### The RedrankAI Solution
We built a **hybrid, multi-signal scoring engine** that mimics human recruiting judgment. It parses candidate profiles holistically across 6 core dimensions, expands vocabulary queries using domain-specific synonym taxonomies, and evaluates platform engagement signals.

---

## 2. Multi-Signal Scoring Engine (The Mathematical Model)

Candidates are ranked using a weighted composite score normalized to a $[0, 1]$ scale. The default weights are configured dynamically in `data/config.json`:

$$\text{Raw Score} = \sum (W_{\text{dimension}} \times S_{\text{dimension}})$$

| Dimension | Weight | Mathematical Signals & Evaluation Criteria |
| :--- | :---: | :--- |
| **Skills** | **30%** | $\text{Direct & Semantic Matches} \times \text{Proficiency Scale} \times \text{Endorsement Volume} \times \text{Duration Months} + \text{Assessment Score Bonus}$ |
| **Career Trajectory** | **25%** | $\sum_{\text{jobs}} (\text{Title Match} \times 0.35 + \text{Description Relevance} \times 0.50 + \text{Industry Fit} \times 0.15) \times \text{Tenure Ratio} \times \text{Recency Bonus} \times \text{Company Size Bonus}$ |
| **Experience Fit** | **15%** | Bell-curve penalty function centered around JD-parsed experience requirements (e.g., matching $N$ years of experience required). |
| **Education** | **10%** | $\max_{\text{degrees}} (\text{Degree Weight} \times 0.50 + \text{Institution Tier} \times 0.30 + \text{Field Relevance} \times 0.20)$ |
| **Behavioral** | **12%** | Recruiter response rates, response latency, GitHub contribution scores, profile completeness, and verified credentials. |
| **Availability** | **8%** | Open-to-work flags, notice period duration (days), and active application frequency (30d). |

---

## 3. Key Technical Implementations

### A. Semantic Expansion Taxonomy
To prevent vocabulary mismatch, the engine expands search queries using a decoupled domain synonym map. For example:
* `"machine learning"` implicitly expands to search for `["ml", "deep learning", "neural network", "ai", "predictive modeling"]`.
* `"sql"` expands to `["mysql", "postgresql", "postgres", "sqlite", "t-sql"]`.

### B. Dynamic Location Engine
To handle regional constraints offline:
1. **Dynamic City Extraction:** On background startup, the engine scans the candidate database, extracting all **28 unique candidate cities** dynamically from the raw profiles.
2. **Canonical Region Grouping:** It resolves synonyms using the `city_synonyms` configuration mapping. For example, if a job description contains `"delhi"`, `"noida"`, or `"gurgaon"`, they are all mapped to the canonical region `"delhi ncr"`.
3. **Multiplier Adjustments:** Candidates located in the matching region receive a `1.0` multiplier. Candidates outside the region who are willing to relocate receive a `0.5` multiplier, while non-relocating candidates receive `0.05`.

### C. Configuration Decoupling (`data/config.json`)
All scoring coefficients, domain synonym taxonomies, degree weights, and regional synonym boundaries are stored in `data/config.json`. The Python codebase parses these variables dynamically, allowing recruiters or system administrators to tweak evaluation rules on-the-fly without rebuilding the codebase.

---

## 4. Performance Engineering (The 5x Optimization Story)

Evaluating a 100,000-row JSONL dataset against a complex string query in Python normally takes **13–15 seconds**. Through rigorous profiling, we optimized this to **~2.5 seconds** (a 5x speedup) using single-threaded performance tactics, avoiding the deadlock risks associated with Flask multi-process forks on macOS:

* **Pre-Normalization at Startup:** We normalize and tokenize all candidate locations, skills, degree fields, and job histories **once** during the background database loading process.
* **Cached Evaluation Constants:** Query-wide metrics (such as the normalized JD keywords set, the target cities lists, and current date boundaries) are calculated once before the loop rather than repeating them 100,000 times inside the evaluation block.
* **Thread-Safe Memory Copying:** The global candidate cache is read under a Python `threading.Lock` and copied instantly, letting Flask request threads query candidate data concurrently without blocking the main event loop.

---

## 5. Technology Stack & Directory Structure

### Stack
* **Backend:** Python 3 + Flask (Microframework serving modular API endpoints).
* **Frontend:** Vanilla HTML5 + ES6 Javascript + Modular CSS (Resets, Scaffolding, Forms, and Results split into stylesheets under 500 lines of code).
* **Animations:** Motion One library for staggered entries and dynamic chart rendering.

### Directory Structure
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

## 6. Getting Started & Local Setup

### Prerequisites
Make sure you have Python 3 and Flask installed:
```bash
pip install Flask
```

### Installation & Execution
1. Clone this repository and navigate to the project directory:
   ```bash
   cd RedrankAI
   ```
2. Start the local server:
   ```bash
   python3 app.py
   ```
3. Open your browser and navigate to:
   ```
   http://localhost:5050
   ```

*Note: On startup, the Flask backend loads the 100k candidate profiles into memory (taking ~4 seconds) and prints `[RedrankAI] Loaded 100,000 candidates (found 28 unique cities)`. Submissions to the search ranking endpoints will execute instantly in under 3 seconds.*
