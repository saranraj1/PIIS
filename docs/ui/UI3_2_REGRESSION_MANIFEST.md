# PIIS UI-3.2 — Complete Regression Preservation Manifest

**Milestone:** UI-3.2  
**Date:** November 2026  
**Status:** 100% Passing & Cryptographically Reconciled  
**Total Tests:** 396 passed (388 baseline M1–M7 + 8 UI-3/3.2 integration)  
**Total Test Files:** 57 `.py` files (56 pre-existing + 1 additive UI-3 integration file)

---

## 1. Test File Enumeration Reconciliation

In prior milestone logs, an apparent ambiguity arose between references to "55 test files", "56 test files", and "57 test files". This section provides the definitive structural reconciliation:

| Category | File Count | Test Count | Description |
|---|---|---|---|
| **Root Fixtures / Harness** | 1 | 0 | `tests/conftest.py` (Pytest configuration and fixture anchors; contains 0 test functions) |
| **Pre-existing Integration Tests** | 6 | 76 | M6 & M7 hardening, enterprise adapters, auth, and security suites |
| **Pre-existing Unit Tests** | 49 | 312 | M1–M5 core pipelines, schemas, retrieval, grounding, and verification suites |
| **Pre-existing Baseline Total** | **56 files** (55 test files + 1 conftest) | **388 tests** | Complete untouched M1–M7 baseline |
| **Additive UI-3/3.2 Integration File** | 1 | 8 | `tests/integration/test_ui3_investigation_endpoints.py` |
| **Current Repository Total** | **57 files** (56 test files + 1 conftest) | **396 tests** | All suites passing (396 passed, 0 failed, 2 warnings) |

### Key Reconciliation Facts:
1. **55 Test Files vs 56 Files:** The pre-existing test suite consisted of 55 files named `test_*.py` plus 1 configuration anchor `conftest.py` = 56 `.py` files under `tests/`.
2. **Additive Nature of UI-3 Tests:** Zero pre-existing tests were modified, renamed, disabled, or removed. The 8 UI-3 tests reside entirely within a single new additive file (`test_ui3_investigation_endpoints.py`).
3. **No M1–M7 Regressions:** All 388 baseline tests pass unmodified.

---

## 2. Bytecode (`.pyc`) Digest Variance Explanation

During automated integrity audits, computing a raw recursive hash of the `tests/` directory tree often produced differing SHA-256 digests between test runs even when no source code had been modified.

### Root Cause Analysis:
When Python executes tests, the interpreter compiles `.py` files into bytecode stored in `__pycache__/*.pyc`. 
Under Python 3.7+ (PEP 552), `.pyc` files contain a 16-byte header:
- Magic number (4 bytes)
- Bit field flags (4 bytes)
- Timestamp or hash of the source file (4 bytes)
- File size (4 bytes)

In timestamp-based bytecode compilation (default), the `.pyc` header records the **file creation / compilation wall-clock timestamp**. Therefore:
1. Running `pytest` regenerates `.pyc` files with the current execution timestamp.
2. Even if the AST and bytecode instructions are bit-for-bit identical, the header timestamp alters the `.pyc` file's SHA-256 hash.
3. Any tool that naively hashes the directory tree without excluding `__pycache__` or `.pyc` files observes non-deterministic hash drift.

### Preservation Invariant:
All source integrity and regression audits in PIIS are strictly computed over **canonical source `.py` files** and `.ts` / `.tsx` files, completely excluding `__pycache__`, `*.pyc`, `node_modules/`, and `.pytest_cache/`.

---

## 3. Complete Test File Cryptographic Inventory (SHA-256)

The following table records the exact SHA-256 hash of all 57 Python files under `tests/` as of Milestone UI-3.2:

| Relative Path | SHA-256 Digest | Tests |
|---|---|---|
| `tests\conftest.py` | `0f7fb135fb887154ad620a95c13eb691d7583f08ace9f6ae133b5594bb45cbf8` | 0 |
| `tests\integration\test_m6_hardening_verification.py` | `30f00f2762817d59ea5843ec904e8942db7756ba08faa4b47b9842ede0a8c1ac` | 17 |
| `tests\integration\test_m6_integration_and_reliability.py` | `ee3077e0cb87622edadf54180f82908908aece6b861135cf0e42dd6f434f4d62` | 20 |
| `tests\integration\test_m7_audit_and_timestamps.py` | `82102f3b7d82f90372d371177a6894bb300ed024a6c62b1bff01f8990d0d6ab1` | 8 |
| `tests\integration\test_m7_enterprise_adapters.py` | `96b982f54ccf64c005c7be90b4ce0cad24d4faebcdb6038f17cc5df6640e8435` | 11 |
| `tests\integration\test_m7_identity_and_auth.py` | `825c0411f91428cfe3725fd8618d231bc7e1d34bbbced06fd6d3ef2451ec5ded` | 10 |
| `tests\integration\test_m7_security_and_reliability.py` | `dda7d79e2307398773920e88cb2a7c691227ac8fbb634e5c881ebec586efd81f` | 10 |
| `tests\integration\test_ui3_investigation_endpoints.py` | `fdaf0b048a9f8d57d6c9a339cf5da0431a4525916e937ba18a9a8d08d5c7d33c` | 8 |
| `tests\unit\test_anomaly_detection.py` | `bd0b4b50d81cdd699bc37d52d6e45233637c68939f8e992b8e800d43b7741680` | 5 |
| `tests\unit\test_bounded_decoder.py` | `edda5b877bf5e404a438cfec3c8a885149d2160999efe42cfe7971f015fc80e4` | 14 |
| `tests\unit\test_classifier.py` | `42f35dff8350112b47c62b2e118ec26d74bb679a15a886a96e709ee963ae894c` | 4 |
| `tests\unit\test_contracts.py` | `e2fdcec25988ab7ef90015dbbf870287c963d06f323d2f7be68e452fa4b6e6d8` | 2 |
| `tests\unit\test_correlation.py` | `f8dec70d1c5478e4c7fe7fb32e5b34af90fc8c148531ecfe4dc6cd1e8d686e0e` | 3 |
| `tests\unit\test_evaluation_v2.py` | `218dc6b6eb53ebb33bc4b6935208b9db43718d7567ccc3322ad75cc22e79c566` | 4 |
| `tests\unit\test_features.py` | `a4045929a0ba159e87dc6f24188fe889a0fee73ebb4f4d6156955321627068ec` | 2 |
| `tests\unit\test_generator_v2.py` | `2493e573988fa2702a6a3a5ca88e454aa55a8b626540ef57c0fa02eb1bc19760` | 4 |
| `tests\unit\test_impact_analysis.py` | `e98092337d934bbe0e16dbdd4612ef42155eb56d4c6055cf2c53814916991611` | 3 |
| `tests\unit\test_knowledge_chunker.py` | `283b5badd45b94d5bc0197f1118ead564c69e51c371148e1c7e788fd4728b7b2` | 3 |
| `tests\unit\test_m3_adversarial_audit.py` | `4fa07dd292352cb631b6663c868b1ccb86058798cf93d1ae8ea3af259a3dec93` | 6 |
| `tests\unit\test_m5_1_approval_tamper.py` | `8fb5add7bf2ce2308b426b54bfc95f03f6b904ba7e5123e6e72f10276dc40567` | 11 |
| `tests\unit\test_m5_1_equipment_grounding.py` | `fb3c3d7aa98fff1f2238662d1629986f7b893db3e956f1df28b343ca76cee373` | 7 |
| `tests\unit\test_m5_1_unicode_security.py` | `514b24a79d210872c199853fc9d1f59353cc84bc23c2fba151a55874488716dd` | 9 |
| `tests\unit\test_m5_2_approval_auth.py` | `96de1f393a57116bff38fadf1fb2dcbb4c1e329af15fa59e054744f3ff856e2c` | 15 |
| `tests\unit\test_m5_2_equipment_grounding.py` | `ad7b4d225a72088d7322c7adfe769244925127a9832c4f7f2cf4ebd99cb3c5fb` | 34 |
| `tests\unit\test_m5_2_unicode_security.py` | `7ab3d0a009c544de78bd9f15121a367e6c495821a0a32a9b27fd5dc35d905615` | 17 |
| `tests\unit\test_m5_3_audit_ledger_canonicalization.py` | `0230388c9d3ecfd513b5f66a84a80f6d938d4fd06ebc491db79d7d9418bac3ca` | 6 |
| `tests\unit\test_m5_3_oidc_verification.py` | `2483e027529908b95f9dc3b6eb085ebcfb10a31afe60169e04c3d98bd30ad310` | 11 |
| `tests\unit\test_m5_3_rollback_protection.py` | `d1f5891a6a575f79fc63c4079003792eb7c96cdc4b873dd7c8b8c3dcee05f995` | 4 |
| `tests\unit\test_m5_3_system_identity.py` | `b93a6e34c725ac1a73fe9398382b5a04b9d0c59fab1a2ec86f3c0d935407d627` | 7 |
| `tests\unit\test_m5_4_canonical_jcs.py` | `336ed30a420e7da02a18f5cdf4452d966e04fba500388c0cb42d039d11f5c696` | 5 |
| `tests\unit\test_m5_4_checkpoint_integrity.py` | `5ffdd9369d075bdc3dedaf7e03250ed4777614295b27f697b1c1bc1a00e4607f` | 5 |
| `tests\unit\test_m5_4_concurrency_and_oidc.py` | `a540d7190729e1905e0fa2a2d30c4a4488b144f18ddebb38c813495e89796a98` | 6 |
| `tests\unit\test_m5_4_transient_safety.py` | `a2abadee32dc240152ac4b4c9cf3d1cc8e6c9e37e4c686f536c39f64886e9d6a` | 3 |
| `tests\unit\test_m5_5_prompt_injection_defense.py` | `aade5f3a62d9e4b99329caa3703922e13f94b90d764aa504f5bba9fafc43c269` | 12 |
| `tests\unit\test_m5_5_temporal_evidence.py` | `b327a355547d46713603df9490ec818f1549b0031d1dd5480bbcf4b5bf879742` | 18 |
| `tests\unit\test_m5_adversarial.py` | `b700a40245b6f2e6184602ccfb4aa4d01f6ff6501f848b70e903a932173fb188` | 5 |
| `tests\unit\test_m5_approval.py` | `405e8a4fde69e3eff4de46e947e17fb8bcc61c72b8c91dcce9a9b23a9910f5f3` | 7 |
| `tests\unit\test_m5_investigation.py` | `b0bd821590661cb023441bb8f3d17b61ecd8786f588454b893fc694856be17de` | 4 |
| `tests\unit\test_m5_runbook_negative.py` | `8fe45fec5fc28ae9a8913903325f59cf2562ab6a51efa29f45eeba6e3120f200` | 4 |
| `tests\unit\test_m5_schemas.py` | `324d8c2d9070106f9c55714c20754f48f3f3c734739a63c4fd56d786d9c80331` | 6 |
| `tests\unit\test_m5_temporal_comprehensive.py` | `d8bd20972005197ab1e4ea2a898a1911b0d18558d384fc2b6e4436c9b5cdb251` | 8 |
| `tests\unit\test_normalization.py` | `fdef6ae5572661bc0dc3d66661413b9e5b2707e1d1a8733dd05f170faca85764` | 3 |
| `tests\unit\test_profiler.py` | `c723b56f68377d12c08c447f76e2f964acebbe937a4d6738ca34894ab5de8f0f` | 3 |
| `tests\unit\test_provenance.py` | `1b987ef4159dee29c30fdc3a90395cdc358c1c1fa31d41e60c9d262fd82c0af0` | 3 |
| `tests\unit\test_retrieval_bm25.py` | `456367eacaf86d72c05dc9fbd6bc1633e7f6d543a61039c58e89077a8db540aa` | 2 |
| `tests\unit\test_retrieval_dense.py` | `cb62bd269b686e6cd8e87bb38e625ccbf658c1ef66fac0e928e8a582b1157b84` | 2 |
| `tests\unit\test_retrieval_engine.py` | `4558fe60a70a7f412b24cd359b48257eac144d743bbf9655cdb5c5ef29ebd7ba` | 5 |
| `tests\unit\test_retrieval_filters.py` | `5abb92f150828a56762240b5c6d9cc38779b9a55e973f090fb0b2d69a373d142` | 3 |
| `tests\unit\test_retrieval_fusion.py` | `a5c0b37519bb9dd1aba2a25a2d4e63637665ca537b18e628f5860fc0448c9769` | 1 |
| `tests\unit\test_retrieval_security.py` | `64bc2cef0b2c533b3cb9d75f768509fbfd282ff49a95d47bf042bad793be32f0` | 5 |
| `tests\unit\test_retrieval_tokenizer.py` | `cd6807b64172c27736ecfae9137e5c8c2409540792af6f8955821461041155a5` | 3 |
| `tests\unit\test_routing_evaluation.py` | `d3cbb98b11b5249529ea8d759943b9adb1e09026ac7c69b6b0d9b42388d1672d` | 3 |
| `tests\unit\test_routing_policy.py` | `9cf3ca98b1ca629dac0ab4eb5c22d8d3dfb5a552b7bd937cd6fff092e7ddeec9` | 5 |
| `tests\unit\test_schemas.py` | `c11be8b90a77f7588e24df797eb94d6814e1bcbd94ac642f8b15449e1e71270f` | 7 |
| `tests\unit\test_severity.py` | `0f0889c818343d35ad9cf47d83668099bd98b150b06e5b248aa063495c5c63cd` | 3 |
| `tests\unit\test_synthetic_generator.py` | `eb4a2ae92a846874a716950c9fb3473f24d70f8d22761fa0ca82a0d64908c778` | 3 |
| `tests\unit\test_trust_boundary.py` | `ad38276f79cf5c5f397ac8d4247ce51e43f499b553e0a4724100462368bf69a0` | 7 |
| **Total** | **57 Files** | **396 Tests** |
