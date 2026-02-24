from index import quoteText, resolveMentions, QUOTE_TRUNCATE


def test_quoteText_single_line():
    assert quoteText("hello") == "> hello"


def test_quoteText_multiline():
    assert quoteText("line1\nline2") == "> line1\n> line2"


def test_quoteText_truncates_long_text():
    long = "x" * (QUOTE_TRUNCATE + 50)
    result = quoteText(long)
    assert result.endswith("...")
    # Original text was truncated to QUOTE_TRUNCATE, then "> " prepended
    assert len(result) <= QUOTE_TRUNCATE + len("> ") + len("...")


def test_quoteText_exact_limit_adds_ellipsis():
    text = "x" * QUOTE_TRUNCATE
    result = quoteText(text)
    assert result.endswith("...")


def test_resolveMentions_known_number():
    result = resolveMentions("hello @123", {"123": "Alice"})
    assert result == "hello @Alice"


def test_resolveMentions_unknown_number():
    result = resolveMentions("hello @999", {})
    assert result == "hello @999"


def test_resolveMentions_multiple():
    result = resolveMentions("@111 and @222", {"111": "Alice", "222": "Bob"})
    assert result == "@Alice and @Bob"
