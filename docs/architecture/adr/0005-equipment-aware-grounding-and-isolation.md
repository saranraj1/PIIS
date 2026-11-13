# ADR-0005: Equipment-Aware Grounding and Generation Isolation

- **Status:** Accepted
- **Decision:** All operational knowledge documents, chunks, queries, and grounded evidence entities carry explicit hardware metadata: `technology_generation` (e.g. `2G`, `3G`, `4G`, `5G`, `TRAN`, `CORE`), `vendor` (e.g. `ERICSSON`, `NOKIA`, `CISCO`, `GENERIC`), and `equipment_family`. Hybrid retrieval enforces hard incompatibility filtering: cross-generation matches (e.g. 2G queries matching 5G SOPs) and incompatible vendor matches are strictly rejected. When no compatible approved runbook exists, the investigation engine safely abstains to `HypothesisStatus.INCONCLUSIVE` with a confidence proxy of 0.0.
- **Context:** Dense vector similarity and BM25 lexical matching falsely matched modern 5G runbooks to legacy 2G GSM and third-party vendor tickets due to overlapping telecom terminology.
- **Consequences:** Eliminates cross-generation and cross-vendor false matching in operational runbook retrieval, ensuring diagnostic recommendations only cite applicable procedures.
