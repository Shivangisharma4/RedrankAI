import { animate, stagger } from 'https://cdn.jsdelivr.net/npm/motion/+esm';

// ── Custom cursor with dynamic delegation ──
const cursor = document.getElementById('cursor');
const ring = document.getElementById('cursor-ring');
let mx = 0, my = 0;
let rx = 0, ry = 0;

document.addEventListener('mousemove', (e) => {
  cursor.style.left = e.clientX + 'px';
  cursor.style.top = e.clientY + 'px';
  mx = e.clientX;
  my = e.clientY;
});

function animateRing() {
  rx += (mx - rx) * 0.12;
  ry += (my - ry) * 0.12;
  ring.style.left = rx + 'px';
  ring.style.top = ry + 'px';
  requestAnimationFrame(animateRing);
}
animateRing();

// Event delegation for cursor hovering
document.addEventListener('mouseover', (e) => {
  const target = e.target.closest('button, a, input, textarea, select, label, .insight-tag, .cursor-toggle-btn, .view-btn');
  if (target) {
    cursor.classList.add('hovering');
  } else {
    cursor.classList.remove('hovering');
  }
});

// Cursor toggle option
function toggleCursor() {
  const isCustomCursorDisabled = document.body.classList.toggle('custom-cursor-disabled');
  const btn = document.getElementById('cursorToggleBtn');
  if (isCustomCursorDisabled) {
    btn.innerHTML = '<span>🖱️ Custom Cursor: OFF</span>';
    localStorage.setItem('customCursorDisabled', 'true');
  } else {
    btn.innerHTML = '<span>✨ Custom Cursor: ON</span>';
    localStorage.setItem('customCursorDisabled', 'false');
  }
}
window.toggleCursor = toggleCursor;

// Load cursor preference on load
if (localStorage.getItem('customCursorDisabled') === 'true') {
  document.body.classList.add('custom-cursor-disabled');
  const btn = document.getElementById('cursorToggleBtn');
  if (btn) btn.innerHTML = '<span>🖱️ Custom Cursor: OFF</span>';
}

// ── Status + loading ──
let currentResults = [];
let sortOrder = 'score';

async function pollStatus() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    const dot = document.getElementById('statusDot');
    const txt = document.getElementById('statusText');
    const banner = document.getElementById('loadBanner');
    const bar = document.getElementById('loadBar');
    const loadText = document.getElementById('loadText');
    const heroCount = document.getElementById('heroCount');
    const footerCount = document.getElementById('footerTotalCount');

    const prog = d.progress;
    const pct = prog.total > 0 ? Math.round((prog.loaded / prog.total) * 100) : 0;
    bar.style.width = pct + '%';
    loadText.textContent = `${(prog.loaded || 0).toLocaleString()} / ${(prog.total || 0).toLocaleString()} profiles loaded`;

    if (d.loaded || prog.done) {
      dot.className = 'status-dot ready';
      txt.textContent = `${d.candidate_count.toLocaleString()} candidates ready`;
      heroCount.textContent = d.candidate_count.toLocaleString();
      footerCount.textContent = d.candidate_count.toLocaleString();
      banner.classList.add('hidden');
      document.getElementById('rankBtn').disabled = false;

      // Transition to insights dashboard
      document.getElementById('emptyState').style.display = 'none';
      const dash = document.getElementById('insightsDashboard');
      dash.style.display = 'block';
      animate(dash, { opacity: [0, 1], y: [15, 0] }, { duration: 0.6, easing: 'ease-out' });
      
      fetchStats();
    } else {
      dot.className = 'status-dot loading';
      txt.textContent = `Loading… ${pct}%`;
      setTimeout(pollStatus, 1500);
    }
  } catch(e) {
    setTimeout(pollStatus, 2000);
  }
}

document.getElementById('rankBtn').disabled = true;
pollStatus();

// ── Fetch aggregate statistics ──
async function fetchStats() {
  try {
    const r = await fetch('/api/stats');
    const data = await r.json();
    
    // Populate stats
    const expData = data.experience_distribution;
    const totalExp = Object.values(expData).reduce((a,b) => a+b, 0);
    
    // Calculate estimated average experience
    let weightedSum = 0;
    let totalCount = 0;
    Object.entries(expData).forEach(([bucket, count]) => {
      let midpoint = 1;
      if (bucket === '3-5') midpoint = 4;
      else if (bucket === '6-10') midpoint = 8;
      else if (bucket === '11+') midpoint = 13;
      weightedSum += count * midpoint;
      totalCount += count;
    });
    const estAvgExp = totalCount > 0 ? (weightedSum / totalCount).toFixed(1) : '5.8';
    
    document.getElementById('insightStatAvgExp').textContent = `${estAvgExp} yrs`;
    document.getElementById('insightStatTotal').textContent = parseInt(document.getElementById('heroCount').textContent).toLocaleString();
    
    // Also populate footer stats dynamically!
    document.getElementById('footerAvgExp').textContent = `${estAvgExp} yrs`;
    document.getElementById('footerSampleSize').textContent = data.sample_size.toLocaleString();
    
    // Render Experience
    const expDistribution = document.getElementById('expDistribution');
    expDistribution.innerHTML = '';
    Object.entries(expData).forEach(([bucket, count]) => {
      const pct = totalExp > 0 ? Math.round((count / totalExp) * 100) : 0;
      const row = document.createElement('div');
      row.className = 'chart-row';
      row.innerHTML = `
        <span class="chart-label">${bucket} yrs</span>
        <div class="chart-bar-container">
          <div class="chart-bar-fill" id="expBar_${bucket.replace('-','_').replace('+','_')}" style="width: 0%"></div>
        </div>
        <span class="chart-val">${pct}%</span>
      `;
      expDistribution.appendChild(row);
    });

    // Render Locations
    const countries = data.top_countries;
    const totalCountries = countries.reduce((sum, item) => sum + item[1], 0);
    const topLocations = document.getElementById('topLocations');
    topLocations.innerHTML = '';
    countries.forEach(([country, count], idx) => {
      const pct = totalCountries > 0 ? Math.round((count / totalCountries) * 100) : 0;
      const row = document.createElement('div');
      row.className = 'chart-row';
      row.innerHTML = `
        <span class="chart-label">${esc(country)}</span>
        <div class="chart-bar-container">
          <div class="chart-bar-fill" id="countryBar_${idx}" style="width: 0%"></div>
        </div>
        <span class="chart-val">${pct}%</span>
      `;
      topLocations.appendChild(row);
    });

    // Render Roles
    const roles = data.top_titles;
    const topRoles = document.getElementById('topRoles');
    topRoles.innerHTML = '';
    roles.forEach(([title, count]) => {
      const span = document.createElement('span');
      span.className = 'insight-tag';
      span.textContent = `${title} (${count})`;
      topRoles.appendChild(span);
    });

    // Render Industries
    const industries = data.top_industries;
    const topIndustries = document.getElementById('topIndustries');
    topIndustries.innerHTML = '';
    industries.forEach(([ind, count]) => {
      const span = document.createElement('span');
      span.className = 'insight-tag';
      span.textContent = `${ind} (${count})`;
      topIndustries.appendChild(span);
    });

    // Animate elements inside dashboard
    setTimeout(() => {
      // Animate exp bars
      Object.entries(expData).forEach(([bucket, count]) => {
        const pct = totalExp > 0 ? Math.round((count / totalExp) * 100) : 0;
        const barEl = document.getElementById(`expBar_${bucket.replace('-','_').replace('+','_')}`);
        if (barEl) animate(barEl, { width: `${pct}%` }, { duration: 1.0, easing: 'ease-out' });
      });

      // Animate country bars
      countries.forEach(([country, count], idx) => {
        const pct = totalCountries > 0 ? Math.round((count / totalCountries) * 100) : 0;
        const barEl = document.getElementById(`countryBar_${idx}`);
        if (barEl) animate(barEl, { width: `${pct}%` }, { duration: 1.0, easing: 'ease-out', delay: idx * 0.05 });
      });

      // Animate tags
      animate(".insight-tag", { opacity: [0, 1], scale: [0.9, 1] }, {
        delay: stagger(0.015),
        duration: 0.35,
        easing: 'ease-out'
      });
    }, 100);

  } catch(e) {
    console.error("Failed to load dashboard insights:", e);
  }
}

// ── Weight display (dynamic normalization calculation) ──
function updateWeightVal(sliderId, valId) {
  recalculateRelativeWeights();
}
window.updateWeightVal = updateWeightVal;

function recalculateRelativeWeights() {
  const sliders = [
    { id: 'wSkills', labelId: 'wSkillsVal' },
    { id: 'wCareer', labelId: 'wCareerVal' },
    { id: 'wExp', labelId: 'wExpVal' },
    { id: 'wEdu', labelId: 'wEduVal' },
    { id: 'wBeh', labelId: 'wBehVal' },
    { id: 'wAvail', labelId: 'wAvailVal' }
  ];

  const vals = sliders.map(s => parseFloat(document.getElementById(s.id).value));
  const total = vals.reduce((a, b) => a + b, 0);

  sliders.forEach((s, idx) => {
    const rawVal = vals[idx];
    const relativePct = total > 0 ? Math.round((rawVal / total) * 100) : 0;
    document.getElementById(s.labelId).textContent = `${relativePct}%`;
  });
}

// Initial weights calculation
recalculateRelativeWeights();

// ── Panel height animation helper ──
function animateHeightToggle(el, isOpen, displayStyle = 'block') {
  if (isOpen) {
    el.style.display = displayStyle;
    el.style.overflow = 'hidden';
    el.style.height = '0px';
    el.style.opacity = '0';
    
    const targetHeight = el.scrollHeight;
    
    animate(el, { height: [0, targetHeight], opacity: [0, 1] }, { duration: 0.3, easing: 'ease-out' }).then(() => {
      el.style.height = 'auto';
      el.style.overflow = 'visible';
    });
  } else {
    el.style.overflow = 'hidden';
    const currentHeight = el.offsetHeight;
    
    animate(el, { height: [currentHeight, 0], opacity: [1, 0] }, { duration: 0.25, easing: 'ease-in' }).then(() => {
      el.style.display = 'none';
      el.style.height = '';
    });
  }
}

// ── Filter toggle ──
function toggleFilters() {
  const panel = document.getElementById('filtersPanel');
  const btn = document.getElementById('filterToggle');
  const isOpen = panel.classList.toggle('open');
  btn.textContent = (isOpen ? '▾' : '▸') + ' Advanced filters';
  
  animateHeightToggle(panel, isOpen, 'block');
}
window.toggleFilters = toggleFilters;

// ── Toast ──
function showToast(msg, type = '') {
  const c = document.getElementById('toastContainer');
  const t = document.createElement('div');
  t.className = 'toast' + (type ? ' ' + type : '');
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}
window.showToast = showToast;

// ── Sort ──
function setSortOrder(order) {
  sortOrder = order;
  document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  renderResults(currentResults);
}
window.setSortOrder = setSortOrder;

// ── Main ranking call ──
async function doRank() {
  const jd = document.getElementById('jdInput').value.trim();
  if (!jd) { showToast('Please enter a job description.', 'error'); return; }

  const btn = document.getElementById('rankBtn');
  btn.classList.add('loading');
  btn.disabled = true;
  document.getElementById('rankBtnText').textContent = 'Ranking…';

  const weights = {
    skills: parseFloat(document.getElementById('wSkills').value),
    career: parseFloat(document.getElementById('wCareer').value),
    experience: parseFloat(document.getElementById('wExp').value),
    education: parseFloat(document.getElementById('wEdu').value),
    behavioral: parseFloat(document.getElementById('wBeh').value),
    availability: parseFloat(document.getElementById('wAvail').value),
  };

  const filters = {};
  const minExp = parseInt(document.getElementById('fMinExp').value);
  const maxExp = parseInt(document.getElementById('fMaxExp').value);
  const wm = document.getElementById('fWorkMode').value;
  const maxNotice = parseInt(document.getElementById('fMaxNotice').value);
  const openOnly = document.getElementById('fOpenToWork').checked;

  if (minExp > 0) filters.min_experience = minExp;
  if (maxExp < 50) filters.max_experience = maxExp;
  if (wm !== 'any') filters.work_mode = wm;
  if (maxNotice < 180) filters.max_notice_days = maxNotice;
  if (openOnly) filters.open_to_work_only = true;

  try {
    const res = await fetch('/api/rank', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        job_description: jd,
        top_n: parseInt(document.getElementById('topN').value),
        weights,
        filters,
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Ranking failed');

    currentResults = data.results;
    showRankResults(data);
    showToast(`✓ Ranked ${data.total_evaluated.toLocaleString()} candidates in ${data.elapsed_seconds}s`);
  } catch(e) {
    showToast(e.message, 'error');
  } finally {
    btn.classList.remove('loading');
    btn.disabled = false;
    document.getElementById('rankBtnText').textContent = 'Find Best Candidates';
  }
}
window.doRank = doRank;

function showRankResults(data) {
  document.getElementById('emptyState').style.display = 'none';
  document.getElementById('insightsDashboard').style.display = 'none';
  
  const header = document.getElementById('resultsHeader');
  header.style.display = 'block';

  document.getElementById('resultsCount').textContent =
    `${data.results.length} candidates shortlisted`;
  document.getElementById('resultsMeta').innerHTML =
    `Evaluated <strong>${data.total_evaluated.toLocaleString()}</strong> of ${data.total_candidates.toLocaleString()} profiles<br>` +
    `<span style="color:var(--accent)">${data.elapsed_seconds}s</span> ranking time`;

  // Keywords
  const kwRow = document.getElementById('kwRow');
  kwRow.innerHTML = '';
  (data.keywords_extracted || []).slice(0, 20).forEach(kw => {
    const t = document.createElement('span');
    t.className = 'kw-tag';
    t.textContent = kw;
    kwRow.appendChild(t);
  });

  renderResults(data.results);
}
window.showRankResults = showRankResults;

function renderResults(results) {
  let sorted = [...results];
  if (sortOrder === 'experience') {
    sorted.sort((a,b) => b.profile.years_of_experience - a.profile.years_of_experience);
  } else if (sortOrder === 'activity') {
    sorted.sort((a,b) => {
      const da = new Date(a.signals.last_active_date || '2000-01-01');
      const db = new Date(b.signals.last_active_date || '2000-01-01');
      return db - da;
    });
  }

  const list = document.getElementById('candidatesList');
  list.innerHTML = '';

  sorted.forEach((c, idx) => {
    const card = buildCard(c, idx + 1);
    list.appendChild(card);
  });

  // Animate candidate cards with stagger
  animate(".candidate-card", { opacity: [0, 1], y: [15, 0] }, {
    delay: stagger(0.04),
    duration: 0.35,
    easing: 'ease-out'
  });
}
window.renderResults = renderResults;

function buildCard(c, displayRank) {
  const card = document.createElement('div');
  card.className = 'candidate-card';
  const pct = Math.round(c.score * 100);
  const scoreClass = pct >= 60 ? 'high' : pct >= 35 ? 'medium' : 'low';
  const isTopThree = displayRank <= 3;

  // Signals
  const sig = c.signals;
  const salRange = sig.expected_salary_range_inr_lpa || {};
  const salText = salRange.min && salRange.max
    ? `₹${salRange.min}–${salRange.max} LPA`
    : '—';

  // Tags
  const tags = [];
  if (sig.open_to_work) tags.push(`<span class="card-tag tag-open">✓ Open to work</span>`);
  if (sig.notice_period_days <= 30) tags.push(`<span class="card-tag tag-notice">⚡ ${sig.notice_period_days}d notice</span>`);
  else if (sig.notice_period_days) tags.push(`<span class="card-tag tag-notice">${sig.notice_period_days}d notice</span>`);
  if (sig.preferred_work_mode) tags.push(`<span class="card-tag tag-mode">${sig.preferred_work_mode}</span>`);
  if (c.profile.location) tags.push(`<span class="card-tag tag-location">📍 ${c.profile.location}</span>`);

  // Breakdown bars
  const comp = c.component_scores;
  const breakdown = ['skills', 'career', 'experience', 'education', 'behavioral', 'availability'];

  const breakdownHTML = breakdown.map(k => `
    <div class="breakdown-bar-wrap">
      <span class="breakdown-label">${k}</span>
      <div class="breakdown-bar"><div class="breakdown-fill fill-${k}" style="width:${Math.round((comp[k]||0)*100)}%"></div></div>
      <span class="breakdown-pct">${Math.round((comp[k]||0)*100)}%</span>
    </div>
  `).join('');

  // Top 3 score breakdown preview (collapsed view)
  const colorMap = {
    skills: 'var(--accent)',
    career: 'var(--teal)',
    experience: 'var(--gold)',
    education: '#7c5cbf',
    behavioral: '#2d7dd2',
    availability: '#27ae60'
  };
  const topComponents = Object.entries(comp)
    .sort((a,b) => b[1] - a[1])
    .slice(0, 3)
    .map(([k,v]) => {
      return `
        <span class="mini-breakdown-item">
          <span class="mini-dot" style="background: ${colorMap[k] || 'var(--ink-muted)'}"></span>
          <span class="mini-label">${k}</span>
          <span class="mini-score">${Math.round(v * 100)}%</span>
        </span>
      `;
    }).join('');

  // Career history (first 3 entries)
  const careerHTML = (c.career_history || []).slice(0, 3).map(job => `
    <div class="career-entry">
      <div class="career-duration">${job.start_date} – ${job.end_date || 'Present'} · ${job.duration_months}mo</div>
      <div class="career-title">${esc(job.title)}</div>
      <div class="career-company">${esc(job.company)} · ${esc(job.industry)} · ${esc(job.company_size)}</div>
      <div class="career-desc">${esc(job.description || '').substring(0, 200)}${(job.description||'').length > 200 ? '…' : ''}</div>
    </div>
  `).join('');

  // Signal grid
  const signalItems = [
    ['Profile complete', comp_score(sig.profile_completeness) + '%'],
    ['GitHub score', sig.github_activity_score >= 0 ? sig.github_activity_score : '—'],
    ['Response rate', Math.round(sig.recruiter_response_rate * 100) + '%'],
    ['Interview rate', Math.round(sig.interview_completion_rate * 100) + '%'],
    ['Last active', sig.last_active_date || '—'],
    ['Salary expect.', salText],
    ['Willing to relocate', sig.willing_to_relocate ? 'Yes' : 'No'],
    ['LinkedIn', sig.linkedin_connected ? '✓' : '—'],
    ['Verified email', sig.verified_email ? '✓' : '—'],
    ['Saved (30d)', sig.saved_by_recruiters_30d],
    ['Connections', sig.connection_count],
    ['Search appear. (30d)', sig.search_appearance_30d],
  ];

  const signalHTML = signalItems.map(([k,v]) => `
    <div class="signal-item">
      <span class="signal-key">${k}</span>
      <span class="signal-val">${v}</span>
    </div>
  `).join('');

  const matchedSkillsHTML = (c.matched_skills || []).length > 0 ? `
    <div class="matched-skills">
      <span class="matched-skills-label">Matched skills</span>
      ${c.matched_skills.map(s => `<span class="skill-chip">${esc(s)}</span>`).join('')}
    </div>
  ` : '';

  card.innerHTML = `
    <div class="card-top">
      <div class="rank-badge">
        <div class="rank-num ${isTopThree ? 'top-three' : ''}">${displayRank}</div>
        <div class="rank-badge-label">rank</div>
      </div>
      <div class="card-identity">
        <div class="card-name">${esc(c.profile.name)}</div>
        <div class="card-title-company"><strong>${esc(c.profile.current_title)}</strong> at ${esc(c.profile.current_company)} · ${c.profile.years_of_experience.toFixed(1)} yrs exp</div>
        <div class="card-tags">${tags.join('')}</div>
        <div class="card-mini-breakdown">${topComponents}</div>
      </div>
      <div class="score-panel">
        <div class="score-ring-wrap">
          <svg class="score-svg" width="64" height="64" viewBox="0 0 64 64">
            <circle class="score-bg" cx="32" cy="32" r="25"/>
            <circle class="score-fill ${scoreClass}" cx="32" cy="32" r="25" id="scoreFill_${c.candidate_id}" style="stroke-dashoffset:${157 - (pct/100)*157}"/>
          </svg>
          <span class="score-number">${pct}%</span>
        </div>
      </div>
    </div>

    <div class="card-reasoning">
      <svg class="reasoning-icon" width="12" height="12" viewBox="0 0 12 12" fill="none">
        <circle cx="6" cy="6" r="5.5" stroke="currentColor" stroke-width="0.8"/>
        <text x="6" y="8.5" text-anchor="middle" font-size="7" fill="currentColor">i</text>
      </svg>
      ${esc(c.reasoning)}
    </div>

    ${matchedSkillsHTML}

    <div class="card-breakdown" id="breakdown_${c.candidate_id}">
      ${breakdownHTML}
    </div>

    <button class="card-expand-btn" onclick="toggleExpand('${c.candidate_id}')">
      <svg class="expand-arrow" width="10" height="10" viewBox="0 0 10 10" fill="none">
        <path d="M2 3.5L5 6.5L8 3.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
      </svg>
      View full profile &amp; scores
    </button>

    <div class="detail-panel" id="detail_${c.candidate_id}">
      <div class="detail-bio" style="grid-column:1/-1;">
        <div class="detail-section-title">Professional Summary</div>
        <p>${esc(c.profile.summary || 'No summary available.')}</p>
      </div>

      <div>
        <div class="detail-section-title">Signal Dashboard</div>
        <div class="signal-grid">${signalHTML}</div>
      </div>

      <div>
        <div class="detail-section-title">Career History</div>
        ${careerHTML || '<div style="font-size:0.8rem;color:var(--ink-muted)">No career history</div>'}
      </div>
    </div>
  `;

  return card;
}
window.buildCard = buildCard;

function toggleExpand(id) {
  const breakdown = document.getElementById(`breakdown_${id}`);
  const detail = document.getElementById(`detail_${id}`);
  const btn = detail.previousElementSibling;
  const isOpen = detail.classList.toggle('open');
  
  btn.classList.toggle('open', isOpen);
  btn.querySelector('span:last-child') && 
    (btn.querySelector('.expand-arrow').closest('button').childNodes[2].textContent = 
      isOpen ? ' Collapse profile' : ' View full profile & scores');

  animateHeightToggle(breakdown, isOpen, 'block');
  animateHeightToggle(detail, isOpen, 'grid');
}
window.toggleExpand = toggleExpand;

function esc(str) {
  if (!str) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
window.esc = esc;

function comp_score(v) { return Math.round(v || 0); }
window.comp_score = comp_score;

// Allow Enter key in textarea (Ctrl+Enter to submit)
document.getElementById('jdInput').addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') doRank();
});
