import os
import re
import signal
import sqlite3
import threading

from dotenv import load_dotenv

load_dotenv()

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")
TARGET_GROUP_ID = os.getenv("TARGET_GROUP_ID", "targetgroup@g.us")
CACHE_SIZE = 500
QUOTE_TRUNCATE = 500
SILENT_TYPES = {"senderKeyDistributionMessage", "protocolMessage"}

contact_names = {}   # phone_number -> display_name


def init_cache(db_path="message_cache.db"):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS message_cache (
            msg_id TEXT PRIMARY KEY,
            sender TEXT NOT NULL,
            text   TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def cache_get(conn, msg_id):
    row = conn.execute(
        "SELECT sender, text FROM message_cache WHERE msg_id = ?", (msg_id,)
    ).fetchone()
    return {"sender": row[0], "text": row[1]} if row else None


def cache_set(conn, msg_id, sender, text):
    conn.execute(
        "INSERT OR REPLACE INTO message_cache (msg_id, sender, text) VALUES (?, ?, ?)",
        (msg_id, sender, text),
    )
    conn.execute("""
        DELETE FROM message_cache WHERE msg_id IN (
            SELECT msg_id FROM message_cache
            ORDER BY rowid ASC
            LIMIT MAX(0, (SELECT COUNT(*) FROM message_cache) - ?)
        )
    """, (CACHE_SIZE,))
    conn.commit()


def quoteText(text):
    truncated = text[:QUOTE_TRUNCATE] + ("..." if len(text) >= QUOTE_TRUNCATE else "")
    return "\n".join(f"> {line}" for line in truncated.split("\n"))


def resolveMentions(text, names=None):
    if names is None:
        names = contact_names
    return re.sub(
        r"@(\d+)",
        lambda m: f"@{names[m.group(1)]}" if m.group(1) in names else m.group(0),
        text,
    )


def main():
    import requests  # noqa: PLC0415
    from neonize.client import NewClient
    from neonize.events import ConnectedEv, MessageEv

    cache = init_cache()
    client = NewClient("neonize.db")

    @client.event(ConnectedEv)
    def on_connected(_client, _event):
        print("WhatsApp connected!")

    def post_to_discord(content):
        payload = {"content": content[:1900]}  # Discord message limit
        requests.post(DISCORD_WEBHOOK, json=payload, timeout=5).raise_for_status()

    @client.event(MessageEv)
    def on_message(wa, event):
        chat = event.Info.MessageSource.Chat
        chat_jid = f"{chat.User}@{chat.Server}"
        if chat_jid != TARGET_GROUP_ID:
            return

        sender = event.Info.Pushname or event.Info.MessageSource.Sender.User[:32] or "Unknown"

        # Track participant name for @mention resolution
        participant = event.Info.MessageSource.Sender.User
        if participant and event.Info.Pushname:
            contact_names[participant] = event.Info.Pushname

        try:
            # Reactions
            if event.Message.HasField("reactionMessage"):
                reaction_emoji = event.Message.reactionMessage.text
                if not reaction_emoji:
                    return  # un-react event; nothing to forward
                quoted_key = event.Message.reactionMessage.key.ID
                original = cache_get(cache, quoted_key)
                if original:
                    body = (
                        f"reacted {reaction_emoji} to {original['sender']}:\n"
                        f"{quoteText(original['text'])}"
                    )
                else:
                    body = f"reacted {reaction_emoji}"
                post_to_discord(f"[whatsapp: {sender}] {body}")
                print(f"Forwarded reaction from {sender}: {reaction_emoji}")
                return

            # Images
            if event.Message.HasField("imageMessage"):
                buffer = wa.download_any(event.Message)
                mime = event.Message.imageMessage.mimetype or "image/jpeg"
                ext = {"image/png": "png", "image/webp": "webp", "image/gif": "gif"}.get(mime, "jpg")
                files = {
                    "file": (
                        f"wa-image-{int(event.Info.Timestamp)}.{ext}",
                        buffer,
                        mime,
                    )
                }
                data = {"content": f"[whatsapp: {sender}]: [Image]"}
                requests.post(DISCORD_WEBHOOK, data=data, files=files, timeout=10).raise_for_status()
                print(f"Forwarded image from {sender}")
                return

            # Text message (plain or extended)
            raw_text = event.Message.conversation or (
                event.Message.extendedTextMessage.text
                if event.Message.HasField("extendedTextMessage")
                else None
            )

            if raw_text:
                text = resolveMentions(raw_text)

                # Persist for reaction/reply lookups
                cache_set(cache, event.Info.ID, sender, text)

                # Reply context
                content = f"[whatsapp: {sender}]: "
                if event.Message.HasField("extendedTextMessage"):
                    quoted_id = event.Message.extendedTextMessage.contextInfo.stanzaID
                    original = cache_get(cache, quoted_id)
                    if original:
                        content = (
                            f"[whatsapp: {sender}] replied to {original['sender']}:\n"
                            f"{quoteText(original['text'])}\n"
                        )

                post_to_discord(content + text)
                print(f"Forwarded text from {sender}: {text[:QUOTE_TRUNCATE]}")
                return

            # Silently drop internal WhatsApp protocol messages
            fields = [f.name for f, _ in event.Message.ListFields()
                      if f.name != "messageContextInfo"]
            if any(f in SILENT_TYPES for f in fields):
                return

            # Unsupported fallback
            msg_type = ", ".join(fields) or "unknown"
            post_to_discord(f"[whatsapp: {sender}]: [Unsupported: {msg_type}]")
            print(f"Forwarded unsupported type from {sender}: {msg_type}")

        except Exception as e:
            print(f"Forward failed: {e}")

    t = threading.Thread(target=client.connect, daemon=True)
    t.start()
    while t.is_alive():
        t.join(timeout=1)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda *_: os._exit(0))
    print("Starting WA -> Discord forwarder...")
    main()
