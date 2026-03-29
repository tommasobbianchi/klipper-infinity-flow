#!/usr/bin/env python3
"""
Generate narration audio + Remotion Caption JSON for klipper-infinity-flow promo video.
Output:
  public/narration.mp3  — audio track
  src/captions.json     — Caption[] for @remotion/captions
"""

import asyncio
import json
import os

import edge_tts
from faster_whisper import WhisperModel

VOICE = "en-US-GuyNeural"
RATE = "+15%"  # Speed up to fit 37s video

SCRIPT = (
    "The Infinity Flow S1 Plus is a smart filament reloader. "
    "But on Klipper — it had no native support. Until now. "
    "We built a bridge. "
    "A Moonraker component connects to the FlowQ cloud "
    "and feeds real-time filament state directly into Klipper. "
    "Virtual sensors appear in Fluidd and Mainsail — "
    "no dummy pins, no extra config. "
    "When a slot runs empty, the printer pauses and swaps automatically. "
    "Three steps to set up: clone, get your token, restart. "
    "No hardware modifications needed. "
    "Open source. Free forever. "
    "Find it on GitHub — native-research slash klipper-infinity-flow."
)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_PATH = os.path.join(OUT_DIR, "public", "narration.mp3")
CAPTIONS_PATH = os.path.join(OUT_DIR, "src", "captions.json")


async def generate_audio():
    communicate = edge_tts.Communicate(SCRIPT, VOICE, rate=RATE)
    audio_chunks = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_chunks.append(chunk["data"])
    with open(AUDIO_PATH, "wb") as f:
        for chunk in audio_chunks:
            f.write(chunk)
    print(f"Audio written: {AUDIO_PATH}")


def transcribe_words():
    """Use faster-whisper to get word-level timestamps."""
    print("Loading Whisper model (tiny.en)...")
    model = WhisperModel("tiny.en", device="cpu", compute_type="int8")
    print("Transcribing for word timestamps...")
    segments, _ = model.transcribe(AUDIO_PATH, word_timestamps=True)

    captions = []
    word_index = 0
    for segment in segments:
        if segment.words is None:
            continue
        for word in segment.words:
            text = word.word  # includes leading space for non-first words
            start_ms = int(word.start * 1000)
            end_ms = int(word.end * 1000)
            captions.append({
                "text": text,
                "startMs": start_ms,
                "endMs": end_ms,
                "timestampMs": start_ms,
                "confidence": word.probability if hasattr(word, "probability") else 1.0,
            })
            word_index += 1

    with open(CAPTIONS_PATH, "w") as f:
        json.dump(captions, f, indent=2)

    total_ms = captions[-1]["endMs"] if captions else 0
    print(f"Captions written: {CAPTIONS_PATH} ({len(captions)} words, {total_ms/1000:.1f}s)")
    return captions


if __name__ == "__main__":
    asyncio.run(generate_audio())
    captions = transcribe_words()
    # Print first 5 for verification
    for c in captions[:5]:
        print(f"  {c['startMs']:5d}ms  {repr(c['text'])}")
