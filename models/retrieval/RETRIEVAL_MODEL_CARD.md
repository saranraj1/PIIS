# PIIS Retrieval Model Card: Hybrid BM25 Okapi & Dense Bi-Encoder

---

## 1. Model Overview

| Attribute | Specification |
|---|---|
| **System** | Production Incident Intelligence System (PIIS) |
| **Subsystem** | Milestone 4: Historical Incident Retrieval & Hybrid Grounding |
| **Model Architectures** | Okapi BM25 Lexical Index + Dense Bi-Encoder (Dual Representation) |
| **Primary Dense Model** | `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional dense vectors) |
| **Fallback Dense Model** | Deterministic Word-Level TF-IDF Projection (Zero-dependency, offline baseline) |
| **Lexical Engine** | Okapi BM25 with Robertson-Spärck Jones non-negative IDF |
| **Fusion Algorithm** | Reciprocal Rank Fusion (RRF, $k=60$) with Calibrated Multi-Modal Quality Modulation |
| **Security Guard** | Pattern-based instruction neutralization and `<operational_evidence>` sandboxing |
| **License** | Apache-2.0 / MIT Compatible |
| **Date** | 2026-11-01 |

---

## 2. Intended Use & Boundaries

### 2.1 Intended Use
- Retrieve approved Standard Operating Procedures (SOPs), runbooks, verified historical incident resolutions (TelecomTS), and 3GPP technical specifications.
- Provide factual, provenance-grounded evidence passages to support Level-2/Level-3 telecom Network Operations Center (NOC) engineers.
- Disambiguate telecom alarms, hex error codes (`0x80040111`), 3GPP interface identifiers (`Xn-U`, `N2`, `N4`), and KPI degradation patterns.
- Protect downstream systems from malicious prompt injections, privilege escalation attempts, and destructive shell commands embedded in incident records.

### 2.2 Out-of-Scope & Misuse Boundaries
- **No Autonomous Action:** The retrieval subsystem is strictly an Information Retrieval (IR) and Evidence Grounding engine. It executes zero operational CLI commands, modifies zero gNodeB parameters, and triggers zero OSS mutations.
- **No Conversational Synthesis:** Conversational response drafting and interactive user dialogue are strictly reserved for Milestone 5.
- **No Synthetic Benchmark Hallucination:** Synthetic benchmarks (M1–M2.1 TelcoBench) must never be presented as real historical operator incidents.
- **No Remote API Dependency:** The retrieval engine operates 100% locally and deterministically, without requiring external proprietary LLM APIs.

---

## 3. Architecture & Mathematical Specifications

### 3.1 Lexical Architecture: Okapi BM25
The lexical component employs Robertson-Spärck Jones Okapi BM25 with length normalization and custom tokenization:

$$\text{Score}_{\text{BM25}}(D, Q) = \sum_{t \in Q} \text{IDF}(t) \cdot \frac{f(t, D) \cdot (k_1 + 1)}{f(t, D) + k_1 \cdot \left(1 - b + b \cdot \frac{|D|}{\text{avgdl}}\right)}$$

- **Hyperparameters:** $k_1 = 1.5$, $b = 0.75$.
- **Non-Negative IDF Formulation:**
  $$\text{IDF}(t) = \max\left(0.0, \ln\left(1.0 + \frac{N - n(t) + 0.5}{n(t) + 0.5}\right)\right)$$
- **Custom Telecom Tokenizer:** Preserves exact alphanumeric alarm strings (`ALM-RAN-VSWR-HIGH`), hexadecimal codes (`0x80040111`), 3GPP interfaces (`Xn-U`, `F1-C`, `N2`, `N4`), and vendor acronyms (`gNodeB`, `P-CSCF`, `AMF`, `UPF`).

### 3.2 Semantic Architecture: Dense Bi-Encoder
- **Base Architecture:** 6-layer MiniLM Transformer (`sentence-transformers/all-MiniLM-L6-v2`).
- **Embedding Dimension:** 384 dimensions.
- **Normalization:** L2-normalized unit vectors ($\|\mathbf{v}\|_2 = 1.0$).
- **Similarity Metric:** Cosine similarity via dot product:
  $$\text{Sim}(\mathbf{q}, \mathbf{d}) = \max(0.0, \mathbf{q} \cdot \mathbf{d})$$
- **Deterministic Offline Fallback:** When PyTorch/Transformers dependencies are missing or timeout exceeds 200ms, the system switches transparently to a word-level TF-IDF L2-normalized vectorizer maintaining identical 384-dimensional cosine similarity contracts.

### 3.3 Reciprocal Rank Fusion & Confidence Calibration
Combines rank positions from lexical and semantic rankers:

$$\text{RRF}(d) = \sum_{m \in \{\text{BM25}, \text{Dense}\}} \frac{w_m}{k + \text{Rank}_m(d)}, \quad k = 60, \quad w_{\text{BM25}} = 1.0, \quad w_{\text{Dense}} = 1.0$$

Calibrated confidence scales rank ratio by multi-modal quality factors:

$$c(d) = \left(\frac{\text{RRF}(d)}{\text{RRF}_{\max}}\right) \cdot \left[0.5 \cdot \min\left(1.0, \frac{s_{\text{BM25}}}{5.0}\right) + 0.5 \cdot \min\left(1.0, \frac{s_{\text{Dense}}}{0.5}\right)\right]$$

---

## 4. Quantitative Benchmark Performance

Evaluated across the 100-query M4 Benchmark Suite (80 ground-truth queries + 10 novel fault queries + 10 adversarial injection queries):

| Metric | Standalone BM25 | Standalone Dense (MiniLM) | Hybrid RRF Engine | Target SLA |
|---|---|---|---|---|
| **Recall@1** | 0.9375 | 0.9500 | **0.9625** | $\ge 0.85$ |
| **Recall@3** | 0.9875 | 0.9750 | **1.0000** | $\ge 0.95$ |
| **Recall@5** | 1.0000 | 0.9875 | **1.0000** | $\ge 0.98$ |
| **Precision@1** | 0.9375 | 0.9500 | **0.9625** | $\ge 0.85$ |
| **Precision@3** | 0.7708 | 0.7917 | **0.7958** | $\ge 0.70$ |
| **MRR (Mean Reciprocal Rank)** | 0.9635 | 0.9650 | **0.9750** | $\ge 0.90$ |
| **nDCG@3** | 0.9595 | 0.9503 | **0.9716** | $\ge 0.90$ |
| **nDCG@5** | 0.9679 | 0.9551 | **0.9716** | $\ge 0.90$ |
| **Domain Precision** | 0.8625 | 0.8958 | **0.9000** | $\ge 0.85$ |
| **Source Attribution Accuracy** | 1.0000 | 1.0000 | **1.0000** | $1.0000$ |
| **Latency P50** | 0.03 ms | 7.11 ms | **7.97 ms** | $< 25.0\text{ ms}$ |
| **Latency P95** | 0.04 ms | 10.09 ms | **9.95 ms** | $< 50.0\text{ ms}$ |

---

## 5. Security & Safety Characteristics

- **Adversarial Threat Detection Rate:** **100.0%** across 5 threat classes (Direct Prompt Injection, Privilege Escalation, Destructive Command Injection, Fake System Prompt, Command Exfiltration/SSRF).
- **Instruction Neutralization Rate:** **100.0%** — all detected malicious instructions are defanged to inert tokens (`[NEUTRALIZED_*]`).
- **Clean Query False Positive Rate:** **0.0%** across 90 clean operational queries.
- **Structural Sandboxing:** All retrieved chunk text is wrapped in `<operational_evidence>` XML boundaries with explicit non-executable epistemic disclaimers.

---

## 6. Failure Modes & Degradation Ladder

| Failure Scenario | Engine Behavior | Epistemic Safeguard |
|---|---|---|
| Dense model timeout ($> 200\text{ ms}$) or crash | Degrades to **Tier 2 (BM25-only)** | Full audit trace flags degraded mode; confidence discounted |
| Incompatible metadata filter eliminates 100% candidates | Anti-Silent Omission triggers | Returns explicit `filter_dropped_all=True` with audit trail |
| Max calibrated confidence $< 0.35$ with exact alarm | Falls back to **Tier 3 (Deterministic SOP Map)** | Delivers vetted SOP linked directly to alarm code |
| Max calibrated confidence $< 0.35$ without alarm match | Falls back to **Tier 4 (Human Review Abstention)** | Returns 0 hallucinated passages; requests human escalation |
