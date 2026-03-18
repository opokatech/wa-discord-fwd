# WhatsApp to Discord Forwarder

## Project Overview

One-way message forwarder that monitors a WhatsApp group and forwards messages in real-time to a Discord channel via webhook. Handles text, replies, reactions, and images.

Built with Python and [neonize](https://github.com/krypton-byte/neonize) (Python bindings to [whatsmeow](https://github.com/tulir/whatsmeow), a Go WhatsApp client using the mobile protocol).

---

## Requirements

- Python 3.11+
- `libmagic1` system package (required by neonize)

```bash
sudo apt-get install -y libmagic1
```

---

## Installation & Usage

### Setup

```bash
# Install dependencies
make req-install

# Configure environment
cp .env_template .env
# Edit .env with your values
```

### Run

```bash
make run
```

On first run a QR code is printed — scan it with WhatsApp on your phone to authenticate. The session is saved to `neonize.db` so subsequent runs connect without scanning again.

Press **Ctrl+C** to stop.

### Other commands

```bash
make req-update     # Upgrade dependencies
make clean          # Remove __pycache__ dirs
make cleanall       # Remove .env and neonize.db (resets session)
```

---

## Configuration

Copy `.env_template` to `.env` and fill in:

| Variable | Required | Description |
|---|---|---|
| `DISCORD_WEBHOOK_URL` | Yes | Discord webhook endpoint |
| `TARGET_GROUP_ID` | Yes | WhatsApp group JID (`1234567890-123456789@g.us`) |
| `DEVICE_NAME` | No | Name shown in WhatsApp → Linked Devices (default: `Neonize`) |

> **Note:** `DEVICE_NAME` is only applied when pairing for the first time (or after deleting `neonize.db`). To rename an existing session, run `make cleanall` and re-pair.

### How to get your Discord webhook URL

1. Server Settings → Integrations → Create Webhook
2. Choose a channel, give it a name, click **Copy Webhook URL**
3. Paste into `.env` as `DISCORD_WEBHOOK_URL`

### How to get your WhatsApp group ID

The easiest way is to run the forwarder with any placeholder group ID first:

```
TARGET_GROUP_ID=placeholder@g.us
```

Send a message in your target group — the console will log the group ID of every incoming message. Copy the correct one into `.env` and restart.

Group IDs are in the format `1234567890-123456789@g.us`.

---

## What gets forwarded

| Message type | Discord output |
|---|---|
| Text | `[whatsapp: Name]: message` |
| Reply | `[whatsapp: Name] replied to Other:\n> quoted\nmessage` |
| Reaction | `[whatsapp: Name] reacted [thumbs up] to Other:\n> quoted` |
| Image | `[whatsapp: Name]: [Image]` + attached file |
| Other | `[whatsapp: Name]: [Unsupported: typeName]` |

Internal WhatsApp protocol messages (key distribution, deletions) are silently ignored.
