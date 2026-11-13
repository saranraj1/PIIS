# M5.2 Equipment Grounding & Vendor Compatibility Report

## Executive Summary

This report documents the resolution of **FIND-M5.1-003** in PIIS Milestone 5.2. In M5.1, the retrieval system suffered from two major limitations:
1. **Conversational Prose Bleed**: Incidents mentioning client software or management tools (such as `Cisco AnyConnect VPN`, `Nokia NetAct EMS`, or `Ericsson ENM`) improperly poisoned the vendor extraction logic, causing non-Cisco equipment incidents to bind to Cisco and reject approved 3GPP runbooks.
2. **Unidirectional Vendor-Neutral Matching**: In `MetadataFilter`, queries for vendor-tagged incidents (e.g., Ericsson) were unable to match generic 3GPP SOPs because compatibility was only evaluated in one direction (`chunk_vendor == incident_vendor`).

In M5.2, [filters.py](file:///c:/Production%20level%20projects/PIIS/src/piis/retrieval/filters.py) and [engine.py](file:///c:/Production%20level%20projects/PIIS/src/piis/investigation/engine.py) were refactored to implement bidirectional vendor-neutral compatibility, strict metadata precedence, and client software noise elimination.

---

## 1. Architecture Implementation

### 1.1 Bidirectional Vendor-Neutral Compatibility
In `MetadataFilter._is_vendor_compatible(target_vendor, chunk_vendor)`:
- Chunks tagged as `GENERIC_3GPP` or `MULTI_VENDOR` are bidirectionally compatible with any vendor-tagged incident (`ERICSSON`, `NOKIA`, `HUAWEI`, `CISCO`, `JUNIPER`, `ZTE`).
- Incidents with `target_vendor == None` or `target_vendor == "MULTI_VENDOR"` can access any runbook.
- Proprietary vendor runbooks (e.g., Cisco-specific SOP `SOP-TRANS-BGP-002`) remain strictly isolated and **cannot** match incidents involving another vendor (e.g., Juniper) or generic queries.
- Missing chunk vendor metadata fails closed (no silent wildcard compatibility).

### 1.2 Elimination of Prose Bleed
In `IncidentInvestigationEngine._extract_vendor(incident)`:
- **Priority 1 (Structured Metadata)**: `incident["metadata"]["vendor"]` or `incident["equipment_vendor"]` take absolute precedence over narrative text.
- **Priority 2 (Network Element Prefixes)**: Element IDs starting with `ERIC-`, `NOK-`, `CISCO-`, `JUN-`, `HUA-`, `ZTE-` reliably extract the equipment vendor.
- **Client Software Filtering**: Narrative mentions of operational management portals and client VPNs are regex-filtered prior to extraction:
  - `Cisco AnyConnect`, `AnyConnect VPN`
  - `Nokia NetAct EMS`, `NetAct`
  - `Ericsson ENM`
  - `Huawei U2000`, `U2000`
  - `Wireshark`, `Webex`, `Zoom`
- **Ambiguity Abstention**: If vendor references remain contradictory or ambiguous, the engine safely abstains to `None`, allowing generic 3GPP runbook retrieval rather than falsely restricting search scope.

---

## 2. Evaluation Results Across 32 Test Cases

The test suite in [test_m5_2_equipment_grounding.py](file:///c:/Production%20level%20projects/PIIS/tests/unit/test_m5_2_equipment_grounding.py) and audit script [audit_m5_2_equipment_grounding.py](file:///c:/Production%20level%20projects/PIIS/scripts/audit_m5_2_equipment_grounding.py) evaluated 32 operational scenarios.

### 2.1 Group 1: Prose Bleed Elimination & End-to-End Grounding

| Case ID | Scenario Name | Injected Prose | Extracted Vendor | Retrieved Runbook | Hypothesis Status |
| :--- | :--- | :--- | :---: | :---: | :---: |
| `EQP-01` | Cisco AnyConnect in 5G RAN Incident | `Cisco AnyConnect VPN` | `ERICSSON` | `SOP-RAN-VSWR-001` | **SUPPORTED** |
| `EQP-02` | Nokia NetAct in 5G Core AMF Incident | `Nokia NetAct EMS` | `None` (Abstain) | `SOP-5GC-AMF-001` | **SUPPORTED** |
| `EQP-03` | Ericsson ENM on Juniper Router Cut | `Ericsson ENM portal` | `JUNIPER` | `SOP-TRANS-FIBER-001` | **SUPPORTED** |
| `EQP-04` | Huawei U2000 on Cisco ASR BGP Flap | `Huawei U2000 bridge` | `CISCO` | `SOP-TRANS-BGP-002` | **SUPPORTED** |

*All 4 end-to-end prose bleed incidents retrieved the correct SOP and produced a `SUPPORTED` diagnostic hypothesis without false-positive vendor contradictions.*

### 2.2 Group 2: Bidirectional Vendor-Neutral Compatibility Matrix

| Case ID | Incident Vendor | Runbook Vendor | Compatibility Expected | Actual Result | Status |
| :--- | :--- | :--- | :---: | :---: | :---: |
| `EQP-05` | `ERICSSON` | `GENERIC_3GPP` | Compatible | `True` | **PASS** |
| `EQP-06` | `NOKIA` | `GENERIC_3GPP` | Compatible | `True` | **PASS** |
| `EQP-07` | `HUAWEI` | `GENERIC_3GPP` | Compatible | `True` | **PASS** |
| `EQP-08` | `CISCO` | `GENERIC_3GPP` | Compatible | `True` | **PASS** |
| `EQP-09` | `JUNIPER` | `GENERIC_3GPP` | Compatible | `True` | **PASS** |
| `EQP-10` | `ZTE` | `GENERIC_3GPP` | Compatible | `True` | **PASS** |
| `EQP-11` | `MULTI_VENDOR`| `GENERIC_3GPP` | Compatible | `True` | **PASS** |
| `EQP-12` | `JUNIPER` | `CISCO` | Incompatible | `False` | **PASS** |
| `EQP-13` | `NOKIA` | `CISCO` | Incompatible | `False` | **PASS** |
| `EQP-14` | `ERICSSON` | `CISCO` | Incompatible | `False` | **PASS** |
| `EQP-15` | `GENERIC_3GPP`| `CISCO` | Incompatible | `False` | **PASS** |
| `EQP-16` | `CISCO` | `JUNIPER` | Incompatible | `False` | **PASS** |
| `EQP-17` | `ERICSSON` | `None` (Missing) | Incompatible (Fail-Closed) | `False` | **PASS** |

### 2.3 Group 3: Structured Precedence & Element Prefix Extraction

| Case ID | Evaluation Target | Expected Extraction | Actual Extraction | Status |
| :--- | :--- | :---: | :---: | :---: |
| `EQP-18` | `metadata.vendor="ERICSSON"`, text mentions Cisco | `ERICSSON` | `ERICSSON` | **PASS** |
| `EQP-19` | `metadata.vendor="NOKIA"`, text mentions Juniper | `NOKIA` | `NOKIA` | **PASS** |
| `EQP-20` | `incident.equipment_vendor="HUAWEI"`, text mentions ZTE | `HUAWEI` | `HUAWEI` | **PASS** |
| `EQP-21` | Element ID `ERIC-AAU-01` | `ERICSSON` | `ERICSSON` | **PASS** |
| `EQP-22` | Element ID `NOK-BBU-02` | `NOKIA` | `NOKIA` | **PASS** |
| `EQP-23` | Element ID `CISCO-ASR-03` | `CISCO` | `CISCO` | **PASS** |
| `EQP-24` | Element ID `JUN-PTX-04` | `JUNIPER` | `JUNIPER` | **PASS** |
| `EQP-25` | Element ID `HUA-RRU-05` | `HUAWEI` | `HUAWEI` | **PASS** |
| `EQP-26` | Element ID `ZTE-B8200-06` | `ZTE` | `ZTE` | **PASS** |
| `EQP-27` | Ambiguous text ("Checked equipment logs") | `None` (Abstain) | `None` | **PASS** |
| `EQP-28` | Client software mention ("Connected via AnyConnect") | `None` (Abstain) | `None` | **PASS** |

### 2.4 Group 4: Cross-Generation Network Isolation

| Case ID | Incident Generation | Runbook Generation | Expected Result | Actual Result | Status |
| :--- | :--- | :--- | :---: | :---: | :---: |
| `EQP-29` | `2G_GSM` | `5G_NR` | Incompatible | `False` | **PASS** |
| `EQP-30` | `3G_UMTS` | `5G_NR` | Incompatible | `False` | **PASS** |
| `EQP-31` | `WIMAX` | `5G_NR` | Incompatible | `False` | **PASS** |
| `EQP-32` | `5G_NR` | `5G_NR` | Compatible | `True` | **PASS** |

**Summary**: 32/32 Passed (100.0% Pass Rate).  
**Artifact Exported**: [m5_2_equipment_grounding_results.json](file:///c:/Production%20level%20projects/PIIS/artifacts/m5_metrics/m5_2_equipment_grounding_results.json).
