import os
import re
import signal
import sqlite3
import threading

from dotenv import load_dotenv

load_dotenv()

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")
TARGET_GROUP_ID = os.getenv("TARGET_GROUP_ID", "targetgroup@g.us")
DEVICE_NAME = os.getenv("DEVICE_NAME", "Neonize")
CACHE_SIZE = 500
QUOTE_TRUNCATE = 500
SILENT_TYPES = {"senderKeyDistributionMessage", "protocolMessage"}

contact_names = {}   # phone_or_lid -> display_name


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


def resolveMentions(text, names=None, mentioned_jids=None):
    if names is None:
        names = contact_names
    if mentioned_jids:
        resolved = [names.get(j.split('@')[0], j.split('@')[0]) for j in mentioned_jids]
        it = iter(resolved)
        return re.sub(r"@\S+", lambda m: f"@{next(it, m.group(0)[1:])}", text)
    return re.sub(
        r"@(\d+)",
        lambda m: f"@{names[m.group(1)]}" if m.group(1) in names else m.group(0),
        text,
    )


def resolve_sender_name(phone: str, pushname: str, names: dict) -> str:
    return names.get(phone) or pushname or phone[:32] or "Unknown"


def main():
    import requests  # noqa: PLC0415
    from neonize.client import NewClient
    from neonize.events import ConnectedEv, MessageEv
    from neonize.proto.waCompanionReg.WAWebProtobufsCompanionReg_pb2 import DeviceProps
    from neonize.utils.jid import build_jid

    cache = init_cache()
    client = NewClient("neonize.db", props=DeviceProps(os=DEVICE_NAME, platformType=DeviceProps.SAFARI))

    @client.event(ConnectedEv)
    def on_connected(_client, _event):
        print("WhatsApp connected!")
        # Pre-populate LID -> name from group participant list
        try:
            group_user, _, group_server = TARGET_GROUP_ID.partition('@')
            group_info = client.get_group_info(build_jid(group_user, group_server))
            for p in group_info.Participants:
                lid = p.LID.User
                phone = p.PhoneNumber.User or p.JID.User
                name = contact_names.get(phone) or p.DisplayName
                if lid and name:
                    contact_names[lid] = name
            print(f"Loaded {len(group_info.Participants)} group participants")
        except Exception as e:
            print(f"Could not load group participants: {e}")

    def post_to_discord(content):
        payload = {"content": content[:1900]}  # Discord message limit
        requests.post(DISCORD_WEBHOOK, json=payload, timeout=5).raise_for_status()

    @client.event(MessageEv)
    def on_message(wa, event):
        chat = event.Info.MessageSource.Chat
        chat_jid = f"{chat.User}@{chat.Server}"
        if chat_jid != TARGET_GROUP_ID:
            return

        sender_jid = event.Info.MessageSource.Sender
        if sender_jid.Server == "lid":
            alt = event.Info.MessageSource.SenderAlt
            phone = alt.User if alt.User else sender_jid.User
        else:
            phone = sender_jid.User
        sender = resolve_sender_name(phone, event.Info.Pushname, contact_names)
        # Cache LID -> resolved name so @lid mentions in message text resolve correctly
        if sender_jid.Server == "lid" and sender_jid.User and sender != "Unknown":
            contact_names[sender_jid.User] = sender

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
                caption = event.Message.imageMessage.caption
                data = {"content": f"[whatsapp: {sender}]:"}
                requests.post(DISCORD_WEBHOOK, data=data, files=files, timeout=10).raise_for_status()
                if caption:
                    post_to_discord(caption)
                print(f"Forwarded image from {sender}")
                return

            # Text message (plain or extended)
            raw_text = event.Message.conversation or (
                event.Message.extendedTextMessage.text
                if event.Message.HasField("extendedTextMessage")
                else None
            )

            if raw_text:
                is_extended = event.Message.HasField("extendedTextMessage")
                mentioned_jids = (
                    list(event.Message.extendedTextMessage.contextInfo.mentionedJID)
                    if is_extended
                    else None
                )
                # Resolve any mentioned LIDs not yet in contact_names
                for jid_str in (mentioned_jids or []):
                    user, _, server = jid_str.partition('@')
                    if user and user not in contact_names and server == "lid":
                        try:
                            phone_jid = wa.get_pn_from_lid(build_jid(user, "lid"))
                            name = contact_names.get(phone_jid.User)
                            if name:
                                contact_names[user] = name
                        except Exception:
                            pass
                text = resolveMentions(raw_text, mentioned_jids=mentioned_jids)

                # Persist for reaction/reply lookups
                cache_set(cache, event.Info.ID, sender, text)

                # Reply context
                content = f"[whatsapp: {sender}]: "
                if is_extended:
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
