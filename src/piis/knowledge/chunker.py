"""Structure-aware document chunker preserving headings, procedures, and safety warnings."""

from __future__ import annotations

import hashlib
import re
from typing import List

from piis.knowledge.models import DocumentSection, KnowledgeChunk, KnowledgeDocument
from piis.provenance import ProvenanceRecord


class StructureAwareChunker:
    """Partitions telecom documents while preserving section hierarchy and procedural continuity."""

    def __init__(
        self,
        target_tokens: int = 350,
        max_tokens: int = 500,
        overlap_tokens: int = 50,
    ):
        self.target_tokens = target_tokens
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Estimate token count based on whitespace and punctuation splitting (~1.3 words/token)."""
        words = len(text.split())
        return max(1, int(words * 1.25))

    def parse_sections(self, content: str) -> List[DocumentSection]:
        """Parse raw markdown content into hierarchical DocumentSection list."""
        lines = content.splitlines()
        sections: List[DocumentSection] = []
        current_heading_path: List[str] = ["Document Overview"]
        current_title = "Overview"
        current_level = 1
        current_body_lines: List[str] = []
        current_warnings: List[str] = []
        current_code_blocks: List[str] = []

        in_code_block = False
        code_block_lines: List[str] = []

        def flush_current():
            body = "\n".join(current_body_lines).strip()
            if body:
                sections.append(
                    DocumentSection(
                        heading_path=list(current_heading_path),
                        heading_level=current_level,
                        title=current_title,
                        body=body,
                        warnings=list(current_warnings),
                        code_blocks=list(current_code_blocks),
                    )
                )

        for line in lines:
            stripped = line.strip()

            # Track fenced code blocks
            if stripped.startswith("```"):
                if in_code_block:
                    in_code_block = False
                    code_block_lines.append(line)
                    current_code_blocks.append("\n".join(code_block_lines))
                    code_block_lines = []
                else:
                    in_code_block = True
                    code_block_lines = [line]
                current_body_lines.append(line)
                continue

            if in_code_block:
                code_block_lines.append(line)
                current_body_lines.append(line)
                continue

            # Check for headings
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
            if heading_match:
                flush_current()
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()

                # Adjust heading path
                if level == 1:
                    current_heading_path = [title]
                elif level == len(current_heading_path) + 1:
                    current_heading_path.append(title)
                elif level <= len(current_heading_path):
                    current_heading_path = current_heading_path[: level - 1] + [title]
                else:
                    current_heading_path.append(title)

                current_title = title
                current_level = level
                current_body_lines = []
                current_warnings = []
                current_code_blocks = []
                continue

            # Check for safety warnings
            if any(kw in stripped.upper() for kw in ["DANGER:", "WARNING:", "CAUTION:", "[!WARNING]", "[!DANGER]"]):
                current_warnings.append(stripped)

            current_body_lines.append(line)

        flush_current()
        return sections

    def chunk_document(self, doc: KnowledgeDocument) -> List[KnowledgeChunk]:
        """Convert a KnowledgeDocument into indexed KnowledgeChunk passages."""
        sections = self.parse_sections(doc.raw_content)
        chunks: List[KnowledgeChunk] = []

        for sec in sections:
            sec_header = f"[Domain: {doc.network_domain} | Doc: {doc.title} | Section: {' > '.join(sec.heading_path)}]\n"
            sec_tokens = self.estimate_tokens(sec.body)

            # Case A: Section fits in a single chunk
            if sec_tokens <= self.max_tokens:
                full_chunk_text = f"{sec_header}\n{sec.body}"
                chunk_id = self._generate_chunk_id(doc.doc_id, sec.title, full_chunk_text)
                chunk_tokens = self.estimate_tokens(full_chunk_text)

                prov = ProvenanceRecord(
                    source_type=doc.provenance.source_type,
                    source_dataset=doc.source_id,
                    source_record_id=chunk_id,
                    transformation_version="1.0.0",
                    checksum_sha256=hashlib.sha256(full_chunk_text.encode()).hexdigest(),
                    metadata={
                        "doc_id": doc.doc_id,
                        "section_name": sec.title,
                        "heading_path": sec.heading_path,
                    },
                )

                chunks.append(
                    KnowledgeChunk(
                        chunk_id=chunk_id,
                        doc_id=doc.doc_id,
                        source_id=doc.source_id,
                        doc_title=doc.title,
                        source_type=doc.doc_type,
                        trust_classification=doc.trust_classification,
                        network_domain=doc.network_domain,
                        target_subsystems=doc.target_subsystems,
                        technology_generation=doc.technology_generation,
                        vendor=doc.vendor,
                        equipment_family=doc.equipment_family,
                        section_name=sec.title,
                        heading_hierarchy=sec.heading_path,
                        content=full_chunk_text,
                        token_count=chunk_tokens,
                        has_diagnostic_commands=len(sec.code_blocks) > 0,
                        has_safety_warnings=len(sec.warnings) > 0,
                        safety_warnings=sec.warnings,
                        checksum=prov.checksum_sha256,
                        provenance=prov,
                    )
                )
            else:
                # Case B: Large section requires procedural sub-chunking
                sub_chunks = self._partition_large_section(sec, sec_header, doc)
                chunks.extend(sub_chunks)

        return chunks

    def _partition_large_section(
        self,
        sec: DocumentSection,
        sec_header: str,
        doc: KnowledgeDocument,
    ) -> List[KnowledgeChunk]:
        """Partition large section preserving procedural step lists and safety warnings."""
        lines = sec.body.splitlines()
        sub_chunks: List[KnowledgeChunk] = []

        current_lines: List[str] = []
        part_idx = 1

        for line in lines:
            current_lines.append(line)
            current_text = "\n".join(current_lines)
            if self.estimate_tokens(current_text) >= self.target_tokens:
                # Flush sub-chunk
                chunk_body = "\n".join(current_lines)
                if sec.warnings and not any(w in chunk_body for w in sec.warnings):
                    # Prepend warning for safety preservation
                    chunk_body = f"Safety Notice: {sec.warnings[0]}\n\n" + chunk_body

                full_chunk_text = f"{sec_header} (Part {part_idx})\n\n{chunk_body}"
                chunk_id = self._generate_chunk_id(doc.doc_id, f"{sec.title}-p{part_idx}", full_chunk_text)
                chunk_tokens = self.estimate_tokens(full_chunk_text)

                prov = ProvenanceRecord(
                    source_type=doc.provenance.source_type,
                    source_dataset=doc.source_id,
                    source_record_id=chunk_id,
                    transformation_version="1.0.0",
                    checksum_sha256=hashlib.sha256(full_chunk_text.encode()).hexdigest(),
                    metadata={
                        "doc_id": doc.doc_id,
                        "section_name": f"{sec.title} Part {part_idx}",
                        "heading_path": sec.heading_path,
                    },
                )

                sub_chunks.append(
                    KnowledgeChunk(
                        chunk_id=chunk_id,
                        doc_id=doc.doc_id,
                        source_id=doc.source_id,
                        doc_title=doc.title,
                        source_type=doc.doc_type,
                        trust_classification=doc.trust_classification,
                        network_domain=doc.network_domain,
                        target_subsystems=doc.target_subsystems,
                        technology_generation=doc.technology_generation,
                        vendor=doc.vendor,
                        equipment_family=doc.equipment_family,
                        section_name=f"{sec.title} (Part {part_idx})",
                        heading_hierarchy=sec.heading_path + [f"Part {part_idx}"],
                        content=full_chunk_text,
                        token_count=chunk_tokens,
                        has_diagnostic_commands=bool(re.search(r"```", chunk_body)),
                        has_safety_warnings=len(sec.warnings) > 0,
                        safety_warnings=sec.warnings,
                        checksum=prov.checksum_sha256,
                        provenance=prov,
                    )
                )

                # Overlap: keep last few lines for context
                overlap_lines = current_lines[-3:] if len(current_lines) >= 3 else []
                current_lines = list(overlap_lines)
                part_idx += 1

        if current_lines:
            chunk_body = "\n".join(current_lines).strip()
            if chunk_body:
                full_chunk_text = f"{sec_header} (Part {part_idx})\n\n{chunk_body}"
                chunk_id = self._generate_chunk_id(doc.doc_id, f"{sec.title}-p{part_idx}", full_chunk_text)
                chunk_tokens = self.estimate_tokens(full_chunk_text)

                prov = ProvenanceRecord(
                    source_type=doc.provenance.source_type,
                    source_dataset=doc.source_id,
                    source_record_id=chunk_id,
                    transformation_version="1.0.0",
                    checksum_sha256=hashlib.sha256(full_chunk_text.encode()).hexdigest(),
                    metadata={"doc_id": doc.doc_id, "section_name": f"{sec.title} Part {part_idx}"},
                )

                sub_chunks.append(
                    KnowledgeChunk(
                        chunk_id=chunk_id,
                        doc_id=doc.doc_id,
                        source_id=doc.source_id,
                        doc_title=doc.title,
                        source_type=doc.doc_type,
                        trust_classification=doc.trust_classification,
                        network_domain=doc.network_domain,
                        target_subsystems=doc.target_subsystems,
                        technology_generation=doc.technology_generation,
                        vendor=doc.vendor,
                        equipment_family=doc.equipment_family,
                        section_name=f"{sec.title} (Part {part_idx})",
                        heading_hierarchy=sec.heading_path + [f"Part {part_idx}"],
                        content=full_chunk_text,
                        token_count=chunk_tokens,
                        has_diagnostic_commands=bool(re.search(r"```", chunk_body)),
                        has_safety_warnings=len(sec.warnings) > 0,
                        safety_warnings=sec.warnings,
                        checksum=prov.checksum_sha256,
                        provenance=prov,
                    )
                )

        return sub_chunks

    @staticmethod
    def _generate_chunk_id(doc_id: str, section: str, content: str) -> str:
        """Compute deterministic chunk ID from doc ID, section name, and content prefix."""
        h = hashlib.sha256(f"{doc_id}:{section}:{content[:128]}".encode()).hexdigest()[:10]
        return f"CHK-{doc_id}-{h}"
