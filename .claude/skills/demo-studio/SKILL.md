---
name: demo-studio
description: Create a narrated voice-over demo of one of this repo's apps — analyze the product, write a narration script, generate voiceover audio (ElevenLabs or macOS say), capture the running app with Playwright, and assemble a finished demo.mp4 with captions. Use when the user asks for a demo video, voiceover, product walkthrough, explainer, or marketing asset for an app in this repo.
---

# Demo Studio

Produce a narrated product demo in five stages. Each stage's output feeds the
next; expensive stages (capture) come after cheap ones (script) so mistakes are
caught early. All intermediate files go in the session scratchpad; final assets
land in `demo-output/<app>/` at the repo root (gitignored — add if missing).

Two modes:
- **Full demo** (default): voiceover + screen capture muxed into `demo.mp4`.
- **Explainer** (audio-only): when the app can't run locally or the user only
  wants narration — skip stages 3–4, deliver `voiceover.m4a` + `captions.srt`
  + the script as markdown.

## Stage 0 — Pick the target and learn the product

Read `references/products.md` (in this skill) for the app inventory, run
commands, and demo highlights. If the user didn't name an app, ask. Then read
the app's README and main entry file to ground the narration in real features —
never invent capabilities. Note which UI states are reachable without live
Databricks credentials (mock/static-data apps capture cleanly; the control
plane and agent app need creds and live infra).

## Stage 1 — Write the narration script

**Skip this stage if an approved `script.json` already exists** — from the
`video-script` skill or the `demo` pipeline skill (same format). When writing
a script here, first read `../video-script/references/hooks.md` (hook rules:
short statement with a number, no question openers) and
`../video-script/references/manuka-voice.md` (Manuka positioning, practitioner
tone, soft engagement CTA — applies to all content, always).

Write `script.json`:

```json
{
  "app": "digital-twin-poc-app",
  "voice": "Samantha",
  "segments": [
    {"id": "hook",     "text": "What if you could see a supply-chain crisis coming...", "action": "land on Command Center, hold on KPI row"},
    {"id": "problem",  "text": "...", "action": "scroll to risk heatmap"},
    {"id": "walkthrough", "text": "...", "action": "click through 2-3 sections"},
    {"id": "close",    "text": "...", "action": "return to hero view"}
  ]
}
```

Script rules:
- 60–120 seconds total narration (~150 words/minute — count words to check).
- Structure: hook → problem → walkthrough of 2–4 features → close with the
  value proposition. Tie industry demos back to the Lakebase/Databricks story
  from `references/products.md` positioning.
- Write for the ear: short sentences, no acronym soup, no markdown, spell out
  numbers the way you'd say them ("nine to sixteen million dollars").
- Each segment's `action` describes what's on screen while it plays — one
  screen beat per segment.
- **Show the script to the user for approval before generating audio.** Render
  it as a readable table (segment / narration / on-screen), not raw JSON.

## Stage 2 — Generate voiceover

```bash
python3 <skill_dir>/scripts/tts.py script.json <scratch>/audio
```

Provider order: Fish Audio S2.1 Pro (key in `~/.config/fish-audio/api_key` or
`FISH_AUDIO_API_KEY`; free through July 2026; omit `voice` for the default
voice, or set it to a Fish reference_id), then ElevenLabs
(`ELEVENLABS_API_KEY`), then macOS `say` (voice name, e.g. Samantha).
Don't send confidential text to hosted providers — Fish may use requests for
model improvement.

**Preferred voice:** the user's cloned voice, reference_id
`86ecbcc2b60040c4bd36b89c14c7a2b6` ("Manas demo voice", private model on his
Fish account) — set it as `voice` in `script.json` by default. Only clone a
voice from recordings of the user themself, with their say-so.

To clone a (new) voice from a recording — ~30–60s of clean continuous speech
(use `silencedetect` to find a good stretch, extract with ffmpeg):

```bash
curl -X POST https://api.fish.audio/model \
  -H "Authorization: Bearer $(cat ~/.config/fish-audio/api_key)" \
  -F visibility=private -F type=tts -F train_mode=fast \
  -F "title=<name>" -F "voices=@sample.mp3"
```

The response `_id` is the reference_id; it trains instantly. Always generate
and play (`afplay`) one test line before voicing the full script. Produces one `.m4a`
per segment plus `timeline.json` with measured start/duration per segment —
this timeline drives capture timing and captions. Spot-check a segment or two
by playing them (`afplay`). Product names often mispronounce — fix them with
respellings that still read fine in captions, since the same text feeds both
(e.g. "DAB" → "D-A-B", "HCP" → "H-C-P").

## Stage 3 — Capture the app

1. Start the app per the run command in `references/products.md`. Verify it
   responds (curl the URL) before filming.
2. Copy `scripts/capture.template.mjs` to the scratchpad as `capture.mjs`; set
   `APP_URL` and write one `ACTIONS` entry per segment id, matching each
   segment's `action` description. Browse the app first (or read its routes/
   component code) to get real selectors — prefer `text=` and role selectors.
   Keep motion slow: glide, hover, one tab-change per segment.
3. In the scratchpad: `npm init -y && npm i playwright && npx playwright
   install chromium` (fast; chromium caches under `~/Library/Caches`), then
   `node capture.mjs <scratch>/audio/timeline.json <scratch>/video`.
4. Watch for "ran longer than its slot" warnings — re-time or trim actions and
   re-run. Capture is cheap once the app is up.
5. **Footage QA (required — do not assemble unverified footage).** Extract
   sample frames from the capture and LOOK at them (Read the PNGs):

   ```bash
   for t in 2 <mid> <late>; do ffmpeg -y -loglevel error -ss $t -i capture.webm -frames:v 1 frame-$t.png; done
   ```

   At minimum: the first seconds, one frame inside each key beat, and the
   close. Check for anything the narration doesn't expect: onboarding/tour
   popups, cookie banners, vendor watermarks (e.g. "Edit with …" badges),
   toasts, blank or half-loaded pages, wrong page for the beat. First-visit
   popups are the classic trap — a fresh Playwright profile has empty
   localStorage, so overlays suppressed in your normal browser WILL appear.
   Fix at the source when the app is ours (remove the trigger in the app
   code); hide via injected CSS in capture.mjs only for third-party cosmetic
   chrome. A capture with a defect on screen is a failed take — fix and
   re-film; never ship it because the narration "mostly covers it".

## Stage 4 — Assemble

```bash
bash <skill_dir>/scripts/assemble.sh <scratch>/audio demo-output/<app> [<scratch>/video/capture.webm]
```

Outputs `voiceover.m4a`, `captions.srt`, and (with video) `demo.mp4` (1080p-max
H.264 + AAC, narration muxed over footage, freeze-frame padding if narration
outruns footage). Verify: play back or at least `ffprobe` the result and check
duration ≈ timeline total. To burn captions in:

```bash
ffmpeg -i demo.mp4 -vf "subtitles=captions.srt:force_style='FontSize=18'" -c:a copy demo_captioned.mp4
```

## Stage 5 — Deliver

Tell the user: where the files are, total runtime, which TTS provider was used,
and offer next steps (ElevenLabs upgrade for natural voice, burned captions,
vertical 9:16 crop for social via
`ffmpeg -i demo.mp4 -vf "crop=ih*9/16:ih" demo_vertical.mp4`).
Also save the approved script as `demo-output/<app>/script.md` so it can be
reused or re-voiced later.
