"""
Unit tests for pipeline/parser.py.

Uses small synthetic ContractNLI-shaped JSON fixtures rather than the real
607-document dataset, so tests stay fast and deterministic.
"""

from __future__ import annotations

import json

from pipeline.parser import (
    check_split_leakage,
    load_all_splits,
    parse_contractnli_file,
)


def make_contractnli_json(doc_id: str, text: str, labels: dict[str, str]) -> dict:
    """Build one minimal ContractNLI-shaped split file with a single document."""
    spans = [[0, 10], [11, 20]]
    annotations = {}
    for hyp_id, choice in labels.items():
        annotations[hyp_id] = {"choice": choice, "spans": [0, 1] if choice != "NotMentioned" else []}

    return {
        "documents": [
            {
                "id": doc_id,
                "file_name": f"{doc_id}.pdf",
                "text": text,
                "spans": spans,
                "annotation_sets": [{"annotations": annotations}],
            }
        ],
        "labels": {hyp_id: f"Hypothesis text for {hyp_id}" for hyp_id in labels},
    }


def test_parse_contractnli_file_basic(tmp_path):
    data = make_contractnli_json("doc1", "Some NDA text here", {"nda-1": "Entailment"})
    filepath = tmp_path / "dev.json"
    filepath.write_text(json.dumps(data))

    dataset = parse_contractnli_file(filepath)

    assert dataset.num_documents == 1
    assert dataset.num_hypotheses == 1
    assert dataset.split_name == "dev"

    doc = dataset.get_document("doc1")
    assert doc is not None
    assert doc.text == "Some NDA text here"
    assert doc.annotations["nda-1"].label == "Entailment"


def test_hypothesis_text_extracted_from_real_contractnli_label_shape(tmp_path):
    """
    The real ContractNLI schema nests each label entry as
    {"short_description": ..., "hypothesis": "..."}, not a plain string.
    hypothesis_text must resolve to the actual sentence, not the dict.
    """
    data = {
        "documents": [
            {
                "id": "doc1", "file_name": "doc1.pdf", "text": "text",
                "spans": [[0, 4]],
                "annotation_sets": [{"annotations": {"nda-1": {"choice": "Entailment", "spans": [0]}}}],
            }
        ],
        "labels": {
            "nda-1": {
                "short_description": "No reverse engineering",
                "hypothesis": "Receiving Party shall not reverse engineer Confidential Information.",
            }
        },
    }
    filepath = tmp_path / "dev.json"
    filepath.write_text(json.dumps(data))

    dataset = parse_contractnli_file(filepath)
    doc = dataset.get_document("doc1")

    assert isinstance(doc.annotations["nda-1"].hypothesis_text, str)
    assert doc.annotations["nda-1"].hypothesis_text == (
        "Receiving Party shall not reverse engineer Confidential Information."
    )


def test_document_id_is_normalised_to_str(tmp_path):
    """
    Real ContractNLI document IDs are ints in the raw JSON (e.g. 3, not
    "3"). doc_id must be normalised to str since evaluation.schemas
    (GoldCase, Prediction) require doc_id: str and reject int outright.
    """
    data = {
        "documents": [{
            "id": 456, "file_name": "doc.pdf", "text": "text", "spans": [],
            "annotation_sets": [{"annotations": {}}],
        }],
        "labels": {"nda-1": {"hypothesis": "h"}},
    }
    filepath = tmp_path / "dev.json"
    filepath.write_text(json.dumps(data))

    dataset = parse_contractnli_file(filepath)
    doc = dataset.documents[0]
    assert doc.doc_id == "456"
    assert isinstance(doc.doc_id, str)


def test_get_evidence_text_matches_span_indices(tmp_path):
    text = "0123456789ABCDEFGHIJ"  # spans [0,10) and [11,20)
    data = make_contractnli_json("doc1", text, {"nda-1": "Contradiction"})
    filepath = tmp_path / "dev.json"
    filepath.write_text(json.dumps(data))

    dataset = parse_contractnli_file(filepath)
    doc = dataset.get_document("doc1")
    evidence = doc.get_evidence_text("nda-1")

    assert evidence == ["0123456789", "BCDEFGHIJ"]


def test_get_evidence_text_unknown_hypothesis_returns_empty(tmp_path):
    data = make_contractnli_json("doc1", "text", {"nda-1": "Entailment"})
    filepath = tmp_path / "dev.json"
    filepath.write_text(json.dumps(data))

    dataset = parse_contractnli_file(filepath)
    doc = dataset.get_document("doc1")
    assert doc.get_evidence_text("nda-999") == []


def test_parse_contractnli_file_missing_file_raises(tmp_path):
    try:
        parse_contractnli_file(tmp_path / "nonexistent.json")
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        pass


def test_parse_contractnli_file_missing_labels_raises(tmp_path):
    filepath = tmp_path / "dev.json"
    filepath.write_text(json.dumps({"documents": [{"id": "d1", "text": "t", "spans": []}]}))
    try:
        parse_contractnli_file(filepath)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_unknown_label_is_skipped(tmp_path):
    data = make_contractnli_json("doc1", "text", {"nda-1": "Entailment"})
    data["documents"][0]["annotation_sets"][0]["annotations"]["nda-2"] = {
        "choice": "TotallyBogusLabel", "spans": [],
    }
    filepath = tmp_path / "dev.json"
    filepath.write_text(json.dumps(data))

    dataset = parse_contractnli_file(filepath)
    doc = dataset.get_document("doc1")
    assert "nda-2" not in doc.annotations
    assert "nda-1" in doc.annotations


def test_label_distribution_counts_across_documents(tmp_path):
    data = make_contractnli_json("doc1", "text", {"nda-1": "Entailment", "nda-2": "Contradiction"})
    filepath = tmp_path / "dev.json"
    filepath.write_text(json.dumps(data))

    dataset = parse_contractnli_file(filepath)
    dist = dataset.label_distribution()
    assert dist["Entailment"] == 1
    assert dist["Contradiction"] == 1
    assert dist["NotMentioned"] == 0


def test_all_cases_yields_doc_annotation_pairs(tmp_path):
    data = make_contractnli_json("doc1", "text", {"nda-1": "Entailment", "nda-2": "NotMentioned"})
    filepath = tmp_path / "dev.json"
    filepath.write_text(json.dumps(data))

    dataset = parse_contractnli_file(filepath)
    cases = dataset.all_cases()
    assert len(cases) == 2
    assert all(doc.doc_id == "doc1" for doc, _ in cases)


def test_load_all_splits_skips_missing_files(tmp_path):
    data = make_contractnli_json("doc1", "text", {"nda-1": "Entailment"})
    (tmp_path / "dev.json").write_text(json.dumps(data))
    # train.json and test.json intentionally absent.

    splits = load_all_splits(tmp_path)

    assert set(splits.keys()) == {"dev"}


def test_check_split_leakage_detects_shared_doc_id():
    dev_data = make_contractnli_json("shared_doc", "text", {"nda-1": "Entailment"})
    test_data = make_contractnli_json("shared_doc", "text", {"nda-1": "Entailment"})

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        Path(d, "dev.json").write_text(json.dumps(dev_data))
        Path(d, "test.json").write_text(json.dumps(test_data))
        splits = load_all_splits(d)

    leaked = check_split_leakage(splits)
    assert leaked == ["shared_doc"]


def test_check_split_leakage_clean_when_disjoint():
    dev_data = make_contractnli_json("dev_doc", "text", {"nda-1": "Entailment"})
    test_data = make_contractnli_json("test_doc", "text", {"nda-1": "Entailment"})

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        Path(d, "dev.json").write_text(json.dumps(dev_data))
        Path(d, "test.json").write_text(json.dumps(test_data))
        splits = load_all_splits(d)

    assert check_split_leakage(splits) == []
