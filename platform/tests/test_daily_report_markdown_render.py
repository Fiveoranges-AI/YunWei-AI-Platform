from platform_app.daily_report import markdown_render


def test_render_markdown_to_html_basic():
    md = "# Title\n\n- item 1\n- item 2"
    html = markdown_render.render(md)
    assert "<h1>" in html
    assert "<ul>" in html
    assert "<li>item 1</li>" in html


def test_render_strips_dangerous_html():
    md = "<script>alert('x')</script>\n\n# ok"
    html = markdown_render.render(md)
    assert "<script>" not in html
    assert "<h1>ok</h1>" in html
