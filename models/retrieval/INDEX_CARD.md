# PIIS Knowledge Index Card: Milestone 4 Vetted Operational Corpus

---

## 1. Index Summary

| Attribute | Specification |
|---|---|
| **Index Identifier** | `PIIS-M4-CORPUS-V1` |
| **Total Registered Sources** | 6 registered knowledge sources |
| **Total Source Documents** | 12 vetted documents |
| **Total Indexed Chunks** | 38 structure-aware chunks |
| **Embedding Dimensions** | 384 dimensions (L2-normalized) |
| **Similarity Metric** | Cosine Similarity (Dot product on unit vectors) |
| **Chunking Parameters** | Target: 350 tokens, Max: 500 tokens, Overlap: 50 tokens |
| **Safety Preservation** | Procedural step continuity + Safety warning duplication |
| **Quarantine Status** | Synthetic benchmark data quarantined (zero pollution) |
| **Creation Date** | 2026-11-01 |

---

## 2. Source Governance & Registry

The index is governed by the `KnowledgeSourceRegistry`, which enforces strict trust boundaries and provenance:

| Source ID | Source Type | Trust Classification | Scope & Description | Checksum Verified |
|---|---|---|---|---|
| `SRC-SOP-RAN-VETTED` | `APPROVED_RUNBOOK` | `HIGH_TRUST_APPROVED` | Vetted RAN SOPs (VSWR, Optical LOS, Handover/RLF) | Yes (SHA-256) |
| `SRC-SOP-TRANS-VETTED`| `APPROVED_RUNBOOK` | `HIGH_TRUST_APPROVED` | Vetted Transport SOPs (BGP flapping, Fiber restoration) | Yes (SHA-256) |
| `SRC-SOP-CORE-VETTED` | `APPROVED_RUNBOOK` | `HIGH_TRUST_APPROVED` | Vetted 5G Core SOPs (AMF storm, UPF buffer overflow) | Yes (SHA-256) |
| `SRC-SOP-IMS-VETTED`  | `APPROVED_RUNBOOK` | `HIGH_TRUST_APPROVED` | Vetted IMS Core SOPs (SIP 503, VoNR degradation) | Yes (SHA-256) |
| `SRC-HIST-TELECOMTS`  | `HISTORICAL_INCIDENT` | `MEDIUM_TRUST_VERIFIED` | Verified TelecomTS incidents (RF jammer, PTP sync, VoLTE) | Yes (SHA-256) |
| `SRC-SPEC-3GPP`       | `PUBLIC_TECHNICAL_REFERENCE` | `HIGH_TRUST_APPROVED` | 3GPP TS 38.300 (Rel-17) & TS 23.501 architecture specs | Yes (SHA-256) |

> [!IMPORTANT]
> **Quarantine Policy:** Synthetic benchmark datasets (M1/M2/M2.1 TelcoBench) are explicitly excluded from this index. They are classified as `SYNTHETIC_BENCHMARK` / `EXPERIMENTAL_UNVERIFIED` and are quarantined from the retrieval corpus.

---

## 3. Corpus Composition & Domain Breakdown

### 3.1 Document Inventory

| Document ID | Title | Domain | Subsystems | Sections / Chunks |
|---|---|---|---|---|
| `SOP-RAN-VSWR-001` | Antenna VSWR and RF Feeder Degradation Resolution | RAN | gNodeB, AAU, Feeder | 4 |
| `SOP-RAN-HANDOVER-002`| gNodeB Handover Failure and Radio Link Failure (RLF) Triage | RAN | gNodeB, UE, RRC | 4 |
| `SOP-TRANS-FIBER-001` | Fronthaul Optical Loss of Signal and Fiber Cut Restoration | TRANSPORT | Fronthaul, SFP28, BBU | 4 |
| `SOP-TRANS-BGP-002` | IP-MPLS Aggregation Router BGP Session Flapping Triage | TRANSPORT | IP-Backhaul, CSR, BGP | 4 |
| `SOP-5GC-AMF-001` | 5G Core AMF Registration Storm & SCTP Association Exhaustion | 5G_CORE | AMF, N2, SCTP, NRF | 4 |
| `SOP-5GC-UPF-002` | 5G Core UPF GTP-U Buffer Overflow and N4 Disconnect | 5G_CORE | UPF, SMF, N4, GTP-U | 3 |
| `SOP-IMS-SIP-001` | IMS Core SIP 503 Service Unavailable and VoNR Degradation | SERVICE | P-CSCF, S-CSCF, VoLTE | 3 |
| `INC-TELTS-JAMMER-0000` | Severe Wireless Communication Degradation From External RF Jamming | RAN | gNodeB, AAU, Air-Interface | 3 |
| `INC-TELTS-SYNC-0001` | Clock Synchronization Drift and GPS Holdover in Rural Cluster | TRANSPORT | gNodeB, PTP-Clock, GPS | 3 |
| `INC-TELTS-VOLTE-0002` | VoLTE Call Drop Surge During Inter-RAT LTE to 5G Handover | SERVICE | IMS, P-CSCF, VoLTE | 3 |
| `REF-3GPP-TS38300` | 3GPP TS 38.300 NR Radio Link Failure and Handover Procedures | RAN | gNodeB, UE, RRC | 3 |
| `REF-3GPP-TS23501` | 3GPP TS 23.501 5G System Architecture, AMF/SMF/UPF Interfaces | 5G_CORE | AMF, SMF, UPF, N2, N4 | 3 |

### 3.2 Domain Distribution
- **RAN (Radio Access Network):** 14 chunks (36.8%)
- **TRANSPORT (Fronthaul / Backhaul / PTP):** 11 chunks (28.9%)
- **5G_CORE (AMF / SMF / UPF / Control-User Plane):** 7 chunks (18.4%)
- **SERVICE (IMS / VoLTE / VoNR):** 6 chunks (15.8%)

---

## 4. Chunking Methodology & Structural Invariants

The `StructureAwareChunker` enforces telecom-specific structural integrity rules:

1. **Header Hierarchy Propagation:** Every chunk prepends full markdown context (`# Document > ## Section > ### Sub-section`) to ensure dense embeddings retain document context.
2. **Procedural Step Atomicity:** Numbered troubleshooting steps (`1. Inspect jumper...`, `2. Connect Site Master...`) are preserved intact without mid-procedure splits.
3. **Safety Warning Duplication:** When a section contains a safety warning (e.g. `> [!WARNING] DANGER: High RF Radiation. De-energize sector radio power`), the warning block is replicated across all child chunks produced from that section.
4. **Deterministic Chunk Identifiers:** Chunk IDs are deterministically formatted as `{doc_id}-CHK-{idx:04d}`.

---

## 5. Cryptographic Fingerprints & Provenance Verification

- **Document Integrity:** Each raw document content is hashed via SHA-256 upon ingestion and recorded in `ProvenanceRecord.checksum_sha256`.
- **Dense Vector Fingerprint:** The dense index computes a SHA-256 fingerprint combining model architecture, dimension, and raw embedding bytes:
  - Hash algorithm: SHA-256
  - Verification check: `DenseBiEncoderIndex.index_fingerprint`
- **Tamper Evidence:** Any modification to document markdown content changes the chunk checksum and index fingerprint, invalidating the cached index and forcing a clean rebuild.

---

## 6. Maintenance & Re-Indexing Lifecycle

- **Automated Re-indexing:** Triggered when any SOP runbook is updated or new TelecomTS incident postmortems are approved by the Network Architecture Review Board.
- **Index Build Command:**
  ```python
  from piis.knowledge.corpus import build_knowledge_base
  from piis.retrieval.engine import HybridRetrievalEngine

  registry, chunks = build_knowledge_base()
  engine = HybridRetrievalEngine()
  engine.index_chunks(chunks)
  ```
- **Hot-Reload Support:** In-memory indices support atomic replacement of chunk dictionaries and vector arrays without restarting the PIIS service.
