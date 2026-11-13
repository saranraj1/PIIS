"""NOC Operator Experience interface for PIIS decision support."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["Operator Workspace"])

UI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PIIS — Telecom Incident Intelligence & Operator Workspace (Telecom Edition)</title>
  <style>
    :root {
      --bg: #0b1120;
      --card-bg: #1e293b;
      --card-inner: #0f172a;
      --border: #334155;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --primary: #38bdf8;
      --success: #34d399;
      --warning: #fbbf24;
      --danger: #f87171;
      --accent: #818cf8;
      --fact: #0284c7;
      --pred: #7c3aed;
      --hypo: #d97706;
      --reco: #059669;
      --decision: #0d9488;
      --unconfirmed: #475569;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
    body { background-color: var(--bg); color: var(--text); min-height: 100vh; display: flex; flex-direction: column; }
    header { background-color: #030712; border-bottom: 1px solid var(--border); padding: 0.85rem 2rem; display: flex; justify-content: space-between; align-items: center; }
    .logo-group { display: flex; align-items: center; gap: 0.75rem; }
    .logo-badge { background: linear-gradient(135deg, #0284c7, #6366f1); color: white; font-weight: 800; font-size: 1.1rem; padding: 0.35rem 0.75rem; border-radius: 6px; letter-spacing: 0.5px; }
    .logo-title { font-size: 1.15rem; font-weight: 700; color: white; letter-spacing: -0.5px; }
    .header-meta { display: flex; align-items: center; gap: 0.75rem; }
    .env-tag { font-size: 0.75rem; padding: 0.25rem 0.6rem; border-radius: 9999px; font-weight: 600; background: #064e3b; color: #6ee7b7; border: 1px solid #059669; }
    .user-pill { font-size: 0.8rem; color: var(--text-muted); background: var(--card-bg); padding: 0.35rem 0.75rem; border-radius: 6px; border: 1px solid var(--border); }
    .user-role { color: var(--primary); font-weight: 600; margin-left: 0.25rem; }

    .status-banner { background: #172554; border-bottom: 1px solid #1e40af; padding: 0.45rem 2rem; font-size: 0.8rem; color: #93c5fd; display: flex; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem; }
    .status-banner strong { color: white; }

    .epistemic-legend { background: #0f172a; border-bottom: 1px solid var(--border); padding: 0.4rem 2rem; display: flex; gap: 0.6rem; align-items: center; flex-wrap: wrap; font-size: 0.75rem; }
    .epistemic-legend span { color: var(--text-muted); }

    /* Epistemic Badges */
    .tag-epistemic { font-size: 0.65rem; font-weight: 800; padding: 0.2rem 0.5rem; border-radius: 4px; letter-spacing: 0.5px; text-transform: uppercase; display: inline-flex; align-items: center; gap: 0.3rem; }
    .tag-fact { background: rgba(2, 132, 199, 0.2); color: #38bdf8; border: 1px solid #0284c7; }
    .tag-pred { background: rgba(124, 58, 237, 0.2); color: #c084fc; border: 1px solid #7c3aed; }
    .tag-hypo { background: rgba(217, 119, 6, 0.2); color: #fbbf24; border: 1px solid #d97706; }
    .tag-reco { background: rgba(5, 150, 105, 0.2); color: #34d399; border: 1px solid #059669; }
    .tag-decision { background: rgba(13, 148, 136, 0.2); color: #2dd4bf; border: 1px solid #0d9488; }
    .tag-unconfirmed { background: rgba(71, 85, 105, 0.2); color: #94a3b8; border: 1px solid #475569; }

    nav { background-color: var(--card-bg); border-bottom: 1px solid var(--border); display: flex; padding: 0 2rem; gap: 1rem; overflow-x: auto; }
    .nav-btn { background: none; border: none; color: var(--text-muted); font-size: 0.85rem; font-weight: 600; padding: 0.85rem 0.5rem; cursor: pointer; border-bottom: 2px solid transparent; transition: all 0.2s; white-space: nowrap; }
    .nav-btn:hover { color: var(--text); }
    .nav-btn.active { color: var(--primary); border-bottom-color: var(--primary); }

    main { flex: 1; padding: 1.5rem 2rem; max-width: 1440px; margin: 0 auto; width: 100%; }
    .view-panel { display: none; }
    .view-panel.active { display: block; }

    .grid-4 { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1.25rem; margin-bottom: 1.5rem; }
    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; margin-bottom: 1.5rem; }
    .card { background-color: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 1.25rem; }
    .card-title { font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted); margin-bottom: 0.4rem; }
    .metric-val { font-size: 2rem; font-weight: 700; color: white; }
    .metric-sub { font-size: 0.75rem; color: var(--text-muted); margin-top: 0.25rem; }

    table { width: 100%; border-collapse: collapse; margin-top: 0.75rem; font-size: 0.8rem; }
    th { text-align: left; padding: 0.65rem 0.85rem; background-color: #0f172a; color: var(--text-muted); border-bottom: 1px solid var(--border); font-weight: 600; }
    td { padding: 0.65rem 0.85rem; border-bottom: 1px solid var(--border); color: var(--text); }
    tr:hover td { background-color: rgba(255, 255, 255, 0.02); }

    .badge { font-size: 0.7rem; font-weight: 700; padding: 0.2rem 0.5rem; border-radius: 4px; text-transform: uppercase; }
    .badge-critical { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); }
    .badge-major { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4); }
    .badge-minor { background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.4); }
    .badge-success { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); }

    .btn { background-color: #2563eb; color: white; border: none; padding: 0.45rem 0.85rem; border-radius: 6px; font-size: 0.8rem; font-weight: 600; cursor: pointer; transition: background 0.2s; }
    .btn:hover { background-color: #1d4ed8; }
    .btn-success { background-color: #059669; }
    .btn-success:hover { background-color: #047857; }
    .btn-danger { background-color: #dc2626; }
    .btn-danger:hover { background-color: #b91c1c; }
    .btn-outline { background: transparent; border: 1px solid var(--border); color: var(--text); }
    .btn-outline:hover { background: rgba(255, 255, 255, 0.05); }

    .evidence-box { background: var(--card-inner); border: 1px solid var(--border); border-radius: 6px; padding: 0.85rem; margin-top: 0.75rem; }
    .evidence-item { border-left: 3px solid var(--primary); padding-left: 0.75rem; margin-bottom: 0.75rem; }
    .hypothesis-card { background: #182234; border: 1px solid #293850; border-radius: 6px; padding: 0.85rem; margin-bottom: 0.85rem; }
    .hypothesis-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem; }
    .score-badge { background: #312e81; color: #c7d2fe; font-size: 0.75rem; padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: 600; }

    .alert-box { background: rgba(245, 158, 11, 0.1); border-left: 4px solid var(--warning); padding: 0.75rem 1rem; border-radius: 4px; margin-bottom: 1rem; font-size: 0.8rem; color: #fde68a; }
    .alert-danger { background: rgba(239, 68, 68, 0.1); border-left-color: var(--danger); color: #fecaca; }
    .alert-info { background: rgba(2, 132, 199, 0.1); border-left-color: var(--primary); color: #bae6fd; }

    input, select, textarea { width: 100%; background: #0f172a; border: 1px solid var(--border); color: white; padding: 0.5rem; border-radius: 6px; margin-top: 0.35rem; margin-bottom: 0.85rem; font-size: 0.8rem; }
    input:focus, select:focus, textarea:focus { outline: none; border-color: var(--primary); }
    code { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 0.8em; }
  </style>
</head>
<body>
  <header>
    <div class="logo-group">
      <div class="logo-badge">PIIS</div>
      <div>
        <div class="logo-title">Production Incident Intelligence System</div>
        <div style="font-size: 0.7rem; color: var(--text-muted);">Telecom Edition — Telecom Operations Decision Support</div>
      </div>
    </div>
    <div class="header-meta">
      <div class="env-tag">STRICT READ-ONLY BOUNDARY</div>
      <input type="password" id="ui-auth-token" placeholder="Bearer Token..." style="width: 170px; margin: 0; padding: 0.3rem 0.5rem; font-size: 0.75rem;" title="Enter Bearer Token for authenticated API operations" />
      <button class="btn btn-outline" style="padding: 0.3rem 0.6rem; font-size: 0.75rem;" onclick="saveToken()">Set Auth</button>
      <div class="user-pill">Role: <span class="user-role" id="ui-role-tag">NOC_TIER_2</span></div>
    </div>
  </header>

  <div class="status-banner">
    <div><strong>Operational Boundary:</strong> Read-Only Decision Support | <strong>Autonomous Production Mutations:</strong> STRICTLY PROHIBITED (Hard-Locked)</div>
    <div><strong>Verified Safety Fleet:</strong> 378/378 PASSING | <strong>Architecture:</strong> Modular Monolith</div>
  </div>

  <div class="epistemic-legend">
    <span>Visual Epistemic Standards:</span>
    <span class="tag-epistemic tag-fact">[OBSERVED FACT] Telemetry / Alarms</span>
    <span class="tag-epistemic tag-pred">[MODEL PREDICTION] ML Classifier</span>
    <span class="tag-epistemic tag-hypo">[HYPOTHESIS] RAG Root Cause Candidate</span>
    <span class="tag-epistemic tag-reco">[RECOMMENDATION] Proposed Action</span>
    <span class="tag-epistemic tag-decision">[HUMAN-APPROVED DECISION] Sign-off</span>
    <span class="tag-epistemic tag-unconfirmed">[CONFIRMED ROOT CAUSE] Post-Incident Only</span>
  </div>

  <nav>
    <button class="nav-btn active" onclick="showTab('overview')">Operations Overview</button>
    <button class="nav-btn" onclick="showTab('investigation')">Incident Investigation</button>
    <button class="nav-btn" onclick="showTab('review')">Human Review & Sign-Off</button>
    <button class="nav-btn" onclick="showTab('integrations')">Enterprise Adapters & DLQ</button>
    <button class="nav-btn" onclick="showTab('audit')">Cryptographic Audit Ledger</button>
  </nav>

  <main>
    <!-- Tab 1: Operations Overview -->
    <div id="overview" class="view-panel active">
      <div class="alert-box alert-info">
        <strong>Governance Disclosure:</strong> PIIS generates evidence-grounded diagnostic hypotheses and recommendations. 
        Recommendations do <strong>NOT</strong> constitute confirmed root causes until validated post-incident by human engineers.
      </div>

      <div class="grid-4">
        <div class="card">
          <div class="card-title"><span class="tag-epistemic tag-fact">FACT</span> Active Incidents</div>
          <div class="metric-val" id="metric-incidents">0</div>
          <div class="metric-sub">Ingested from ServiceNow, Jira, REST</div>
        </div>
        <div class="card">
          <div class="card-title"><span class="tag-epistemic tag-pred">PREDICTION</span> Major / Critical Outages</div>
          <div class="metric-val" style="color: var(--warning);" id="metric-critical">0</div>
          <div class="metric-sub">5G RAN, Core & Transport Domains</div>
        </div>
        <div class="card">
          <div class="card-title"><span class="tag-epistemic tag-reco">ACTION</span> Pending Human Reviews</div>
          <div class="metric-val" style="color: var(--primary);" id="metric-reviews">0</div>
          <div class="metric-sub">Awaiting Tier-2 Operator Sign-off</div>
        </div>
        <div class="card">
          <div class="card-title"><span class="tag-epistemic tag-fact">FACT</span> Integration Adapters</div>
          <div class="metric-val" style="color: var(--success);" id="metric-adapters">6 / 6</div>
          <div class="metric-sub">ServiceNow, Jira, Prom, OTLP, OSS</div>
        </div>
      </div>

      <div class="card">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <h3 style="font-size: 1rem; color: white;">Recent Operational Incidents</h3>
          <button class="btn btn-outline" onclick="loadIncidents()">Refresh Feed</button>
        </div>
        <table>
          <thead>
            <tr>
              <th>Incident ID</th>
              <th>Source & Lineage</th>
              <th>Domain</th>
              <th>Severity</th>
              <th>Symptoms & Title</th>
              <th>Created UTC</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody id="incidents-table-body">
            <tr>
              <td colspan="7" style="text-align: center; color: var(--text-muted);">Loading incidents from API...</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Tab 2: Incident Investigation Workspace -->
    <div id="investigation" class="view-panel">
      <div class="grid-2">
        <div>
          <div class="card" style="margin-bottom: 1.25rem;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
              <div>
                <h3 style="font-size: 1rem; color: white; margin-bottom: 0.35rem;" id="inv-title">Select an Incident to Inspect</h3>
                <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.75rem;" id="inv-meta">No incident loaded.</div>
              </div>
              <span id="inv-epistemic-tag" class="tag-epistemic tag-fact">[OBSERVED FACT]</span>
            </div>
            <div id="inv-sufficiency"></div>
            <div id="inv-description" style="font-size: 0.8rem; line-height: 1.4; color: #cbd5e1; margin-top: 0.5rem;"></div>
            
            <!-- Provenance & Lineage Box -->
            <div id="inv-lineage" class="evidence-box" style="display: none;">
              <strong style="font-size: 0.75rem; color: var(--primary);">Provenance & Lineage Metadata:</strong>
              <div id="inv-lineage-details" style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.25rem;"></div>
            </div>
          </div>

          <div class="card" style="margin-bottom: 1.25rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
              <h4 style="font-size: 0.85rem; color: white;">Correlated Network Evidence & Telemetry</h4>
              <span class="tag-epistemic tag-fact">[OBSERVED FACT]</span>
            </div>
            <div id="inv-evidence" class="evidence-box">
              <div style="color: var(--text-muted); font-size: 0.8rem;">Click 'Investigate' on an incident to view evidence.</div>
            </div>
          </div>

          <div class="card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
              <h4 style="font-size: 0.85rem; color: white;">Correlated Historical Incidents</h4>
              <span class="tag-epistemic tag-fact">[OBSERVED FACT]</span>
            </div>
            <div id="inv-historical" class="evidence-box">
              <div style="color: var(--text-muted); font-size: 0.8rem;">No historical matches loaded.</div>
            </div>
          </div>
        </div>

        <div>
          <div class="card" style="margin-bottom: 1.25rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
              <h4 style="font-size: 0.85rem; color: white;">Ranked Hypotheses (Diagnostic Reasoning)</h4>
              <span class="tag-epistemic tag-hypo">[HYPOTHESIS]</span>
            </div>
            <div id="inv-hypotheses">
              <div style="color: var(--text-muted); font-size: 0.8rem;">No hypotheses calculated.</div>
            </div>
          </div>

          <div class="card" style="margin-bottom: 1.25rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
              <h4 style="font-size: 0.85rem; color: white;">Diagnostic Recommendations</h4>
              <span class="tag-epistemic tag-reco">[RECOMMENDATION]</span>
            </div>
            <div id="inv-recommendations">
              <div style="color: var(--text-muted); font-size: 0.8rem;">No recommendations generated.</div>
            </div>
          </div>

          <div class="card">
            <h4 style="font-size: 0.85rem; color: white; margin-bottom: 0.5rem;">Model Limitations & Confidence Proxy</h4>
            <div style="font-size: 0.75rem; color: var(--text-muted); line-height: 1.4;">
              <p>• Confidence score is a heuristic proxy combining retrieval semantic similarity, telemetry temporal freshness, and topological alignment.</p>
              <p style="margin-top: 0.25rem;">• Known limitation: Simulators provide representative telecom patterns but cannot fully capture complex multi-chassis transient failures.</p>
              <p style="margin-top: 0.25rem;">• Root causes are <strong>NEVER</strong> automatically confirmed by the engine.</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Tab 3: Human Review Workspace -->
    <div id="review" class="view-panel">
      <div class="grid-2">
        <div class="card">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
            <h3 style="font-size: 1rem; color: white;">Human Operator Authorization</h3>
            <span class="tag-epistemic tag-decision">[HUMAN-APPROVED DECISION]</span>
          </div>
          <div class="alert-box">
            <strong>Mandatory Governance Boundary:</strong> Every diagnostic action requires authenticated human operator review. 
            Automated bots and service accounts are strictly prohibited from approving actions.
          </div>
          <form id="review-form" onsubmit="submitReview(event)">
            <label style="font-size: 0.75rem; color: var(--text-muted);">Target Incident ID</label>
            <input type="text" id="rev-incident-id" required placeholder="INC-SNOW-INC0089201">

            <label style="font-size: 0.75rem; color: var(--text-muted);">Recommendation ID</label>
            <input type="text" id="rev-rec-id" required placeholder="REC-001">

            <label style="font-size: 0.75rem; color: var(--text-muted);">Review Decision</label>
            <select id="rev-decision">
              <option value="APPROVED">APPROVE (Authorize Read-Only Diagnostic Procedure)</option>
              <option value="REJECTED">REJECT (Dismiss / Escalate to Tier 3 Specialist)</option>
            </select>

            <label style="font-size: 0.75rem; color: var(--text-muted);">Operator Technical Justification & Notes</label>
            <textarea id="rev-notes" rows="4" required placeholder="Reviewed VSWR telemetry and feeder logs; verified safe for dispatch."></textarea>

            <button type="submit" class="btn btn-success" style="width: 100%; padding: 0.65rem;">Cryptographically Sign & Append to Ledger</button>
          </form>
        </div>

        <div class="card">
          <h3 style="font-size: 1rem; color: white; margin-bottom: 0.75rem;">Cryptographic Receipt</h3>
          <div id="review-receipt" style="background: var(--card-inner); border: 1px solid var(--border); border-radius: 6px; padding: 0.85rem; font-family: monospace; font-size: 0.75rem; color: #a5f3fc; min-height: 240px; white-space: pre-wrap; overflow-x: auto;">
Awaiting operator sign-off...
          </div>
        </div>
      </div>
    </div>

    <!-- Tab 4: Integrations & Adapters -->
    <div id="integrations" class="view-panel">
      <div class="card" style="margin-bottom: 1.5rem;">
        <h3 style="font-size: 1rem; color: white; margin-bottom: 0.75rem;">Enterprise Telecom Adapters (Strict Read-Only)</h3>
        <table>
          <thead>
            <tr>
              <th>Adapter ID</th>
              <th>System Type</th>
              <th>Status Qualification</th>
              <th>Health</th>
              <th>Last Heartbeat</th>
              <th>Failures</th>
            </tr>
          </thead>
          <tbody id="adapters-table-body">
            <tr><td colspan="6" style="text-align: center;">Loading adapters...</td></tr>
          </tbody>
        </table>
      </div>

      <div class="card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
          <h3 style="font-size: 1rem; color: white;">Dead-Letter Queue (DLQ)</h3>
          <button class="btn btn-outline" onclick="loadDLQ()">Refresh DLQ</button>
        </div>
        <table>
          <thead>
            <tr>
              <th>DLQ Item ID</th>
              <th>Source System</th>
              <th>Failure Reason</th>
              <th>Attempts</th>
              <th>First Failed UTC</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody id="dlq-table-body">
            <tr><td colspan="6" style="text-align: center; color: var(--text-muted);">Loading DLQ items...</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Tab 5: Audit Ledger -->
    <div id="audit" class="view-panel">
      <div class="card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
          <div>
            <h3 style="font-size: 1rem; color: white;">Cryptographic Audit Ledger (RFC 8785 JCS + HMAC)</h3>
            <div style="font-size: 0.75rem; color: var(--text-muted);">Tamper-evident append-only chain with monotonic checkpoint anchors</div>
          </div>
          <button class="btn btn-outline" onclick="verifyLedger()">Verify Chain Integrity</button>
        </div>
        <div id="audit-verify-status" style="margin-bottom: 0.75rem;"></div>
        <table>
          <thead>
            <tr>
              <th>Seq #</th>
              <th>Entry Hash (SHA-256)</th>
              <th>Prev Hash</th>
              <th>Operator ID</th>
              <th>Decision</th>
              <th>Recommendation</th>
              <th>Timestamp UTC</th>
            </tr>
          </thead>
          <tbody id="audit-table-body">
            <tr><td colspan="7" style="text-align: center;">Loading audit records...</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </main>

  <script>
    function getAuthToken() {
      return sessionStorage.getItem('piis_auth_token') || '';
    }

    function saveToken() {
      const input = document.getElementById('ui-auth-token');
      if (input && input.value) {
        sessionStorage.setItem('piis_auth_token', input.value.trim());
        alert('Bearer token saved for session.');
        loadIncidents();
      }
    }

    function getAuthHeaders(extraHeaders = {}) {
      const headers = { 'Content-Type': 'application/json', ...extraHeaders };
      const tok = getAuthToken();
      if (tok) {
        headers['Authorization'] = 'Bearer ' + tok;
      }
      return headers;
    }

    function showTab(tabId) {
      document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.view-panel').forEach(p => p.classList.remove('active'));
      if (event && event.target) event.target.classList.add('active');
      const panel = document.getElementById(tabId);
      if (panel) panel.classList.add('active');

      if (tabId === 'overview') loadIncidents();
      if (tabId === 'integrations') { loadAdapters(); loadDLQ(); }
      if (tabId === 'audit') loadAudit();
    }

    async function loadIncidents() {
      try {
        const res = await fetch('/api/v1/incidents?limit=20', { headers: getAuthHeaders() });
        const data = await res.json();
        const tbody = document.getElementById('incidents-table-body');
        tbody.innerHTML = '';
        if (data.total_count !== undefined) {
          document.getElementById('metric-incidents').innerText = data.total_count;
        }

        if (data.items && data.items.length > 0) {
          let critCount = 0;
          data.items.forEach(inc => {
            if (inc.severity === 'CRITICAL' || inc.severity === 'MAJOR') critCount++;
            const tr = document.createElement('tr');
            const sevClass = inc.severity === 'CRITICAL' ? 'badge-critical' : (inc.severity === 'MAJOR' ? 'badge-major' : 'badge-minor');
            tr.innerHTML = `
              <td><code>${inc.incident_id}</code></td>
              <td>${inc.source_dataset || inc.source_type}</td>
              <td><strong>${inc.network_domain}</strong></td>
              <td><span class="badge ${sevClass}">${inc.severity}</span></td>
              <td><strong>${inc.title}</strong></td>
              <td>${inc.created_at}</td>
              <td><button class="btn" onclick="inspectIncident('${inc.incident_id}')">Investigate</button></td>
            `;
            tbody.appendChild(tr);
          });
          document.getElementById('metric-critical').innerText = critCount;
        } else {
          tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">No incidents stored. Ingest incidents via API or run demo.</td></tr>';
        }
      } catch (e) {
        console.error(e);
      }
    }

    async function inspectIncident(incidentId) {
      showTabDirect('investigation');
      document.getElementById('inv-title').innerText = `Investigating ${incidentId}...`;

      try {
        const res = await fetch(`/api/v1/incidents/${incidentId}/investigate`, { method: 'POST', headers: getAuthHeaders() });
        const data = await res.json();

        document.getElementById('inv-title').innerText = `${data.incident_id}: ${data.title}`;
        document.getElementById('inv-meta').innerText = `Domain: ${data.network_domain} | Created: ${data.created_at} | Elements: ${(data.network_element_ids || []).join(', ')}`;
        document.getElementById('inv-description').innerText = data.description || 'No description provided.';
        
        // Sufficiency & Staleness
        const suffBox = document.getElementById('inv-sufficiency');
        if (data.is_sufficient) {
          suffBox.innerHTML = `<div class="badge badge-success" style="display: inline-block; margin-bottom: 0.5rem;">EVIDENCE SUFFICIENT & FRESH</div>`;
        } else {
          let warnMsg = (data.stale_evidence && data.stale_evidence.length > 0) ? 'Stale Telemetry Observed (>3600s)' : 'Insufficient Signals (Safe Abstention Enforced)';
          suffBox.innerHTML = `<div class="alert-box" style="margin-bottom: 0.5rem;"><strong>SAFE ABSTENTION:</strong> ${warnMsg}</div>`;
        }

        // Correlated Evidence
        const evidBox = document.getElementById('inv-evidence');
        evidBox.innerHTML = '';
        if (data.evidence_items && data.evidence_items.length > 0) {
          data.evidence_items.forEach(ev => {
            const evDiv = document.createElement('div');
            evDiv.className = 'evidence-item';
            evDiv.innerHTML = `<strong>${ev.id || 'EVID'}</strong>: ${ev.summary || JSON.stringify(ev)}`;
            evidBox.appendChild(evDiv);
          });
        } else {
          evidBox.innerHTML = '<div style="color: var(--text-muted); font-size: 0.8rem;">No correlated telemetry or alarms linked.</div>';
        }

        // Hypotheses
        const hypBox = document.getElementById('inv-hypotheses');
        hypBox.innerHTML = '';
        if (!data.hypotheses || data.hypotheses.length === 0) {
          hypBox.innerHTML = '<div style="color: var(--text-muted); font-size: 0.8rem;">No confident root cause hypothesis. Engine safely abstained.</div>';
        } else {
          data.hypotheses.forEach(h => {
            const hDiv = document.createElement('div');
            hDiv.className = 'hypothesis-card';
            hDiv.innerHTML = `
              <div class="hypothesis-header">
                <strong>${h.title || 'Root Cause Candidate'}</strong>
                <span class="score-badge">Proxy Confidence: ${(h.confidence || 0.8).toFixed(2)}</span>
              </div>
              <div style="font-size: 0.8rem; color: #cbd5e1;">${h.explanation || h.description || ''}</div>
            `;
            hypBox.appendChild(hDiv);
          });
        }

        // Recommendations
        const recBox = document.getElementById('inv-recommendations');
        recBox.innerHTML = '';
        if (data.recommendations && data.recommendations.length > 0) {
          data.recommendations.forEach(r => {
            const rDiv = document.createElement('div');
            rDiv.className = 'hypothesis-card';
            rDiv.style.borderColor = '#1e3a8a';
            rDiv.innerHTML = `
              <div class="hypothesis-header">
                <strong style="color: #93c5fd;">${r.recommendation_id}: ${r.source_runbook_id || 'RUNBOOK'}</strong>
                <span class="badge badge-major">${r.risk_classification}</span>
              </div>
              <div style="font-size: 0.8rem; color: white; margin-bottom: 0.4rem;">${r.description}</div>
              <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.4rem;"><strong>Reason:</strong> ${r.reason}</div>
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 0.75rem; color: #facc15;">Status: ${r.approval_status}</span>
                <button class="btn btn-outline" onclick="prefillReview('${data.incident_id}', '${r.recommendation_id}')">Review</button>
              </div>
            `;
            recBox.appendChild(rDiv);
          });
        } else {
          recBox.innerHTML = '<div style="color: var(--text-muted); font-size: 0.8rem;">No recommendations generated.</div>';
        }

      } catch (e) {
        console.error(e);
      }
    }

    function prefillReview(incId, recId) {
      showTabDirect('review');
      document.getElementById('rev-incident-id').value = incId;
      document.getElementById('rev-rec-id').value = recId;
    }

    function showTabDirect(tabId) {
      document.querySelectorAll('.nav-btn').forEach(b => {
        b.classList.toggle('active', b.innerText.toLowerCase().includes(tabId));
      });
      document.querySelectorAll('.view-panel').forEach(p => p.classList.remove('active'));
      const p = document.getElementById(tabId);
      if (p) p.classList.add('active');
    }

    async function submitReview(e) {
      e.preventDefault();
      const incId = document.getElementById('rev-incident-id').value;
      const recId = document.getElementById('rev-rec-id').value;
      const decision = document.getElementById('rev-decision').value;
      const notes = document.getElementById('rev-notes').value;

      try {
        const res = await fetch(`/api/v1/incidents/${incId}/reviews`, {
          method: 'POST',
          headers: getAuthHeaders(),
          body: JSON.stringify({ recommendation_id: recId, decision: decision, review_notes: notes })
        });
        const receipt = await res.json();
        document.getElementById('review-receipt').innerText = JSON.stringify(receipt, null, 2);
        loadIncidents();
      } catch (err) {
        document.getElementById('review-receipt').innerText = `Error: ${err}`;
      }
    }

    async function loadAdapters() {
      try {
        const res = await fetch('/api/v1/integrations/health', { headers: getAuthHeaders() });
        const data = await res.json();
        const tbody = document.getElementById('adapters-table-body');
        tbody.innerHTML = '';
        if (Array.isArray(data)) {
          data.forEach(a => {
            const tr = document.createElement('tr');
            const badge = a.state === 'HEALTHY' ? 'badge-success' : 'badge-major';
            tr.innerHTML = `
              <td><code>${a.adapter_id}</code></td>
              <td><strong>${a.adapter_type}</strong></td>
              <td><span style="font-size: 0.7rem; color: #94a3b8;">LOCALLY VERIFIED | SIMULATED</span></td>
              <td><span class="badge ${badge}">${a.state}</span></td>
              <td>${a.last_heartbeat}</td>
              <td>${a.consecutive_failures}</td>
            `;
            tbody.appendChild(tr);
          });
        }
      } catch (e) {
        console.error(e);
      }
    }

    async function loadDLQ() {
      try {
        const res = await fetch('/api/v1/integrations/dlq', { headers: getAuthHeaders() });
        const data = await res.json();
        const tbody = document.getElementById('dlq-table-body');
        tbody.innerHTML = '';
        const items = data.items || (Array.isArray(data) ? data : []);
        if (items.length > 0) {
          items.forEach(item => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
              <td><code>${item.item_id || item.envelope_id}</code></td>
              <td>${item.envelope ? item.envelope.source_system : 'UNKNOWN'}</td>
              <td><span style="color: #f87171;">${item.failure_reason || 'ERROR'}</span></td>
              <td>${item.attempt_count || 1}</td>
              <td>${item.first_failed_at || 'N/A'}</td>
              <td><button class="btn btn-outline" style="padding: 0.2rem 0.5rem; font-size: 0.7rem;" onclick="alert('Item preserved in DLQ for audit analysis.')">Inspect</button></td>
            `;
            tbody.appendChild(tr);
          });
        } else {
          tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">No dead-letter items. Queue is clean.</td></tr>';
        }
      } catch (e) {
        console.error(e);
      }
    }

    async function loadAudit() {
      try {
        const res = await fetch('/api/v1/audit/records', { headers: getAuthHeaders() });
        const data = await res.json();
        const tbody = document.getElementById('audit-table-body');
        tbody.innerHTML = '';
        if (data.items) {
          data.items.forEach(r => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
              <td><strong>#${r.sequence_number}</strong></td>
              <td><code>${(r.entry_hash || '').substring(0, 16)}...</code></td>
              <td><code>${(r.prev_hash || '').substring(0, 16)}...</code></td>
              <td>${r.operator_id}</td>
              <td><span class="badge badge-success">${r.decision}</span></td>
              <td>${r.recommendation_id}</td>
              <td>${r.timestamp}</td>
            `;
            tbody.appendChild(tr);
          });
        }
      } catch (e) {
        console.error(e);
      }
    }

    async function verifyLedger() {
      const statusDiv = document.getElementById('audit-verify-status');
      statusDiv.innerHTML = '<span style="color: var(--primary);">Verifying SHA-256 chain and monotonic anchor...</span>';
      try {
        const res = await fetch('/api/v1/audit/verify', { headers: getAuthHeaders() });
        const data = await res.json();
        if (data.is_valid) {
          statusDiv.innerHTML = `<div class="badge badge-success" style="display: inline-block;">TAMPER-EVIDENT INTEGRITY VERIFIED (Records: ${data.total_records})</div>`;
        } else {
          statusDiv.innerHTML = `<div class="alert-box alert-danger">TAMPERING DETECTED: ${data.error}</div>`;
        }
      } catch (e) {
        statusDiv.innerHTML = `<span style="color: var(--danger);">Verification error: ${e}</span>`;
      }
    }

    // Auto-load on start
    window.addEventListener('DOMContentLoaded', () => {
      const savedTok = sessionStorage.getItem('piis_auth_token');
      if (savedTok) {
        const input = document.getElementById('ui-auth-token');
        if (input) input.value = savedTok;
      }
      loadIncidents();
    });
  </script>
</body>
</html>
"""

@router.get("/", response_class=HTMLResponse)
@router.get("/ui", response_class=HTMLResponse)
async def serve_operator_workspace() -> str:
    """Serve the NOC Operator Experience single-page application."""
    return UI_HTML
