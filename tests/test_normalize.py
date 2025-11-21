from crawler.parser import normalize_url


def test_normalize_basic_absolute():
    base = "https://example.com/"
    out = normalize_url(base, "/about")
    assert out == "https://example.com/about"


def test_normalize_fragment_removed():
    base = "https://example.com/x"
    out = normalize_url(base, "details#section")
    assert out == "https://example.com/details"


def test_blocked_schemes():
    base = "https://example.com/"
    assert normalize_url(base, "mailto:test@example.com") is None
    assert normalize_url(base, "javascript:void(0)") is None


def test_blocked_extensions():
    base = "https://example.com/"
    assert normalize_url(base, "image.JPG") is None
    assert normalize_url(base, "doc.pdf") is None


def test_strip_default_ports():
    base = "http://example.com/"
    out = normalize_url(base, "http://example.com:80/path")
    assert out == "http://example.com/path"
    base2 = "https://example.com/"
    out2 = normalize_url(base2, "https://example.com:443/path")
    assert out2 == "https://example.com/path"
