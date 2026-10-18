"""Tests for 100% air-gapped / offline environment integrity.

Verifies bundled local fonts (Inter, JetBrainsMono), local Chart.js bundle,
and asserts zero external CDN calls exist across all HTML templates.
"""

from pathlib import Path


def _get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def test_bundled_chart_js_exists_and_valid():
    root = _get_project_root()
    chart_js = root / "app" / "static" / "js" / "chart.umd.min.js"
    assert chart_js.exists(), "Local chart.umd.min.js bundle missing"
    assert chart_js.stat().st_size > 100_000, "Local chart.umd.min.js bundle appears corrupted or truncated"

    # Verify UMD bundle signature
    content = chart_js.read_text(encoding="utf-8", errors="ignore")
    assert "Chart" in content


def test_bundled_local_fonts_exist_and_non_empty():
    root = _get_project_root()
    fonts_dir = root / "app" / "static" / "fonts"
    assert fonts_dir.is_dir(), "app/static/fonts directory missing"

    inter = fonts_dir / "Inter-Regular.woff2"
    jb_mono = fonts_dir / "JetBrainsMono-Regular.woff2"

    assert inter.exists(), "Inter-Regular.woff2 font missing"
    assert inter.stat().st_size > 5_000, "Inter-Regular.woff2 font file too small"

    assert jb_mono.exists(), "JetBrainsMono-Regular.woff2 font missing"
    assert jb_mono.stat().st_size > 5_000, "JetBrainsMono-Regular.woff2 font file too small"


def test_templates_have_zero_external_cdn_references():
    root = _get_project_root()
    templates_dir = root / "app" / "templates"
    templates = list(templates_dir.rglob("*.html"))
    assert len(templates) > 0, "No templates found to inspect"

    forbidden_cdns = [
        "fonts.googleapis.com",
        "fonts.gstatic.com",
        "cdn.jsdelivr.net",
        "unpkg.com",
        "cdnjs.cloudflare.com",
        "maxcdn.bootstrapcdn.com",
        "code.jquery.com",
        "ajax.googleapis.com",
    ]

    violations = []
    for tmpl in templates:
        content = tmpl.read_text(encoding="utf-8")
        for cdn in forbidden_cdns:
            if cdn in content:
                violations.append(f"{tmpl.name} contains external CDN reference: {cdn}")

    assert not violations, "Air-gap audit failed:\n" + "\n".join(violations)


def test_templates_use_local_static_assets():
    root = _get_project_root()
    base_html = root / "app" / "templates" / "base.html"
    assert base_html.exists()
    base_content = base_html.read_text(encoding="utf-8")
    assert "/static/css/style_v2.css" in base_content

    # Templates with charts reference local bundle, not CDN
    for tmpl_name in ["intelligence.html", "ranking.html"]:
        tmpl = root / "app" / "templates" / tmpl_name
        assert tmpl.exists()
        content = tmpl.read_text(encoding="utf-8")
        assert "chart.umd.min.js" in content
        assert "cdn.jsdelivr.net" not in content

    # Verify stylesheet configures offline @font-face rules
    css_file = root / "app" / "static" / "css" / "style_v2.css"
    assert css_file.exists()
    css_content = css_file.read_text(encoding="utf-8")
    assert "@font-face" in css_content
    assert "Inter-Regular.woff2" in css_content
    assert "JetBrainsMono-Regular.woff2" in css_content
