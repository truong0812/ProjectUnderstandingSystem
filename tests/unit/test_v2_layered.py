from pathlib import Path

from project_understanding_v2.pipeline import ingest_repository
from project_understanding_v2.review import build_review_context


FIXTURE = Path(__file__).parents[1] / "fixtures" / "python_service"


def test_v2_ingest_builds_layered_snapshot():
    snapshot = ingest_repository(str(FIXTURE))

    assert snapshot.files
    assert snapshot.modules
    assert snapshot.classes
    assert snapshot.functions
    assert snapshot.architecture.layers
    assert snapshot.quality.files_scanned >= 4
    assert snapshot.quality.parser_error_count == 0
    assert snapshot.quality.summary_coverage_by_level["architecture"] == 1


def test_v2_review_context_walks_from_function_to_layers():
    snapshot = ingest_repository(str(FIXTURE))

    context = build_review_context(
        snapshot,
        changed_files=["src/services/user_service.py"],
        changed_symbols=["login"],
    )

    changed_names = {function.name for function in context.changed_functions}
    module_names = {module.name for module in context.owning_modules}
    layer_names = {layer.name for layer in context.architecture_layers}

    assert "login" in changed_names
    assert "services" in module_names
    assert "application" in layer_names
    assert "authentication" in context.risk_markers
    assert context.review_checklist
    assert any("src/services/user_service.py" in item for item in context.evidence)
