#!/usr/bin/env bash
# Assemble final demo: concat narration segments (with gaps), mux over video,
# and emit an SRT caption sidecar.
#
# Usage: assemble.sh <audio_dir> <out_dir> [video.webm]
#   audio_dir  directory containing <id>.m4a segments + timeline.json (from tts.py)
#   out_dir    where voiceover.m4a, captions.srt, and demo.mp4 land
#   video.webm optional Playwright screen recording; if omitted, produces
#              audio-only voiceover.m4a + captions (explainer mode)
#
# If a lead.json ({"leadSeconds": N}) sits next to the video, that many seconds
# of pre-narration footage (page load/settle) are trimmed so beats align.
set -euo pipefail

AUDIO_DIR="$1"; OUT_DIR="$2"; VIDEO="${3:-}"
TIMELINE="$AUDIO_DIR/timeline.json"
mkdir -p "$OUT_DIR"

python3 - "$TIMELINE" "$AUDIO_DIR" "$OUT_DIR" <<'PY'
import json, os, subprocess, sys
# ffmpeg concat resolves relative paths against the list file's dir — use absolute
timeline, audio_dir, out_dir = (os.path.abspath(p) for p in sys.argv[1:4])
tl = json.load(open(timeline))
gap = tl["gap"]

# gap silence MUST match the segments' sample rate/channels or the concat
# demuxer emits broken timestamps and the output duration is garbage
first = f"{audio_dir}/{tl['segments'][0]['id']}.m4a"
probe = subprocess.check_output(["ffprobe","-v","error","-select_streams","a",
    "-show_entries","stream=sample_rate,channels","-of","csv=p=0", first]).decode().strip()
rate, ch = probe.split(",")
layout = {"1": "mono", "2": "stereo"}.get(ch, "mono")
subprocess.run(["ffmpeg","-y","-loglevel","error","-f","lavfi",
    "-i",f"anullsrc=r={rate}:cl={layout}","-t",str(gap),
    "-c:a","aac","-b:a","160k",f"{out_dir}/_gap.m4a"], check=True)

lines = []
for i, seg in enumerate(tl["segments"]):
    if i: lines.append(f"file '{out_dir}/_gap.m4a'")
    lines.append(f"file '{audio_dir}/{seg['id']}.m4a'")
open(f"{out_dir}/_concat.txt","w").write("\n".join(lines))

subprocess.run(["ffmpeg","-y","-loglevel","error","-f","concat","-safe","0",
    "-i",f"{out_dir}/_concat.txt","-c:a","aac","-b:a","160k",
    f"{out_dir}/voiceover.m4a"], check=True)

# sanity: concat output must be within 2s of the timeline total
dur = float(subprocess.check_output(["ffprobe","-v","error","-show_entries",
    "format=duration","-of","default=noprint_wrappers=1:nokey=1",
    f"{out_dir}/voiceover.m4a"]).strip())
if abs(dur - tl["total"]) > 2:
    sys.exit(f"voiceover.m4a is {dur:.1f}s but timeline says {tl['total']:.1f}s — concat produced bad timestamps")

# SRT captions from timeline
def ts(t):
    h=int(t//3600); m=int(t%3600//60); s=int(t%60); ms=int((t%1)*1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"
srt=[]
for i, seg in enumerate(tl["segments"], 1):
    srt.append(f"{i}\n{ts(seg['start'])} --> {ts(seg['start']+seg['duration'])}\n{seg['text']}\n")
open(f"{out_dir}/captions.srt","w").write("\n".join(srt))
print(f"wrote voiceover.m4a ({dur:.1f}s) + captions.srt")
PY

if [[ -n "$VIDEO" ]]; then
  # Playwright webms carry unreliable PTS: re-timestamp as constant 25 fps
  # (Playwright's actual capture rate), trim the pre-narration lead, freeze the
  # last frame as padding, and hard-cap at narration length + a short tail.
  LEAD=0
  LEAD_JSON="$(dirname "$VIDEO")/lead.json"
  [[ -f "$LEAD_JSON" ]] && LEAD=$(python3 -c "import json;print(json.load(open('$LEAD_JSON'))['leadSeconds'])")
  AUDIO_LEN=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$OUT_DIR/voiceover.m4a")
  OUT_LEN=$(python3 -c "print(round($AUDIO_LEN + 1.5, 2))")
  ffmpeg -y -loglevel error -i "$VIDEO" -i "$OUT_DIR/voiceover.m4a" \
    -filter_complex "[0:v]setpts=N/25/TB,trim=start=${LEAD},setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration=10,scale='min(1920,iw)':-2[v]" \
    -map "[v]" -map 1:a -r 25 -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p \
    -c:a aac -t "$OUT_LEN" "$OUT_DIR/demo.mp4"
  echo "wrote $OUT_DIR/demo.mp4 (${OUT_LEN}s, lead trim ${LEAD}s)"
fi

rm -f "$OUT_DIR/_gap.m4a" "$OUT_DIR/_concat.txt"
