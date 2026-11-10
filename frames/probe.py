"""Probe library videos for their CTA: word timestamps (faster-whisper) + end-card detection (blur) + tail thumbs.
Input frames/probe.txt: "<slug> <render_id>" per line. Output frames/out/probe/<slug>/{probe.json, t*.jpg}."""
import json, os, subprocess, sys
import numpy as np
from PIL import Image
from faster_whisper import WhisperModel

BASE = "https://ukljtxjwaulovdbyuzzj.supabase.co/functions/v1/post-media?r="
model = WhisperModel("small.en", device="cpu", compute_type="int8")
os.makedirs("/tmp/v", exist_ok=True)

def sh(*a):
    return subprocess.run(a, check=True, capture_output=True, text=True).stdout

for line in open("frames/probe.txt"):
    if not line.strip():
        continue
    slug, rid = line.split()[:2]
    out = f"frames/out/probe/{slug}"; os.makedirs(out, exist_ok=True)
    f = f"/tmp/v/{rid}.mp4"
    try:
        if not os.path.exists(f):
            sh("curl", "-sSL", "--retry", "3", "-o", f, BASE + rid)
        dur = float(sh("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f).strip())
        wav = f"/tmp/v/{rid}.wav"
        sh("ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", f, "-ac", "1", "-ar", "16000", wav)
        segs, _ = model.transcribe(wav, word_timestamps=True, vad_filter=False, beam_size=5)
        words = [{"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)} for s in segs for w in s.words]
        # sharpness per frame over the last 10 s (10 fps, 270 px wide, grayscale)
        t0 = max(0.0, dur - 10.0)
        tmpd = f"/tmp/v/{rid}_sh"; os.makedirs(tmpd, exist_ok=True)
        sh("ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-ss", f"{t0:.2f}", "-i", f, "-vf", "fps=10,scale=270:-2,format=gray", f"{tmpd}/s%04d.png")
        sharp = []
        for i, p in enumerate(sorted(os.listdir(tmpd))):
            a = np.asarray(Image.open(f"{tmpd}/{p}"), dtype=np.float32)
            lap = a[1:-1, 1:-1] * 4 - a[:-2, 1:-1] - a[2:, 1:-1] - a[1:-1, :-2] - a[1:-1, 2:]
            sharp.append([round(t0 + i / 10, 2), round(float(lap.var()), 1)])
        # tail thumbs, 2 fps, last 14 s
        t1 = max(0.0, dur - 14.0)
        sh("ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-ss", f"{t1:.2f}", "-i", f, "-vf", "fps=2,scale=200:-2", "-q:v", "6", f"{out}/t%03d.jpg")
        json.dump({"slug": slug, "render": rid, "dur": dur, "tail_t0": t1, "words": words, "sharp": sharp}, open(f"{out}/probe.json", "w"))
        print(slug, dur, len(words))
    except Exception as e:  # keep going
        print("FAIL", slug, e, file=sys.stderr)
        json.dump({"slug": slug, "render": rid, "error": str(e)}, open(f"{out}/probe.json", "w"))
