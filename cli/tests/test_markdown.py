from pathlib import Path

from walkthrough.markdown import render_markdown

from test_validate import filled_plan

GOLDEN = Path(__file__).parent / "golden" / "walkthrough.md"


def test_markdown_matches_golden():
    assert render_markdown(filled_plan()) == GOLDEN.read_text()


def test_deleted_file_excerpt_comes_from_before():
    wt = filled_plan()
    wt.files[0].status = "deleted"
    wt.files[0].before, wt.files[0].after = wt.files[0].after, ""
    out = render_markdown(wt)
    assert "def greet(name):" in out
