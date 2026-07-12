#!/usr/bin/env python3
"""Generate per-segment voiceover audio from a script.json.

Usage: python3 tts.py <script.json> <out_dir> [--voice VOICE]

script.json format:
{
  "app": "app-name",
  "voice": "Samantha",            # optional; mac `say` voice or ElevenLabs voice id
  "segments": [
    {"id": "intro", "text": "Welcome to ...", "action": "show landing page"},
    ...
  ]
}

Provider selection (first match wins):
  - Fish Audio key present  -> Fish Audio S2.1 Pro free API (voice = optional
    reference_id; omit for the default voice). Key comes from FISH_AUDIO_API_KEY
    or ~/.config/fish-audio/api_key. Free through end of July 2026, no SLA;
    requests may be used by Fish Audio for model improvement.
  - ELEVENLABS_API_KEY set  -> ElevenLabs (voice = voice id, default Rachel)
  - otherwise               -> macOS `say` (voice = say voice, default Samantha)

Outputs: <out_dir>/<id>.m4a per segment, plus <out_dir>/timeline.json with
measured durations (seconds) so the capture script can time on-screen actions.
"""
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

ELEVEN_DEFAULT_VOICE = "21m00Tcm4TlvDq8ikWAM"  # Rachel
SAY_DEFAULT_VOICE = "Samantha"
GAP_SECONDS = 0.6  # breathing room inserted between segments at assembly time
FISH_KEY_FILE = Path.home() / ".config" / "fish-audio" / "api_key"


def fish_api_key() -> str | None:
    key = os.environ.get("FISH_AUDIO_API_KEY")
    if not key and FISH_KEY_FILE.exists():
        key = FISH_KEY_FILE.read_text().strip()
    return key or None


def duration_of(path: Path) -> float:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    )
    return float(out.strip())


def tts_say(text: str, voice: str, out: Path) -> None:
    aiff = out.with_suffix(".aiff")
    subprocess.run(["say", "-v", voice, "-o", str(aiff), text], check=True)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(aiff),
         "-c:a", "aac", "-b:a", "160k", str(out)],
        check=True,
    )
    aiff.unlink()


def tts_fish(text: str, voice: str | None, out: Path, api_key: str) -> None:
    body = {"text": text, "format": "mp3"}
    if voice:
        body["reference_id"] = voice
    mp3 = out.with_suffix(".mp3")
    # curl instead of urllib: python.org macOS builds often lack CA certs.
    # Config via stdin keeps the key out of the process list.
    config = (
        f'url = "https://api.fish.audio/v1/tts"\n'
        f'header = "Authorization: Bearer {api_key}"\n'
        f'header = "Content-Type: application/json"\n'
        f'header = "model: s2.1-pro-free"\n'
    )
    result = subprocess.run(
        ["curl", "-sS", "--fail-with-body", "--config", "-",
         "--data-binary", json.dumps(body), "-o", str(mp3)],
        input=config.encode(), capture_output=True,
    )
    if result.returncode != 0:
        err = mp3.read_text(errors="replace") if mp3.exists() else ""
        raise RuntimeError(
            f"Fish Audio request failed: {result.stderr.decode().strip()} {err}".strip()
        )
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3),
         "-c:a", "aac", "-b:a", "160k", str(out)],
        check=True,
    )
    mp3.unlink()


def tts_elevenlabs(text: str, voice: str, out: Path, api_key: str) -> None:
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
        data=json.dumps({
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }).encode(),
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
    )
    mp3 = out.with_suffix(".mp3")
    with urllib.request.urlopen(req) as resp:
        mp3.write_bytes(resp.read())
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3),
         "-c:a", "aac", "-b:a", "160k", str(out)],
        check=True,
    )
    mp3.unlink()


def main() -> None:
    script_path = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    script = json.loads(script_path.read_text())

    voice_override = None
    if "--voice" in sys.argv:
        voice_override = sys.argv[sys.argv.index("--voice") + 1]

    fish_key = fish_api_key()
    eleven_key = os.environ.get("ELEVENLABS_API_KEY")
    if fish_key:
        provider, api_key = "fish", fish_key
        voice = voice_override or script.get("voice")  # None -> default voice
    elif eleven_key:
        provider, api_key = "elevenlabs", eleven_key
        voice = voice_override or script.get("voice") or ELEVEN_DEFAULT_VOICE
    else:
        provider, api_key = "say", None
        voice = voice_override or script.get("voice") or SAY_DEFAULT_VOICE
    print(f"provider={provider} voice={voice or '(default)'}")

    timeline = {"provider": provider, "voice": voice, "gap": GAP_SECONDS,
                "segments": []}
    t = 0.0
    for seg in script["segments"]:
        out = out_dir / f"{seg['id']}.m4a"
        if provider == "fish":
            tts_fish(seg["text"], voice, out, api_key)
        elif provider == "elevenlabs":
            tts_elevenlabs(seg["text"], voice, out, api_key)
        else:
            tts_say(seg["text"], voice, out)
        dur = duration_of(out)
        timeline["segments"].append({
            "id": seg["id"], "text": seg["text"],
            "action": seg.get("action", ""),
            "start": round(t, 2), "duration": round(dur, 2),
        })
        print(f"  {seg['id']}: {dur:.2f}s (starts at {t:.2f}s)")
        t += dur + GAP_SECONDS

    timeline["total"] = round(t - GAP_SECONDS, 2)
    (out_dir / "timeline.json").write_text(json.dumps(timeline, indent=2))
    print(f"total narration: {timeline['total']:.2f}s -> {out_dir}/timeline.json")


if __name__ == "__main__":
    main()
