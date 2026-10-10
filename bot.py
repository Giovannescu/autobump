"""
Discord AutoBump Reminder Bot
-----------------------------
Watches for the official DISBOARD bot's "time to bump" reminder and posts
your own reminder message in ONE chosen channel.

- Never pings anyone (all mentions are disabled).
- Never runs /bump (a real person must do that).
- Sends only one reminder per DISBOARD message.

All settings come from environment variables (see .env.example).
"""

import logging
import os
import re
import sys
from collections import deque
from time import monotonic

import discord
from dotenv import load_dotenv

# Loads a local .env file if present (for testing on your own computer).
# On Render you set environment variables in the dashboard instead.
load_dotenv()

# --------------------------------------------------------------------------
# CONFIGURATION
# --------------------------------------------------------------------------

# The official DISBOARD bot's user ID (same for every server).
DEFAULT_DISBOARD_BOT_ID = 302050872383242240

# Text of the reminder your bot sends.
DEFAULT_REMINDER_MESSAGE = "🔔 Time to bump the server! Type `/bump` to bump it! 🚀"

# ---- Reminder detection (EASY TO ADJUST) ----------------------------------
# A DISBOARD message counts as a reminder if its text (message body + embed
# text) contains ANY phrase from REMINDER_KEYWORDS and NONE from IGNORE_KEYWORDS.
# Matching is case-insensitive. You can change these here, or without editing
# code by setting the REMINDER_KEYWORDS / IGNORE_KEYWORDS environment
# variables (separate phrases with the | character).
DEFAULT_REMINDER_KEYWORDS = [
    "bump now",
    "time to bump",
    "bump the server",
    "/bump",
]
DEFAULT_IGNORE_KEYWORDS = [
    "bump done",
    "bump successful",
    "bumped by",
    "check it out on disboard",
    "wait another",
    "until the server can be bumped",
]

# Safety net: never send two reminders closer together than this (seconds).
DEFAULT_MIN_SECONDS_BETWEEN_REMINDERS = 600

log = logging.getLogger("autobump")


def _env_list(name, default):
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return list(default)
    return [p.strip().lower() for p in raw.split("|") if p.strip()]


def _env_int(name, default=None):
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        log.error("Environment variable %s must be a number, got %r", name, raw)
        sys.exit(1)


def _env_bool(name, default=False):
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


DISBOARD_BOT_ID = _env_int("DISBOARD_BOT_ID", DEFAULT_DISBOARD_BOT_ID)
TARGET_CHANNEL_ID = _env_int("TARGET_CHANNEL_ID")
REMINDER_MESSAGE = os.getenv("REMINDER_MESSAGE") or DEFAULT_REMINDER_MESSAGE
REMINDER_KEYWORDS = _env_list("REMINDER_KEYWORDS", DEFAULT_REMINDER_KEYWORDS)
IGNORE_KEYWORDS = _env_list("IGNORE_KEYWORDS", DEFAULT_IGNORE_KEYWORDS)
MIN_SECONDS_BETWEEN_REMINDERS = _env_int(
    "MIN_SECONDS_BETWEEN_REMINDERS", DEFAULT_MIN_SECONDS_BETWEEN_REMINDERS
)
# When true, logs the full text of every DISBOARD message so you can see
# exactly what DISBOARD writes and tune the keywords above.
DEBUG_LOG_DISBOARD = _env_bool("DEBUG_LOG_DISBOARD", False)

# --------------------------------------------------------------------------
# DETECTION LOGIC
# --------------------------------------------------------------------------


def _normalize(text):
    return re.sub(r"\s+", " ", text.lower()).strip()


def extract_text(message):
    """Collects text from the message body AND all embeds."""
    parts = [message.content or ""]
    for embed in message.embeds:
        parts.append(embed.title or "")
        parts.append(embed.description or "")
        if embed.author and embed.author.name:
            parts.append(embed.author.name)
        if embed.footer and embed.footer.text:
            parts.append(embed.footer.text)
        for field in embed.fields:
            parts.append(field.name or "")
            parts.append(field.value or "")
    return _normalize(" ".join(p for p in parts if p))


def is_reminder_text(text):
    """True if the (already normalized) text looks like a bump reminder."""
    if any(bad in text for bad in IGNORE_KEYWORDS):
        return False
    return any(good in text for good in REMINDER_KEYWORDS)


def run_self_test():
    """Offline check of the detection rules: python bot.py --selftest"""
    cases = [
        ("Bump now! Please type /bump to bump the server", True),
        ("Time to bump the server </bump:947088344167366698>", True),
        ("Bump done! :thumbsup: Check it out on DISBOARD.", False),
        ("Please wait another 42 minutes until the server can be bumped", False),
        ("Hello, thanks for using DISBOARD", False),
    ]
    ok = True
    for text, expected in cases:
        got = is_reminder_text(_normalize(text))
        status = "OK  " if got == expected else "FAIL"
        ok = ok and got == expected
        print(f"{status} expected={expected!s:5} got={got!s:5} | {text}")
    print("All tests passed." if ok else "Some tests FAILED.")
    return ok


# --------------------------------------------------------------------------
# BOT
# --------------------------------------------------------------------------

intents = discord.Intents.default()
intents.message_content = True  # Also enable "Message Content Intent" in the Developer Portal!

client = discord.Client(intents=intents)

_seen_ids = set()
_seen_order = deque(maxlen=500)
_last_sent = None  # monotonic timestamp of the last reminder we sent


def _already_handled(message_id):
    """Returns True if we've seen this message ID; otherwise remembers it."""
    if message_id in _seen_ids:
        return True
    if len(_seen_order) == _seen_order.maxlen:
        _seen_ids.discard(_seen_order[0])
    _seen_order.append(message_id)
    _seen_ids.add(message_id)
    return False


async def _get_target_channel():
    channel = client.get_channel(TARGET_CHANNEL_ID)
    if channel is None:
        channel = await client.fetch_channel(TARGET_CHANNEL_ID)
    return channel


async def send_reminder():
    global _last_sent
    try:
        channel = await _get_target_channel()
    except discord.NotFound:
        log.error("Target channel %s not found. Check TARGET_CHANNEL_ID.", TARGET_CHANNEL_ID)
        return
    except discord.Forbidden:
        log.error("No access to channel %s. Give the bot 'View Channel'.", TARGET_CHANNEL_ID)
        return
    except discord.HTTPException as exc:
        log.error("Could not look up the target channel: %s", exc)
        return

    if not isinstance(channel, discord.abc.Messageable):
        log.error("Channel %s cannot receive messages.", TARGET_CHANNEL_ID)
        return

    try:
        await channel.send(
            REMINDER_MESSAGE,
            allowed_mentions=discord.AllowedMentions.none(),  # never ping anyone
        )
        _last_sent = monotonic()
        log.info("Reminder sent to channel %s.", TARGET_CHANNEL_ID)
    except discord.Forbidden:
        log.error(
            "Missing permission to send in channel %s. Give the bot "
            "'View Channel' and 'Send Messages' there.",
            TARGET_CHANNEL_ID,
        )
    except discord.HTTPException as exc:
        log.error("Discord refused to send the reminder: %s", exc)


@client.event
async def on_ready():
    log.info("Logged in as %s (ID: %s)", client.user, client.user.id)
    log.info("Watching for DISBOARD bot ID %s; reminders go to channel %s.",
             DISBOARD_BOT_ID, TARGET_CHANNEL_ID)
    log.info("Reminder keywords: %s | Ignored: %s", REMINDER_KEYWORDS, IGNORE_KEYWORDS)


@client.event
async def on_message(message):
    try:
        # Only messages from DISBOARD, only inside servers, never our own.
        if message.guild is None or message.author.id != DISBOARD_BOT_ID:
            return
        if client.user is not None and message.author.id == client.user.id:
            return

        text = extract_text(message)

        if DEBUG_LOG_DISBOARD:
            log.info("DISBOARD message %s in #%s: %r", message.id,
                     getattr(message.channel, "name", "?"), text)

        if not text:
            log.debug("DISBOARD message %s has no readable text "
                      "(is Message Content Intent enabled?).", message.id)
            return

        if not is_reminder_text(text):
            log.debug("Message %s is not a reminder; ignoring.", message.id)
            return

        if _already_handled(message.id):
            log.info("Already handled message %s; skipping.", message.id)
            return

        if _last_sent is not None and monotonic() - _last_sent < MIN_SECONDS_BETWEEN_REMINDERS:
            log.info("A reminder was sent very recently; skipping message %s.", message.id)
            return

        log.info("Reminder detected in message %s.", message.id)
        await send_reminder()
    except Exception:  # keep the bot alive no matter what
        log.exception("Unexpected error while handling message")


def main():
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )

    if "--selftest" in sys.argv:
        sys.exit(0 if run_self_test() else 1)

    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        log.error("DISCORD_TOKEN is missing. Add it as an environment variable.")
        sys.exit(1)
    if TARGET_CHANNEL_ID is None:
        log.error("TARGET_CHANNEL_ID is missing. Add it as an environment variable.")
        sys.exit(1)

    try:
        client.run(token, log_handler=None)
    except discord.LoginFailure:
        log.error("Discord rejected the token. Reset it in the Developer Portal "
                  "and update DISCORD_TOKEN.")
        sys.exit(1)
    except discord.PrivilegedIntentsRequired:
        log.error("Message Content Intent is OFF. Enable it in the Developer Portal "
                  "(Bot page > Privileged Gateway Intents).")
        sys.exit(1)


if __name__ == "__main__":
    main()
