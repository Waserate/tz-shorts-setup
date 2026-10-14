---
name: shorts-edit
description: Use when the user types /shorts-edit or asks to clean up / finish a Take A Zeat or Bangkok Esports Short in CapCut (captions, B-roll, title, layout, face framing). Runs the shorts-pipeline scripts on a CapCut draft in the one order that works, refusing while CapCut is open.
---

# shorts-edit — finish a Short in CapCut with the pipeline scripts

Pipeline folder: `%TZ_SHORTS_HOME%\shorts-pipeline` (set by setup.ps1).
Python: `%TZ_SHORTS_HOME%\shorts-pipeline\venv\Scripts\python.exe` — never the system Python.
Full background: `HANDOFF.md` (RUNBOOK section) and `ERRORS.md` in that folder. Read ERRORS.md
before debugging anything.

Talk to the user in polite, plain Thai. Never use กู/มึง.

## 0. Ask for what is missing — do not guess

| need | from the user |
|---|---|
| draft name | exactly as shown in CapCut's project list |
| `terms_<clip>.txt` | proper nouns (people, games, places), one per line — offer to draft it from the captions |
| `caption_terms_<clip>.json` | Thai-script English → English, spelled numbers → numerals — offer to draft it |
| B-roll plan / stills | only if they want B-roll; `broll_<clip>.json`, `stills_<clip>.json` |
| title text | the 1–2 line title |

The user does these in CapCut BEFORE you run anything:
1. new draft, import `Video Main.mp4`, **Captions > Auto captions > Thai**
2. their own cleaning cut (dead air, retakes, counting in) — their cut is the standard
3. **close CapCut**

## 1. Hard rules

- 🟥 **CapCut must be closed before every script.** It rewrites `draft_content.json` from memory
  on exit and silently undoes the work. Check first:
  `tasklist /FI "IMAGENAME eq CapCut.exe"` — if it is listed, stop and ask the user to close it.
- 🟥 **Order is fixed.** Later steps find tracks by position; run `normalise_tracks` first and
  again at the end.
- 🟥 **Stop at the first error.** Quote the exact error, say which step stopped and which steps
  did not run, then diagnose (diagnosing-bugs skill). Never skip a failed step and continue.
- 🟥 Never delete the user's footage, VO, images or drafts. Backups go to `shorts-pipeline\backup`.

## 2. The run (from the pipeline folder)

```
1.  normalise_tracks.py   --draft "<name>"
2.  resplit_captions.py   --draft "<name>" --terms-file terms_<clip>.txt
3.  apply_caption_terms.py --draft-file "<draft folder>\draft_content.json" --rules caption_terms_<clip>.json --out "<draft folder>\draft_content.json"
4.  enrich_draft.py       --draft "<name>" --skip-look --zoom-share 0 --broll-plan broll_<clip>.json --comments stills_<clip>.json
5.  add_title.py          --draft "<name>" --text "<title>" --at 0 --until <seconds> --box 0.92
6.  fix_layout.py         --draft "<name>" --follow-draft --main-bottom
7.  face_frame.py         --draft "<name>"
8.  fill_frame.py         --draft "<name>" --skip-track 2
9.  uniform_captions.py   --draft "<name>" --size 20
10. normalise_tracks.py   --draft "<name>"
11. check_black.py        --draft "<name>"     # must print "ไม่พบจอดำ"
```

`<draft folder>` = `%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft\<name>`.
Skip step 4 if there is no B-roll. Run `<script> --help` when unsure of a flag — the help text
is the truth, this list is a summary.

## 3. Hand back

Tell the user, in Thai: which steps ran, what `check_black` printed, and that CapCut can be
opened now. Things they still do by hand (by design): inserted reaction clips, background music,
captions for inserted clips, removing a comment still.
