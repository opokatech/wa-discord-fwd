require('dotenv').config();
const { makeWASocket, useMultiFileAuthState, DisconnectReason, downloadMediaMessage } = require('@whiskeysockets/baileys');
const { Boom } = require('@hapi/boom');
const pino = require('pino');
const qrcode = require('qrcode-terminal');
const axios = require('axios');
const FormData = require('form-data');

const DISCORD_WEBHOOK = process.env.DISCORD_WEBHOOK_URL;
const TARGET_GROUP_ID = process.env.TARGET_GROUP_ID || 'targetgroup@g.us';  // Set in .env

// Cache to store recent messages for reaction context
const messageCache = new Map();
const CACHE_SIZE = 100; // Keep last 100 messages

async function start() {
  const { state, saveCreds } = await useMultiFileAuthState('auth_info');

  const sock = makeWASocket({
    logger: pino({ level: 'silent' }),
    printQRInTerminal: false,
    auth: state,
    version: [2, 3000, 1027934701],  // Working Jan 2026 version from GitHub fixes [web:100]
    browser: ['Chrome (Linux)', '120.0.6099.234', 'Linux']  // Stable browser UA
  });


  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', (update) => {
    const { connection, lastDisconnect, qr } = update;
    if (qr) {
      console.log('Scan QR Code:');
      qrcode.generate(qr, { small: true });
    }
    if (connection === 'close') {
      const shouldReconnect = (lastDisconnect?.error instanceof Boom)?.output?.statusCode !== DisconnectReason.loggedOut;
      console.log('Connection closed:', lastDisconnect?.error, 'Reconnecting:', shouldReconnect);
      if (shouldReconnect) start();
    } else if (connection === 'open') {
      console.log('WhatsApp connected!');
    }
  });

  sock.ev.on('messages.upsert', async (m) => {
    const msg = m.messages[0];
    // console.log('Group ID:', msg.key.remoteJid);

    // if (!msg.key.fromMe && msg.key.remoteJid.endsWith('@g.us')) {  // Log all groups first
    //   console.log('Group candidate:', msg.key.remoteJid);
    // }

    if (msg.key.remoteJid === TARGET_GROUP_ID) {
      const sender = msg.pushName || msg.key.participant?.split('@')[0]?.slice(0, 32) || 'Unknown';
      let content = `[whatsapp: ${sender}]: `;

      try {
        // Handle reactions
        if (msg.message?.reactionMessage) {
          const reaction = msg.message.reactionMessage.text;
          const reactionEmoji = {
            '👍': 'thumbs up',
            '❤️': 'heart',
            '😂': 'laughing face',
            '😢': 'crying face',
            '😮': 'surprised face',
            '🔥': 'fire',
            '👏': 'clapping hands',
            '🙏': 'folded hands',
            '😊': 'smile'
          };
          const reactionText = reactionEmoji[reaction] || reaction;

          // Get the message key that was reacted to
          const quotedKey = msg.message.reactionMessage.key?.id;
          let originalText = quotedKey ? messageCache.get(quotedKey) : null;

          const reactionContent = originalText
            ? `Reacted [${reactionText}] to: "${originalText.slice(0, 100)}${originalText.length > 100 ? '...' : ''}"`
            : `[Reaction: ${reactionText}]`;

          const payload = { content: content + reactionContent };

          await axios.post(DISCORD_WEBHOOK, payload, { timeout: 5000 });
          console.log(`Forwarded reaction from ${sender}: ${reactionText}`);
          return;
        }

        // Handle images
        if (msg.message?.imageMessage) {
          const buffer = await downloadMediaMessage(
            msg,
            'buffer',
            {},
            {
              logger: pino({ level: 'silent' }),
              reuploadRequest: sock.updateMediaMessage
            }
          );
          const form = new FormData();
          form.append('file', buffer, {
            filename: `wa-image-${Date.now()}.jpg`,
            contentType: msg.message.imageMessage.mimetype
          });
          form.append('content', `${content}[Image]`);

          await axios.post(DISCORD_WEBHOOK, form, { headers: form.getHeaders(), timeout: 10000 });
          console.log(`Forwarded image from ${sender}`);
          return;
        }

        // Handle text
        const text = msg.message?.conversation || msg.message?.extendedTextMessage?.text || '[Unsupported media]';

        // Cache this message for reaction lookups
        messageCache.set(msg.key.id, text.slice(0, 100));
        if (messageCache.size > CACHE_SIZE) {
          const firstKey = messageCache.keys().next().value;
          messageCache.delete(firstKey);
        }

        const payload = { content: content + text.slice(0, 1900) };  // Discord limit

        await axios.post(DISCORD_WEBHOOK, payload, { timeout: 5000 });
        console.log(`Forwarded text from ${sender}: ${text.slice(0, 50)}`);
      } catch (error) {
        console.error('Forward failed:', error.message);
      }
    }
  });
}

console.log('Starting WA -> Discord forwarder...');
start().catch(err => {
  console.error('Startup failed:', err);
  process.exit(1);
});
