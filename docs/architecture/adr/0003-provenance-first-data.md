# ADR-0003: Provenance-first data model

- **Status:** Accepted
- **Decision:** Every source/derived/synthetic/annotated record carries provenance and source references.
- **Context:** Mixed datasets and synthetic augmentation can otherwise create false claims and irreproducible results.
- **Consequences:** Canonical records include source_type, source_dataset, source_record_id and transformation/annotation metadata.
