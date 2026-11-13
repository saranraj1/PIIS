import json
import os

def make_notebook(cells):
    return {
        "cells": cells,
        "metadata": {
            "language_info": {
                "name": "python",
                "version": "3.11.0"
            },
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 5
    }

def md_cell(lines):
    return {"cell_type": "markdown", "metadata": {}, "source": lines}

def code_cell(lines):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": lines}

# -------------------------------------------------------------
# Notebook 1: Incident Triage & Investigation
# -------------------------------------------------------------
nb1_cells = [
    md_cell([
        "# PIIS: Telecom Incident Triage and Evidence Investigation\n",
        "\n",
        "This notebook demonstrates the end-to-end analytical workflow of the **Production Incident Intelligence System (PIIS)**.\n",
        "\n",
        "### Workflow Objectives\n",
        "1. Ingest multi-vendor telecom incident envelopes (ServiceNow, Jira).\n",
        "2. Execute multi-domain triage classification and severity prediction.\n",
        "3. Perform causal telemetry anomaly detection and topological blast radius analysis.\n",
        "4. Run hybrid evidence retrieval (Okapi BM25 + dense semantic embeddings).\n",
        "5. Review synthesized hypotheses, evidence registers, and runbook recommendations.\n"
    ]),
    code_cell([
        "import sys\n",
        "import os\n",
        "from pprint import pprint\n",
        "from datetime import datetime, timezone\n",
        "\n",
        "# Add src directory to Python path\n",
        "sys.path.insert(0, os.path.abspath('../src'))\n",
        "\n",
        "from piis.pipeline.unified import UnifiedIngestionPipeline\n",
        "from piis.integrations.contracts import IngestionEnvelope\n",
        "from piis.integrations.itsm.servicenow import ServiceNowAdapter\n",
        "from piis.integrations.telemetry.prometheus import PrometheusAdapter\n",
        "from piis.integrations.alarms.oss_nms import OSSAlarmAdapter\n",
        "\n",
        "print('PIIS core modules successfully imported.')\n"
    ]),
    md_cell([
        "## 1. Pipeline Initialization and Adapter Registration\n",
        "PIIS uses a unified ingestion pipeline that standardizes multi-source telecom payloads into canonical envelopes.\n"
    ]),
    code_cell([
        "pipeline = UnifiedIngestionPipeline()\n",
        "pipeline.register_adapter(ServiceNowAdapter())\n",
        "pipeline.register_adapter(PrometheusAdapter())\n",
        "pipeline.register_adapter(OSSAlarmAdapter(adapter_id='ALM-NOK', source_system='NokiaOSS', vendor_hint='NOKIA'))\n",
        "\n",
        "print('Registered Adapters:', [a['adapter_id'] for a in pipeline.list_adapters()])\n"
    ]),
    md_cell([
        "## 2. Ingesting a Canonical Telecom Incident\n",
        "Simulate an incoming ServiceNow ticket reporting an RF feeder mismatch on a 5G gNodeB.\n"
    ]),
    code_cell([
        "now_iso = datetime.now(timezone.utc).isoformat()\n",
        "ticket = {\n",
        "    'sys_id': 'a98df7b01b827300c0147596cc4bcb11',\n",
        "    'number': 'INC0089201',\n",
        "    'short_description': 'Sector degraded: High VSWR on 5G NR Cell-1',\n",
        "    'description': 'NOC telemetry indicates RF feeder mismatch and VSWR > 1.8 on gNodeB GNB-RAN-701.',\n",
        "    'priority': '2',\n",
        "    'category': 'RAN',\n",
        "    'u_network_domain': 'RAN',\n",
        "    'cmdb_ci': 'GNB-RAN-701',\n",
        "    'state': '1',\n",
        "    'sys_created_on': now_iso,\n",
        "    'u_affected_subscribers': 1420,\n",
        "    'u_fault_category': 'antenna_vswr_fault'\n",
        "}\n",
        "\n",
        "envelope = IngestionEnvelope.create(\n",
        "    source_system='ServiceNow',\n",
        "    source_type='OPERATOR_INTERNAL',\n",
        "    raw_payload=ticket,\n",
        "    external_event_id=ticket['number'],\n",
        "    observation_timestamp=now_iso\n",
        ")\n",
        "result = pipeline.ingest_envelope(envelope)\n",
        "print('Ingestion Status:', result.status)\n",
        "print('Canonical Incident ID:', result.canonical_id)\n"
    ]),
    md_cell([
        "## 3. Automated Evidence Grounding and Investigation Execution\n",
        "Trigger the multi-stage investigation engine to analyze the incident against historical runbooks and active alarms.\n"
    ]),
    code_cell([
        "ctx = pipeline.investigate_incident(result.canonical_id)\n",
        "print('Incident Title:', ctx.title)\n",
        "print('Domain:', ctx.network_domain)\n",
        "print('Hypotheses Count:', len(ctx.hypotheses))\n",
        "print('Recommendations Count:', len(ctx.recommendations))\n",
        "print('Epistemic Status:', ctx.epistemic_status)\n"
    ]),
    md_cell([
        "## 4. Ranked Hypotheses and Diagnostic Recommendations\n",
        "Inspect the synthesized hypotheses and human-reviewable diagnostic steps.\n"
    ]),
    code_cell([
        "for idx, hyp in enumerate(ctx.hypotheses, 1):\n",
        "    print(f'\\nHypothesis #{idx} (Status: {hyp.status}, Confidence Proxy: {hyp.confidence_proxy}):')\n",
        "    print(f'  Description: {hyp.description}')\n",
        "    print(f'  Rationale: {hyp.confidence_rationale}')\n",
        "\n",
        "print('\\n--- Recommended Diagnostic Actions ---')\n",
        "for rec in ctx.recommendations:\n",
        "    print(f'- Action: {rec.description}')\n",
        "    print(f'  Reason: {rec.reason}')\n",
        "    print(f'  Runbook: {rec.source_runbook_id}')\n",
        "    print(f'  Approval Required: {rec.human_approval_required}')\n"
    ])
]

# -------------------------------------------------------------
# Notebook 2: Telemetry Anomaly Detection
# -------------------------------------------------------------
nb2_cells = [
    md_cell([
        "# PIIS: Causal Telemetry Anomaly Detection\n",
        "\n",
        "This notebook explores the statistical and machine-learning anomaly detection algorithms used in PIIS.\n",
        "\n",
        "### Key Principles\n",
        "- **Strict Causal Aggregations:** Calculations use trailing rolling windows to prevent lookahead data leakage.\n",
        "- **Multi-Model Evaluator:** Combines 3-Sigma Dynamic Thresholding and Isolation Forest algorithms.\n",
        "- **Telecom Signal Focus:** Evaluates radio frequency VSWR, optical Rx power attenuation, and UPF packet drop ratios.\n"
    ]),
    code_cell([
        "import sys\n",
        "import os\n",
        "import numpy as np\n",
        "from datetime import datetime, timezone, timedelta\n",
        "\n",
        "sys.path.insert(0, os.path.abspath('../src'))\n",
        "\n",
        "from piis.anomaly.detector import TelemetryAnomalyPipeline\n",
        "\n",
        "print('Anomaly detection pipeline imported.')\n"
    ]),
    md_cell([
        "## 1. Generating Baseline and Degraded Telemetry Streams\n",
        "Simulate 60 minutes of nominal VSWR telemetry on a 5G gNodeB followed by an abrupt antenna feeder degradation.\n"
    ]),
    code_cell([
        "np.random.seed(42)\n",
        "base_time = datetime.now(timezone.utc) - timedelta(minutes=60)\n",
        "\n",
        "# 45 nominal minutes (mean = 1.15, std = 0.05)\n",
        "nominal = np.random.normal(1.15, 0.05, 45)\n",
        "# 15 degraded minutes (feeder degradation, mean = 1.95, std = 0.10)\n",
        "degraded = np.random.normal(1.95, 0.10, 15)\n",
        "vswr_values = np.concatenate([nominal, degraded])\n",
        "\n",
        "timestamps = [(base_time + timedelta(minutes=i)).isoformat() for i in range(60)]\n",
        "print(f'Generated {len(vswr_values)} time-series samples.')\n"
    ]),
    md_cell([
        "## 2. Running Anomaly Evaluation\n",
        "Feed the samples into the detector to observe dynamic threshold breach detection.\n"
    ]),
    code_cell([
        "detector = TelemetryAnomalyPipeline()\n",
        "anomalies_detected = []\n",
        "\n",
        "for ts, val in zip(timestamps, vswr_values):\n",
        "    res = detector.evaluate_sample(\n",
        "        metric_name='vswr_ratio',\n",
        "        network_element_id='GNB-RAN-701',\n",
        "        value=float(val),\n",
        "        timestamp=ts\n",
        "    )\n",
        "    if res.is_anomaly:\n",
        "        anomalies_detected.append((ts, val, res.severity, res.z_score))\n",
        "\n",
        "print(f'Total Anomaly Windows Triggered: {len(anomalies_detected)}')\n",
        "if anomalies_detected:\n",
        "    print('First Detected Anomaly:')\n",
        "    print(f'  Timestamp: {anomalies_detected[0][0]}')\n",
        "    print(f'  Value: {anomalies_detected[0][1]:.3f}')\n",
        "    print(f'  Severity: {anomalies_detected[0][2]}')\n",
        "    print(f'  Z-Score: {anomalies_detected[0][3]:.2f}')\n"
    ])
]

# -------------------------------------------------------------
# Notebook 3: Cryptographic Audit Ledger Verification
# -------------------------------------------------------------
nb3_cells = [
    md_cell([
        "# PIIS: Cryptographic Audit Ledger & RFC 8785 Verification\n",
        "\n",
        "This notebook demonstrates the cryptographic integrity architecture of PIIS.\n",
        "\n",
        "### Integrity Guarantees\n",
        "- **RFC 8785 Canonicalization (JCS):** Guarantees byte-level JSON serialization determinism across different runtimes.\n",
        "- **SHA-256 Hash Chaining:** Every entry links to the previous entry digest, preventing undetected record insertion or deletion.\n",
        "- **HMAC-SHA256 Notarization:** Authenticated review receipts prove authorization by genuine human operators.\n",
        "- **Monotonic Checkpoint Anchor:** Verifies that the ledger has not suffered truncation or state rollbacks.\n"
    ]),
    code_cell([
        "import sys\n",
        "import os\n",
        "import json\n",
        "\n",
        "sys.path.insert(0, os.path.abspath('../src'))\n",
        "\n",
        "from piis.audit.canonical import CanonicalJsonSerializer\n",
        "from piis.investigation.approval import HumanApprovalWorkflow\n",
        "from piis.investigation.schemas import DiagnosticRecommendation, RecommendationRisk\n",
        "\n",
        "print('Audit and cryptographic modules imported.')\n"
    ]),
    md_cell([
        "## 1. RFC 8785 Canonical JSON Serialization Proof\n",
        "Demonstrate how key reordering or whitespace changes produce an identical cryptographic byte representation.\n"
    ]),
    code_cell([
        "obj1 = {'b_field': 100, 'a_field': 'telecom', 'nested': {'y': 2, 'x': 1}}\n",
        "obj2 = {'nested': {'x': 1, 'y': 2}, 'a_field': 'telecom', 'b_field': 100}\n",
        "\n",
        "serializer = CanonicalJsonSerializer()\n",
        "canonical_bytes1 = serializer.serialize(obj1)\n",
        "canonical_bytes2 = serializer.serialize(obj2)\n",
        "digest1 = serializer.compute_digest(obj1)\n",
        "digest2 = serializer.compute_digest(obj2)\n",
        "\n",
        "print('Canonical Bytes Match:', canonical_bytes1 == canonical_bytes2)\n",
        "print('SHA-256 Digest Match:', digest1 == digest2)\n",
        "print('Canonical Output:', canonical_bytes1.decode('utf-8'))\n"
    ]),
    md_cell([
        "## 2. Review Decision Signing and Ledger Chaining\n",
        "Register a diagnostic recommendation and simulate an authenticated human operator approval.\n"
    ]),
    code_cell([
        "workflow = HumanApprovalWorkflow()\n",
        "rec = DiagnosticRecommendation(\n",
        "    recommendation_id='REC-AUDIT-001',\n",
        "    description='Perform RF feeder realignment on Cell 1',\n",
        "    reason='VSWR exceeds 1.8 baseline',\n",
        "    supporting_evidence_ids=['EVID-001'],\n",
        "    source_runbook_id='SOP-RAN-VSWR-001',\n",
        "    risk_classification=RecommendationRisk.READ_ONLY_SAFE,\n",
        "    human_approval_required=True\n",
        ")\n",
        "workflow.register_recommendation(rec, incident_id='INC-SNOW-INC0089201')\n",
        "\n",
        "receipt = workflow.approve_recommendation(\n",
        "    recommendation_id='REC-AUDIT-001',\n",
        "    reviewer_id='noc-operator-01',\n",
        "    review_notes='Verified RF line telemetry; feeder replacement approved.'\n",
        ")\n",
        "\n",
        "print('Approval Receipt Generated:')\n",
        "print('  Action:', receipt.action)\n",
        "print('  Sequence ID:', receipt.sequence_id)\n",
        "print('  Record Digest (SHA-256):', receipt.record_digest)\n",
        "print('  Previous Digest:', receipt.previous_record_digest)\n",
        "print('  HMAC Signature:', receipt.hmac_signature[:32] + '...')\n"
    ])
]

os.makedirs("notebooks", exist_ok=True)
with open("notebooks/01_incident_triage_and_investigation.ipynb", "w", encoding="utf-8") as f:
    json.dump(make_notebook(nb1_cells), f, indent=2)

with open("notebooks/02_telemetry_anomaly_detection.ipynb", "w", encoding="utf-8") as f:
    json.dump(make_notebook(nb2_cells), f, indent=2)

with open("notebooks/03_cryptographic_audit_ledger_verification.ipynb", "w", encoding="utf-8") as f:
    json.dump(make_notebook(nb3_cells), f, indent=2)

print("All 3 notebooks successfully written to notebooks/")
