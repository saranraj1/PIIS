# ADR-0004: Tamper-Evident Approval Audit Chain and Reviewer Contracts

- **Status:** Accepted
- **Decision:** Enforce a strict finite-state machine for human approvals (`PENDING_REVIEW` -> `APPROVED` / `REJECTED` / `MODIFIED`), with prohibited transitions out of terminal states raising `IllegalStateTransitionError`. Audit trails are linked via canonical RFC-8785 JSON serialization, SHA-256 hash pointer chaining (`previous_entry_sha256`), and HMAC-SHA256 checkpoint signatures. Reviewer identities require authenticated credentials (`AuthenticatedReviewer`), and recommendation content is cryptographically bound in memory to prevent post-approval mutations.
- **Context:** The M5 adversarial validation showed that unkeyed in-memory logs could be altered, reordered, or deleted without detection, and terminal approval states could be overwritten.
- **Consequences:** Provides cryptographic tamper-evidence and reviewer accountability for operational decision support without assuming unverified enterprise PKI infrastructure.
