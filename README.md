# WhatsApp to Discord Forwarder

## Project Overview

This project is a one-way message forwarder that automatically sends messages from a WhatsApp group to a Discord server via webhooks. It uses the Baileys library to connect to WhatsApp Web and monitors a target group for new messages, then forwards them in real-time to Discord.

**Note:** This project (including this file) was generated with assistance from AI (Perplexity + GitHub Copilot).

---

## How to Create a Discord Webhook

1. **Open Discord Server Settings**
   - Navigate to your Discord server
   - Go to Settings → Integrations

2. **Create a Webhook**
   - Click "Create Webhook"
   - Give it a name (e.g., "WhatsApp Forwarder")
   - Optionally, set a custom avatar

3. **Select the Channel**
   - Choose the channel where messages will be forwarded
   - Click "Create Webhook"

4. **Copy the Webhook URL**
   - Copy the webhook URL provided
   - Store it safely (this is your `DISCORD_WEBHOOK_URL`)

5. **Configure in Your Project**
   - Add the URL to your `.env` file: `DISCORD_WEBHOOK_URL=https://discordapp.com/api/webhooks/...`

---

## How to Get WhatsApp Group ID Using Web.WhatsApp

1. **Open Web.WhatsApp**
   - Go to [web.whatsapp.com](https://web.whatsapp.com)
   - Scan the QR code with your phone to authenticate

2. **Select Your Target Group**
   - Open the group chat you want to monitor
   - The URL will change to include the group information

3. **Extract the Group ID**
   - Open your browser's Developer Console (F12 or Ctrl+Shift+I)
   - Go to the Network tab and monitor requests
   - Look for the chat identifier in the API calls
   - Group IDs are in the format: `12345678901234567890@g.us`

4. **Alternative Method - Using This App**
   - Run the app with any group ID initially
   - The app logs incoming messages with their group IDs
   - Check the console output to see which group ID receives messages
   - Update your `.env` with `TARGET_GROUP_ID=yourGroupID@g.us`

5. **Configure in Your Project**
   - Add the group ID to your `.env` file: `TARGET_GROUP_ID=12345678901234567890@g.us`

---

## Installation & Usage

### Using Makefile (Recommended)

```bash
make req-install    # Install dependencies
make run            # Start the forwarder
make clean          # Remove node_modules and package-lock.json
make cleanall       # Remove all including .env and auth_info
```

### Manual Installation

```bash
npm install
node index.js
```

### Configuration

1. **Copy the environment template:**
   ```bash
   cp .env_template .env
   ```

2. **Configure your `.env` file with:**
   ```
   DISCORD_WEBHOOK_URL=your_webhook_url
   TARGET_GROUP_ID=your_group_id@g.us
   ```

For reference, see `.env_template` for the required environment variables.
