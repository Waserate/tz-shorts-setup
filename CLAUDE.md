# TZ Shorts — Claude instructions for this PC

This PC is used to edit short-form clips (Shorts / Reels / TikTok) for the YouTube channels
**Take A Zeat** (influencer drama, internet culture) and **Bangkok Esports** (gaming, esports).
The footage is filmed already; the job is captions, B-roll, title, layout and a clean CapCut draft.

## How to talk

- Reply in **plain, full Thai sentences** — even if the caveman plugin is on, explanations to the
  user stay in complete, easy Thai. Technical terms may stay in English.
- 🟥 Never use กู/มึง or other crude pronouns. Neutral/polite Thai only.
- Be straight: no flattery, and say clearly when you don't know. Never invent facts, sources or numbers.

## The Shorts workflow

- To finish a clip in CapCut use the **`/shorts-edit`** skill. Its rules are not optional:
  🟥 CapCut closed before every script · fixed step order · stop at the first error and report it.
- Pipeline code: `shorts-pipeline\` (this repo). Read `shorts-pipeline\ERRORS.md` before debugging.
  `HANDOFF.md` was written on the original PC — its `N:\...` paths mean this repo folder;
  every script now gets its paths from `shorts-pipeline\config.py`.
- 🟥 Never delete footage, voice-over, images, or CapCut drafts the user made. Temp copies only.

## Reading clips from the internet

Claude cannot watch video directly. Download it, then read its subtitles and look at frames.

| source | use |
|---|---|
| YouTube / Facebook / IG / TikTok / X video | `yt-dlp "<url>"` (add `--write-auto-subs --sub-langs th,en` for subtitles; IG/FB often need `--cookies-from-browser chrome`) |
| look at the picture | `ffmpeg -i clip.mp4 -vf fps=1/5 frame_%03d.jpg` then read the jpgs |
| YouTube transcript + summary | `notebooklm` skill (needs `notebooklm login` once) |
| a tweet (x.com/…/status/…) | `python %USERPROFILE%\tools\x-scraper-toolkit\fxtweet.py <url>` — x.com blocks normal web fetches |
| general web / search | `agent-reach` skill (`agent-reach doctor` shows what works) |

## Other tools on this PC

- **Remotion** (`remotion\`): video graphics from code — `npm run studio` to preview,
  `npm run render` to export. The Remotion Agent Skill teaches you its API.
- **Whisper Thai model** (`shorts-pipeline\models\`): fallback captions when CapCut Auto Caption
  is not usable — `run_subs.py`. Slow without an NVIDIA card.
- Plugins: superpowers (planning/debugging workflows), claude-mem (memory across chats), caveman (short replies).
