# duels.ink replay reviews in Discord, on your Claude subscription

Claude Code runs in a container on Unraid with the official Discord plugin. Post a duels.ink replay link and it replies with a review written from the side of whoever recorded the replay, using the replay viewer's play numbers ("Game 1, 24/102"). You can ask follow-up questions in the same chat.

It uses your Claude Pro or Max login (Claude Code's Discord plugin needs a claude.ai login, not an API key), so reviews count against your normal usage limits. It only answers while the container is running.

## 1. Create the Discord bot
1. https://discord.com/developers/applications → **New Application** → name it.
2. **Bot** tab → **Reset Token** → copy the token. Turn on **Message Content Intent** → Save.
3. **OAuth2 → URL Generator**: scope `bot`; permissions View Channels, Send Messages, Create Public Threads, Send Messages in Threads, Read Message History, Attach Files, Add Reactions. Open the URL and add the bot to your server.
4. In Discord: Settings → Advanced → turn on **Developer Mode**. Right-click the channel you'll post replays in → **Copy Channel ID**. Keep it for step 4.

## 2. Add the container in Unraid
GitHub builds the image automatically on every push to `main` and publishes it to `ghcr.io/dextersarus/duels-review-claude:latest` (Actions tab → "Build and publish image").

The image comes from a private repo, so Unraid can't pull it until you either:
- **make the package public** (simplest; the image holds no secrets, since your login and tokens live in your appdata folders): GitHub → your profile → **Packages** → `duels-review-claude` → **Package settings** → **Change visibility** → Public, or
- **log Unraid in to ghcr.io**: create a classic token with only `read:packages`, then in the Unraid terminal run `docker login ghcr.io -u dextersarus` and paste the token as the password.

Then in the Unraid terminal:

```bash
mkdir -p /mnt/user/appdata/duels-review-claude/home /mnt/user/appdata/duels-review-claude/work
chown -R 99:100 /mnt/user/appdata/duels-review-claude
curl -fsSL -o /boot/config/plugins/dockerMan/templates-user/my-duels-review-claude.xml \
  https://raw.githubusercontent.com/dextersarus/duels-review-claude/main/unraid/duels-review-claude.xml
```

That last command only works once the repo is public. Otherwise, open `unraid/duels-review-claude.xml` on GitHub, copy its contents, and save it to `/boot/config/plugins/dockerMan/templates-user/my-duels-review-claude.xml` (e.g. `nano` in the terminal).

In Unraid: **Docker** tab → **Add Container** → **Template** → pick **duels-review-claude** under User templates → **Apply**.

The first start installs Claude Code and Bun into the home folder (a minute or two; click the container icon → **Logs** to watch).

Already running it from an earlier `docker run`? Stop and remove that container first (`docker stop duels-review-claude && docker rm duels-review-claude`), then add it from the template with the same folders. Your login, pairing and reviews are kept.

**Updating:** after I push changes, wait for the GitHub build to finish (a green check on the commit), then in the Docker tab click **Check for Updates** → **apply update** on the container.

<details><summary>Alternative: build it yourself on Unraid</summary>

```bash
mkdir -p /mnt/user/appdata/duels-review-claude && cd /mnt/user/appdata/duels-review-claude
docker run --rm -v "$PWD":/git alpine/git clone https://x-access-token:YOUR_TOKEN@github.com/dextersarus/duels-review-claude.git src
docker build -t duels-review-claude src
docker run -d --name duels-review-claude --restart unless-stopped \
  -v /mnt/user/appdata/duels-review-claude/home:/home/claude \
  -v /mnt/user/appdata/duels-review-claude/work:/work \
  duels-review-claude
```
`YOUR_TOKEN` is a fine-grained token with Contents: Read-only on this repo.
</details>

## 3. One-time setup inside Claude Code
Attach to the session: in the Docker tab click the container icon → **Console**, then run `tmux attach -t claude`. (From the Unraid terminal instead: `docker exec -it duels-review-claude tmux attach -t claude`.)

Then, in Claude Code:
1. Trust the `/work` folder when asked.
2. `/login` → choose your Claude account → open the link on your PC, sign in, paste the code back.
3. Install the plugin:
   ```
   /plugin marketplace add anthropics/claude-plugins-official
   /plugin marketplace update claude-plugins-official
   /plugin install discord@claude-plugins-official
   /reload-plugins
   /discord:configure YOUR_DISCORD_BOT_TOKEN
   ```
4. Detach with **Ctrl-b** then **d**, then switch to normal mode:
   ```bash
   docker exec duels-review-claude touch /home/claude/.duels-setup-done
   docker restart duels-review-claude
   ```

## 4. Pair the two of you and open the channel
Attach again (`docker exec -it duels-review-claude tmux attach -t claude`). If Claude Code asks you to confirm skipping permission prompts, accept.

1. Each of you DMs the bot. It replies with a pairing code. For each code, type in Claude Code: `/discord:access pair CODE`
2. Lock it to you two: `/discord:access policy allowlist`
3. Let it read your replay channel: `/discord:access group add CHANNEL_ID`
   - By default it only answers when @mentioned in that channel. To have replay links reviewed without an @mention (recommended), also run:
     `/discord:access set mentionPatterns '["duels.ink/replay/"]'`
     Any message with a replay link then counts as a mention, and ordinary chat never reaches the bot. Avoid `--no-mention`: it sends every message in the channel to the bot.
4. Detach (**Ctrl-b**, **d**).

Test it: post `@YourBot https://duels.ink/replay/01a1cc4f-fbdf-7e6e-bacc-fde2b926f080` in the channel, or DM it the link.

## Letting others in the server use it
DMs need pairing, but a server channel has its own access list. A channel added with `/discord:access group add CHANNEL_ID` and no `--allow` list lets anyone in that channel @mention the bot. To limit it to certain people: `/discord:access group add CHANNEL_ID --allow USER_ID1,USER_ID2` (right-click a person → Copy User ID). Run `/discord:access` to see the current settings.

Every review counts against your Claude subscription's usage, and a subscription is meant for personal use, so keep this to a small group.

## Usage-limit alerts (optional)
When your Claude usage limit is hit, the bot can't post anything itself, so a small watcher in the container does it through a Discord webhook:
1. In Discord: **Server Settings → Integrations → Webhooks → New Webhook**. Pick your replay channel, name it (e.g. "Replay Coach status"), give it the bot's icon if you like, then **Copy Webhook URL**.
2. In Unraid: Docker tab → click the container → **Edit** → paste it into **Discord webhook URL** → **Apply**.

When the limit is hit you'll get one message like "Claude usage limit reached. Replay reviews are paused. It resets **9pm**." Repost any link that didn't get its review once it resets. Treat the webhook URL like a password: anyone with it can post in that channel.

## Update notes (optional)
After each update the bot posts what's new, from `CHANGELOG.md`, in a channel you choose:
1. In Discord, right-click the channel → **Copy Channel ID**. Make sure the bot can see and post there (channel settings → Permissions → add the bot's role with View Channel and Send Messages).
2. In Unraid: Docker tab → click the container → **Edit** → paste it into **Update notes channel ID** → **Apply**. On an older template, add a Variable with Key `UPDATES_CHANNEL_ID`.

It posts once per new version, when the container starts on it. The first time, it posts only the newest version's notes. Without a channel ID it falls back to the usage-limit webhook, if you set one.

## Troubleshooting
- **Bot shows offline / red X next to Discord in `/mcp`:** the plugin's connector failed to start. The container installs its dependencies on start, so run `docker restart duels-review-claude` first. If it's still red, select it in `/mcp` and press Enter to see the error. "Invalid token" means re-run `/discord:configure`; "disallowed intents" means turn on Message Content Intent.
- **Stuck on a warning screen:** attach and accept the permissions prompt.

## Day to day
- When a link is posted in a channel, the bot starts a thread on your message, posts an estimate there, then posts the review in the thread and pings you. It deletes the estimate and reacts ✅ on your message (❌ with a one-line reason if something failed). In DMs it answers in the DM.
- Ask questions or call out mistakes inside the review's thread by replying to one of the bot's messages (or @mentioning it). It answers with a new message and never edits the original review; confirmed corrections are saved in `work/reviews/<id>.followups.md` and included if the review is reposted.
- The plugin can't create threads or delete messages, so `work/discord_tool.py` does those two things through Discord's API, using the bot token the plugin already stores. It only deletes the bot's own messages.
- **Talking among yourselves in a thread:** plain messages there are ignored. If you Reply to one of the bot's messages or @mention it, it answers, unless your message starts with `//`, which always means "not for the bot".
- **The bot learns from corrections.** When someone's call-out checks out against the replay and card text, the bot saves a general lesson to `work/lessons.md` and posts "📌 Saved for future reviews: …" in the thread. It reads that file before every review. Strategy disagreements that come down to judgment aren't saved. To drop a lesson, tell the bot ("remove that lesson") or delete the line from the file. `lessons.md` is yours: updates never overwrite it.
- **Bot permissions:** threads need **Create Public Threads** and **Send Messages in Threads**. If you invited the bot before threads were added: Server Settings → Roles → the bot's role → turn both on (or re-invite it with the URL from step 1).
- The estimate ("about 3 minutes") starts from a rough default and, after 3 reviews, uses how long reviews actually take on your server (`work/reviews/timings.csv`).
- To re-run an old review with the latest rules, delete its file from `work/reviews/` (the `.md`) and post the link again.
- Reviews are saved in `/mnt/user/appdata/duels-review-claude/work/reviews/`. Posting the same link again reposts the saved review instead of using your usage on a new one.
- To watch what it's doing: `docker exec -it duels-review-claude tmux attach -t claude` (detach with Ctrl-b, d; don't type `/exit` unless you want it to restart).
- If your Claude login expires, attach and run `/login` again.
- To change how reviews are written, edit `work/review-rules.md` in the repo (it's replaced on every start). Your matchup notes in `work/context.md` on the server are yours to edit; restart the container afterwards.
- Updating: Docker tab → Check for Updates (see step 2). Your `context.md` is kept; `CLAUDE.md`, `review-rules.md` and `replay_tool.py` always come from the new version, so edit those in the repo.

## Permissions and safety
Unattended, Claude Code would stop and wait at every permission prompt, so the container runs it with `--dangerously-skip-permissions`. That's reasonable here because:
- it's in its own container with no access to the rest of your server (only its two appdata folders),
- only the two paired Discord accounts can talk to it (`policy allowlist`),
- `CLAUDE.md` limits it to running `replay_tool.py` and writing reviews, and `.claude/settings.json` adds deny rules for your Claude login, web requests and its own instruction files.

To get permission prompts back instead, edit the container in the Docker tab, open **Show more settings**, and clear **Claude flags**. The plugin then sends Allow/Deny buttons to your Discord DMs whenever it needs approval.

## Files
- `work/CLAUDE.md`: standing instructions for the Discord session (replaced on every start; edit it in the repo).
- `work/review-rules.md`: the champion-level review method and format (replaced on every start; edit it in the repo).
- `work/context.md`: Princess vs Circle notes, used only for that matchup.
- `work/lessons.md`: lessons the bot has learned from confirmed corrections (kept across updates).
- `work/discord_tool.py`: starts the review thread and deletes the bot's own estimate message (the plugin can't do either).
- `work/replay_tool.py`: fetches a replay and duels.ink's win-probability estimates and prints the play-by-play with the biggest swings marked and a board snapshot at the start of every turn (what the recording player could see then) (standard-library Python; also handy on its own: `python3 replay_tool.py <link>`).
- `unraid/duels-review-claude.xml`: Unraid container template.
- `watch_limits.py`: posts the usage-limit alert to your Discord webhook.
- `announce_update.py` and `CHANGELOG.md`: post the update notes after each update.
- `.github/workflows/docker-publish.yml`: runs the tests and publishes the image to ghcr.io.
