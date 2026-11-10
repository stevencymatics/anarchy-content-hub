#!/usr/bin/env bash
# Pull library videos via post-media and extract frames.
# picks.txt ("slot render seconds") -> full-res covers/frame-NN.jpg
# else list.txt ("slot render") -> 1 fps small frames in frames/out/NN/
set -u
BASE="https://ukljtxjwaulovdbyuzzj.supabase.co/functions/v1/post-media?r="
mkdir -p /tmp/v
if [ -s frames/picks.txt ]; then
  mkdir -p covers
  while read -r slot rid sec; do
    [ -z "$slot" ] && continue
    f=/tmp/v/$rid.mp4
    [ -s "$f" ] || curl -sSL --retry 3 -o "$f" "$BASE$rid"
    ffmpeg -nostdin -loglevel error -y -ss "$sec" -i "$f" -frames:v 1 -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2" -q:v 2 "covers/frame-$(printf %02d $slot).jpg" || echo "FAIL $slot"
  done < frames/picks.txt
else
  while read -r slot rid; do
    [ -z "$slot" ] && continue
    f=/tmp/v/$rid.mp4
    curl -sSL --retry 3 -o "$f" "$BASE$rid" || { echo "DL FAIL $slot"; continue; }
    d=frames/out/$(printf %02d $slot); mkdir -p "$d"
    ffmpeg -nostdin -loglevel error -y -i "$f" -vf "fps=2,scale=240:-2" -q:v 5 "$d/f%04d.jpg" || echo "FF FAIL $slot"
    echo "$slot $(ls $d | wc -l)"
  done < frames/list.txt
fi
