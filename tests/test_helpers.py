from app import quoteText, resolveMentions, QUOTE_TRUNCATE, resolve_sender_name

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

def test_resolveMentions_jids_resolves_typed_mention():
    # @typed text resolved via mentionedJid list
    result = resolveMentions("hey @ali", mentioned_jids=["48601@s.whatsapp.net"], names={"48601": "Alice"})
    assert result == "hey @Alice"

def test_resolveMentions_jids_resolves_numeric_mention():
    # @number also resolved via mentionedJid positional matching
    result = resolveMentions("hey @48601", mentioned_jids=["48601@s.whatsapp.net"], names={"48601": "Alice"})
    assert result == "hey @Alice"

def test_resolveMentions_jids_fallback_to_jid_user():
    # JID user part used when no name found
    result = resolveMentions("hey @ali", mentioned_jids=["48601@s.whatsapp.net"], names={})
    assert result == "hey @48601"

def test_resolveMentions_jids_multiple_positional():
    result = resolveMentions("@ali and @bob", mentioned_jids=["111@s.whatsapp.net", "222@lid"], names={"111": "Alice", "222": "Bob"})
    assert result == "@Alice and @Bob"


def test_resolve_prefers_contact_name():
    assert resolve_sender_name("48601", "Karol", {"48601": "Karol Ambroszkiewicz"}) == "Karol Ambroszkiewicz"

def test_resolve_falls_back_to_pushname():
    assert resolve_sender_name("48601", "Karol", {}) == "Karol"

def test_resolve_falls_back_to_phone():
    assert resolve_sender_name("48601", "", {}) == "48601"

def test_resolve_truncates_long_phone():
    phone = "9" * 50
    assert resolve_sender_name(phone, "", {}) == "9" * 32

def test_resolve_unknown_when_all_empty():
    assert resolve_sender_name("", "", {}) == "Unknown"
