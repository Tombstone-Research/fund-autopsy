
let currentData = null;
const input = document.getElementById('tickerInput');

// Tooltip definitions for cost categories
const COST_TOOLTIPS = {
  'Expense Ratio': 'The annual fee the fund charges, deducted from your returns. This is the cost they tell you about.',
  'Brokerage Commissions': 'What the fund pays brokers to execute trades. Reported annually in the N-CEN filing but not included in the expense ratio.',
  'Bid-Ask Spread Cost': 'The difference between buy and sell prices on securities the fund trades. Estimated from the fund\'s holdings mix and turnover rate.',
  'Market Impact Cost': 'The price movement caused by the fund\'s own trading activity. Larger trades in less liquid markets create bigger impact. Estimated using the Edelen, Evans & Kadlec (2007) framework.',
  'Soft Dollar Arrangements': 'When a fund pays higher brokerage commissions in exchange for research services. The excess cost is passed to shareholders.',
  'Hidden Fee Score': 'A 0-100 score measuring how much of a fund\'s true cost is hidden below the stated expense ratio. Lower is better — it means fewer surprises.',
  'Cash Drag': 'The opportunity cost of holding cash instead of investing. Active funds often keep 3-5% in cash for redemptions — that uninvested money drags returns.',
  'Position-Adjusted Turnover': 'Turnover weighted by position concentration. A fund trading large concentrated positions costs more per trade than one trading small positions across hundreds of stocks.',
  'Fee Waiver': 'The gap between the fund\'s gross and net expense ratio. The discount comes from a temporary fee waiver that can be removed at any time — your costs could jump.',
};

// Helper function to add info icon to a label
function addInfoIcon(label) {
  if (COST_TOOLTIPS[label]) {
    return `${label}<span class="info-icon">?<span class="tooltip">${COST_TOOLTIPS[label]}</span></span>`;
  }
  return label;
}

// Build shareable summary for current fund
function buildShareSummary() {
  if (!currentData) return null;
  const d = currentData;

  function getGradeForShare(low, high) {
    if (!high) return 'N/A';
    const mid = (low + high) / 2;
    if (mid < 10) return 'A';
    if (mid < 25) return 'B';
    if (mid < 50) return 'C';
    if (mid < 100) return 'D';
    return 'F';
  }

  const grade = getGradeForShare(d.total_hidden_low, d.total_hidden_high);
  const hiddenLow = d.total_hidden_low ? d.total_hidden_low.toFixed(0) : '0';
  const hiddenHigh = d.total_hidden_high ? d.total_hidden_high.toFixed(0) : '0';
  const erPctOf = (d.expense_ratio_pct && d.total_hidden_high)
    ? Math.round(((d.total_hidden_low + d.total_hidden_high) / 2) / (d.expense_ratio_pct * 100) * 100)
    : null;
  const conflicts = d.conflict_flags ? d.conflict_flags.length : 0;

  return { grade, hiddenLow, hiddenHigh, erPctOf, conflicts, ticker: d.ticker, name: d.name };
}

// Share on X with pre-filled tweet
function shareOnX() {
  const s = buildShareSummary();
  if (!s) return;

  let tweet = `${s.ticker} gets a ${s.grade} on hidden costs.`;
  tweet += ` ${s.hiddenLow}–${s.hiddenHigh} bps in trading costs not in the expense ratio.`;
  if (s.erPctOf) tweet += ` That's +${s.erPctOf}% on top of the stated fee.`;
  if (s.conflicts > 0) tweet += ` ${s.conflicts} conflict${s.conflicts > 1 ? 's' : ''} flagged.`;
  tweet += `\n\nRun your fund: github.com/tombstoneresearch/fund-autopsy`;
  tweet += `\n\n#FundAutopsy`;

  const url = 'https://twitter.com/intent/tweet?text=' + encodeURIComponent(tweet);
  window.open(url, '_blank', 'width=550,height=420');
}

// Copy shareable text to clipboard
function shareResults() {
  const s = buildShareSummary();
  if (!s) return;

  const text = [
    `${s.ticker} Fund Autopsy: Grade ${s.grade}`,
    `Hidden costs: ${s.hiddenLow}–${s.hiddenHigh} bps`,
    s.erPctOf ? `+${s.erPctOf}% beyond stated expense ratio` : '',
    s.conflicts > 0 ? `${s.conflicts} conflict${s.conflicts > 1 ? 's' : ''} flagged` : '',
    ``,
    `github.com/tombstoneresearch/fund-autopsy`,
  ].filter(Boolean).join('\n');

  navigator.clipboard.writeText(text).then(() => {
    const btn = document.getElementById('shareBtn');
    const orig = btn.textContent;
    btn.textContent = 'Copied!';
    btn.style.borderColor = 'var(--green)';
    btn.style.color = 'var(--green)';
    setTimeout(() => {
      btn.textContent = orig;
      btn.style.borderColor = '';
      btn.style.color = '';
    }, 2000);
  });
}

input.addEventListener('keydown', e => {
  if (e.key === 'Enter') {
    const t = input.value.trim().toUpperCase();
    if (t) runAnalysis(t);
  }
});

// Welcome page search bar
const welcomeInput = document.getElementById('welcomeTickerInput');
if (welcomeInput) {
  welcomeInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      triggerWelcomeSearch();
    }
  });
}

function triggerWelcomeSearch() {
  const el = document.getElementById('welcomeTickerInput');
  const t = (el.value || '').trim().toUpperCase();
  if (t) {
    // Check if it's a comma-separated comparison
    if (t.includes(',')) {
      runComparison(t);
    } else {
      runAnalysis(t);
    }
  }
}

function triggerWelcomeCompare() {
  const el = document.getElementById('compareInput');
  const t = (el.value || '').trim();
  if (t) runComparison(t);
}

document.addEventListener('DOMContentLoaded', () => {
  const welcomeEl = document.getElementById('welcomeTickerInput');
  if (welcomeEl) welcomeEl.focus();
});

// Home / reset
function goHome() {
  document.getElementById('dash').style.display = 'none';
  document.getElementById('error').style.display = 'none';
  document.getElementById('loading').style.display = 'none';
  document.getElementById('welcome').style.display = '';
  document.getElementById('homeBtn').style.display = 'none';
  input.value = '';
  const welcomeEl = document.getElementById('welcomeTickerInput');
  if (welcomeEl) { welcomeEl.value = ''; welcomeEl.focus(); }
  currentData = null;
}

// Tab switching
function switchTab(tab) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + tab).classList.add('active');
  // Find the button whose onclick matches this tab
  document.querySelectorAll('.tab-btn').forEach(btn => {
    if (btn.getAttribute('onclick') && btn.getAttribute('onclick').includes("'" + tab + "'")) {
      btn.classList.add('active');
    }
  });

  if (tab === 'dollar') {
    setTimeout(() => recalculateDollarImpact(), 100);
  }
}

// Dollar impact calculator
['calcInvestment', 'calcHorizon', 'calcReturn'].forEach(id => {
  document.getElementById(id).addEventListener('change', recalculateDollarImpact);
  document.getElementById(id).addEventListener('input', recalculateDollarImpact);
});

function recalculateDollarImpact() {
  if (!currentData) return;

  const inv = parseFloat(document.getElementById('calcInvestment').value) || 100000;
  const yrs = parseFloat(document.getElementById('calcHorizon').value) || 20;
  const ret = parseFloat(document.getElementById('calcReturn').value) || 7;

  const erPct = (currentData.expense_ratio_pct || 0) / 100;
  const hiddenLow = (currentData.total_hidden_low || 0) / 10000;
  const hiddenHigh = (currentData.total_hidden_high || 0) / 10000;

  const r = ret / 100;

  // Scenario 0: No costs (pure compound growth)
  const scenario0 = inv * Math.pow(1 + r, yrs);

  // Scenario 1: Expense ratio only
  const scenario1 = inv * Math.pow(1 + r - erPct, yrs);

  // Scenario 2: True total cost (midpoint of low/high hidden)
  const avgHidden = (hiddenLow + hiddenHigh) / 2;
  const scenario2 = inv * Math.pow(1 + r - erPct - avgHidden, yrs);

  const hidden = scenario0 - scenario2;
  const hiddenLowVal = inv * Math.pow(1 + r - erPct - hiddenLow, yrs);
  const hiddenHighVal = inv * Math.pow(1 + r - erPct - hiddenHigh, yrs);
  const hiddenRangeLow = scenario0 - hiddenHighVal;
  const hiddenRangeHigh = scenario0 - hiddenLowVal;

  // Render scenarios
  const scenariosHtml = `
    <div class="scenario-card">
      <div class="scenario-title">No Costs</div>
      <div class="scenario-value">$${formatNumber(scenario0)}</div>
      <div class="scenario-sub">Pure compound growth at ${ret}% p.a.</div>
    </div>
    <div class="scenario-card">
      <div class="scenario-title">Expense Ratio Only</div>
      <div class="scenario-value">$${formatNumber(scenario1)}</div>
      <div class="scenario-sub">What you think you're paying</div>
    </div>
    <div class="scenario-card">
      <div class="scenario-title">True Total Cost</div>
      <div class="scenario-value">$${formatNumber(scenario2)}</div>
      <div class="scenario-sub">Including hidden trading costs</div>
    </div>
  `;
  document.getElementById('scenariosContainer').innerHTML = scenariosHtml;

  // Impact card
  document.getElementById('impactValue').textContent = `$${formatNumber(hiddenRangeLow)} – $${formatNumber(hiddenRangeHigh)}`;

  // Bar chart
  const maxVal = Math.max(scenario0, scenario1, scenario2) * 1.1;
  const h0 = (scenario0 / maxVal) * 100;
  const h1 = (scenario1 / maxVal) * 100;
  const h2 = (scenario2 / maxVal) * 100;

  const barsHtml = `
    <div class="bar-col">
      <div class="bar scenario-0" style="height:${h0}%"></div>
      <div class="bar-value">$${formatShort(scenario0)}</div>
      <div class="bar-label">No Costs</div>
    </div>
    <div class="bar-col">
      <div class="bar scenario-1" style="height:${h1}%"></div>
      <div class="bar-value">$${formatShort(scenario1)}</div>
      <div class="bar-label">ER Only</div>
    </div>
    <div class="bar-col">
      <div class="bar scenario-2" style="height:${h2}%"></div>
      <div class="bar-value">$${formatShort(scenario2)}</div>
      <div class="bar-label">True Cost</div>
    </div>
  `;
  document.getElementById('barsContainer').innerHTML = barsHtml;
}

// Stage animation
let stageTimer;
function animateStages() {
  const ids = ['s1','s2','s3','s4'];
  let i = 0;
  clearInterval(stageTimer);
  ids.forEach(id => { document.getElementById(id).className = 'stage'; });
  document.getElementById(ids[0]).className = 'stage active';
  stageTimer = setInterval(() => {
    if (i < ids.length) document.getElementById(ids[i]).className = 'stage done';
    i++;
    if (i < ids.length) document.getElementById(ids[i]).className = 'stage active';
    if (i >= ids.length) clearInterval(stageTimer);
  }, 1800);
}

// Score Card Generation (Shareable Report Card)
function generateScoreCard(d) {
  // Calculate letter grade based on hidden cost gap
  function getGrade(hiddenLow, hiddenHigh) {
    if (!hiddenHigh) return 'N/A';
    const midpoint = (hiddenLow + hiddenHigh) / 2;
    if (midpoint < 10) return 'A';
    if (midpoint < 25) return 'B';
    if (midpoint < 50) return 'C';
    if (midpoint < 100) return 'D';
    return 'F';
  }

  const grade = getGrade(d.total_hidden_low, d.total_hidden_high);

  // Calculate dollar cost per $100K
  const dollarImpactMidpoint = d.dollar_impact && d.dollar_impact.hidden_cost_low && d.dollar_impact.hidden_cost_high
    ? (d.dollar_impact.hidden_cost_low + d.dollar_impact.hidden_cost_high) / 2
    : null;

  const dollarText = dollarImpactMidpoint
    ? `Your fund charged $${Math.round(dollarImpactMidpoint / 1000).toFixed(1)}K per $100K invested in hidden costs over 20 years`
    : 'Insufficient data for dollar impact calculation';

  const hiddenLowBps = d.total_hidden_low ? d.total_hidden_low.toFixed(1) : '0';
  const hiddenHighBps = d.total_hidden_high ? d.total_hidden_high.toFixed(1) : '0';

  const scoreCardHtml = `
    <div class="score-card">
      <div class="score-card-inner">
        <div class="score-header">
          <div class="score-branding">Fund Autopsy Report Card</div>
          <div class="score-ticker">${d.ticker}</div>
          <div class="score-title">${d.name}</div>
        </div>

        <div class="score-body">
          <div class="score-grades">
            <div class="score-grade-item">
              <div class="score-grade-label">Overall Hidden Cost Grade</div>
              <div class="score-grade-letter ${grade}">${grade}</div>
              <div class="score-grade-sub">${hiddenLowBps} – ${hiddenHighBps} bps</div>
            </div>
          </div>

          <div class="score-metrics">
            <div class="score-metric-box">
              <div class="score-metric-label">Hidden Costs Over 20 Years</div>
              <div class="score-metric-value">\$${formatShort(dollarImpactMidpoint || 0)}</div>
              <div class="score-metric-sub">per \$100K invested</div>
            </div>
            ${d.true_cost_low_pct ? `
            <div class="score-metric-box">
              <div class="score-metric-label">True Total Cost</div>
              <div class="score-metric-value">${d.true_cost_low_pct.toFixed(2)}–${d.true_cost_high_pct.toFixed(2)}%</div>
              <div class="score-metric-sub">ER + hidden costs</div>
            </div>
            ` : ''}
          </div>
        </div>

        <div class="score-footer">
          <div class="score-share-prompt">Share this autopsy</div>
          <div class="score-share-buttons">
            <button class="score-share-btn score-share-x" onclick="shareOnX()">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
              Post on X
            </button>
            <button class="score-share-btn score-share-copy" onclick="shareResults()">
              Copy Results
            </button>
          </div>
        </div>
      </div>
    </div>
  `;

  return scoreCardHtml;
}

// copyScoreCard removed — share buttons now use shareOnX() and shareResults()

function show(id) {
  ['welcome','loading','error','dash','compare'].forEach(s => {
    const el = document.getElementById(s);
    if (s === 'dash') { el.classList.toggle('visible', s === id); }
    else { el.style.display = s === id ? '' : 'none'; }
    if (s === id && s === 'dash') el.classList.add('visible');
    if (s !== id && s === 'dash') el.classList.remove('visible');
  });
  document.getElementById('homeBtn').style.display = (id === 'welcome') ? 'none' : 'flex';
}

async function runAnalysis(ticker) {
  input.value = ticker;
  document.getElementById('loadTicker').textContent = ticker;
  show('loading');
  animateStages();

  try {
    const resp = await fetch(`/api/analyze/${ticker}`);
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      if (resp.status === 404) {
        throw new Error('Fund not found. Please check the ticker and try again.');
      }
      throw new Error(err.detail || `HTTP ${resp.status}`);
    }
    const data = await resp.json();
    currentData = data;
    clearInterval(stageTimer);
    ['s1','s2','s3','s4'].forEach(id => document.getElementById(id).className = 'stage done');
    setTimeout(() => renderDash(data), 400);
    refreshLeaderboardAfterAnalysis();
  } catch (e) {
    clearInterval(stageTimer);
    showStyledError('Analysis Failed', e.message);
  }
}

function showStyledError(title, message, suggestion) {
  const errorCard = document.getElementById('errorCard');
  const suggestionHtml = suggestion ? `<div class="error-suggestion">${suggestion}</div>` : '';
  errorCard.innerHTML = `
    <div class="error-icon">⚠️</div>
    <div class="error-title">${title}</div>
    <p>${message}</p>
    ${suggestionHtml}
    <p style="margin-top:16px"><span class="example-chip" onclick="show('welcome')" style="cursor:pointer;display:inline-block">Try another ticker</span></p>
  `;
  show('error');
}

function renderDash(d) {
  // Generate and display score card
  const scoreCardHtml = generateScoreCard(d);
  document.getElementById('scoreCardContainer').innerHTML = scoreCardHtml;
  document.getElementById('scoreCardContainer').style.display = 'block';

  // Title
  document.getElementById('fundTitle').innerHTML =
    `${d.name} <span class="ticker">${d.ticker}</span>`;
  document.getElementById('fundFamily').textContent = d.family + ' — ' + d.share_class;

  // KPIs
  const kpis = [
    { label: 'Net Assets', value: d.net_assets_display },
    { label: 'Holdings', value: String(d.holdings_count) },
    { label: 'Turnover', value: (d.portfolio_turnover || 0).toFixed(1) + '%' },
    { label: 'Filing Period', value: d.period_end || 'N/A' },
  ];
  if (d.position_adjusted_turnover) {
    kpis.push({ label: addInfoIcon('Position-Adjusted Turnover'), value: (d.position_adjusted_turnover * 10000).toFixed(1) + ' PAT' });
  }
  if (d.cash_pct) {
    kpis.push({ label: 'Cash/STIV', value: d.cash_pct.toFixed(1) + '%' });
  }
  if (d.er_waiver_gap_bps) {
    kpis.push({ label: addInfoIcon('Fee Waiver'), value: d.er_waiver_gap_bps.toFixed(0) + ' bps' });
  }
  document.getElementById('kpiStrip').innerHTML = kpis.map(k =>
    `<div class="kpi"><div class="kpi-label">${k.label}</div><div class="kpi-value">${k.value}</div></div>`
  ).join('');

  // Hero card — handle missing expense ratio gracefully
  const hasER = d.expense_ratio_pct != null;
  const statedER = hasER ? d.expense_ratio_pct.toFixed(2) : null;
  const trueER = d.true_cost_low_pct != null ? d.true_cost_low_pct.toFixed(2) : null;
  const trueHigh = d.true_cost_high_pct != null ? d.true_cost_high_pct.toFixed(2) : null;
  const hiddenLow = d.total_hidden_low != null ? d.total_hidden_low.toFixed(1) : null;
  const hiddenHigh = d.total_hidden_high != null ? d.total_hidden_high.toFixed(1) : null;

  const heroReported = document.getElementById('heroReported');
  const heroActual = document.getElementById('heroActual');
  const heroHidden = document.getElementById('heroHidden');
  heroReported.textContent = statedER || 'N/A';
  heroReported.parentElement.querySelector('.hero-unit').textContent = statedER ? '%' : '';
  heroActual.textContent = trueER && trueHigh ? trueER + ' – ' + trueHigh : 'N/A';
  heroActual.parentElement.querySelector('.hero-unit').textContent = trueER ? '%' : '';
  heroHidden.textContent = hiddenLow && hiddenHigh ? hiddenLow + ' – ' + hiddenHigh : (hiddenLow || 'N/A');
  heroHidden.parentElement.querySelector('.hero-unit').textContent = hiddenLow ? 'bps' : '';

  // Show hidden cost as % of stated ER
  const heroHiddenSub = document.getElementById('heroHiddenSub');
  if (hasER && d.total_hidden_low != null && d.total_hidden_high != null) {
    const erBps = d.expense_ratio_pct * 100;
    const midHidden = (d.total_hidden_low + d.total_hidden_high) / 2;
    const pctOfER = Math.round(midHidden / erBps * 100);
    heroHiddenSub.innerHTML = `+${pctOfER}% beyond stated expense ratio`;
  } else {
    heroHiddenSub.textContent = 'Trading costs not in the expense ratio';
  }

  // Conflict badge in hero card
  const heroConflictBadge = document.getElementById('heroConflictBadge');
  if (d.conflict_flags && d.conflict_flags.length > 0) {
    heroConflictBadge.style.display = 'inline-flex';
    heroConflictBadge.innerHTML = `⚠ ${d.conflict_flags.length} conflict${d.conflict_flags.length > 1 ? 's' : ''} flagged`;
  } else {
    heroConflictBadge.style.display = 'none';
  }

  // Show note if ER missing
  const heroSub = heroReported.closest('.hero-col').querySelector('.hero-sub');
  if (!hasER) heroSub.textContent = '497K not available for this fund';

  // X-Ray Tab: Render Conflict Highlights
  const conflictHighlightSection = document.getElementById('conflictHighlightSection');
  const noConflictSection = document.getElementById('noConflictSection');
  const conflictHighlightContent = document.getElementById('conflictHighlightContent');

  // Map conflict flags to structured data with descriptions
  const conflictDescriptions = {
    'soft_dollar': {
      label: 'Soft Dollar Arrangements',
      description: 'Fund uses inflated brokerage commissions in exchange for research services. The cost is buried in trading commissions, not disclosed separately.'
    },
    'affiliated_broker': {
      label: 'Affiliated Broker',
      description: 'Fund routes trades through a broker affiliated with the fund complex or investment adviser. Creates incentive misalignment on execution quality.'
    },
    'securities_lending': {
      label: 'Securities Lending Conflict',
      description: 'Fund lends portfolio securities to generate revenue. Income is split between fund and lending agent, creating risk of poor lending decisions.'
    }
  };

  // Parse conflict flags and render appropriately
  let parsedConflicts = [];
  if (d.conflict_flags && d.conflict_flags.length > 0) {
    // Simple flag strings from API—build a merged conflict list
    const flagText = d.conflict_flags.join(' ').toLowerCase();

    if (flagText.includes('soft dollar') || d.soft_dollar_indicator) {
      parsedConflicts.push(conflictDescriptions.soft_dollar);
    }
    if (flagText.includes('affiliated') || d.has_affiliated_broker) {
      parsedConflicts.push(conflictDescriptions.affiliated_broker);
    }
    if ((d.securities_lending && d.securities_lending.is_lending) || flagText.includes('lending')) {
      parsedConflicts.push(conflictDescriptions.securities_lending);
    }

    // If we didn't parse anything structured, use the raw flags
    if (parsedConflicts.length === 0) {
      parsedConflicts = d.conflict_flags.map(f => ({
        label: f.split(':')[0].trim(),
        description: f.split(':')[1]?.trim() || 'Structural conflict identified in fund operations.'
      }));
    }
  }

  if (parsedConflicts.length > 0) {
    conflictHighlightSection.style.display = 'block';
    noConflictSection.style.display = 'none';

    const conflictHtml = parsedConflicts.map(c => `
      <div class="conflict-flag-item">
        <div class="conflict-flag-icon">⚠</div>
        <div class="conflict-flag-text">
          <span class="conflict-flag-label">${c.label}</span>
          <span class="conflict-flag-description">${c.description}</span>
        </div>
      </div>
    `).join('');

    conflictHighlightContent.innerHTML = conflictHtml;
  } else {
    conflictHighlightSection.style.display = 'none';
    noConflictSection.style.display = 'block';
  }

  // Cost rows
  let rowsHtml = '';
  d.costs.forEach(c => {
    const isSub = c.label.includes('Soft Dollar');
    const valClass = c.tag === 'reported' ? 'reported' : c.tag === 'warning' ? 'warning' : 'estimated';
    const tagClass = c.tag === 'reported' ? 'tag-reported' : c.tag === 'warning' ? 'tag-warning' : 'tag-estimated';
    const tagLabel = c.tag === 'reported' ? 'SEC filing' : c.tag === 'warning' ? 'not disclosed' : 'estimated';
    const labelWithIcon = addInfoIcon(c.label);
    rowsHtml += `<div class="cost-row${isSub ? ' sub' : ''}" ${c.note ? `title="${c.note}"` : ''}>
      <span class="cost-label">${labelWithIcon}</span>
      <span class="cost-val ${valClass}">${c.value || '—'}</span>
      <span class="tag ${tagClass}">${tagLabel}</span>
    </div>`;
  });
  // Hidden cost total (sub-NAV drag only, excludes expense ratio)
  const hiddenTotalLabel = hiddenLow && hiddenHigh
    ? `${hiddenLow} – ${hiddenHigh} bps`
    : (hiddenLow ? `${hiddenLow} bps` : '—');
  rowsHtml += `<div class="cost-row total">
    <span class="cost-label" style="font-weight:700">Total Sub-NAV Drag</span>
    <span class="cost-val total">${hiddenTotalLabel}</span>
    <span class="tag tag-estimated">composite</span>
  </div>`;
  // True total cost (ER + hidden)
  if (trueER && trueHigh) {
    rowsHtml += `<div class="cost-row total" style="border-top:2px solid var(--accent)">
      <span class="cost-label" style="font-weight:700;color:var(--accent)">True Total Cost</span>
      <span class="cost-val total" style="color:var(--red)">${trueER} – ${trueHigh}%</span>
      <span class="tag tag-warning">ER + hidden</span>
    </div>`;
  }
  document.getElementById('costRows').innerHTML = rowsHtml;

  // Fee breakdown
  let feeHtml = '';
  if (d.fee_breakdown && d.fee_breakdown.length) {
    d.fee_breakdown.forEach(f => {
      feeHtml += `<div class="cost-row">
        <span class="cost-label">${f.label}</span>
        <span class="cost-val estimated">${f.pct.toFixed(3)}%</span>
        <span class="tag tag-estimated">prospectus</span>
      </div>`;
    });
    if (d.max_sales_load && d.max_sales_load > 0) {
      feeHtml += `<div class="cost-row">
        <span class="cost-label">Max Sales Load</span>
        <span class="cost-val warning">${d.max_sales_load.toFixed(2)}%</span>
        <span class="tag tag-warning">front-end</span>
      </div>`;
    }
  } else {
    feeHtml = '<div style="padding:12px 20px;color:var(--text-dim);font-size:13px">No fee breakdown available</div>';
  }
  document.getElementById('feeRows').innerHTML = feeHtml;

  // Asset bars
  let barsHtml = '';
  d.asset_mix.forEach(a => {
    const w = Math.min(a.pct, 100);
    barsHtml += `<div class="asset-row">
      <span class="asset-label">${a.label}</span>
      <div class="asset-track"><div class="asset-fill" style="width:${w}%;background:${a.color}"></div></div>
      <span class="asset-pct">${a.pct.toFixed(1)}%</span>
    </div>`;
  });
  document.getElementById('assetBars').innerHTML = barsHtml;

  // Notes
  if (d.data_notes && d.data_notes.length) {
    document.getElementById('notesPanel').style.display = '';
    document.getElementById('notesContent').innerHTML =
      d.data_notes.map(n => `<div class="note-item">${n}</div>`).join('');
  } else {
    document.getElementById('notesPanel').style.display = 'none';
  }

  // Deep Dive: Conflict Flags
  const flagsContainer = document.getElementById('conflictFlagsContainer');
  const flagsList = document.getElementById('conflictFlagsList');
  if (d.conflict_flags && d.conflict_flags.length > 0) {
    flagsContainer.style.display = 'block';
    flagsList.innerHTML = d.conflict_flags.map(f =>
      `<div style="padding:6px 0;border-bottom:1px solid rgba(239,68,68,0.15);color:var(--red);font-size:13px;line-height:1.5">
        <span style="margin-right:8px">&#9888;</span>${f}
      </div>`
    ).join('');
  } else {
    flagsContainer.style.display = 'none';
  }

  // Deep Dive: Commissions
  document.getElementById('aggCommissions').textContent = '$' + formatNumber(d.aggregate_commission_dollars || 0);

  // Deep Dive: Brokers
  let brokerHtml = '<div class="panel-header">Top Brokers by Commission</div>';
  if (d.top_brokers && d.top_brokers.length) {
    d.top_brokers.slice(0, 10).forEach(b => {
      const affLabel = b.is_affiliated ? ' (AFFILIATED)' : '';
      brokerHtml += `<div class="broker-row">
        <span class="broker-name">${b.name}${affLabel ? '<span class="broker-affiliated">' + affLabel + '</span>' : ''}</span>
        <span class="broker-commission">$${formatNumber(b.commission)}</span>
      </div>`;
    });
  }
  document.getElementById('brokersContainer').innerHTML = brokerHtml;

  // Deep Dive: Securities Lending
  let lendHtml = '<div class="panel-header">Securities Lending Program</div>';
  if (d.securities_lending) {
    const sl = d.securities_lending;
    lendHtml += `<div class="broker-row">
      <span class="broker-name">Active</span>
      <span style="color:${sl.is_lending ? 'var(--green)' : 'var(--text-dim)'};font-weight:700">${sl.is_lending ? 'Yes' : 'No'}</span>
    </div>`;
    if (sl.is_lending) {
      lendHtml += `<div class="broker-row">
        <span class="broker-name">Lending Agent</span>
        <span>${sl.agent_name}</span>
      </div>
      <div class="broker-row">
        <span class="broker-name">Agent Affiliated</span>
        <span style="color:${sl.is_agent_affiliated ? 'var(--red)' : 'var(--green)'};font-weight:700">${sl.is_agent_affiliated ? 'Yes' : 'No'}</span>
      </div>
      <div class="broker-row">
        <span class="broker-name">Net Income (Fund Share)</span>
        <span class="broker-commission">$${formatNumber(sl.net_income || 0)}</span>
      </div>`;
    }
  }
  document.getElementById('lendingContainer').innerHTML = lendHtml;

  // Deep Dive: Service Providers
  let provHtml = '';
  if (d.service_providers) {
    const sp = d.service_providers;
    const providers = [
      { role: 'Investment Adviser', name: sp.adviser },
      { role: 'Administrator', name: sp.administrator },
      { role: 'Custodian', name: sp.custodian },
      { role: 'Transfer Agent', name: sp.transfer_agent },
      { role: 'Auditor', name: sp.auditor },
    ];
    providers.forEach(p => {
      provHtml += `<div class="provider-card">
        <div class="provider-role">${p.role}</div>
        <div class="provider-name${!p.name ? ' na' : ''}">${p.name || 'Not Disclosed'}</div>
      </div>`;
    });
  }
  document.getElementById('providersContainer').innerHTML = provHtml;

  show('dash');

  // Reset findings strip and deep dive supplementary sections
  document.getElementById('findingsStrip').style.display = 'none';
  document.getElementById('findingsContent').innerHTML = '';
  document.getElementById('saiSection').style.display = 'none';
  document.getElementById('ncsrSection').style.display = 'none';
  document.getElementById('feeHistorySection').style.display = 'none';

  // Fetch supplementary data asynchronously (non-blocking)
  fetchSupplementaryData(d.ticker);
}

// ── Supplementary data: SAI, N-CSR, Fee History ──
// Design: One-line verdict chips appear on X-Ray tab.
//         Full detail renders in Deep Dive tab.

function addFinding(icon, label, verdict, severity) {
  const strip = document.getElementById('findingsStrip');
  const content = document.getElementById('findingsContent');
  strip.style.display = 'block';
  const idx = content.children.length;
  const chip = document.createElement('div');
  chip.className = `finding-chip finding-${severity}`;
  chip.style.animationDelay = `${idx * 0.1}s`;
  chip.innerHTML = `<span class="finding-icon">${icon}</span><span class="finding-label">${label}</span><span class="finding-verdict">${verdict}</span>`;
  content.appendChild(chip);
}

async function fetchSupplementaryData(ticker) {
  fetchSAI(ticker);
  fetchNCSR(ticker);
  fetchFeeHistory(ticker);
}

async function fetchSAI(ticker) {
  const section = document.getElementById('saiSection');
  const content = document.getElementById('saiContent');
  section.style.display = 'none';

  try {
    const resp = await fetch(`/api/sai/${ticker}`);
    if (!resp.ok) return;
    const data = await resp.json();

    // ── X-Ray verdict chips ──
    if (data.pm_compensation) {
      const pm = data.pm_compensation;
      if (pm.compensation_not_linked_to_fund_performance) {
        addFinding('💰', 'PM Comp:', 'Not linked to fund performance', 'red');
      } else if (pm.bonus_linked_to_performance) {
        addFinding('💰', 'PM Comp:', 'Tied to fund performance', 'green');
      } else if (pm.bonus_linked_to_aum) {
        addFinding('💰', 'PM Comp:', 'Tied to AUM, not returns', 'yellow');
      }
    }

    if (data.soft_dollar_info && data.soft_dollar_info.has_soft_dollar_arrangements) {
      addFinding('📋', 'SAI:', 'Soft dollar arrangements confirmed', 'red');
    }

    // ── Deep Dive detail ──
    section.style.display = 'block';
    let html = '';

    if (data.pm_compensation) {
      const pm = data.pm_compensation;
      html += `<div style="background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px 20px;margin-bottom:12px">
        <div style="font-weight:600;font-size:13px;color:var(--accent);margin-bottom:10px">Portfolio Manager Compensation</div>`;
      [
        { label: 'Base Salary', val: pm.has_base_salary },
        { label: 'Bonus', val: pm.has_bonus },
        { label: 'Equity Ownership', val: pm.has_equity_ownership },
        { label: 'Deferred Compensation', val: pm.has_deferred_comp },
      ].forEach(item => {
        const color = item.val ? 'var(--green)' : 'var(--text-dim)';
        html += `<div class="cost-row"><span class="cost-label">${item.label}</span><span style="color:${color};font-weight:600">${item.val ? 'Yes' : 'No'}</span></div>`;
      });
      html += `<div style="margin-top:8px;padding-top:8px;border-top:1px solid var(--border)">
        <div style="font-size:11px;color:var(--text-dim);margin-bottom:6px;text-transform:uppercase;letter-spacing:1px">Bonus Linked To</div>`;
      [
        { label: 'Fund Performance', val: pm.bonus_linked_to_performance, good: true },
        { label: 'Assets Under Management', val: pm.bonus_linked_to_aum, good: false },
        { label: 'Firm Profit', val: pm.bonus_linked_to_firm_profit, good: false },
      ].forEach(item => {
        if (item.val) {
          const color = item.good ? 'var(--green)' : 'var(--yellow)';
          html += `<div class="cost-row"><span class="cost-label">${item.label}</span><span style="color:${color};font-weight:600">Yes</span></div>`;
        }
      });
      if (pm.compensation_not_linked_to_fund_performance) {
        html += `<div class="cost-row"><span class="cost-label" style="color:var(--red)">NOT linked to fund performance</span><span style="color:var(--red);font-weight:600">⚠</span></div>`;
      }
      html += '</div></div>';
    }

    if (data.soft_dollar_info) {
      const sd = data.soft_dollar_info;
      html += `<div style="background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px 20px;margin-bottom:12px">
        <div style="font-weight:600;font-size:13px;color:var(--accent);margin-bottom:10px">Soft Dollar Arrangements</div>
        <div class="cost-row"><span class="cost-label">Soft Dollar Arrangements</span><span style="color:${sd.has_soft_dollar_arrangements ? 'var(--red)' : 'var(--green)'};font-weight:600">${sd.has_soft_dollar_arrangements ? 'Active' : 'None'}</span></div>
        <div class="cost-row"><span class="cost-label">Commission Sharing</span><span style="color:${sd.uses_commission_sharing ? 'var(--yellow)' : 'var(--text-dim)'};font-weight:600">${sd.uses_commission_sharing ? 'Yes' : 'No'}</span></div>
      </div>`;
    }

    if (data.commissions && data.commissions.length > 0) {
      html += `<div style="background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px 20px;margin-bottom:12px">
        <div style="font-weight:600;font-size:13px;color:var(--accent);margin-bottom:10px">SAI Commission History</div>`;
      data.commissions.forEach(c => {
        html += `<div style="font-weight:500;font-size:12px;color:var(--text);margin-top:8px;margin-bottom:4px">${c.fund_name}</div>`;
        Object.keys(c.annual_commissions).sort().reverse().forEach(yr => {
          html += `<div class="cost-row"><span class="cost-label">${yr}</span><span class="cost-val">$${formatNumber(c.annual_commissions[yr])}</span></div>`;
        });
      });
      html += '</div>';
    }

    if (data.conflict_flags && data.conflict_flags.length > 0) {
      html += `<div style="background:var(--red-dim);border:1px solid rgba(239,68,68,0.25);border-radius:12px;padding:16px 20px">`;
      data.conflict_flags.forEach(f => {
        html += `<div style="padding:4px 0;color:var(--red);font-size:13px"><span style="margin-right:8px">⚠</span>${f}</div>`;
      });
      html += '</div>';
    }

    content.innerHTML = html || '<div style="color:var(--text-dim);font-size:13px;padding:8px 0">No SAI data available.</div>';
  } catch (e) { /* SAI is supplementary */ }
}

async function fetchNCSR(ticker) {
  const section = document.getElementById('ncsrSection');
  const content = document.getElementById('ncsrContent');
  section.style.display = 'none';

  try {
    const resp = await fetch(`/api/ncsr/${ticker}`);
    if (!resp.ok) return;
    const data = await resp.json();

    // ── X-Ray verdict chip: commission trend ──
    if (data.commissions && data.commissions.length > 0) {
      const first = data.commissions[0];
      const years = Object.keys(first.annual_commissions).sort();
      if (years.length >= 2) {
        const oldest = first.annual_commissions[years[0]];
        const newest = first.annual_commissions[years[years.length - 1]];
        if (oldest > 0 && newest > 0) {
          const pctChange = ((newest - oldest) / oldest * 100).toFixed(0);
          if (newest > oldest * 1.1) {
            addFinding('📈', 'Commissions:', `Up ${pctChange}% over ${years.length} years`, 'red');
          } else if (newest < oldest * 0.9) {
            addFinding('📉', 'Commissions:', `Down ${Math.abs(pctChange)}% over ${years.length} years`, 'green');
          } else {
            addFinding('📊', 'Commissions:', `Stable over ${years.length} years`, 'neutral');
          }
        }
      }
    }

    // ── Deep Dive detail ──
    section.style.display = 'block';
    let html = `<div style="font-size:12px;color:var(--text-dim);margin-bottom:12px">Filing: ${data.filing_date} (${data.is_annual ? 'Annual N-CSR' : 'Semi-Annual N-CSRS'})</div>`;

    if (data.commissions && data.commissions.length > 0) {
      html += `<div style="background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px 20px;margin-bottom:12px">
        <div style="font-weight:600;font-size:13px;color:var(--accent);margin-bottom:10px">Audited Brokerage Commissions</div>`;
      data.commissions.forEach(c => {
        html += `<div style="font-weight:500;font-size:12px;color:var(--text);margin-top:8px;margin-bottom:4px">${c.fund_name}</div>`;
        Object.keys(c.annual_commissions).sort().reverse().forEach(yr => {
          html += `<div class="cost-row"><span class="cost-label">${yr}</span><span class="cost-val">$${formatNumber(c.annual_commissions[yr])}</span></div>`;
        });
        if (c.research_commissions && Object.keys(c.research_commissions).length > 0) {
          html += `<div style="margin-top:6px;font-size:11px;color:var(--yellow)">Research-Directed:</div>`;
          Object.keys(c.research_commissions).sort().reverse().forEach(yr => {
            html += `<div class="cost-row"><span class="cost-label" style="padding-left:12px">${yr} (research)</span><span class="cost-val" style="color:var(--yellow)">$${formatNumber(c.research_commissions[yr])}</span></div>`;
          });
        }
      });
      html += '</div>';
    }

    if (data.turnover && data.turnover.length > 0) {
      html += `<div style="background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px 20px;margin-bottom:12px">
        <div style="font-weight:600;font-size:13px;color:var(--accent);margin-bottom:10px">Historical Portfolio Turnover</div>`;
      data.turnover.forEach(t => {
        if (t.fund_name) html += `<div style="font-weight:500;font-size:12px;color:var(--text);margin-top:8px;margin-bottom:4px">${t.fund_name}</div>`;
        Object.keys(t.annual_turnover).sort().reverse().forEach(yr => {
          html += `<div class="cost-row"><span class="cost-label">${yr}</span><span class="cost-val">${t.annual_turnover[yr]}%</span></div>`;
        });
      });
      html += '</div>';
    }

    content.innerHTML = html || '<div style="color:var(--text-dim);font-size:13px;padding:8px 0">No N-CSR data available.</div>';
  } catch (e) { /* N-CSR is supplementary */ }
}

async function fetchFeeHistory(ticker) {
  const section = document.getElementById('feeHistorySection');
  const content = document.getElementById('feeHistoryContent');
  section.style.display = 'none';

  try {
    const resp = await fetch(`/api/fee-history/${ticker}`);
    if (!resp.ok) return;
    const data = await resp.json();
    if (!data.snapshots || data.snapshots.length === 0) return;

    // ── X-Ray verdict chip ──
    if (data.has_changes && data.changes.length > 0) {
      const net = data.net_change_bps;
      if (net > 0) {
        addFinding('🔺', 'Fees:', `Quietly raised +${net.toFixed(1)} bps`, 'red');
      } else {
        addFinding('🔻', 'Fees:', `Lowered ${net.toFixed(1)} bps`, 'green');
      }
    } else if (data.snapshots.length >= 2) {
      addFinding('✓', 'Fees:', `Stable across ${data.snapshots.length} filings`, 'green');
    }

    // ── Deep Dive detail ──
    section.style.display = 'block';
    let html = '';

    if (data.has_changes && data.changes.length > 0) {
      html += `<div style="font-weight:600;font-size:13px;color:var(--red);margin-bottom:10px">Fee Changes Detected</div>`;
      data.changes.forEach(c => {
        const arrow = c.direction === 'increase' ? '↑' : '↓';
        const color = c.direction === 'increase' ? 'var(--red)' : 'var(--green)';
        const sign = c.change_bps > 0 ? '+' : '';
        html += `<div class="cost-row">
          <span class="cost-label">${c.field_label}</span>
          <span class="cost-val" style="color:${color}">${arrow} ${sign}${c.change_bps.toFixed(1)} bps</span>
        </div>
        <div style="font-size:11px;color:var(--text-dim);padding:0 0 6px 0">${c.old_value.toFixed(3)}% → ${c.new_value.toFixed(3)}% (${c.old_filing_date} → ${c.new_filing_date})</div>`;
      });
      html += `<div style="margin-top:8px;padding-top:8px;border-top:1px solid var(--border);font-weight:600;font-size:13px">
        Net change: <span style="color:${data.net_change_bps > 0 ? 'var(--red)' : 'var(--green)'}">${data.net_change_bps > 0 ? '+' : ''}${data.net_change_bps.toFixed(1)} bps</span>
      </div>`;
    } else {
      html += `<div style="color:var(--green);font-size:13px">✓ No fee changes detected across ${data.snapshots.length} recent filings.</div>`;
    }

    html += `<div style="margin-top:12px;padding-top:12px;border-top:1px solid var(--border)">
      <div style="font-size:11px;color:var(--text-dim);text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">Filing Timeline</div>`;
    data.snapshots.forEach(s => {
      const er = s.effective_expense_ratio;
      html += `<div class="cost-row">
        <span class="cost-label">${s.filing_date} <span style="color:var(--text-dim)">(${s.form_type})</span></span>
        <span class="cost-val">${er ? er.toFixed(3) + '%' : 'N/A'}</span>
      </div>`;
    });
    html += '</div>';

    content.innerHTML = html;
  } catch (e) { /* Fee history is supplementary */ }
}

function formatNumber(n) {
  return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

function formatShort(n) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
  if (n >= 1000) return (n / 1000).toFixed(0) + 'K';
  return n.toFixed(0);
}

// ── Worst Offender Leaderboard ──

let currentLeaderboardSort = 'hidden_cost_mid_bps';

async function loadLeaderboard(sortBy) {
  sortBy = sortBy || currentLeaderboardSort;
  currentLeaderboardSort = sortBy;

  try {
    const resp = await fetch(`/api/leaderboard?sort_by=${sortBy}&limit=25`);
    if (!resp.ok) return;
    const data = await resp.json();
    renderLeaderboard(data.entries, data.stats);
  } catch (e) {
    // Silently fail — leaderboard is supplementary
  }
}

function renderLeaderboard(entries, stats) {
  const section = document.getElementById('leaderboardSection');
  const statsEl = document.getElementById('leaderboardStats');
  const tableEl = document.getElementById('leaderboardTable');

  if (!entries || entries.length === 0) {
    section.style.display = 'block';
    statsEl.innerHTML = '';
    tableEl.innerHTML = `
      <div class="leaderboard-empty">
        <div class="leaderboard-empty-icon">&#9760;</div>
        <div class="leaderboard-empty-text">The board is empty. Be the first to expose a fund.</div>
        <div class="leaderboard-empty-sub">Look up any ticker above to add it to the Worst Offenders list.</div>
      </div>
    `;
    return;
  }

  section.style.display = 'block';

  // Stats bar
  statsEl.innerHTML = `
    <div class="leaderboard-stat">
      <div class="leaderboard-stat-value">${stats.total_funds}</div>
      <div class="leaderboard-stat-label">Funds Exposed</div>
    </div>
    <div class="leaderboard-stat">
      <div class="leaderboard-stat-value">${stats.total_lookups}</div>
      <div class="leaderboard-stat-label">Total Lookups</div>
    </div>
    ${stats.avg_hidden_bps ? `
    <div class="leaderboard-stat">
      <div class="leaderboard-stat-value">${stats.avg_hidden_bps}</div>
      <div class="leaderboard-stat-label">Avg Hidden (bps)</div>
    </div>` : ''}
  `;

  // Update sort button states
  document.querySelectorAll('.leaderboard-sort-btn').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-sort') === currentLeaderboardSort);
  });

  // Table
  let html = `
    <div class="lb-row lb-row-header">
      <span>#</span>
      <span>Ticker</span>
      <span>Fund</span>
      <span style="text-align:right">Hidden Cost</span>
      <span style="text-align:right">True Cost</span>
      <span class="lb-grade" style="font-size:10px">Grade</span>
      <span class="lb-lookups" style="font-size:10px">Looks</span>
    </div>
  `;

  entries.forEach((entry, i) => {
    const rank = i + 1;
    const rankClass = rank <= 3 ? ` lb-rank-${rank}` : '';
    const hiddenText = entry.hidden_cost_low_bps !== null
      ? `${entry.hidden_cost_low_bps.toFixed(0)}–${entry.hidden_cost_high_bps.toFixed(0)}`
      : '—';
    const trueText = entry.true_cost_mid_bps
      ? `${(entry.true_cost_mid_bps / 100).toFixed(2)}%`
      : '—';

    html += `
      <div class="lb-row" onclick="runAnalysis('${entry.ticker}')">
        <span class="lb-rank${rankClass}">${rank}</span>
        <span class="lb-ticker">${entry.ticker}</span>
        <span class="lb-name" title="${entry.name}">${entry.name}</span>
        <span class="lb-hidden">${hiddenText} bps</span>
        <span class="lb-true-cost">${trueText}</span>
        <span class="lb-grade ${entry.grade}">${entry.grade}</span>
        <span class="lb-lookups">${entry.lookup_count}</span>
      </div>
    `;
  });

  tableEl.innerHTML = html;
}

// Sort button click handlers
document.querySelectorAll('.leaderboard-sort-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const sortBy = btn.getAttribute('data-sort');
    loadLeaderboard(sortBy);
  });
});

// Load leaderboard on page load
document.addEventListener('DOMContentLoaded', () => {
  loadLeaderboard();
});

// Refresh leaderboard after each analysis completes
function refreshLeaderboardAfterAnalysis() {
  setTimeout(() => loadLeaderboard(), 500);
}

// Comparison feature
const compareInput = document.getElementById('compareInput');
if (compareInput) {
  compareInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      const tickers = compareInput.value.trim();
      if (tickers) runComparison(tickers);
    }
  });
}

async function runComparison(tickerString) {
  const tickers = tickerString.split(',').map(t => t.trim().toUpperCase()).filter(t => t);

  if (tickers.length < 2) {
    showStyledError('Invalid Input', 'Please provide at least 2 fund tickers separated by commas.', 'Example: AGTHX, VFINX, FCNTX');
    return;
  }

  if (tickers.length > 5) {
    showStyledError('Too Many Funds', 'Maximum 5 funds for comparison.');
    return;
  }

  show('loading');
  document.getElementById('loadTicker').textContent = tickers.join(', ');
  animateStages();

  try {
    const resp = await fetch(`/api/compare?tickers=${encodeURIComponent(tickers.join(','))}`);
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${resp.status}`);
    }
    const data = await resp.json();
    clearInterval(stageTimer);
    ['s1','s2','s3','s4'].forEach(id => document.getElementById(id).className = 'stage done');
    setTimeout(() => renderComparison(data.results, data.errors), 400);
  } catch (e) {
    clearInterval(stageTimer);
    showStyledError('Comparison Failed', e.message);
  }
}

function renderComparison(results, errors) {
  if (!results || results.length === 0) {
    const errorDetail = errors && errors.length > 0
      ? `Could not retrieve: ${errors.map(e => e.ticker).join(', ')}`
      : 'Could not retrieve data for the requested funds.';
    showStyledError('No Data Available', errorDetail);
    return;
  }

  // Find lowest and highest true cost
  let lowestTrueCost = Infinity;
  let highestTrueCost = -Infinity;
  let lowestTicker = '';
  let highestTicker = '';

  results.forEach(fund => {
    const trueCostHigh = fund.true_cost_high_bps || 0;
    if (trueCostHigh < lowestTrueCost) {
      lowestTrueCost = trueCostHigh;
      lowestTicker = fund.ticker;
    }
    if (trueCostHigh > highestTrueCost) {
      highestTrueCost = trueCostHigh;
      highestTicker = fund.ticker;
    }
  });

  // Render cards
  let cardsHtml = '';
  results.forEach(fund => {
    const isLowest = fund.ticker === lowestTicker;
    const isHighest = fund.ticker === highestTicker;
    const cardClass = isLowest ? 'lowest-cost' : isHighest ? 'highest-cost' : '';
    const costBadge = isLowest ? 'LOWEST COST' : isHighest ? 'HIGHEST COST' : '';

    const expenseRatio = fund.expense_ratio_pct ? fund.expense_ratio_pct.toFixed(3) : 'N/A';
    const trueLow = fund.true_cost_low_pct ? fund.true_cost_low_pct.toFixed(3) : 'N/A';
    const trueHigh = fund.true_cost_high_pct ? fund.true_cost_high_pct.toFixed(3) : 'N/A';
    const hiddenLow = fund.total_hidden_low ? fund.total_hidden_low.toFixed(1) : 'N/A';
    const hiddenHigh = fund.total_hidden_high ? fund.total_hidden_high.toFixed(1) : 'N/A';
    const turnover = fund.portfolio_turnover ? fund.portfolio_turnover.toFixed(1) : 'N/A';
    const holdings = fund.holdings_count || 'N/A';
    const netAssets = fund.net_assets_display || 'N/A';

    // Dollar impact: show savings vs highest-cost fund
    let dollarImpactHtml = '';
    if (fund.dollar_impact && fund.dollar_impact.true_cost_high !== null && !isHighest) {
      const highestFund = results.find(f => f.ticker === highestTicker);
      if (highestFund && highestFund.dollar_impact && highestFund.dollar_impact.true_cost_high !== null) {
        const saving = highestFund.dollar_impact.true_cost_high - fund.dollar_impact.true_cost_high;
        if (saving > 0) {
          dollarImpactHtml = `
            <div class="comp-dollar-impact">
              <div class="comp-dollar-impact-label">Saves vs highest-cost fund (20yr)</div>
              <div class="comp-dollar-impact-value">+${formatShort(saving)}</div>
            </div>`;
        }
      }
    }

    cardsHtml += `
      <div class="comp-card ${cardClass}">
        ${costBadge ? `<div class="comp-cost-badge">${costBadge}</div>` : ''}
        <div class="comp-card-header">
          <div class="comp-card-ticker">${fund.ticker}</div>
          <div class="comp-card-name">${fund.name}</div>
        </div>
        <div class="comp-metric">
          <span class="comp-metric-label">Expense Ratio</span>
          <span class="comp-metric-value">${expenseRatio}%</span>
        </div>
        <div class="comp-metric">
          <span class="comp-metric-label">True Total Cost Range</span>
          <span class="comp-metric-value highlight">${trueLow}% – ${trueHigh}%</span>
        </div>
        <div class="comp-metric">
          <span class="comp-metric-label">Hidden Costs</span>
          <span class="comp-metric-value">${hiddenLow} – ${hiddenHigh} bps</span>
        </div>
        <div class="comp-metric">
          <span class="comp-metric-label">Portfolio Turnover</span>
          <span class="comp-metric-value">${turnover}%</span>
        </div>
        <div class="comp-metric">
          <span class="comp-metric-label">Holdings</span>
          <span class="comp-metric-value">${holdings}</span>
        </div>
        <div class="comp-metric">
          <span class="comp-metric-label">Net Assets</span>
          <span class="comp-metric-value">${netAssets}</span>
        </div>
        ${dollarImpactHtml}
      </div>`;
  });

  document.getElementById('comparisonCardsContainer').innerHTML = cardsHtml;
  show('compare');
}
