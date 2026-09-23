"""Guards against a Dockerfile-only bug class already hit twice in this
codebase: a source file the app reads at runtime (e.g. a bundled .docx
template) exists in every local/dev/test checkout regardless of what the
Dockerfile copies, so pytest run from the source tree can never catch a
missing COPY line — only a check against the Dockerfile's own text can."""

from pathlib import Path

_DOCKERFILE = Path(__file__).resolve().parent.parent / "Dockerfile"


def test_dockerfile_copies_docs_templates_for_mb02a_export():
    text = _DOCKERFILE.read_text()
    assert "COPY docs/templates" in text, (
        "app/agents/eb/mb02_export.py loads docs/templates/template_MB02a.docx "
        "at runtime via a path relative to its own module location — if the "
        "Dockerfile doesn't COPY docs/templates into the image, every non-blocked "
        "MB02a export 500s in production (file exists in every dev/test checkout, "
        "so no other test catches this)."
    )
