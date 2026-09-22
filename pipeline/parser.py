"""
ContractNLI dataset parser.

Reads the ContractNLI JSON format into structured Python objects.
Each NDA document contains text spans and 17 hypothesis annotations
with labels (Entailment / Contradiction / NotMentioned) and evidence spans.

The ContractNLI JSON schema (per split file):
{
  "documents": [
    {
      "id": "...",
      "file_name": "...",
      "text": "full NDA text",
      "spans": [
        [start_char, end_char],  // span boundaries
        ...
      ],
      "annotation_sets": [
        {
          "annotations": {
            "nda-1": {
              "choice": "Entailment" | "Contradiction" | "NotMentioned",
              "spans": [0, 3, 7]  // indices into the spans array
            },
            ...
          }
        }
      ]
    }
  ],
  "labels": {
    "nda-1": "Hypothesis text...",
    ...
  }
}
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pipeline.logging_config import get_logger

logger = get_logger("parser")

# Valid classification labels
VALID_LABELS = {"Entailment", "Contradiction", "NotMentioned"}


@dataclass(frozen=True)
class EvidenceSpan:
    """A single evidence span from the NDA text."""
    span_index: int
    start_char: int
    end_char: int
    text: str


@dataclass(frozen=True)
class Annotation:
    """One hypothesis annotation for a document."""
    hypothesis_id: str
    hypothesis_text: str
    label: str  # Entailment | Contradiction | NotMentioned
    evidence_spans: tuple[EvidenceSpan, ...] = ()


@dataclass
class NDADocument:
    """A parsed NDA document with all its annotations."""
    doc_id: str
    file_name: str
    text: str
    spans: list[tuple[int, int]]
    annotations: dict[str, Annotation] = field(default_factory=dict)

    @property
    def num_annotations(self) -> int:
        return len(self.annotations)

    def get_evidence_text(self, hypothesis_id: str) -> list[str]:
        """Return evidence span texts for a given hypothesis."""
        ann = self.annotations.get(hypothesis_id)
        if ann is None:
            return []
        return [span.text for span in ann.evidence_spans]


@dataclass
class ContractNLIDataset:
    """Parsed ContractNLI dataset (one split)."""
    documents: list[NDADocument]
    hypotheses: dict[str, str]  # hypothesis_id -> hypothesis text
    split_name: str = ""

    @property
    def num_documents(self) -> int:
        return len(self.documents)

    @property
    def num_hypotheses(self) -> int:
        return len(self.hypotheses)

    def get_document(self, doc_id: str) -> Optional[NDADocument]:
        """Look up a document by ID."""
        for doc in self.documents:
            if doc.doc_id == doc_id:
                return doc
        return None

    def label_distribution(self) -> dict[str, int]:
        """Count labels across all documents and hypotheses."""
        counts: dict[str, int] = {"Entailment": 0, "Contradiction": 0, "NotMentioned": 0}
        for doc in self.documents:
            for ann in doc.annotations.values():
                counts[ann.label] = counts.get(ann.label, 0) + 1
        return counts

    def all_cases(self) -> list[tuple[NDADocument, Annotation]]:
        """Yield all (document, annotation) pairs for evaluation."""
        cases = []
        for doc in self.documents:
            for ann in doc.annotations.values():
                cases.append((doc, ann))
        return cases


def parse_contractnli_file(filepath: str | Path) -> ContractNLIDataset:
    """
    Parse a single ContractNLI JSON file (train.json, dev.json, or test.json).

    Args:
        filepath: Path to the JSON file.

    Returns:
        ContractNLIDataset with all documents and hypotheses.

    Raises:
        FileNotFoundError: if the file does not exist.
        ValueError: if the JSON structure is unexpected.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"ContractNLI file not found: {filepath}")

    logger.info(f"Parsing ContractNLI file: {filepath.name}")

    with open(filepath, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Extract hypothesis texts. ContractNLI's real schema nests each entry as
    # {"short_description": ..., "hypothesis": "..."} rather than a plain
    # string; accept a plain string too for synthetic/test fixtures.
    raw_labels = raw.get("labels", {})
    hypotheses: dict[str, str] = {
        hyp_id: (entry.get("hypothesis", "") if isinstance(entry, dict) else str(entry))
        for hyp_id, entry in raw_labels.items()
    }
    if not hypotheses:
        raise ValueError(f"No 'labels' (hypotheses) found in {filepath}")

    # Parse documents
    raw_docs = raw.get("documents", [])
    if not raw_docs:
        raise ValueError(f"No 'documents' found in {filepath}")

    documents: list[NDADocument] = []
    parse_errors = 0

    for raw_doc in raw_docs:
        try:
            doc = _parse_document(raw_doc, hypotheses)
            documents.append(doc)
        except Exception as e:
            parse_errors += 1
            doc_id = raw_doc.get("id", "unknown")
            logger.warning(f"Failed to parse document {doc_id}: {e}")

    split_name = filepath.stem  # train, dev, or test
    logger.info(
        f"Parsed {len(documents)} documents from {split_name} "
        f"({parse_errors} errors, {len(hypotheses)} hypotheses)"
    )

    return ContractNLIDataset(
        documents=documents,
        hypotheses=hypotheses,
        split_name=split_name,
    )


def _parse_document(raw_doc: dict, hypotheses: dict[str, str]) -> NDADocument:
    """Parse a single document entry from the ContractNLI JSON."""
    # ContractNLI document IDs are ints in the raw JSON; normalise to str
    # since evaluation.schemas (GoldCase, Prediction) require doc_id: str.
    doc_id = str(raw_doc["id"])
    file_name = raw_doc.get("file_name", doc_id)
    text = raw_doc["text"]
    raw_spans = raw_doc.get("spans", [])

    # Parse span boundaries
    spans: list[tuple[int, int]] = []
    for s in raw_spans:
        if isinstance(s, (list, tuple)) and len(s) == 2:
            spans.append((int(s[0]), int(s[1])))

    # Parse annotations
    annotations: dict[str, Annotation] = {}
    annotation_sets = raw_doc.get("annotation_sets", [])

    if annotation_sets:
        # Use the first annotation set (ContractNLI has one per document)
        ann_set = annotation_sets[0]
        raw_annotations = ann_set.get("annotations", {})

        for hyp_id, ann_data in raw_annotations.items():
            label = ann_data.get("choice", "")
            if label not in VALID_LABELS:
                logger.warning(
                    f"Unknown label '{label}' for {doc_id}/{hyp_id}, skipping"
                )
                continue

            # Build evidence spans
            evidence_spans: list[EvidenceSpan] = []
            span_indices = ann_data.get("spans", [])
            for idx in span_indices:
                if 0 <= idx < len(spans):
                    start, end = spans[idx]
                    span_text = text[start:end]
                    evidence_spans.append(EvidenceSpan(
                        span_index=idx,
                        start_char=start,
                        end_char=end,
                        text=span_text,
                    ))

            hyp_text = hypotheses.get(hyp_id, "")
            annotations[hyp_id] = Annotation(
                hypothesis_id=hyp_id,
                hypothesis_text=hyp_text,
                label=label,
                evidence_spans=tuple(evidence_spans),
            )

    return NDADocument(
        doc_id=doc_id,
        file_name=file_name,
        text=text,
        spans=spans,
        annotations=annotations,
    )


def load_all_splits(data_dir: str | Path = "data/contractnli") -> dict[str, ContractNLIDataset]:
    """
    Load all available ContractNLI splits (train, dev, test).

    Returns:
        Dict mapping split name to dataset.
    """
    data_dir = Path(data_dir)
    splits: dict[str, ContractNLIDataset] = {}

    for split_name in ("train", "dev", "test"):
        filepath = data_dir / f"{split_name}.json"
        if filepath.exists():
            splits[split_name] = parse_contractnli_file(filepath)
        else:
            logger.info(f"Split file not found, skipping: {filepath}")

    return splits


def check_split_leakage(
    splits: dict[str, ContractNLIDataset],
) -> list[str]:
    """
    Check for document-level leakage between splits.

    Returns list of document IDs that appear in more than one split.
    """
    doc_to_splits: dict[str, list[str]] = {}
    for split_name, dataset in splits.items():
        for doc in dataset.documents:
            doc_to_splits.setdefault(doc.doc_id, []).append(split_name)

    leaked = [
        doc_id for doc_id, split_list in doc_to_splits.items()
        if len(split_list) > 1
    ]

    if leaked:
        logger.error(f"LEAKAGE DETECTED: {len(leaked)} documents appear in multiple splits")
    else:
        logger.info("No split leakage detected")

    return leaked
