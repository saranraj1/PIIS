# PIIS Human Review Annotation Protocol & Adjudication Standard

**Document ID:** PIIS-PROTO-M2-HUMAN-01  
**Target Dataset:** `docs/data/M2_HUMAN_REVIEW_SAMPLE.jsonl` (36 Stratified Sample Cards)  
**Governance:** Independent Double-Blind Review with Inter-Annotator Agreement (Cohen's / Fleiss' Kappa)  
**Status:** DRAFTED & LOCKED FOR REVIEW PANEL EXECUTION  

---

## 1. Scope & Objective

This protocol defines the instructions, rubric scoring, and statistical adjudication procedures for independent human domain experts evaluating PIIS synthetic incident records.

**Audit Notice:** The existence of sample cards in `M2_HUMAN_REVIEW_SAMPLE.jsonl` with status `PENDING_AUDIT` does NOT constitute human validation. Operational validation requires completing this protocol with at least two qualified telecom operations engineers.

---

## 2. Reviewer Qualifications & Blinded Setup

- **Reviewer Panel:** Minimum 2 Senior Telecom Operations Engineers (NOC Tier-2 / Tier-3, 5+ years experience in 4G/5G radio and core operations).
- **Blinded Presentation:** Reviewers are presented with:
  - Incident `title`
  - Incident `description`
  - Reported `network_domain`
  - Reported `affected_subscribers`
  - Reported `network_element_ids`
- **Quarantined from Reviewers:**
  - `scenario_family_id`
  - `template_id`
  - `causal_configuration_id`
  - Model predictions and rule formulas.

---

## 3. Four-Dimension Evaluation Rubric

Reviewers score each sample card on four independent dimensions (1 to 5 scale):

### Dimension 1: Technical & Causal Realism (1–5)
- **5 (Highly Realistic):** Technical symptoms, alarms, and KPI behavior reflect actual live 4G/5G network failure modes.
- **3 (Plausible):** Minor phrasing awkwardness, but physically coherent.
- **1 (Unrealistic / Fabricated):** Impossible combination of metrics or domain confusion (e.g. BGP routing in RAN physical layer).

### Dimension 2: Operational Severity Consistency (1–5)
- **5 (Consistently Rated):** The assigned severity tier (`CRITICAL`, `MAJOR`, `MINOR`, `WARNING`) accurately reflects the operational business impact given the subscriber count, redundancy state, and service criticality.
- **3 (Debatable):** Disagreement of at most 1 severity tier (e.g. `MAJOR` vs `CRITICAL`).
- **1 (Severe Inconsistency):** Critical outage with $>10,000$ subscribers labeled `WARNING`, or routine diurnal trough labeled `CRITICAL`.

### Dimension 3: Support Tier Assignment (1–5)
- **5 (Accurate Routing):** Support tier (`L1`, `L2`, `L3`, `HUMAN_REVIEW`) matches operational procedures:
  - Documented automated SOP $\rightarrow$ L1
  - Physical RF instrumentation / optical OTDR $\rightarrow$ L2
  - Vendor software defect / field fiber cable splice $\rightarrow$ L3
  - Ambient noise / nominal baseline $\rightarrow$ HUMAN_REVIEW
- **1 (Erroneous Routing):** L1 assigned to physical fiber cut, or L3 assigned to standard routine reload.

### Dimension 4: Natural Language Quality (1–5)
- **5 (Authentic):** Phrasing mirrors NOC operator notes, OSS alarm digests, or customer trouble tickets.
- **1 (Artificial):** Repetitive synthetic template artifacts or unnatural robotic syntax.

---

## 4. Inter-Annotator Agreement & Adjudication Protocol

1. **Cohen's Kappa ($\kappa$):** Computed pairwise across independent annotator severity and support tier ratings.
   - Target Acceptance Threshold: $\kappa \ge 0.70$ (substantial agreement).
   - If $\kappa < 0.60$, rubric calibration session must be held before continuing.
2. **Disagreement Adjudication:** Where annotators disagree by 1 tier, a third adjudicating Senior Network Architect reviews the case card to issue the final operational consensus label.
