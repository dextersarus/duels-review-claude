#!/bin/bash
# Starts Claude Code in a tmux session named "claude" and keeps it running.
#   Setup mode (first run):  plain `claude`, so you can log in and install the Discord plugin.
#   Normal mode:             `claude --channels plugin:discord@...` once ~/.duels-setup-done exists.
set -u

# Seed the workspace on first start; never overwrite files you've edited.
mkdir -p /work/reviews
cp -rn /opt/work-default/. /work/ 2>/dev/null || true
# The replay tool is code, not settings: always take the image's version.
cp -f /opt/work-default/replay_tool.py /work/replay_tool.py

# Claude Code and Bun live in the persistent home folder; install them once.
if ! command -v bun >/dev/null 2>&1; then
  echo "Installing Bun…"; curl -fsSL https://bun.sh/install | bash
fi
if ! command -v claude >/dev/null 2>&1; then
  echo "Installing Claude Code…"; curl -fsSL https://claude.ai/install.sh | bash
fi

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

# Keep the container alive as long as the tmux session exists.
while tmux has-session -t claude 2>/dev/null; do sleep 30; done
