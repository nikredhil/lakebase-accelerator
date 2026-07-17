---
name: video-script
description: Write an engaging, story-driven product video script in Manuka's opinionated practitioner voice, sized to a duration the user specifies in minutes — hook-first structure backed by engagement data (statement hooks with numbers, no question openers), paced with retention re-hooks, positioned as Manuka thought-leadership (why work with us, what makes us different, our take on Databricks releases), output as a readable script plus demo-studio-compatible script.json. Use when the user asks for a video script, product video script, "N-minute script", promo/launch/explainer script, or narration copy for a product — and does NOT (yet) want the full video produced.
---

# Video Script Studio

Write a product video script that fits a target duration and holds attention
the whole way through. Script only — no audio, no capture. If the user then
wants it produced, hand the approved `script.json` to the `demo-studio` skill
(the format is compatible). If the user wants the finished video start-to-
finish, the `demo` skill chains this skill with demo-studio — use that
instead of running this one standalone.

## Inputs

1. **Duration in minutes** — required. If the user didn't give one, ask; do
   not guess. Everything below scales from it.
2. **The product** — an app in this repo (read its README + main entry file;
   `demo-studio/references/products.md` has the inventory) or a product the
   user describes. Ground every claim in real features — never invent
   capabilities, metrics, or customer results. If a beat needs a number the
   product doesn't have, ask the user for a real one or cut the beat.
3. **Audience and platform** if stated (LinkedIn, YouTube, sales call,
   keynote) — affects tone and CTA, not structure.

## Step 1 — Size the script

Narration pace is ~150 words per minute. **Word budget = minutes × 150,
tolerance ±10%.** Count the words and state the count when presenting the
script; a beautiful script that runs long is a failed script.

Pick the beat structure by duration:

| Duration | Beats |
|---|---|
| ≤ 1 min | HOOK → problem → one payoff moment → close |
| 1–2 min | HOOK → problem + stakes → 2–3 feature story beats → proof number → close |
| 2–4 min | Cold-open story → problem + stakes → narrative walkthrough (3–5 beats, each an open loop the next beat pays off) → proof → reframe/objection kill → close |
| 4+ min | Acts with chapter re-hooks: Act I tension, Act II the journey through the product, Act III payoff + vision → close. Every act opens with its own mini-hook. |

Budget roughly 10% of words to the hook+setup, 65% to the middle, 25% to
proof+close. Longer video ≠ longer sentences — it means more beats.

## Step 2 — Write the hook (the whole game)

The first line decides whether anyone watches line two. Rules, from the
engagement data in `references/hooks.md` (read it before writing):

- **Statement, not a question.** Question openers underperform by 34%.
- **Put a specific number in it.** Number-led openers beat vague ones 35 vs 26.
- **Short.** 1–5 words is the sweet spot; never past 10. "Nine million
  dollars. Gone in one shift." beats "Have you ever wondered how much
  downtime costs your plant?"
- A question is allowed only if it carries a sharp, specific tension the
  video immediately pays off — never "Ever struggled with X?"

Write 3 candidate hooks, pick the strongest, keep the other two in the
deliverable as alternates.

## Step 3 — Write the body, story-first and in Manuka's voice

**Read `references/manuka-voice.md` before writing a single beat.** Every
script is Manuka thought-leadership first, product demo second: it must land
at least one of the three angles (why work with us, what makes us different,
our take on Unity Catalog / AI Gateway / AI Observability / CDP / Omnigent
and other Databricks releases), sound like a practitioner rather than a
brand account, and close with an invitation to engage — never a hard-sell
CTA. Opinionated beats are proposed, flagged, and approved by the user; never
bluff a take on a release you don't know.

**Never feature-tour.** "Here we have the dashboard, and over here…" is
banned. Instead, follow one persona through one bad day (or one crisis, one
decision) and let the product enter as the turn in the story. Features appear
because the story needs them, in the order the persona would reach for them.

Engagement mechanics to build in:

- **Re-hook every 30–45 seconds.** Retention decays; reset it with a new open
  loop, a number, or a turn ("That fixed the outage. It did not fix the
  cause."). For scripts over 2 minutes this is what separates watched from
  abandoned.
- **Open loops.** End beats on tension the next beat resolves.
- **Numbers as proof.** Concrete beats vague everywhere, not just the hook —
  "forty seconds, not four hours", "three clicks", "one screen".
- **Contrast.** Before/after, old-way/new-way, cost-of-inaction vs payoff.
- **One CTA.** Close with a single invitation to engage (per the voice
  guide), not a menu and not a hard sell.

Write for the ear: short sentences, active voice, no acronym soup, no
markdown in narration text, spell numbers the way you'd say them ("nine to
sixteen million dollars"). Read it aloud mentally — if you'd stumble, rewrite.

## Step 4 — Deliver

Produce two artifacts:

1. **A readable script** — markdown table: `beat | time | narration |
   on-screen`. Time column is cumulative (e.g. `0:00–0:12`), computed from
   word counts at 150 wpm. Below the table: total word count, computed
   runtime vs. target, and the two alternate hooks.
2. **`script.json`** in the demo-studio format (`app`, `voice`, `segments`
   with `id`/`text`/`action`) so it can be voiced and filmed without rework.
   Default `voice` to the user's cloned Fish reference
   `86ecbcc2b60040c4bd36b89c14c7a2b6`.

Show the readable script to the user for approval. Offer next steps: revise a
beat, re-cut to a different duration, or run `demo-studio` to produce the
video.
