# AutoBump Reminder Bot

A small Discord bot. When the DISBOARD bot says it's time to bump, this bot posts

> 🔔 Time to bump the server! Type `/bump` to bump it! 🚀

in one channel you choose. It never pings anyone, never runs `/bump` itself,
and sends only one reminder per DISBOARD message.

## Files

| File | What it is |
|---|---|
| `bot.py` | The bot |
| `requirements.txt` | Libraries to install |
| `.env.example` | List of settings (no secrets) |
| `.gitignore` | Keeps secrets out of GitHub |
| `.python-version` | Tells Render which Python to use |

## Step 1: Create the bot on Discord

1. Go to https://discord.com/developers/applications and click **New Application**. Name it and create it.
2. Left menu: **Bot**.
3. Scroll to **Privileged Gateway Intents** and turn **ON "Message Content Intent"**. Click **Save Changes**.
4. Click **Reset Token**, then copy the token. Keep it private, like a password. Never post it anywhere.

## Step 2: Invite the bot to your server

1. In the Developer Portal, left menu: **General Information**. Copy the **Application ID**.
2. Open this link in your browser, replacing `YOUR_APPLICATION_ID` with that number:

   `https://discord.com/oauth2/authorize?client_id=YOUR_APPLICATION_ID&scope=bot&permissions=3072`

3. Pick your server and click **Authorize**.

The link asks for only two permissions: **View Channel** and **Send Messages**.
No Administrator, no "Mention Everyone".

If your reminder channel has special permissions, make sure the bot's role can
View and Send there.

## Step 3: Get your channel ID

1. Discord: **User Settings > Advanced > Developer Mode: ON**.
2. Right-click the channel where reminders should appear > **Copy Channel ID**.

## Step 4: Deploy on Render

Render Background Workers are **paid** (a Starter instance costs roughly
$7/month; check Render's pricing page for the current price). There is no free
tier for always-on workers. Free Render web services go to sleep and are not
suitable for a bot.

1. Create an account at https://render.com and connect your GitHub.
2. **New + > Background Worker**.
3. Select your `autobump` repository.
4. Settings:
   - **Language:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
   - **Instance type:** Starter (or any paid type)
5. Scroll to **Environment Variables** and click **Add Environment Variable** twice:
   - Key `DISCORD_TOKEN`, Value: your bot token
   - Key `TARGET_CHANNEL_ID`, Value: your channel ID
6. Click **Create Background Worker**. Wait for the deploy to finish.
7. Open the **Logs** tab. You should see `Logged in as ...`.

## Step 5: Test it

**Quick test (no waiting):**
1. In Discord, copy your own user ID (right-click your name > Copy User ID).
2. In Render > your worker > **Environment**, temporarily add:
   - `DISBOARD_BOT_ID` = your own user ID
   - `REMINDER_KEYWORDS` = `test reminder`
3. Save (Render redeploys). Type `test reminder` in any channel the bot can see.
4. The bot should post the reminder in your target channel. Typing it again right away
   will NOT post again (anti-repeat protection, 10 minutes).
5. **Delete both variables** afterwards so the bot listens to the real DISBOARD again.

**Real test:**
1. Add `DEBUG_LOG_DISBOARD` = `true`.
2. Run `/bump`. DISBOARD replies "Bump done"; the bot must stay silent.
3. About 2 hours later DISBOARD sends its reminder; the bot should post yours.
4. In the Logs you will see the exact text of each DISBOARD message.

## If the reminder is not detected

I could not check DISBOARD's current wording, so the detection phrases are
adjustable. With `DEBUG_LOG_DISBOARD=true`, look in Render Logs for lines like
`DISBOARD message ...: '<text>'`. Pick a phrase from the real reminder and set:

`REMINDER_KEYWORDS` = `your phrase|another phrase`

(separate phrases with `|`). If a non-reminder message is wrongly detected, add
a phrase from it to `IGNORE_KEYWORDS`.

## Troubleshooting

- **"DISCORD_TOKEN is missing"**: add the variable in Render.
- **"Discord rejected the token"**: reset the token and update the variable.
- **"Message Content Intent is OFF"**: redo Step 1.3.
- **"Missing permission to send"**: give the bot View Channel + Send Messages in that channel.
- **Nothing happens**: turn on `DEBUG_LOG_DISBOARD` and read the logs.

## Run on your own computer (optional)

```
pip install -r requirements.txt
python bot.py --selftest   # checks the detection rules offline
```
Copy `.env.example` to `.env`, fill in the values, then run `python bot.py`.
