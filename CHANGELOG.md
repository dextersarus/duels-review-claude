# Update notes

Newest first. Each `## <version>` section is posted to Discord the first time the bot starts on that version. Write the bullets for the people using the bot: what changed for them, in plain words.

## 1.9.0 (2026-11-27)
- Reviews of Amber/Emerald Princess Aggro now use our team's playing guide: mulligan targets, ideal openers, which 4-drop to play on turn 3 (on the play or draw, against Steel or not) and the deck's main combos. The review says when a play follows or breaks the guide.

## 1.8.1 (2026-11-25)
- When the Claude usage limit resets, the alert channel now says "✅ Claude usage limit has reset" instead of posting the limit-reached message again.

## 1.8.0 (2026-11-16)
- Every game's review now starts with the mulligan: what you kept, what you sent back, and whether that was right.
- Game 1's mulligan is judged blind, using only what the mulligan screen showed (your hand, play or draw, the opponent's ink colors). From Game 2 on, it also uses every card the opponent showed in the earlier games.

## 1.7.0 (2026-11-16)
- Want to talk about a review without the bot answering? Start your message with `//` and it stays out of it, even if you reply to one of its messages. Plain messages in a thread (no reply to the bot, no @mention) are already ignored.

## 1.6.0 (2026-11-16)
- The bot now posts update notes like these in the channel whenever it's updated.

## 1.5.0 (2026-11-16)
- Every review gets its own thread on the message with the replay link.
- Ask questions or call out mistakes in the thread by replying to the bot. It answers with a new message and never edits the original review.
- When a call-out checks out, the bot saves the general lesson and applies it to future reviews. It posts "📌 Saved for future reviews" so you can see what it learned. Tell it "remove that lesson" to undo one.

## 1.4.0 (2026-11-13)
- Reviews judge each decision only on what you could see at that moment. Each turn now starts with a board snapshot, and the opponent's hidden hand is treated as a range, not a fact.
- The "Analyzing…" message is deleted when the review is posted, and your message gets ✅ (or ❌ with a reason if something failed).

## 1.3.0 (2026-11-13)
- Reviews use Discord formatting (headings, bullets, highlighted numbers) and no longer attach files or show link previews.
- You get pinged when your review is ready.
- If the Claude usage limit is hit, a message says when reviews will be back.

## 1.2.0 (2026-11-13)
- Reviews follow a world-champion method: map both decks, find each game's clock, rebuild the board at turning points and check every suggested line with real numbers.
- duels.ink's win-probability swings point the review at the moments that mattered.
- In channels, the bot only answers messages with a replay link, an @mention, or a reply to it.

## 1.1.0 (2026-11-13)
- The bot posts an estimate of how long the review will take, and the estimates get more accurate as it learns how long reviews take.

## 1.0.0 (2026-11-13)
- Post a duels.ink replay link and get a review written from the side of whoever recorded it, with the replay viewer's play numbers.
- Posting a link that was already reviewed reposts the saved review.
