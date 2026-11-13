# Developer and operations runbook

## Local setup
1. Install Python 3.11+.
2. Create a virtual environment.
3. Install `pip install -e ".[dev]"`.
4. Run `pytest`.
5. Profile a permitted dataset file with `python scripts/profile_dataset.py <file>`.

## Data intake
- Check terms first.
- Store original files under `data/raw/<source_id>/`.
- Generate SHA-256 profile.
- Never edit raw files in place.
- Quarantine malformed files and document errors.

## Incident response for PIIS itself
- Preserve logs and trace IDs.
- Identify affected release/model/policy version.
- Disable LLM/retrieval component independently if it returns unsafe or ungrounded outputs.
- Keep deterministic, read-only triage available where safe.
- Roll back model or policy version if regressions are confirmed.
- Record incident timeline and corrective action.

## Backup and retention
Production retention, encryption, backup and deletion windows must be defined by the deploying operator and applicable law/policy before pilot use.
