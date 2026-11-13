# Annotation handbook — draft v0.1

## Purpose
Create defensible labels for support routing and operational triage. This is not a universal telecom standard; each pilot operator must approve its support policy.

## Separate label dimensions
- Fault category: what technical failure appears to have occurred.
- Severity: operational impact under an agreed severity rubric.
- Support level: which support role should own the next action under the operator's policy.
- Resolution state: whether a fix is proposed, in progress or confirmed.
- Root cause: confirmed causal mechanism, not merely symptom or correlation.

## Support labels
- L1: documented first-line procedure is authorized and appropriate.
- L2: deeper technical investigation or elevated diagnostic capability is required.
- L3: vendor/product engineering or specialist ownership is required.
- HUMAN_REVIEW: evidence or policy is insufficient, ambiguous or high-risk.
- UNLABELED: not yet reviewed.

## Annotation procedure
1. Annotator receives only fields available at the prediction decision time for routing labels.
2. Annotator records label, rationale, evidence references and policy version.
3. Ambiguous cases are marked HUMAN_REVIEW, not forced into L1/L2.
4. A second annotator reviews a sample and all disagreements.
5. Adjudication records final label and disagreement reason.
6. Report inter-annotator agreement and label distribution.

## Prohibited shortcuts
- Do not label all RAN incidents as L2.
- Do not label based solely on severity.
- Do not infer support tier from a fault class or resolution text.
- Do not use post-resolution information for ticket-time prediction labels.
