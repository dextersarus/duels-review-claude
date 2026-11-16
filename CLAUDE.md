# Working on this repo

This repo builds the Docker image for Andrew's Discord replay-review bot (see README.md). `work/CLAUDE.md` is the bot's own instructions inside the container, not instructions for working on the repo.

- Every change that people using the bot would notice gets a new version at the top of `CHANGELOG.md`: `## X.Y.Z (YYYY-MM-DD)` with short plain-language bullets. The bot posts these to Discord after each update. Bump the minor version for new behaviour and the patch version for fixes. Internal-only changes (tests, CI) don't need an entry.
- Run `python3 -m pytest -q tests` before pushing; CI runs the same tests and then publishes `ghcr.io/dextersarus/duels-review-claude:latest`.
- `work/context.md` and `work/lessons.md` belong to the users on the server and are never overwritten by updates. Everything else in `work/` is replaced from the image on every start.
