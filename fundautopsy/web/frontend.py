"""Inline HTML dashboard — single-page app served by FastAPI."""

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Fund Autopsy — Total Cost of Ownership Analyzer</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #08090d;
  --surface: #0f1117;
  --surface-2: #161923;
  --surface-3: #1c2030;
  --border: #232838;
  --border-light: #2d3348;
  --text: #e8e6e3;
  --text-dim: #8b90a0;
  --text-muted: #555b6e;
  --accent: #c9a84c;
  --accent-dim: rgba(201,168,76,0.15);
  --green: #4ade80;
  --green-dim: rgba(74,222,128,0.12);
  --red: #ef4444;
  --red-dim: rgba(239,68,68,0.10);
  --yellow: #fbbf24;
  --yellow-dim: rgba(251,191,36,0.10);
  --blue: #60a5fa;
  --purple: #a78bfa;
}

* { margin:0; padding:0; box-sizing:border-box; }

body {
  background: var(--bg);
  color: var(--text);
  font-family: 'Inter', -apple-system, sans-serif;
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
}

/* ── Top bar ── */
.topbar {
  position: sticky; top: 0; z-index: 100;
  background: rgba(8,9,13,0.85);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border);
  padding: 0 32px;
  height: 56px;
  display: flex;
  align-items: center;
  gap: 20px;
}
.topbar-brand {
  display: flex; align-items: center; gap: 10px;
  font-weight: 800; font-size: 15px; letter-spacing: 0.5px;
  color: var(--text);
  flex-shrink: 0;
}
.topbar-icon {
  width: 28px; height: 28px;
  background: var(--accent);
  border-radius: 5px;
  display: flex; align-items: center; justify-content: center;
  font-weight: 900; font-size: 13px; color: #08090d;
}
.topbar-sub {
  font-size: 11px;
  color: var(--text-muted);
  letter-spacing: 1.5px;
  text-transform: uppercase;
  font-weight: 600;
}

/* ── Home Button ── */
.home-btn {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-dim);
  cursor: pointer;
  padding: 8px 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  flex-shrink: 0;
}
.home-btn:hover {
  color: var(--accent);
  border-color: var(--accent);
  background: var(--accent-dim);
}

/* ── Search ── */
.search-wrap {
  flex: 1;
  max-width: 480px;
  position: relative;
}
.search-input {
  width: 100%;
  height: 38px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text);
  font-family: 'JetBrains Mono', monospace;
  font-size: 14px;
  font-weight: 600;
  padding: 0 16px 0 40px;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
  text-transform: uppercase;
  letter-spacing: 1px;
}
.search-input::placeholder {
  text-transform: none;
  letter-spacing: 0;
  font-family: 'Inter', sans-serif;
  font-weight: 400;
  color: var(--text-muted);
}
.search-input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-dim);
}
.search-icon {
  position: absolute; left: 13px; top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted); font-size: 14px;
  pointer-events: none;
}
.search-hint {
  position: absolute; right: 12px; top: 50%;
  transform: translateY(-50%);
  font-size: 10px;
  color: var(--text-muted);
  background: var(--surface-3);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Inter', sans-serif;
  letter-spacing: 0;
  text-transform: none;
}

/* ── Layout ── */
.main {
  max-width: 1200px;
  margin: 0 auto;
  padding: 32px 24px 80px;
}

/* ── Welcome state ── */
.welcome {
  text-align: center;
  padding: 120px 24px;
  max-width: 560px;
  margin: 0 auto;
}
.welcome h1 {
  font-size: 42px;
  font-weight: 900;
  letter-spacing: -1px;
  line-height: 1.1;
  margin-bottom: 16px;
}
.welcome h1 span { color: var(--accent); }
.welcome p {
  font-size: 17px;
  color: var(--text-dim);
  line-height: 1.6;
  margin-bottom: 32px;
}
.welcome-examples {
  display: flex;
  gap: 10px;
  justify-content: center;
  flex-wrap: wrap;
}
.example-chip {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 16px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  font-weight: 600;
  color: var(--accent);
  cursor: pointer;
  transition: all 0.15s;
}
.example-chip:hover {
  background: var(--accent-dim);
  border-color: var(--accent);
}

/* ── Loading ── */
.loading {
  text-align: center;
  padding: 100px 24px;
}
.loading-spinner {
  width: 48px; height: 48px;
  border: 3px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto 24px;
}
@keyframes spin { to { transform: rotate(360deg); } }
.loading-stages {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  margin-top: 24px;
}
.stage {
  font-size: 13px;
  color: var(--text-muted);
  transition: color 0.3s;
  display: flex; align-items: center; gap: 8px;
}
.stage.active { color: var(--accent); }
.stage.done { color: var(--green); }
.stage-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--text-muted);
}
.stage.active .stage-dot { background: var(--accent); box-shadow: 0 0 8px var(--accent); }
.stage.done .stage-dot { background: var(--green); }

/* ── Error ── */
.error-msg {
  text-align: center;
  padding: 80px 24px;
  color: var(--red);
  font-size: 16px;
}
.error-msg p { margin-top: 8px; color: var(--text-dim); font-size: 14px; }

/* ── Dashboard ── */
.dash { display: none; }
.dash.visible { display: block; animation: fadeUp 0.4s ease; }

@keyframes fadeUp {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ── Tab bar ── */
.tab-bar {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--border);
  margin-bottom: 32px;
}
.tab-btn {
  background: none;
  border: none;
  color: var(--text-dim);
  font-size: 14px;
  font-weight: 600;
  padding: 16px 24px;
  cursor: pointer;
  transition: color 0.2s, border-bottom-color 0.2s;
  border-bottom: 2px solid transparent;
  font-family: 'Inter', sans-serif;
  letter-spacing: 0.5px;
}
.tab-btn:hover {
  color: var(--accent);
}
.tab-btn.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}

.tab-content {
  display: none;
  animation: fadeUp 0.3s ease;
}
.tab-content.active {
  display: block;
}

/* Fund header */
.fund-header {
  margin-bottom: 32px;
}
.fund-title {
  font-size: 32px;
  font-weight: 800;
  letter-spacing: -0.5px;
  line-height: 1.15;
}
.fund-title .ticker {
  font-family: 'JetBrains Mono', monospace;
  color: var(--accent);
  font-weight: 700;
}
.fund-family { font-size: 15px; color: var(--text-dim); margin-top: 4px; }

/* KPI strip */
.kpi-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  margin-bottom: 28px;
}
.kpi {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 18px 20px;
}
.kpi-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  color: var(--text-muted);
  font-weight: 700;
  margin-bottom: 6px;
}
.kpi-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 20px;
  font-weight: 700;
}
.kpi-sub { font-size: 12px; color: var(--text-dim); margin-top: 2px; }

/* Hero card */
.hero-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 40px;
  margin-bottom: 28px;
  position: relative;
  overflow: hidden;
}
.hero-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--accent), var(--yellow), var(--red));
}
.hero-split {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 32px;
}
.hero-col {
  text-align: center;
  padding: 8px 0;
}
.hero-col:nth-child(2) {
  border-left: 1px solid var(--border);
  border-right: 1px solid var(--border);
}
.hero-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 2px;
  color: var(--text-muted);
  font-weight: 700;
  margin-bottom: 12px;
}
.hero-number {
  font-family: 'JetBrains Mono', monospace;
  font-size: 44px;
  font-weight: 700;
  line-height: 1;
  margin-bottom: 8px;
}
.hero-col:nth-child(1) .hero-number {
  color: var(--green);
}
.hero-col:nth-child(2) .hero-number {
  color: var(--yellow);
}
.hero-col:nth-child(3) .hero-number {
  color: var(--red);
}
.hero-unit { font-size: 18px; color: var(--text-dim); }
.hero-sub {
  font-size: 13px;
  color: var(--text-dim);
  margin-top: 16px;
  line-height: 1.5;
}

/* Two-column layout */
.dash-grid {
  display: grid;
  grid-template-columns: 1fr 340px;
  gap: 20px;
  align-items: start;
}

/* Panel */
.panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
}
.panel-header {
  padding: 16px 20px;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 2px;
  color: var(--text-muted);
  font-weight: 700;
  background: var(--surface-2);
  border-bottom: 1px solid var(--border);
}
.cost-row {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 16px;
  padding: 15px 20px;
  border-bottom: 1px solid var(--border);
  align-items: center;
}
.cost-row:last-child { border-bottom: none; }
.cost-row.sub { padding-left: 36px; }
.cost-row.sub .cost-label { color: var(--text-dim); font-size: 13px; }
.cost-row.total {
  background: var(--surface-2);
  border-top: 2px solid var(--border-light);
  border-bottom: none;
}
.cost-label { font-size: 14px; font-weight: 500; }
.cost-val {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 600;
  font-size: 14px;
  text-align: right;
}
.cost-val.reported { color: var(--green); }
.cost-val.estimated { color: var(--yellow); }
.cost-val.warning { color: var(--red); font-weight: 700; }
.cost-val.total { color: var(--yellow); font-size: 16px; }

.tag {
  font-size: 9px;
  text-transform: uppercase;
  letter-spacing: 1px;
  padding: 3px 7px;
  border-radius: 4px;
  font-weight: 700;
  white-space: nowrap;
}
.tag-reported { background: var(--green-dim); color: var(--green); }
.tag-estimated { background: var(--yellow-dim); color: var(--yellow); }
.tag-warning { background: var(--red-dim); color: var(--red); }

/* Sidebar */
.sidebar-section { margin-bottom: 20px; }
.sidebar-section:last-child { margin-bottom: 0; }

.asset-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 20px;
}
.asset-label {
  width: 70px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-dim);
  flex-shrink: 0;
}
.asset-track {
  flex: 1;
  height: 18px;
  background: var(--surface-2);
  border-radius: 3px;
  overflow: hidden;
}
.asset-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.6s ease;
}
.asset-pct {
  width: 52px;
  text-align: right;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

/* Notes */
.notes {
  padding: 16px 20px;
}
.note-item {
  font-size: 12px;
  color: var(--text-dim);
  padding: 3px 0 3px 14px;
  position: relative;
  line-height: 1.5;
}
.note-item::before {
  content: '\2022';
  position: absolute;
  left: 0;
  color: var(--text-muted);
}

/* ── Dollar Impact Tab ── */
.calc-section {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 24px;
}
.calc-title {
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  color: var(--text-muted);
  margin-bottom: 20px;
}
.calc-inputs {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
}
.calc-input-group {
  display: flex;
  flex-direction: column;
}
.calc-input-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-dim);
  margin-bottom: 8px;
}
.calc-input-row {
  display: flex;
  gap: 8px;
}
.calc-input {
  flex: 1;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text);
  font-family: 'JetBrains Mono', monospace;
  font-size: 14px;
  font-weight: 600;
  padding: 10px 12px;
  outline: none;
  transition: border-color 0.2s;
}
.calc-input:focus {
  border-color: var(--accent);
}
.calc-unit {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 50px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-dim);
}

.scenarios-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
  margin-bottom: 28px;
}
.scenario-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px;
}
.scenario-title {
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  color: var(--text-muted);
  margin-bottom: 16px;
}
.scenario-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 28px;
  font-weight: 700;
  color: var(--accent);
  margin-bottom: 8px;
}
.scenario-sub {
  font-size: 12px;
  color: var(--text-dim);
  line-height: 1.5;
}

.impact-card {
  background: var(--surface);
  border: 2px solid var(--border);
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 28px;
  text-align: center;
}
.impact-title {
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  color: var(--text-muted);
  margin-bottom: 12px;
}
.impact-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 36px;
  font-weight: 700;
  color: var(--red);
  line-height: 1;
}
.impact-sub {
  font-size: 12px;
  color: var(--text-dim);
  margin-top: 12px;
}

.bars-chart {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 24px;
}
.bars-title {
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  color: var(--text-muted);
  margin-bottom: 20px;
}
.bars-container {
  display: flex;
  gap: 20px;
  align-items: flex-end;
  height: 220px;
}
.bar-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
.bar {
  width: 100%;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 6px;
  transition: all 0.3s ease;
  position: relative;
  min-height: 20px;
}
.bar.scenario-0 { background: var(--green); border-color: var(--green); }
.bar.scenario-1 { background: var(--yellow); border-color: var(--yellow); }
.bar.scenario-2 { background: var(--red); border-color: var(--red); }
.bar-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-dim);
  text-align: center;
}
.bar-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  font-weight: 700;
  color: var(--accent);
  text-align: center;
}

/* ── Deep Dive Tab ── */
.section-title {
  font-size: 16px;
  font-weight: 700;
  margin-top: 32px;
  margin-bottom: 16px;
}
.section-title:first-child { margin-top: 0; }
.broker-list {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
}
.broker-row {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 16px;
  padding: 15px 20px;
  border-bottom: 1px solid var(--border);
  align-items: center;
}
.broker-row:last-child { border-bottom: none; }
.broker-name { font-size: 14px; font-weight: 500; }
.broker-affiliated { font-size: 11px; color: var(--red); font-weight: 700; }
.broker-commission {
  font-family: 'JetBrains Mono', monospace;
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  text-align: right;
}

.provider-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 16px;
}
.provider-role {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  color: var(--text-muted);
  font-weight: 700;
  margin-bottom: 8px;
}
.provider-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
}
.provider-name.na { color: var(--text-dim); }

/* ── About Tab ── */
.about-section {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 24px;
}
.about-title {
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 12px;
}
.about-text {
  font-size: 14px;
  color: var(--text-dim);
  line-height: 1.6;
  margin-bottom: 12px;
}
.about-text:last-child { margin-bottom: 0; }
.about-list {
  margin: 12px 0;
  padding-left: 20px;
}
.about-list li {
  font-size: 14px;
  color: var(--text-dim);
  line-height: 1.6;
  margin-bottom: 8px;
}
.reference-link {
  color: var(--accent);
  text-decoration: none;
  transition: color 0.2s;
}
.reference-link:hover {
  color: var(--yellow);
}

/* Footer */
.footer {
  margin-top: 40px;
  padding-top: 24px;
  border-top: 1px solid var(--border);
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
}
.footer-left {
  font-size: 11px;
  color: var(--text-muted);
  line-height: 1.8;
}
.footer-right { text-align: right; }
.footer-brand {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--text-dim);
}
.footer-url {
  font-size: 11px;
  color: var(--text-muted);
  font-family: 'JetBrains Mono', monospace;
}

/* Responsive */
@media (max-width: 900px) {
  .dash-grid { grid-template-columns: 1fr; }
  .hero-split { grid-template-columns: 1fr; gap: 16px; }
  .hero-col:nth-child(2) { border-left: none; border-right: none; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); padding: 16px 0; }
  .scenarios-grid { grid-template-columns: 1fr; }
  .bars-container { flex-wrap: wrap; height: auto; }
  .topbar { padding: 0 16px; }
  .fund-title { font-size: 24px; }
  .hero-number { font-size: 36px; }
  .kpi-strip { grid-template-columns: repeat(2, 1fr); }
  .tab-btn { padding: 12px 16px; font-size: 13px; }
}
@media (max-width: 600px) {
  .main { padding: 16px 12px 60px; }
  .tab-bar { gap: 0; margin-bottom: 24px; }
  .tab-btn { padding: 12px 12px; font-size: 12px; }
  .hero-split { gap: 20px; }
  .kpi-strip { grid-template-columns: 1fr; }
  .calc-inputs { grid-template-columns: 1fr; }
  .hero-card { padding: 24px; }
  .hero-number { font-size: 28px; }
  .scenario-value { font-size: 22px; }
}

/* ── Comparison view ── */
.compare-prompt {
  margin-top: 32px;
}
.compare-prompt > div:first-child {
  font-size: 13px;
  color: var(--text-dim);
  margin-bottom: 8px;
}
.compare-input-wrap {
  display: flex;
  gap: 8px;
}

.comparison-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}
.comparison-title {
  font-size: 28px;
  font-weight: 700;
  color: var(--text);
}
.comparison-reset-btn {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-dim);
  cursor: pointer;
  padding: 10px 16px;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.2s;
}
.comparison-reset-btn:hover {
  color: var(--accent);
  border-color: var(--accent);
  background: var(--accent-dim);
}

.comparison-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 20px;
  margin-bottom: 32px;
}

.comp-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px;
  position: relative;
  transition: all 0.3s;
}
.comp-card.lowest-cost {
  border-color: var(--green);
  box-shadow: 0 0 20px rgba(74, 222, 128, 0.15);
}
.comp-card.highest-cost {
  border-color: var(--red);
  opacity: 0.85;
}

.comp-card-header {
  margin-bottom: 16px;
  border-bottom: 1px solid var(--border);
  padding-bottom: 12px;
}
.comp-card-ticker {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  font-size: 15px;
  color: var(--accent);
  margin-bottom: 4px;
}
.comp-card-name {
  font-size: 13px;
  color: var(--text-dim);
  line-height: 1.4;
}

.comp-cost-badge {
  display: inline-block;
  position: absolute;
  top: 12px;
  right: 12px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.8px;
  text-transform: uppercase;
  padding: 4px 8px;
  border-radius: 4px;
  background: var(--green-dim);
  color: var(--green);
}
.comp-card.highest-cost .comp-cost-badge {
  background: var(--red-dim);
  color: var(--red);
}

.comp-metric {
  margin-bottom: 12px;
  font-size: 13px;
}
.comp-metric-label {
  color: var(--text-dim);
  display: block;
  margin-bottom: 2px;
  font-weight: 500;
}
.comp-metric-value {
  color: var(--text);
  font-weight: 600;
  font-size: 14px;
}
.comp-metric-value.highlight {
  color: var(--accent);
}

.comp-dollar-impact {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
  margin-top: 16px;
  font-size: 12px;
  text-align: center;
}
.comp-dollar-impact-label {
  color: var(--text-dim);
  display: block;
  margin-bottom: 4px;
}
.comp-dollar-impact-value {
  color: var(--green);
  font-weight: 700;
  font-size: 14px;
  font-family: 'JetBrains Mono', monospace;
}
.comp-card.highest-cost .comp-dollar-impact-value {
  color: var(--text-dim);
}

@media (max-width: 900px) {
  .comparison-cards {
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  }
}
@media (max-width: 600px) {
  .comparison-cards {
    grid-template-columns: 1fr;
  }
  .comparison-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }
  .comparison-reset-btn {
    align-self: flex-start;
  }
}
</style>
</head>
<body>

<div class="topbar">
  <div class="topbar-brand">
    <div class="topbar-icon">☠</div>
    Fund Autopsy
  </div>
  <div class="topbar-sub">Tombstone Research</div>
  <div class="search-wrap">
    <span class="search-icon">&#128269;</span>
    <input class="search-input" id="tickerInput" type="text"
           placeholder="Enter fund ticker..." maxlength="6" autocomplete="off" spellcheck="false">
    <span class="search-hint">Enter &#8629;</span>
  </div>
  <button class="home-btn" id="homeBtn" onclick="goHome()" title="Back to home" style="display:none">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
  </button>
</div>

<div class="main">
  <!-- Welcome -->
  <div id="welcome" class="welcome">
    <h1>X-ray your <span>mutual fund</span></h1>
    <p>See the hidden trading costs your fund company doesn't show you.
       Brokerage commissions, soft dollars, bid-ask spreads, and market impact
       — pulled directly from SEC filings.</p>
    <div class="welcome-examples">
      <div class="example-chip" onclick="runAnalysis('AGTHX')">AGTHX</div>
      <div class="example-chip" onclick="runAnalysis('VFINX')">VFINX</div>
      <div class="example-chip" onclick="runAnalysis('FCNTX')">FCNTX</div>
      <div class="example-chip" onclick="runAnalysis('DODGX')">DODGX</div>
      <div class="example-chip" onclick="runAnalysis('FFFHX')">FFFHX</div>
    </div>
    <div class="compare-prompt">
      <div>Compare funds side-by-side</div>
      <div class="compare-input-wrap">
        <input class="search-input" id="compareInput" type="text"
               placeholder="e.g. AGTHX, VFINX, FCNTX" autocomplete="off" spellcheck="false"
               style="max-width:400px;width:100%;">
      </div>
    </div>
  </div>

  <!-- Loading -->
  <div id="loading" class="loading" style="display:none">
    <div class="loading-spinner"></div>
    <div style="font-size:18px;font-weight:600;margin-bottom:4px">Analyzing <span id="loadTicker" style="color:var(--accent);font-family:'JetBrains Mono',monospace"></span></div>
    <div style="font-size:13px;color:var(--text-dim)">Pulling live SEC EDGAR data...</div>
    <div class="loading-stages" id="stages">
      <div class="stage active" id="s1"><span class="stage-dot"></span> Resolving ticker via SEC</div>
      <div class="stage" id="s2"><span class="stage-dot"></span> Retrieving N-CEN filing</div>
      <div class="stage" id="s3"><span class="stage-dot"></span> Parsing N-PORT holdings</div>
      <div class="stage" id="s4"><span class="stage-dot"></span> Computing hidden costs</div>
    </div>
  </div>

  <!-- Error -->
  <div id="error" class="error-msg" style="display:none"></div>

  <!-- Comparison Results -->
  <div id="compare" style="display:none">
    <div class="comparison-header">
      <div class="comparison-title">Fund Comparison</div>
      <button class="comparison-reset-btn" onclick="goHome()">Compare Different Funds</button>
    </div>
    <div id="comparisonCardsContainer" class="comparison-cards"></div>
  </div>

  <!-- Dashboard -->
  <div id="dash" class="dash">
    <div class="fund-header">
      <div class="fund-title" id="fundTitle"></div>
      <div class="fund-family" id="fundFamily"></div>
    </div>

    <!-- Tab bar -->
    <div class="tab-bar">
      <button class="tab-btn active" onclick="switchTab('xray')">X-Ray</button>
      <button class="tab-btn" onclick="switchTab('dollar')">Dollar Impact</button>
      <button class="tab-btn" onclick="switchTab('deepdive')">Deep Dive</button>
      <button class="tab-btn" onclick="switchTab('about')">About</button>
    </div>

    <!-- Tab 1: X-Ray -->
    <div id="tab-xray" class="tab-content active">
      <div class="kpi-strip" id="kpiStrip"></div>

      <div class="hero-card">
        <div class="hero-split">
          <div class="hero-col">
            <div class="hero-label">What They Report</div>
            <div class="hero-number"><span id="heroReported"></span><span class="hero-unit">%</span></div>
            <div class="hero-sub">Stated Expense Ratio</div>
          </div>
          <div class="hero-col">
            <div class="hero-label">What It Actually Costs</div>
            <div class="hero-number"><span id="heroActual"></span><span class="hero-unit">%</span></div>
            <div class="hero-sub">True Total Cost Range</div>
          </div>
          <div class="hero-col">
            <div class="hero-label">Hidden Fees</div>
            <div class="hero-number"><span id="heroHidden"></span><span class="hero-unit">bps</span></div>
            <div class="hero-sub">Trading costs not in the expense ratio</div>
          </div>
        </div>
      </div>

      <div class="dash-grid">
        <div>
          <div class="panel">
            <div class="panel-header">Hidden Cost Breakdown</div>
            <div id="costRows"></div>
          </div>

          <div class="panel" style="margin-top:20px">
            <div class="panel-header">Fee Breakdown</div>
            <div id="feeRows"></div>
          </div>
        </div>
        <div>
          <div class="panel sidebar-section">
            <div class="panel-header">Asset Allocation</div>
            <div id="assetBars" style="padding:12px 0"></div>
          </div>
          <div class="panel sidebar-section" id="notesPanel" style="display:none">
            <div class="panel-header">Data Notes</div>
            <div class="notes" id="notesContent"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Tab 2: Dollar Impact -->
    <div id="tab-dollar" class="tab-content">
      <div class="calc-section">
        <div class="calc-title">Customize Your Scenario</div>
        <div class="calc-inputs">
          <div class="calc-input-group">
            <label class="calc-input-label">Investment Amount</label>
            <div class="calc-input-row">
              <input class="calc-input" id="calcInvestment" type="number" value="100000" min="1000" step="1000">
              <div class="calc-unit">USD</div>
            </div>
          </div>
          <div class="calc-input-group">
            <label class="calc-input-label">Time Horizon</label>
            <div class="calc-input-row">
              <input class="calc-input" id="calcHorizon" type="number" value="20" min="1" max="50" step="1">
              <div class="calc-unit">yrs</div>
            </div>
          </div>
          <div class="calc-input-group">
            <label class="calc-input-label">Assumed Return</label>
            <div class="calc-input-row">
              <input class="calc-input" id="calcReturn" type="number" value="7" min="0" max="20" step="0.1">
              <div class="calc-unit">% p.a.</div>
            </div>
          </div>
        </div>
      </div>

      <div class="scenarios-grid" id="scenariosContainer"></div>

      <div class="impact-card">
        <div class="impact-title">Hidden Costs Steal</div>
        <div class="impact-value" id="impactValue"></div>
        <div class="impact-sub">from your portfolio over the investment period</div>
      </div>

      <div class="bars-chart">
        <div class="bars-title">Final Portfolio Value Comparison</div>
        <div class="bars-container" id="barsContainer"></div>
      </div>
    </div>

    <!-- Tab 3: Deep Dive -->
    <div id="tab-deepdive" class="tab-content">
      <div id="conflictFlagsContainer" style="display:none;margin-bottom:24px">
        <div class="section-title" style="color:var(--red)">Conflict Flags</div>
        <div id="conflictFlagsList" style="background:var(--red-dim);border:1px solid rgba(239,68,68,0.25);border-radius:12px;padding:16px 20px"></div>
      </div>

      <div class="section-title">Brokerage Commissions</div>
      <div style="background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px 20px;margin-bottom:20px">
        <div class="cost-row">
          <span class="cost-label">Aggregate Commissions Paid</span>
          <span class="cost-val" id="aggCommissions" style="color:var(--text)"></span>
        </div>
      </div>

      <div class="broker-list" id="brokersContainer"></div>

      <div class="section-title">Securities Lending</div>
      <div class="broker-list" id="lendingContainer"></div>

      <div class="section-title">Service Providers</div>
      <div id="providersContainer"></div>

      <div style="background:var(--surface-2);border-left:2px solid var(--border);border-radius:6px;padding:16px;margin-top:32px;font-size:12px;color:var(--text-dim);line-height:1.6">
        Data sourced from SEC Form N-CEN (fund operating information) and N-PORT (holdings and portfolio). All data is public and available via EDGAR.
      </div>
    </div>

    <!-- Tab 4: About -->
    <div id="tab-about" class="tab-content">
      <div class="about-section">
        <div class="about-title">What is Fund Autopsy?</div>
        <div class="about-text">
          Fund Autopsy reveals the true cost of ownership for mutual funds. Mutual fund companies are required to disclose their expense ratio
          (management fee, 12b-1 fees, and other expenses). But that number alone doesn't tell the full story.
        </div>
        <div class="about-text">
          Every time a fund buys or sells securities, it incurs trading costs that aren't reflected in the expense ratio: brokerage commissions,
          bid-ask spreads, market impact, and in many cases, undisclosed "soft dollar" arrangements where the fund uses client commissions
          to pay for research.
        </div>
        <div class="about-text">
          Fund Autopsy pulls data directly from SEC filings to calculate the full cost of ownership, including these hidden trading costs.
          The result is a true picture of how much a fund actually costs to own.
        </div>
      </div>

      <div class="about-section">
        <div class="about-title">Where does the data come from?</div>
        <ul class="about-list">
          <li><strong>Form N-CEN:</strong> Annual operating information including brokerage commissions, soft dollar arrangements, securities lending, and service provider details.</li>
          <li><strong>Form N-PORT:</strong> Monthly portfolio holdings (publicly disclosed with a 60-day lag), used to estimate bid-ask spreads and market impact by asset class.</li>
          <li><strong>Form 497K:</strong> Prospectus and expense ratio data.</li>
          <li><strong>SEC EDGAR:</strong> All filings retrieved from the public EDGAR database.</li>
        </ul>
      </div>

      <div class="about-section">
        <div class="about-title">Methodology</div>
        <ul class="about-list">
          <li><strong>Expense Ratio:</strong> Management fee, 12b-1 fee, and other expenses extracted from the fund's 497K summary prospectus via structured SEC filings.</li>
          <li><strong>Brokerage Commissions:</strong> Reported directly from Form N-CEN as aggregate dollars paid to executing brokers, converted to basis points using net assets from N-PORT.</li>
          <li><strong>Soft Dollar Arrangements:</strong> N-CEN discloses whether a fund directs brokerage commissions to brokers who provide research services in return. When active, the fund is paying inflated per-share commissions (e.g. 5 cents instead of 2 cents) and the difference subsidizes research the manager would otherwise pay for out of pocket. This cost is captured in the brokerage commission line, but there is a secondary effect that cannot be cleanly quantified from public filings: funds routing for soft dollar value rather than best execution may accept wider effective spreads and greater market impact. Our spread and impact estimates use asset-class averages and turnover rates rather than actual execution data, so they do not double-count the soft dollar effect, but they also cannot capture execution quality degradation specific to a given fund. We flag soft dollar arrangements as a qualitative warning rather than a precise dollar figure for this reason.</li>
          <li><strong>Bid-Ask Spreads & Market Impact:</strong> Estimated from portfolio turnover rate and the fund's asset class mix derived from N-PORT holdings. Equities, high-yield bonds, and international securities carry higher estimated spreads than investment-grade domestic fixed income. These are model estimates, not observed execution costs.</li>
          <li><strong>True Total Cost:</strong> Expense ratio + hidden trading costs, presented as a range (low estimate uses conservative spread assumptions; high estimate uses wider assumptions for less liquid asset classes).</li>
        </ul>
      </div>

      <div class="about-section">
        <div class="about-title">SEC Filing Structure</div>
        <div class="about-text">
          SEC filings for mutual funds follow a trust-based hierarchy that creates complexity for any fund-level analysis tool.
          A single registrant (CIK) represents a trust entity, which may contain dozens of fund series. Each series may have multiple
          share classes (Investor, Institutional, Admiral, etc.).
        </div>
        <div class="about-text">
          Form N-CEN is filed once per trust and contains operating data for every series within that trust. We match to the
          correct series using the SEC's series identifier (e.g. S000006037 for Fidelity Contrafund within CIK 24238, which is
          Fidelity Puritan Trust). Form N-PORT is filed per-series on a quarterly basis with full portfolio holdings and
          asset breakdowns. Form 497K is the summary prospectus filed per share class. When a ticker resolves to a trust
          with multiple series, we iterate through recent filings until we find the one matching the target series, rather
          than assuming the most recent filing belongs to the fund you searched for.
        </div>
      </div>

      <div class="about-section">
        <div class="about-title">References & Further Reading</div>
        <div class="about-text">
          The cost estimation framework draws on established academic and regulatory work on mutual fund trading costs:
        </div>
        <ul class="about-list">
          <li>Edelen, Evans, and Kadlec (2013) — "Shedding Light on 'Invisible' Costs: Trading Costs in Mutual Funds" (Financial Analysts Journal). Foundational study estimating trading costs as a material drag on fund returns beyond the expense ratio.</li>
          <li>Chalmers, Edelen, and Kadlec (1999) — "An Analysis of Mutual Fund Trading Costs" (Working Paper). Early quantification of bid-ask spread and market impact costs for equity mutual funds.</li>
          <li>SEC Form N-CEN (Investment Company Reporting Modernization, 2018) — Annual census-type filing that replaced N-SAR, requiring disclosure of brokerage commissions, soft dollar arrangements, securities lending, and service providers.</li>
          <li>SEC Form N-PORT (2019) — Monthly portfolio reporting with 60-day public lag, providing granular holdings and asset classification data used for spread estimation.</li>
          <li>Livingston and O'Neal (1996) — "Mutual Fund Brokerage Commissions" (Journal of Financial Research). Analysis of commission variation across fund types and the role of soft dollar arrangements in inflating per-share costs.</li>
        </ul>
      </div>

      <div class="about-section">
        <div class="about-title">How This Started</div>
        <div class="about-text">
          Fund Autopsy began with a simple question: what does a mutual fund actually cost? The expense ratio was the obvious answer,
          but pulling SEC filings revealed a second cost layer hiding underneath it. Brokerage commissions in N-CEN data showed funds
          paying millions in trading costs that never appear on any investor statement.
        </div>
        <div class="about-text">
          That led to the next question: if commissions are hidden, what else is? N-PORT holdings data revealed the raw material
          for estimating bid-ask spreads and market impact. Soft dollar arrangements showed funds paying inflated commissions
          so their managers could get research for free. Each filing we parsed surfaced another cost nobody was talking about.
        </div>
        <div class="about-text">
          Then we found the Statement of Additional Information &mdash; a companion document to the prospectus that funds are required
          to file but only provide to investors "upon request." Inside it: broker-specific commission breakdowns, portfolio manager
          compensation structures, revenue sharing arrangements, and commission recapture programs. An entire layer of conflict
          and cost data, technically public, practically invisible.
        </div>
        <div class="about-text">
          Each discovery opened the next door. Fund costs led to advisor conflicts. Advisor conflicts led to BrokerCheck and FINRA data.
          Revenue sharing explained why certain funds end up on recommended lists. The chain of realizations turned a cost calculator
          into a regulatory transparency engine. We coined "sub-NAV drag" to name what the industry had left unnamed, and we're
          building parsers for every filing the SEC requires &mdash; because the data was always there. Nobody had stitched it together.
        </div>
        <div class="about-text">
          This project was built entirely with AI. Every parser, every data pipeline, every piece of research was developed
          in collaboration between a financial planning professional and Claude. The tool exists because AI made it possible
          to read, parse, and connect regulatory filings at a scale that would have taken a team of analysts months to accomplish manually.
        </div>
      </div>

      <div class="about-section">
        <div class="about-title">Built by Tombstone Research</div>
        <div class="about-text">
          Fund Autopsy is a public research tool built by <strong>Tombstone Research</strong>, an independent financial research firm focused on transparency
          in fund costs and performance. Source code is available on <a href="https://github.com/tombstoneresearch/fund-autopsy" class="reference-link" target="_blank">GitHub</a>.
        </div>
      </div>

      <div class="about-section">
        <div class="about-title">Important Disclosures</div>
        <div class="about-text" style="font-size:12px; color:var(--text-muted); line-height:1.7;">
          Fund Autopsy is an independent research tool provided for educational and informational purposes only.
          It does not constitute investment advice, a recommendation, or an offer to buy or sell any security.
          Past performance is not indicative of future results. All investments involve risk, including possible loss of principal.
          Hidden cost estimates are based on publicly available SEC filings and standard academic models for bid-ask spreads
          and market impact; actual trading costs may vary. Users should consult with a qualified financial advisor before
          making any investment decisions. Tombstone Research is not a registered investment adviser, broker-dealer, or
          financial planner. Data is sourced from public SEC EDGAR filings and may contain errors, omissions, or delays.
          Tombstone Research makes no warranty regarding the accuracy or completeness of the information presented.
        </div>
      </div>
    </div>

    <div class="footer">
      <div class="footer-left">
        For educational and informational purposes only. Not investment advice. Past performance is not indicative of future results.
      </div>
      <div class="footer-right">
        <div class="footer-brand">Tombstone Research</div>
        <div class="footer-url">github.com/tombstoneresearch/fund-autopsy</div>
      </div>
    </div>
  </div>
</div>

<script>
let currentData = null;
const input = document.getElementById('tickerInput');

input.addEventListener('keydown', e => {
  if (e.key === 'Enter') {
    const t = input.value.trim().toUpperCase();
    if (t) runAnalysis(t);
  }
});

document.addEventListener('DOMContentLoaded', () => input.focus());

// Home / reset
function goHome() {
  document.getElementById('dash').style.display = 'none';
  document.getElementById('error').style.display = 'none';
  document.getElementById('loading').style.display = 'none';
  document.getElementById('welcome').style.display = '';
  document.getElementById('homeBtn').style.display = 'none';
  input.value = '';
  input.focus();
  currentData = null;
}

// Tab switching
function switchTab(tab) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + tab).classList.add('active');
  event.target.classList.add('active');

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
      throw new Error(err.detail || `HTTP ${resp.status}`);
    }
    const data = await resp.json();
    currentData = data;
    clearInterval(stageTimer);
    ['s1','s2','s3','s4'].forEach(id => document.getElementById(id).className = 'stage done');
    setTimeout(() => renderDash(data), 400);
  } catch (e) {
    clearInterval(stageTimer);
    document.getElementById('error').innerHTML =
      `<div style="font-size:20px;font-weight:700">Analysis Failed</div><p>${e.message}</p>
       <p style="margin-top:16px"><span class="example-chip" onclick="show('welcome')" style="cursor:pointer;display:inline-block">Try another ticker</span></p>`;
    show('error');
  }
}

function renderDash(d) {
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

  // Show note if ER missing
  const heroSub = heroReported.closest('.hero-col').querySelector('.hero-sub');
  if (!hasER) heroSub.textContent = '497K not available for this fund';

  // Cost rows
  let rowsHtml = '';
  d.costs.forEach(c => {
    const isSub = c.label.includes('Soft Dollar');
    const valClass = c.tag === 'reported' ? 'reported' : c.tag === 'warning' ? 'warning' : 'estimated';
    const tagClass = c.tag === 'reported' ? 'tag-reported' : c.tag === 'warning' ? 'tag-warning' : 'tag-estimated';
    const tagLabel = c.tag === 'reported' ? 'SEC filing' : c.tag === 'warning' ? 'not disclosed' : 'estimated';
    rowsHtml += `<div class="cost-row${isSub ? ' sub' : ''}" ${c.note ? `title="${c.note}"` : ''}>
      <span class="cost-label">${c.label}</span>
      <span class="cost-val ${valClass}">${c.value || '—'}</span>
      <span class="tag ${tagClass}">${tagLabel}</span>
    </div>`;
  });
  rowsHtml += `<div class="cost-row total">
    <span class="cost-label" style="font-weight:700">Total Hidden Costs</span>
    <span class="cost-val total">${trueER} – ${trueHigh}%</span>
    <span class="tag tag-estimated">composite</span>
  </div>`;
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
}

function formatNumber(n) {
  return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

function formatShort(n) {
  if (n >= 1000000) return '$' + (n / 1000000).toFixed(1) + 'M';
  if (n >= 1000) return '$' + (n / 1000).toFixed(0) + 'K';
  return '$' + n.toFixed(0);
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
    document.getElementById('error').innerHTML =
      `<div style="font-size:20px;font-weight:700">Invalid Input</div><p>Please provide at least 2 fund tickers separated by commas.</p>
       <p style="margin-top:16px"><span class="example-chip" onclick="show('welcome')" style="cursor:pointer;display:inline-block">Try again</span></p>`;
    show('error');
    return;
  }

  if (tickers.length > 5) {
    document.getElementById('error').innerHTML =
      `<div style="font-size:20px;font-weight:700">Too Many Funds</div><p>Maximum 5 funds for comparison.</p>
       <p style="margin-top:16px"><span class="example-chip" onclick="show('welcome')" style="cursor:pointer;display:inline-block">Try again</span></p>`;
    show('error');
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
    document.getElementById('error').innerHTML =
      `<div style="font-size:20px;font-weight:700">Comparison Failed</div><p>${e.message}</p>
       <p style="margin-top:16px"><span class="example-chip" onclick="show('welcome')" style="cursor:pointer;display:inline-block">Try again</span></p>`;
    show('error');
  }
}

function renderComparison(results, errors) {
  if (!results || results.length === 0) {
    document.getElementById('error').innerHTML =
      `<div style="font-size:20px;font-weight:700">No Data Available</div><p>Could not retrieve data for the requested funds.</p>
       <p style="margin-top:16px"><span class="example-chip" onclick="show('welcome')" style="cursor:pointer;display:inline-block">Try again</span></p>`;
    show('error');
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
</script>
</body>
</html>"""
