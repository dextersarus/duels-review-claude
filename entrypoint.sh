#!/bin/bash
# Starts Claude Code in a tmux session named "claude" and keeps it running.
#   Setup mode (first run):  plain `claude`, so you can log in and install the Discord plugin.
#   Normal mode:             `claude --channels plugin:discord@...` once ~/.duels-setup-done exists.
set -u

# Seed the workspace on first start; never overwrite files you've edited.
mkdir -p /work/reviews
cp -rn /opt/work-default/. /work/ 2>/dev/null || true
# The bot's instructions, review method and replay tool come from the image: always take the latest.
# (context.md, your matchup notes, is yours to edit and is never overwritten.)
cp -f /opt/work-default/replay_tool.py /opt/work-default/discord_tool.py /opt/work-default/CLAUDE.md /opt/work-default/review-rules.md /work/
# Deck playing guides come from the image too (add or edit them in the repo).
rm -rf /work/guides && cp -r /opt/work-default/guides /work/guides
mkdir -p /work/.claude && cp -f /opt/work-default/.claude/settings.json /work/.claude/settings.json

# Claude Code and Bun live in the persistent home folder; install them once.
if ! command -v bun >/dev/null 2>&1; then
  echo "Installing Bun…"; curl -fsSL https://bun.sh/install | bash
fi
if ! command -v claude >/dev/null 2>&1; then
  echo "Installing Claude Code…"; curl -fsSL https://claude.ai/install.sh | bash
fi

# The Discord plugin's connector needs its Bun dependencies; without them /mcp shows a red X.
for d in "$HOME"/.claude/plugins/cache/claude-plugins-official/discord/*/; do
  if [ -f "$d/package.json" ] && [ ! -d "$d/node_modules" ]; then
    echo "Installing Discord plugin dependencies in $d…"
    (cd "$d" && bun install --no-summary) || echo "bun install failed in $d"
  fi
done

if [ -f "$HOME/.duels-setup-done" ]; then
  CMD="claude ${CLAUDE_FLAGS---dangerously-skip-permissions} --channels plugin:discord@claude-plugins-official"
  echo "Normal mode: $CMD"
else
  CMD="claude"
  echo "Setup mode. Attach with: docker exec -it duels-review-claude tmux attach -t claude"
fi

tmux kill-session -t claude 2>/dev/null || true
tmux new-session -d -s claude -c /work \
  "while true; do $CMD; echo 'Claude Code exited. Restarting in 10 seconds (Ctrl-C to stop)…'; sleep 10; done"

# Post update notes once per new version (needs UPDATES_CHANNEL_ID or DISCORD_WEBHOOK_URL).
if [ -f "$HOME/.duels-setup-done" ] && { [ -n "${UPDATES_CHANNEL_ID:-}" ] || [ -n "${DISCORD_WEBHOOK_URL:-}" ]; }; then
  python3 /usr/local/bin/announce_update.py &
fi

# Post to Discord when the Claude usage limit is hit (needs DISCORD_WEBHOOK_URL).
if [ -n "${DISCORD_WEBHOOK_URL:-}" ] && [ -f "$HOME/.duels-setup-done" ]; then
  python3 /usr/local/bin/watch_limits.py &
fi

# Keep the container alive as long as the tmux session exists.
while tmux has-session -t claude 2>/dev/null; do sleep 30; done
