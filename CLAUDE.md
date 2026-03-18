# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

WhatsApp-to-Discord message forwarder. Monitors a target WhatsApp group via the neonize library (Python bindings to whatsmeow/Go) and forwards messages (text, images, reactions) to a Discord channel via webhook.

Single-file Python application (`app.py`). No build step.

## Commands

```bash
make req-install    # Install pip-tools and sync dependencies
make run            # Start the forwarder (python app.py)
make req-update     # Upgrade and recompile dependencies
make clean          # Remove __pycache__ dirs
make cleanall       # Remove .env and neonize.db
```

Tests: `pytest tests/` or `.venv/bin/pytest tests/`

## Configuration

Environment variables loaded from `.env` (see `.env_template`):
- `DISCORD_WEBHOOK_URL` - Discord webhook endpoint
- `TARGET_GROUP_ID` - WhatsApp group JID (format: `1234567890-123456789@g.us`)

## Architecture

All logic lives in `app.py`:

1. **Connection** (`main()`) - Creates a neonize WhatsApp client, handles QR auth on first run (session persisted in `neonize.db`), connects and blocks.

2. **Connected handler** (`on_connected` event) - Pre-populates `contact_names` from the group participant list so display names are available before any messages arrive.

3. **Message handler** (`on_message` event, registered via `@client.event(MessageEv)`) - Filters messages by `TARGET_GROUP_ID`, then dispatches by type:
   - **Reactions** - Maps emoji to text description, looks up original message + sender from cache, formats as `[whatsapp: X] reacted [Y] to Z:` with blockquote. Un-reacts (empty emoji) are silently dropped.
   - **Images** - Downloads media via `wa.download_any()`, uploads to Discord as multipart form-data
   - **Replies** - Looks up quoted message + sender from cache via `contextInfo.stanzaID`, formats as `[whatsapp: X] replied to Z:` with blockquote
   - **Text** - Extracts from `conversation` or `extendedTextMessage.text`, caches for lookups, POSTs to Discord webhook
   - **Unsupported** - Forwards the message type name (e.g. `[Unsupported: videoMessage]`) to Discord

3. **Message cache** - Dict-based LRU (`CACHE_SIZE` entries) storing message ID -> `{ text, sender }`, used to provide context when forwarding reactions and replies.

4. **`quoteText()` helper** - Truncates text to `QUOTE_TRUNCATE` chars and prefixes every line with `>` for Discord blockquote rendering.

5. **`resolveMentions()` helper** - Replaces `@phonenumber` with `@displayname` using the `contact_names` map built from incoming messages.

All forwarded messages are prefixed with `[whatsapp: sendername]` and text is truncated to 1900 chars (Discord limit). Constants `CACHE_SIZE`, `QUOTE_TRUNCATE`, and `REACTION_EMOJI` are module-level.

## Key Dependencies

- `neonize` - Python bindings to whatsmeow (Go); implements the WhatsApp mobile protocol. Requires `libmagic1` system package at runtime (`apt-get install libmagic1`).
- `requests` - HTTP client for Discord webhook POSTs
- `python-dotenv` - `.env` loading
- `pytest` - Test runner (tests cover pure helper functions only)

## Dependency Management

Uses pip-tools:
- `requirements.in` — direct dependencies
- `requirements.txt` — generated lockfile (committed); regenerate with `make req-update`
