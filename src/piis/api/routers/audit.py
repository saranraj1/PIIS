"""Cryptographic audit ledger inspection and verification endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from piis.api.routers.incidents import get_workflow
from piis.api.schemas import (
    AuditRecordDetailResponse,
    AuditRecordItem,
    AuditSummaryResponse,
    AuditVerificationResponse,
    PaginatedResponse,
)
from piis.auth import (
    AuthenticatedPrincipal,
    Permission,
    require_permissions,
)
from piis.investigation.approval import (
    ApprovalStatus,
    AuditLogEntry,
    HumanApprovalWorkflow,
)

router = APIRouter(prefix="/api/v1/audit", tags=["Audit & Cryptographic Ledger"])


def _map_entry_to_schema(entry: Any) -> AuditRecordItem:
    """Map an internal AuditLogEntry to the safe, redacted AuditRecordItem schema."""
    return AuditRecordItem(
        sequence_number=entry.sequence_number,
        entry_hash=entry.entry_sha256,
        prev_hash=entry.previous_entry_sha256 or "",
        operator_id=entry.operator_id,
        decision=entry.action,
        recommendation_id=entry.recommendation_id or "",
        timestamp=entry.timestamp_utc,
        schema_version=entry.schema_version,
        has_hmac=bool(entry.hmac_signature),
        audit_id=entry.audit_id,
        action=entry.action,
        previous_status=getattr(entry, "previous_status", None),
        new_status=getattr(entry, "new_status", None),
        incident_id=getattr(entry, "incident_id", None),
        reviewer_role=getattr(entry, "reviewer_role", None),
        authorization_scope=getattr(entry, "authorization_scope", None),
        principal_type=getattr(entry, "principal_type", None),
        reviewer_auth_hash=getattr(entry, "reviewer_auth_hash", None),
        key_id=getattr(entry, "key_id", None),
        hmac_signature=getattr(entry, "hmac_signature", None),
        notes=getattr(entry, "notes", None),
        notes_cryptographically_covered=getattr(entry, "notes_cryptographically_covered", True),
        recommendation_content_hash=getattr(entry, "recommendation_content_hash", None),
        state_sha256=getattr(entry, "state_sha256", None),
        verification_status="TAMPER_EVIDENT",
    )


@router.get(
    "/records",
    response_model=PaginatedResponse[AuditRecordItem],
    summary="List Cryptographic Audit Records",
    description="Inspect the tamper-evident RFC 8785 JCS audit ledger entries with filtering and pagination.",
)
async def list_audit_records(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    incident_id: Optional[str] = Query(default=None, description="Filter by incident ID"),
    action: Optional[str] = Query(default=None, description="Filter by action type (e.g. APPROVE, REJECT, REGISTER_RECOMMENDATION)"),
    operator_id: Optional[str] = Query(default=None, description="Filter by operator/reviewer ID"),
    from_sequence: Optional[int] = Query(default=None, ge=1, description="Minimum sequence number (inclusive)"),
    to_sequence: Optional[int] = Query(default=None, ge=1, description="Maximum sequence number (inclusive)"),
    from_timestamp: Optional[str] = Query(default=None, description="Earliest ISO timestamp (inclusive)"),
    to_timestamp: Optional[str] = Query(default=None, description="Latest ISO timestamp (inclusive)"),
    order: str = Query(default="desc", pattern="^(asc|desc)$", description="Sort order by sequence number (asc or desc)"),
    principal: AuthenticatedPrincipal = Depends(require_permissions(Permission.VIEW_AUDIT_LOGS)),
    workflow: HumanApprovalWorkflow = Depends(get_workflow),
) -> PaginatedResponse[AuditRecordItem]:
    """Retrieve paginated audit ledger records with verified provenance."""
    trail = workflow.get_audit_trail()
    filtered = trail

    if incident_id:
        target_inc = incident_id.strip().lower()
        filtered = [
            e for e in filtered
            if getattr(e, "incident_id", None) and target_inc in str(e.incident_id).lower()
        ]

    if action:
        target_act = action.strip().upper()
        filtered = [
            e for e in filtered
            if getattr(e, "action", None) and (
                target_act == str(e.action).upper()
                or target_act in str(e.action).upper()
            )
        ]

    if operator_id:
        target_op = operator_id.strip().lower()
        filtered = [
            e for e in filtered
            if getattr(e, "operator_id", None) and target_op in str(e.operator_id).lower()
        ]

    if from_sequence is not None:
        filtered = [e for e in filtered if e.sequence_number >= from_sequence]

    if to_sequence is not None:
        filtered = [e for e in filtered if e.sequence_number <= to_sequence]

    if from_timestamp:
        filtered = [e for e in filtered if e.timestamp_utc >= from_timestamp]

    if to_timestamp:
        filtered = [e for e in filtered if e.timestamp_utc <= to_timestamp]

    if order == "desc":
        filtered = list(reversed(filtered))

    total = len(filtered)
    page = filtered[offset : offset + limit]
    items = [_map_entry_to_schema(entry) for entry in page]

    return PaginatedResponse(
        items=items,
        total_count=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/records/{sequence_number}",
    response_model=AuditRecordDetailResponse,
    summary="Get Single Cryptographic Audit Record Detail",
    description="Inspect full record provenance, canonical RFC 8785 JSON representation, and hash/HMAC verification.",
)
async def get_audit_record_detail(
    sequence_number: int,
    principal: AuthenticatedPrincipal = Depends(require_permissions(Permission.VIEW_AUDIT_LOGS)),
    workflow: HumanApprovalWorkflow = Depends(get_workflow),
) -> AuditRecordDetailResponse:
    """Retrieve detailed inspection for a single sequence entry in the audit ledger."""
    trail = workflow.get_audit_trail()
    matched = None
    for entry in trail:
        if entry.sequence_number == sequence_number:
            matched = entry
            break

    if not matched:
        raise HTTPException(
            status_code=404,
            detail=f"Audit record with sequence number {sequence_number} not found in ledger.",
        )

    canonical_json = matched.get_canonical_serialized()
    recomputed_hash = matched.compute_canonical_hash()
    hash_matches = recomputed_hash == matched.entry_sha256

    hmac_valid = False
    if workflow._signing_key and matched.hmac_signature:
        recomputed_hmac = hmac.new(
            workflow._signing_key,
            canonical_json.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        hmac_valid = hmac.compare_digest(recomputed_hmac, matched.hmac_signature)

    is_genesis = (matched.sequence_number == 1) or (matched.previous_entry_sha256 == "GENESIS_CHECKPOINT")

    checkpoint_aligned = False
    if workflow._checkpoint_anchor and trail and trail[-1].sequence_number == matched.sequence_number:
        try:
            cp = workflow._checkpoint_anchor.get_latest_checkpoint()
            if cp and cp.get("sequence_number") == matched.sequence_number and cp.get("entry_sha256") == matched.entry_sha256:
                checkpoint_aligned = True
        except Exception:
            checkpoint_aligned = False

    rec_exists = bool(matched.recommendation_id and matched.recommendation_id in workflow._recommendations)

    provenance_chain: Dict[str, Any] = {
        "incident_id": matched.incident_id,
        "recommendation_id": matched.recommendation_id,
        "has_stored_recommendation": rec_exists,
        "operator_id": matched.operator_id,
        "reviewer_role": matched.reviewer_role,
        "action": matched.action,
        "timestamp_utc": matched.timestamp_utc,
        "schema_version": matched.schema_version,
        "key_id": matched.key_id,
    }

    return AuditRecordDetailResponse(
        record=_map_entry_to_schema(matched),
        canonical_json=canonical_json,
        canonical_hash_matches=hash_matches,
        recomputed_hash=recomputed_hash,
        hmac_valid=hmac_valid,
        is_genesis=is_genesis,
        checkpoint_aligned=checkpoint_aligned,
        provenance_chain=provenance_chain,
    )


@router.get(
    "/summary",
    response_model=AuditSummaryResponse,
    summary="Audit Ledger Summary Metrics",
    description="High-level overview metrics of the cryptographic audit ledger and checkpoint state.",
)
async def get_audit_summary(
    principal: AuthenticatedPrincipal = Depends(require_permissions(Permission.VIEW_AUDIT_LOGS)),
    workflow: HumanApprovalWorkflow = Depends(get_workflow),
) -> AuditSummaryResponse:
    """Retrieve operational summary metrics for the audit ledger."""
    trail = workflow.get_audit_trail()
    actions_breakdown: Dict[str, int] = {}
    for entry in trail:
        actions_breakdown[entry.action] = actions_breakdown.get(entry.action, 0) + 1

    anchor_present = False
    anchor_sequence: Optional[int] = None
    anchor_hash: Optional[str] = None

    if workflow._checkpoint_anchor:
        anchor_present = True
        try:
            cp = workflow._checkpoint_anchor.get_latest_checkpoint()
            if cp:
                anchor_sequence = cp.get("sequence_number")
                anchor_hash = cp.get("entry_sha256")
        except Exception:
            pass

    return AuditSummaryResponse(
        total_records=len(trail),
        latest_sequence=trail[-1].sequence_number if trail else 0,
        earliest_timestamp=trail[0].timestamp_utc if trail else None,
        latest_timestamp=trail[-1].timestamp_utc if trail else None,
        actions_breakdown=actions_breakdown,
        anchor_present=anchor_present,
        anchor_sequence=anchor_sequence,
        anchor_hash=anchor_hash,
        storage_type="JSONL_APPEND_ONLY",
        canonicalization_scheme="RFC_8785_JCS",
        hashing_algorithm="SHA_256",
        mac_algorithm="HMAC_SHA256",
        anchor_mechanism="FileBasedCheckpointAnchor (Local Monotonic Parity)",
        limitations=[
            "Audit ledger persistence and verification is single-process local to this host.",
            "Local checkpoint anchor detects rollbacks within this filesystem, but cannot prevent coordinated host-level snapshot restoration.",
            "HMAC-SHA256 provides symmetric authentication with local key material, not asymmetric digital signatures or non-repudiation.",
            "Audit ledger is append-only and strictly read-only; no record mutations or overrides can be executed via the API.",
        ],
    )


@router.get(
    "/verify",
    response_model=AuditVerificationResponse,
    summary="Verify Audit Hash Chain Integrity",
    description="Verify mathematical continuity of SHA-256 hash chain, RFC 8785 canonicalization, HMAC signatures, and checkpoint anchor parity.",
)
async def verify_audit_ledger(
    principal: AuthenticatedPrincipal = Depends(require_permissions(Permission.VERIFY_AUDIT_LEDGER)),
    workflow: HumanApprovalWorkflow = Depends(get_workflow),
) -> AuditVerificationResponse:
    """Verify entire cryptographic audit ledger, sequence continuity, HMACs, and anchor head.

    Verification Architecture (Two-Layer Precedence Model):
    - Layer 1: Structural Verification (Independent of Cryptographic Keys):
      * Complete physical JSONL ledger scan for malformed JSON, truncated lines, or missing fields.
      * Monotonic sequence number continuity ($s_i = i$).
      * Hash chain continuity ($H_{i,prev} == H_{i-1}$, beginning at GENESIS_CHECKPOINT).
      * RFC 8785 canonical SHA-256 digest recomputation (requires no secret key material).
      * In-memory approved recommendation binding immutability.
    - Layer 2: Cryptographic & Anchor Parity Verification:
      * HMAC-SHA256 signature verification (requires workflow._signing_key).
      * Local checkpoint anchor head verification (requires workflow._checkpoint_anchor).

    Deterministic State Precedence:
    1. Known corruption, tampering, broken hash chain, sequence discontinuity, or anchor mismatch -> FAILED.
    2. Known incomplete or truncated record (without fatal corruption) -> INCOMPLETE.
    3. Structurally valid ledger, but required cryptographic key or anchor unavailable -> UNAVAILABLE.
    4. All structural and cryptographic/checkpoint checks pass -> VERIFIED.
    """
    trail = workflow.get_audit_trail()
    total = len(trail)

    fatal_corruption_errors: List[str] = []
    incomplete_errors: List[str] = []
    unavailable_errors: List[str] = []

    hash_chain_valid = True
    jcs_canonicalization_valid = True
    hmac_signatures_valid = True
    checkpoint_parity_valid = True

    # Check key availability
    key_available = bool(workflow._signing_key)
    if not key_available:
        hmac_signatures_valid = False
        unavailable_errors.append(
            "HMAC signing key unavailable; cryptographic signature verification cannot be performed."
        )

    # Check anchor availability
    anchor_present = False
    anchor_sequence: Optional[int] = None
    anchor_hash: Optional[str] = None

    if workflow._checkpoint_anchor:
        anchor_present = True
        try:
            cp = workflow._checkpoint_anchor.get_latest_checkpoint()
            if cp:
                anchor_sequence = cp.get("sequence_number")
                anchor_hash = cp.get("entry_sha256")
        except Exception as e:
            fatal_corruption_errors.append(f"Checkpoint anchor read error: {e}")
            checkpoint_parity_valid = False
    else:
        checkpoint_parity_valid = False
        unavailable_errors.append(
            "External checkpoint anchor is not configured or unavailable; parity verification cannot be performed."
        )

    # -----------------------------------------------------------------------
    # Layer 1: Structural verification of physical disk ledger file
    # -----------------------------------------------------------------------
    if workflow._ledger_path and workflow._ledger_path.exists():
        try:
            expected_disk_seq = 1
            expected_disk_prev_hash = "GENESIS_CHECKPOINT"
            seen_disk_seqs = set()

            # Read all non-empty lines with their 1-based physical line numbers
            raw_entries: List[tuple[int, str]] = []
            with workflow._ledger_path.open("r", encoding="utf-8", errors="replace") as f:
                for line_no, raw_line in enumerate(f, start=1):
                    stripped = raw_line.strip()
                    if stripped:
                        raw_entries.append((line_no, stripped))

            final_line_no = raw_entries[-1][0] if raw_entries else None

            for line_no, line_str in raw_entries:
                is_final_physical_line = (line_no == final_line_no)
                try:
                    import json
                    parsed = json.loads(line_str)
                    if not isinstance(parsed, dict):
                        fatal_corruption_errors.append(
                            f"Malformed record structure at line {line_no}: expected JSON object, got {type(parsed).__name__}"
                        )
                        continue

                    mandatory_fields = ["sequence_number", "entry_sha256", "audit_id"]
                    missing = [f for f in mandatory_fields if f not in parsed]
                    if missing:
                        fatal_corruption_errors.append(
                            f"Structurally invalid record in disk ledger at line {line_no}: missing mandatory field(s): {', '.join(missing)}"
                        )
                        continue

                    disk_seq = parsed.get("sequence_number")
                    if not isinstance(disk_seq, int):
                        fatal_corruption_errors.append(
                            f"Invalid sequence number type at line {line_no}: {type(disk_seq).__name__}"
                        )
                    elif disk_seq in seen_disk_seqs:
                        fatal_corruption_errors.append(
                            f"Duplicate sequence number {disk_seq} in disk ledger at line {line_no}"
                        )
                    elif disk_seq != expected_disk_seq:
                        fatal_corruption_errors.append(
                            f"Sequence discontinuity in disk ledger at line {line_no}: expected seq={expected_disk_seq}, got seq={disk_seq}"
                        )
                    seen_disk_seqs.add(disk_seq)
                    expected_disk_seq = (disk_seq + 1) if isinstance(disk_seq, int) else expected_disk_seq

                    # Verify disk hash pointer
                    disk_prev = parsed.get("previous_entry_sha256")
                    if disk_prev is not None and disk_prev != expected_disk_prev_hash:
                        fatal_corruption_errors.append(
                            f"Broken hash chain in disk ledger at line {line_no}: expected previous_entry_sha256='{expected_disk_prev_hash}', got '{disk_prev}'"
                        )

                    # Verify canonical digest recomputation on disk without requiring secret keys
                    try:
                        entry_obj = AuditLogEntry.model_validate(parsed)
                        recomputed = entry_obj.compute_canonical_hash()
                        if recomputed != entry_obj.entry_sha256:
                            fatal_corruption_errors.append(
                                f"Tampered record digest in disk ledger at line {line_no}: stored={entry_obj.entry_sha256[:12]}... vs recomputed={recomputed[:12]}..."
                            )
                    except Exception as val_err:
                        fatal_corruption_errors.append(
                            f"Structurally invalid record schema in disk ledger at line {line_no}: {val_err}"
                        )

                    disk_entry_sha = parsed.get("entry_sha256")
                    if disk_entry_sha:
                        expected_disk_prev_hash = disk_entry_sha

                except Exception as json_err:
                    err_str = str(json_err).lower()
                    # Precise truncation classification (UI-6.1.2):
                    # INCOMPLETE is ONLY credible for the final physical record of the ledger.
                    # Any malformed record before the final physical line cannot be an interrupted append.
                    if not is_final_physical_line:
                        fatal_corruption_errors.append(
                            f"Malformed record before final line at line {line_no}: {json_err}"
                        )
                    else:
                        # Credible incomplete final write:
                        # 1. Must begin with a valid JSON object prefix: '{"' or '{ "' or '{\n' or '{'
                        # 2. Must NOT end with a closing '}' (which would indicate a completed JSON object structure)
                        # 3. Must exhibit an EOF-related premature termination error
                        is_unfinished_obj = (
                            line_str.lstrip().startswith('{"')
                            or line_str.lstrip().startswith('{ "')
                            or line_str.strip() == "{"
                        )
                        has_no_closing_brace = not line_str.rstrip().endswith("}")
                        is_eof_indicator = any(
                            ind in err_str
                            for ind in (
                                "unterminated",
                                "expecting ':' delimiter",
                                "expecting ',' delimiter",
                                "expecting value",
                                "expecting property name",
                                "end of",
                                "unexpected eof",
                            )
                        )
                        if is_unfinished_obj and has_no_closing_brace and is_eof_indicator:
                            incomplete_errors.append(
                                f"Malformed or truncated record in disk ledger at line {line_no}: {json_err}"
                            )
                        else:
                            fatal_corruption_errors.append(
                                f"Malformed JSON syntax in disk ledger at line {line_no}: {json_err}"
                            )
        except Exception as disk_err:
            fatal_corruption_errors.append(f"Ledger file read error: {disk_err}")

    # -----------------------------------------------------------------------
    # Genesis empty state verification
    # -----------------------------------------------------------------------
    if total == 0:
        if workflow._checkpoint_anchor:
            try:
                anchor_valid, anchor_err = workflow._checkpoint_anchor.verify_ledger_head(None)
                if not anchor_valid:
                    checkpoint_parity_valid = False
                    fatal_corruption_errors.append(anchor_err or "External checkpoint anchor mismatch on empty ledger.")
            except Exception as anchor_err:
                checkpoint_parity_valid = False
                fatal_corruption_errors.append(f"External checkpoint anchor verification exception: {anchor_err}")

        all_errors = fatal_corruption_errors + incomplete_errors + unavailable_errors

        # Genesis state precedence determination
        if len(fatal_corruption_errors) > 0:
            status_str = "FAILED"
            is_valid = False
        elif len(incomplete_errors) > 0:
            status_str = "INCOMPLETE"
            is_valid = False
        elif not key_available or not anchor_present:
            status_str = "UNAVAILABLE"
            is_valid = False
        else:
            status_str = "VERIFIED"
            is_valid = True

        return AuditVerificationResponse(
            is_valid=is_valid,
            verification_status=status_str,
            total_records=0,
            records_checked=0,
            first_sequence=None,
            last_sequence=None,
            latest_sequence=0,
            latest_hash=None,
            hash_chain_valid=True,
            jcs_canonicalization_valid=True,
            hmac_signatures_valid=key_available,
            checkpoint_parity_valid=checkpoint_parity_valid,
            anchor_present=anchor_present,
            anchor_sequence=anchor_sequence,
            anchor_hash=anchor_hash,
            error=all_errors[0] if all_errors else None,
            errors=all_errors,
            verified_at=datetime.now(timezone.utc).isoformat(),
            verification_scope="FULL_LEDGER",
            limitations=[
                "Verification is local to this single-process node.",
                "Local checkpoint anchor detects rollbacks within this filesystem, but cannot prevent coordinated host-level snapshot restoration.",
                "HMAC-SHA256 provides symmetric authentication with local key material, not asymmetric digital signatures or non-repudiation.",
            ],
        )

    # -----------------------------------------------------------------------
    # Layer 1 & 2: Hash chain, canonical hash, HMAC, and anchor verification
    # -----------------------------------------------------------------------
    expected_prev = "GENESIS_CHECKPOINT"

    for idx, entry in enumerate(trail, start=1):
        # Layer 1: Sequence monotonicity
        if entry.sequence_number != idx:
            hash_chain_valid = False
            fatal_corruption_errors.append(
                f"Sequence discontinuity at index {idx}: expected seq={idx}, got seq={entry.sequence_number}"
            )

        # Layer 1: Hash chain link integrity (requires no secret key)
        if entry.previous_entry_sha256 != expected_prev:
            hash_chain_valid = False
            fatal_corruption_errors.append(
                f"Broken hash chain at {entry.audit_id}: previous_entry_sha256 '{entry.previous_entry_sha256}' "
                f"does not match preceding entry digest '{expected_prev}'"
            )

        # Layer 1: RFC 8785 Canonical JCS recomputation (pure SHA-256, requires no secret key)
        recomputed_hash = entry.compute_canonical_hash()
        if recomputed_hash != entry.entry_sha256:
            jcs_canonicalization_valid = False
            fatal_corruption_errors.append(
                f"Tampered record digest at {entry.audit_id}: stored={entry.entry_sha256[:12]}... "
                f"vs recomputed={recomputed_hash[:12]}..."
            )

        # Layer 2: HMAC-SHA256 verification (when key available)
        if key_available:
            recomputed_hmac = hmac.new(
                workflow._signing_key,
                entry.get_canonical_serialized().encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(recomputed_hmac, entry.hmac_signature):
                hmac_signatures_valid = False
                fatal_corruption_errors.append(
                    f"Invalid HMAC signature at {entry.audit_id}: possible unauthorized log substitution or key mismatch"
                )

        expected_prev = entry.entry_sha256

    # Layer 2: External monotonic anchor verification (when anchor available)
    if workflow._checkpoint_anchor:
        latest = trail[-1] if trail else None
        try:
            anchor_valid, anchor_err = workflow._checkpoint_anchor.verify_ledger_head(latest)
            if not anchor_valid:
                checkpoint_parity_valid = False
                fatal_corruption_errors.append(anchor_err or "External checkpoint anchor mismatch.")
        except Exception as anchor_err:
            checkpoint_parity_valid = False
            fatal_corruption_errors.append(f"External checkpoint anchor verification exception: {anchor_err}")

    # Layer 1: Verify recommendation binding for approved recommendations
    for rec_id, rec in workflow._recommendations.items():
        if rec.approval_status == ApprovalStatus.APPROVED:
            if not workflow.verify_recommendation_binding(rec_id):
                fatal_corruption_errors.append(
                    f"Approved recommendation '{rec_id}' was mutated in memory after approval."
                )

    all_errors = fatal_corruption_errors + incomplete_errors + unavailable_errors

    # -----------------------------------------------------------------------
    # Strict Verification Precedence Determination
    # -----------------------------------------------------------------------
    # Rule 1: Fatal corruption, broken chain, tampering, discontinuity, or anchor mismatch -> FAILED
    # Rule 2: Incomplete or truncated records (without fatal corruption) -> INCOMPLETE
    # Rule 3: Structurally valid, but missing cryptographic key or anchor -> UNAVAILABLE
    # Rule 4: All structural, cryptographic, and parity checks pass -> VERIFIED
    if len(fatal_corruption_errors) > 0:
        status_str = "FAILED"
        is_valid = False
    elif len(incomplete_errors) > 0:
        status_str = "INCOMPLETE"
        is_valid = False
    elif not key_available or not anchor_present:
        status_str = "UNAVAILABLE"
        is_valid = False
    elif len(all_errors) > 0:
        status_str = "FAILED"
        is_valid = False
    else:
        status_str = "VERIFIED"
        is_valid = True

    return AuditVerificationResponse(
        is_valid=is_valid,
        verification_status=status_str,
        total_records=total,
        records_checked=total,
        first_sequence=trail[0].sequence_number if trail else None,
        last_sequence=trail[-1].sequence_number if trail else None,
        latest_sequence=trail[-1].sequence_number if trail else 0,
        latest_hash=trail[-1].entry_sha256 if trail else None,
        hash_chain_valid=hash_chain_valid,
        jcs_canonicalization_valid=jcs_canonicalization_valid,
        hmac_signatures_valid=key_available and hmac_signatures_valid,
        checkpoint_parity_valid=checkpoint_parity_valid,
        anchor_present=anchor_present,
        anchor_sequence=anchor_sequence,
        anchor_hash=anchor_hash,
        error=all_errors[0] if all_errors else None,
        errors=all_errors,
        verified_at=datetime.now(timezone.utc).isoformat(),
        verification_scope="FULL_LEDGER",
        limitations=[
            "Verification is local to this single-process node.",
            "Local checkpoint anchor detects rollbacks within this filesystem, but cannot prevent coordinated host-level snapshot restoration.",
            "HMAC-SHA256 provides symmetric authentication with local key material, not asymmetric digital signatures or non-repudiation.",
        ],
    )
