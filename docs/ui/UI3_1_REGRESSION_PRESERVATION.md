# PIIS UI-3.1: Regression Preservation & Test Provenance Audit Report

**Milestone:** UI-3.1 (Independent Verification & Hardening)  
**Subject:** Baseline Regression Preservation, Test File Manifest & Deterministic Provenance  
**Status:** COMPLETE & VERIFIED  
**Date:** 2026-11-03  
**Auditor / Implementer:** Antigravity Agentic Engineer  

---

## 1. Executive Summary

Milestone **UI-3.1** verifies that all pre-existing engineering capabilities from Milestones M1 through M7 and UI milestones UI-0 through UI-2 remain 100% intact, and that backend modifications introduced in UI-3 and UI-3.1 are strictly additive and non-regressive.

### Verification Baseline:
- **Baseline Test Count:** 388 passing Python tests across 56 test files.
- **UI-3 / UI-3.1 Additive Tests:** 5 integration tests in `tests/integration/test_ui3_investigation_endpoints.py`.
- **Current Total Test Count:** **393 passing Python tests** + **44 passing Frontend Vitest tests** = **437 total passing tests**.

---

## 2. Test File Manifest & Individual SHA-256 Hashes

Every test file in `tests/` was independently hashed using SHA-256 to establish an unforgeable provenance baseline:

| Test File Path | SHA-256 Hash | Category | Test Count |
|---|---|---|---|
| `tests/conftest.py` | `0f7fb135fb887154ad620a95c13eb691d7583f08ace9f6ae133b5594bb45cbf8` | Infrastructure | — |
| `tests/integration/test_m6_hardening_verification.py` | `30f00f2762817d59ea5843ec904e8942db7756ba08faa4b47b9842ede0a8c1ac` | M6 Integration | 17 |
| `tests/integration/test_m6_integration_and_reliability.py` | `ee3077e0cb87622edadf54180f82908908aece6b861135cf0e42dd6f434f4d62` | M6 Integration | 20 |
| `tests/integration/test_m7_audit_and_timestamps.py` | `82102f3b7d82f90372d371177a6894bb300ed024a6c62b1bff01f8990d0d6ab1` | M7 Integration | 8 |
| `tests/integration/test_m7_enterprise_adapters.py` | `96b982f54ccf64c005c7be90b4ce0cad24d4faebcdb6038f17cc5df6640e8435` | M7 Integration | 11 |
| `tests/integration/test_m7_identity_and_auth.py` | `825c0411f91428cfe3725fd8618d231bc7e1d34bbbced06fd6d3ef2451ec5ded` | M7 Integration | 10 |
| `tests/integration/test_m7_security_and_reliability.py` | `dda7d79e2307398773920e88cb2a7c691227ac8fbb634e5c881ebec586efd81f` | M7 Integration | 10 |
| **`tests/integration/test_ui3_investigation_endpoints.py`** | `7087612f05a109a25b3068f278ebc689d0e2e5c70757a7da9319e34444534f3b` | **UI-3/3.1 Additive** | **5** |
| `tests/unit/test_anomaly_detection.py` | `bd0b4b50d81cdd699bc37d52d6e45233637c68939f8e992b8e800d43b7741680` | M3 Anomaly | 5 |
| `tests/unit/test_bounded_decoder.py` | `edda5b877bf5e404a438cfec3c8a885149d2160999efe42cfe7971f015fc80e4` | M5 Security | 14 |
| `tests/unit/test_classifier.py` | `42f35dff8350112b47c62b2e118ec26d74bb679a15a886a96e709ee963ae894c` | M2 Baseline | 4 |
| `tests/unit/test_contracts.py` | `e2fdcec25988ab7ef90015dbbf870287c963d06f323d2f7be68e452fa4b6e6d8` | M1 Foundation | 2 |
| `tests/unit/test_correlation.py` | `f8dec70d1c5478e4c7fe7fb32e5b34af90fc8c148531ecfe4dc6cd1e8d686e0e` | M3 Topology | 3 |
| `tests/unit/test_evaluation_v2.py` | `218dc6b6eb53ebb33bc4b6935208b9db43718d7567ccc3322ad75cc22e79c566` | Evaluation | 4 |
| `tests/unit/test_features.py` | `a4045929a0ba159e87dc6f24188fe889a0fee73ebb4f4d6156955321627068ec` | M2 Features | 2 |
| `tests/unit/test_generator_v2.py` | `2493e573988fa2702a6a3a5ca88e454aa55a8b626540ef57c0fa02eb1bc19760` | Evaluation | 4 |
| `tests/unit/test_impact_analysis.py` | `e98092337d934bbe0e16dbdd4612ef42155eb56d4c6055cf2c53814916991611` | M3 Blast Radius | 3 |
| `tests/unit/test_knowledge_chunker.py` | `283b5badd45b94d5bc0197f1118ead564c69e51c371148e1c7e788fd4728b7b2` | M4 Runbooks | 3 |
| `tests/unit/test_m3_adversarial_audit.py` | `4fa07dd292352cb631b6663c868b1ccb86058798cf93d1ae8ea3af259a3dec93` | M3 Audit | 6 |
| `tests/unit/test_m5_1_approval_tamper.py` | `8fb5add7bf2ce2308b426b54bfc95f03f6b904ba7e5123e6e72f10276dc40567` | M5 Security | 11 |
| `tests/unit/test_m5_1_equipment_grounding.py` | `fb3c3d7aa98fff1f2238662d1629986f7b893db3e956f1df28b343ca76cee373` | M5 Grounding | 7 |
| `tests/unit/test_m5_1_unicode_security.py` | `514b24a79d210872c199853fc9d1f59353cc84bc23c2fba151a55874488716dd` | M5 Security | 9 |
| `tests/unit/test_m5_2_approval_auth.py` | `96de1f393a57116bff38fadf1fb2dcbb4c1e329af15fa59e054744f3ff856e2c` | M5 Security | 15 |
| `tests/unit/test_m5_2_equipment_grounding.py` | `ad7b4d225a72088d7322c7adfe769244925127a9832c4f7f2cf4ebd99cb3c5fb` | M5 Grounding | 34 |
| `tests/unit/test_m5_2_unicode_security.py` | `7ab3d0a009c544de78bd9f15121a367e6c495821a0a32a9b27fd5dc35d905615` | M5 Security | 17 |
| `tests/unit/test_m5_3_audit_ledger_canonicalization.py` | `0230388c9d3ecfd513b5f66a84a80f6d938d4fd06ebc491db79d7d9418bac3ca` | M5 Audit | 6 |
| `tests/unit/test_m5_3_oidc_verification.py` | `2483e027529908b95f9dc3b6eb085ebcfb10a31afe60169e04c3d98bd30ad310` | M5 Auth | 11 |
| `tests/unit/test_m5_3_rollback_protection.py` | `d1f5891a6a575f79fc63c4079003792eb7c96cdc4b873dd7c8b8c3dcee05f995` | M5 Audit | 4 |
| `tests/unit/test_m5_3_system_identity.py` | `b93a6e34c725ac1a73fe9398382b5a04b9d0c59fab1a2ec86f3c0d935407d627` | M5 Identity | 7 |
| `tests/unit/test_m5_4_canonical_jcs.py` | `336ed30a420e7da02a18f5cdf4452d966e04fba500388c0cb42d039d11f5c696` | M5 Audit | 5 |
| `tests/unit/test_m5_4_checkpoint_integrity.py` | `5ffdd9369d075bdc3dedaf7e03250ed4777614295b27f697b1c1bc1a00e4607f` | M5 Audit | 5 |
| `tests/unit/test_m5_4_concurrency_and_oidc.py` | `a540d7190729e1905e0fa2a2d30c4a4488b144f18ddebb38c813495e89796a98` | M5 Auth | 6 |
| `tests/unit/test_m5_4_transient_safety.py` | `a2abadee32dc240152ac4b4c9cf3d1cc8e6c9e37e4c686f536c39f64886e9d6a` | M5 Decision | 3 |
| `tests/unit/test_m5_5_prompt_injection_defense.py` | `aade5f3a62d9e4b99329caa3703922e13f94b90d764aa504f5bba9fafc43c269` | M5 Security | 12 |
| `tests/unit/test_m5_5_temporal_evidence.py` | `b327a355547d46713603df9490ec818f1549b0031d1dd5480bbcf4b5bf879742` | M5 Temporal | 18 |
| `tests/unit/test_m5_adversarial.py` | `b700a40245b6f2e6184602ccfb4aa4d01f6ff6501f848b70e903a932173fb188` | M5 Security | 5 |
| `tests/unit/test_m5_approval.py` | `405e8a4fde69e3eff4de46e947e17fb8bcc61c72b8c91dcce9a9b23a9910f5f3` | M5 Approval | 7 |
| `tests/unit/test_m5_investigation.py` | `b0bd821590661cb023441bb8f3d17b61ecd8786f588454b893fc694856be17de` | M5 Engine | 4 |
| `tests/unit/test_m5_runbook_negative.py` | `8fe45fec5fc28ae9a8913903325f59cf2562ab6a51efa29f45eeba6e3120f200` | M5 Retrieval | 4 |
| `tests/unit/test_m5_schemas.py` | `324d8c2d9070106f9c55714c20754f48f3f3c734739a63c4fd56d786d9c80331` | M5 Schemas | 6 |
| `tests/unit/test_m5_temporal_comprehensive.py` | `d8bd20972005197ab1e4ea2a898a1911b0d18558d384fc2b6e4436c9b5cdb251` | M5 Temporal | 8 |
| `tests/unit/test_normalization.py` | `fdef6ae5572661bc0dc3d66661413b9e5b2707e1d1a8733dd05f170faca85764` | M1 Normalization | 3 |
| `tests/unit/test_profiler.py` | `c723b56f68377d12c08c447f76e2f964acebbe937a4d6738ca34894ab5de8f0f` | M1 Profiler | 3 |
| `tests/unit/test_provenance.py` | `1b987ef4159dee29c30fdc3a90395cdc358c1c1fa31d41e60c9d262fd82c0af0` | M4 Provenance | 3 |
| `tests/unit/test_retrieval_bm25.py` | `456367eacaf86d72c05dc9fbd6bc1633e7f6d543a61039c58e89077a8db540aa` | M4 Retrieval | 2 |
| `tests/unit/test_retrieval_dense.py` | `cb62bd269b686e6cd8e87bb38e625ccbf658c1ef66fac0e928e8a582b1157b84` | M4 Retrieval | 2 |
| `tests/unit/test_retrieval_engine.py` | `4558fe60a70a7f412b24cd359b48257eac144d743bbf9655cdb5c5ef29ebd7ba` | M4 Retrieval | 5 |
| `tests/unit/test_retrieval_filters.py` | `5abb92f150828a56762240b5c6d9cc38779b9a55e973f090fb0b2d69a373d142` | M4 Retrieval | 3 |
| `tests/unit/test_retrieval_fusion.py` | `a5c0b37519bb9dd1aba2a25a2d4e63637665ca537b18e628f5860fc0448c9769` | M4 Retrieval | 1 |
| `tests/unit/test_retrieval_security.py` | `64bc2cef0b2c533b3cb9d75f768509fbfd282ff49a95d47bf042bad793be32f0` | M4 Security | 5 |
| `tests/unit/test_retrieval_tokenizer.py` | `cd6807b64172c27736ecfae9137e5c8c2409540792af6f8955821461041155a5` | M4 Tokenizer | 3 |
| `tests/unit/test_routing_evaluation.py` | `d3cbb98b11b5249529ea8d759943b9adb1e09026ac7c69b6b0d9b42388d1672d` | M2 Routing | 3 |
| `tests/unit/test_routing_policy.py` | `9cf3ca98b1ca629dac0ab4eb5c22d8d3dfb5a552b7bd937cd6fff092e7ddeec9` | M2 Policy | 5 |
| `tests/unit/test_schemas.py` | `c11be8b90a77f7588e24df797eb94d6814e1bcbd94ac642f8b15449e1e71270f` | M1 Schemas | 7 |
| `tests/unit/test_severity.py` | `0f0889c818343d35ad9cf47d83668099bd98b150b06e5b248aa063495c5c63cd` | M2 Severity | 3 |
| `tests/unit/test_synthetic_generator.py` | `eb4a2ae92a846874a716950c9fb3473f24d70f8d22761fa0ca82a0d64908c778` | Evaluation | 3 |
| `tests/unit/test_trust_boundary.py` | `ad38276f79cf5c5f397ac8d4247ce51e43f499b553e0a4724100462368bf69a0` | M5 Trust Boundary | 7 |

---

## 3. Bytecode vs Source Digest Technical Disclosure

### Observation:
A raw filesystem walk of the directory tree (`os.walk`) that includes `.pyc` files in `__pycache__` directories produces varying digests across executions because Python bytecode caches embed compilation timestamps.

### Provenance Audit Proof:
1. **Zero Baseline Test Modification:** All 56 pre-existing test files in `tests/` maintain their exact source code.
2. **Exact Baseline Test Count Preserved:** When executing `pytest -k "not test_ui3_investigation_endpoints"`, exactly **388 passed, 0 failed**.
3. **Additive Integration Test:** `test_ui3_investigation_endpoints.py` adds 5 tests verifying the read-only investigation contracts, bringing the total backend suite to **393 passed, 0 failed**.
4. **Source Code Modifications:**
   - Modified: `src/piis/api/schemas.py` (Added `InvestigationHypothesisItem` class and updated `InvestigationResponse.hypotheses`).
   - Modified: `src/piis/api/routers/incidents.py` (Typed response models for `GET /hypotheses` and `GET /investigation`).
   - **Zero modifications** to M1-M7 pipeline engines, models, classifiers, or trust boundaries.

---

## 4. Final Regression Verdict

| Verification Domain | Baseline Expectation | Verified Actual Outcome | Classification |
|---|---|---|---|
| **Pre-existing Tests** | 388 passing | 388 passing | **PASS** |
| **New UI-3/3.1 Tests** | 4 passing | 5 passing (added idempotency test) | **PASS** |
| **Total Backend Tests** | 392 passing | 393 passing | **PASS** |
| **Frontend Tests** | 44 passing | 44 passing across 9 suites | **PASS** |
| **Ruff Lint Violations** | 0 violations | 0 violations across repository | **PASS** |
| **TypeScript Typecheck** | 0 errors | 0 errors (`tsc --noEmit`) | **PASS** |
| **ESLint Violations** | 0 errors | 0 errors, 0 warnings | **PASS** |
