from readiness.adapters.llm.mock import MockLLM
from readiness.ingestion.classify import llm_refine_classification
from readiness.models import DocClass, DocumentRef, ExtractedDocument
from readiness.pipeline import run_assessment


def _doc(name, cls, conf):
    return ExtractedDocument(
        ref=DocumentRef(id=name, name=name, uri=f"file:///{name}", source="local"),
        text="some text",
        classification=cls,
        classification_confidence=conf,
    )


def test_only_unsure_docs_are_sent_and_weaker_verdicts_are_ignored():
    sure = _doc("sure", DocClass.NETWORK, 0.9)
    unsure = _doc("unsure", DocClass.IRRELEVANT, 0.2)
    weak = _doc("weak", DocClass.IRRELEVANT, 0.5)
    mock = MockLLM(
        canned={
            "ClassificationBatch": {
                "items": [
                    {"doc_id": "unsure", "classification": "operations", "confidence": 0.9},
                    {"doc_id": "weak", "classification": "network", "confidence": 0.4},  # less sure than keywords
                ]
            }
        }
    )
    out = llm_refine_classification([sure, unsure, weak], mock)
    _, prompt = mock.calls[0]
    assert 'id="unsure"' in prompt and 'id="weak"' in prompt and 'id="sure"' not in prompt
    assert out[1].classification == DocClass.OPERATIONS and out[1].classification_confidence == 0.9
    assert out[2].classification == DocClass.IRRELEVANT  # LLM verdict below keyword confidence is ignored
    assert out[0].classification == DocClass.NETWORK


def test_pipeline_uses_guarded_classifier_when_enabled(settings, fixtures_dir):
    base, _ = run_assessment(f"file://{fixtures_dir / 'synthetic_acme'}", settings, "security_only")
    readme = next(d for d in base.documents if d.name == "README.md")  # low-confidence 'irrelevant'
    assert base.document_classes[readme.id] == DocClass.IRRELEVANT
    mock = MockLLM(
        canned={
            "ClassificationBatch": {
                "items": [{"doc_id": readme.id, "classification": "operations", "confidence": 0.95}]
            }
        }
    )
    s = settings.model_copy(update={"use_llm_classifier": True})
    report, _ = run_assessment(f"file://{fixtures_dir / 'synthetic_acme'}", s, "security_only", llm=mock)
    assert report.document_classes[readme.id] == DocClass.OPERATIONS
    assert report.llm_provider == "mock"
    system, prompt = mock.calls[0]
    assert "untrusted client data" in system and readme.id in prompt


def test_classifier_off_by_default_makes_no_llm_calls(settings, fixtures_dir):
    mock = MockLLM()
    run_assessment(f"file://{fixtures_dir / 'synthetic_acme'}", settings, "security_only", llm=mock)
    assert mock.calls == []
