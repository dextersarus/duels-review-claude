# duels.ink replay reviews in Discord, on your Claude subscription

Claude Code runs in a container on Unraid with the official Discord plugin. Post a duels.ink replay link and it replies with a review written from the side of whoever recorded the replay, using the replay viewer's play numbers ("Game 1, 24/102"). You can ask follow-up questions in the same chat.

It uses your Claude Pro or Max login (Claude Code's Discord plugin needs a claude.ai login, not an API key), so reviews count against your normal usage limits. It only answers while the container is running.

## 1. Create the Discord bot
1. https://discord.com/developers/applications → **New Application** → name it.
2. **Bot** tab → **Reset Token** → copy the token. Turn on **Message Content Intent** → Save.
3. **OAuth2 → URL Generator**: scope `bot`; permissions View Channels, Send Messages, Send Messages in Threads, Read Message History, Attach Files, Add Reactions. Open the URL and add the bot to your server.
4. In Discord: Settings → Advanced → turn on **Developer Mode**. Right-click the channel you'll post replays in → **Copy Channel ID**. Keep it for step 5.

## 2. Get the code onto Unraid
The repo is private, so cloning needs a GitHub token:
1. GitHub → Settings → Developer settings → **Fine-grained tokens** → Generate new token. Repository access: only `duels-review-claude`. Permissions: **Contents: Read-only**. Copy the token.
2. In the Unraid terminal (replace `YOUR_TOKEN`). This uses a throwaway git container, so it works whether or not Unraid has git installed:

```bash
mkdir -p /mnt/user/appdata/duels-review-claude && cd /mnt/user/appdata/duels-review-claude
docker run --rm -v "$PWD":/git alpine/git clone https://x-access-token:YOUR_TOKEN@github.com/dextersarus/duels-review-claude.git src
mkdir -p home work && chown -R 99:100 home work
```

To update later: `docker run --rm -v /mnt/user/appdata/duels-review-claude/src:/git alpine/git pull`, then rebuild (next step).

## 3. Build and start the container

```bash
docker build -t duels-review-claude /mnt/user/appdata/duels-review-claude/src
docker run -d --name duels-review-claude --restart unless-stopped \
  -v /mnt/user/appdata/duels-review-claude/home:/home/claude \
  -v /mnt/user/appdata/duels-review-claude/work:/work \
  duels-review-claude
```

With the Compose Manager plugin you can instead run `docker compose up -d --build` in the `src` folder.

To rebuild after an update: `docker stop duels-review-claude && docker rm duels-review-claude`, then run both commands above again. Your login and reviews are kept in the `home` and `work` folders.

The first start installs Claude Code and Bun into the persistent home folder (a minute or two; watch with `docker logs -f duels-review-claude`).

## 4. One-time setup inside Claude Code
Attach to the session:

```bash
docker exec -it duels-review-claude tmux attach -t claude
```

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

## 5. Pair the two of you and open the channel
Attach again (`docker exec -it duels-review-claude tmux attach -t claude`). If Claude Code asks you to confirm skipping permission prompts, accept.

1. Each of you DMs the bot. It replies with a pairing code. For each code, type in Claude Code: `/discord:access pair CODE`
2. Lock it to you two: `/discord:access policy allowlist`
3. Let it read your replay channel: `/discord:access group add CHANNEL_ID`
   - By default it only answers when @mentioned in that channel. To have it react to every message there, use `/discord:access group add CHANNEL_ID --no-mention` instead.
4. Detach (**Ctrl-b**, **d**).

Test it: post `@YourBot https://duels.ink/replay/01a1cc4f-fbdf-7e6e-bacc-fde2b926f080` in the channel, or DM it the link.

## Letting others in the server use it
DMs need pairing, but a server channel has its own access list. A channel added with `/discord:access group add CHANNEL_ID` and no `--allow` list lets anyone in that channel @mention the bot. To limit it to certain people: `/discord:access group add CHANNEL_ID --allow USER_ID1,USER_ID2` (right-click a person → Copy User ID). Run `/discord:access` to see the current settings.

Every review counts against your Claude subscription's usage, and a subscription is meant for personal use, so keep this to a small group.

## Troubleshooting
- **Bot shows offline / red X next to Discord in `/mcp`:** the plugin's connector failed to start. The container installs its dependencies on start, so run `docker restart duels-review-claude` first. If it's still red, select it in `/mcp` and press Enter to see the error. "Invalid token" means re-run `/discord:configure`; "disallowed intents" means turn on Message Content Intent.
- **Stuck on a warning screen:** attach and accept the permissions prompt.

## Day to day
- When a link is posted, the bot first replies with an estimate ("about 3 minutes"). It starts from a rough default and, after 3 reviews, uses how long reviews actually take on your server (`work/reviews/timings.csv`).
- Reviews are saved in `/mnt/user/appdata/duels-review-claude/work/reviews/`. Posting the same link again reposts the saved review instead of using your usage on a new one.
- To watch what it's doing: `docker exec -it duels-review-claude tmux attach -t claude` (detach with Ctrl-b, d; don't type `/exit` unless you want it to restart).
- If your Claude login expires, attach and run `/login` again.
- To change how reviews are written, edit `work/review-rules.md` or `work/context.md` (your matchup notes) and run `docker restart duels-review-claude`.
- Updating: pull and rebuild as in step 3. Your edited `review-rules.md` and `context.md` are kept; `CLAUDE.md` and `replay_tool.py` always come from the new version.

## Permissions and safety
Unattended, Claude Code would stop and wait at every permission prompt, so the container runs it with `--dangerously-skip-permissions`. That's reasonable here because:
- it's in its own container with no access to the rest of your server (only its two appdata folders),
- only the two paired Discord accounts can talk to it (`policy allowlist`),
- `CLAUDE.md` limits it to running `replay_tool.py` and writing reviews, and `.claude/settings.json` adds deny rules for your Claude login, web requests and its own instruction files.

To get permission prompts back instead, recreate the container with `-e CLAUDE_FLAGS=""` added to the `docker run` command (or uncomment `CLAUDE_FLAGS: ""` in `docker-compose.yml`). The plugin then sends Allow/Deny buttons to your Discord DMs whenever it needs approval.

## Files
- `work/CLAUDE.md`: standing instructions for the Discord session (replaced on every start; edit it in the repo).
- `work/review-rules.md`: how reviews are written and formatted.
- `work/context.md`: Princess vs Circle notes, used only for that matchup.
- `work/replay_tool.py`: fetches a replay from duels.ink and prints the play-by-play (standard-library Python; also handy on its own: `python3 replay_tool.py <link>`).
