FROM debian:bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl unzip git python3 tmux procps \
 && rm -rf /var/lib/apt/lists/*

# Unraid's default owner is nobody:users (99:100). Claude Code refuses to skip
# permission prompts as root, so it runs as this user.
RUN useradd -m -u 99 -g 100 -s /bin/bash claude

# Default workspace (CLAUDE.md, review rules, replay tool). Copied into /work on first start.
COPY work /opt/work-default
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh && chown -R 99:100 /opt/work-default

ENV HOME=/home/claude \
    PATH=/home/claude/.local/bin:/home/claude/.bun/bin:/usr/local/bin:/usr/bin:/bin \
    TERM=xterm-256color \
    LANG=C.UTF-8
USER 99:100
WORKDIR /work

# /home/claude keeps the Claude login, plugin and Discord token; /work keeps reviews.
VOLUME ["/home/claude", "/work"]
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
