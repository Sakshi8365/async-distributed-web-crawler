from crawler.parser import normalize_url, extract_links


def test_normalize_url_basic():
    base = "https://example.com/path/index.html"
    assert normalize_url(base, "/about") == "https://example.com/about"
    assert normalize_url(base, "#frag") == "https://example.com/path/index.html"
    assert normalize_url(base, "mailto:foo@example.com") is None


def test_extract_links_filters_binary_and_duplicates():
    base = "https://example.com/"
    html = """
    <html><head><title>Test</title></head>
    <body>
        <a href="/a">A</a>
        <a href="/a#frag">A2</a>
        <a href="/image.jpg">img</a>
        <a href="https://other.com/">other</a>
    </body></html>
    """
    title, links = extract_links(base, html, allowed_domains={"example.com"})
    assert title == "Test"
    assert links == ["https://example.com/a"]
