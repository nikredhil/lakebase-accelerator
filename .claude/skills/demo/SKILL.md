---
name: demo
description: End-to-end product demo video pipeline — chains the video-script skill (duration-sized, Manuka-voice, engagement-data script) into the demo-studio skill (voiceover, Playwright capture, assembly) to go from "make me an N-minute demo of X" to a finished demo.mp4. Use when the user wants a complete narrated demo video produced start-to-finish. If they only want the script, use video-script; if they already have an approved script and only want it produced, use demo-studio.
---

# Demo Pipeline

Produce a finished, narrated demo video by chaining two skills in sequence.
This skill adds no craft of its own — it sequences the other two and owns the
handoff. Read each phase's SKILL.md and follow it fully; do not paraphrase
from memory.

## Inputs

Same as `video-script`: **duration in minutes** (required — ask, don't
guess), the **app** (ask if not named), audience/platform if stated. Confirm
up front that the app can be captured (see the credential notes in
`demo-studio/references/products.md`) — if it can't run locally, tell the
user and offer demo-studio's audio-only explainer mode before writing a
script sized for footage.

## Phase 0 (optional) — Fresh hook research

If the user wants the hook grounded in current data for their niche (or asks
"what's working right now"), run the `linkedin-post-research` skill on the
video's topic first and feed its pattern report into Phase 1 alongside
`video-script/references/hooks.md`. Skip by default — the bundled hook data
is sufficient for most scripts.

## Phase 1 — Script (video-script skill)

Read `.claude/skills/video-script/SKILL.md` and execute all of it: duration
sizing, the hook rules in its `references/hooks.md`, the Manuka voice and
positioning rules in its `references/manuka-voice.md`, and both deliverables
(readable script table + `script.json`).

**Hard gate: the user must approve the script — including any flagged
Manuka opinion beats — before any audio is generated.** Revisions loop here;
audio and capture are downstream of an approved script only.

## Phase 2 — Produce (demo-studio skill)

Read `.claude/skills/demo-studio/SKILL.md` and execute **stages 2–5, skipping
stage 1** — the approved `script.json` from Phase 1 replaces it (the formats
are identical, and the voice field already defaults to the user's cloned Fish
reference). Stage 0's product research also already happened in Phase 1;
reuse it, but still verify the run command and that the app responds before
filming.

Handoff mechanics:
- Put `script.json` in the session scratchpad where demo-studio's `tts.py`
  expects it.
- Each segment's `action` from Phase 1 becomes the capture plan — write one
  `ACTIONS` entry per segment id.
- Save the approved script as `demo-output/<app>/script.md` (demo-studio
  stage 5 requires this anyway).

**Hard gate: footage QA before assembly.** Demo-studio stage 3's frame check
is mandatory here — extract frames from every capture (open, each key beat,
close), Read them, and confirm the screen matches each beat's `action` with
no popups, watermarks, or half-loaded pages. Assemble only verified footage,
and spot-check frames of the final mp4 too (the lead trim can shift beats).

Rework rules — fix at the cheapest stage that owns the problem:
- A segment's `action` isn't filmable (selector doesn't exist, state
  unreachable) → revise that segment's action and re-capture. Narration text
  unchanged means no re-voicing.
- Narration itself must change (mispronunciation respellings excepted —
  demo-studio stage 2 handles those) → that is a script change: get the
  user's sign-off on the new wording, re-voice only the changed segments,
  then re-capture ones whose timing shifted.

## Deliver

Per demo-studio stage 5: file locations, total runtime, TTS provider used,
and next-step offers (burned captions, vertical crop). Confirm the final
runtime is within ±10% of the duration the user asked for — that promise was
made in Phase 1 and the video has to keep it.
