"""
extractor.py

Handles Step 1 and Step 2 of the pipeline:
  1. Turning a YouTube URL into a video ID.
  2. Pulling the transcript (text + timestamps) and, optionally,
     screenshots of key moments in the video.
"""

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urlparse, parse_qs

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)


@dataclass
class TranscriptLine:
    text: str
    start: float
    duration: float


@dataclass
class Frame:
    timestamp: float
    path: str


@dataclass
class VideoData:
    video_id: str
    url: str
    transcript: List[TranscriptLine] = field(default_factory=list)
    frames: List[Frame] = field(default_factory=list)


def extract_video_id(url: str) -> str:
    """Pull the 11-character video ID out of any common YouTube URL shape."""
    url = url.strip()

    # youtu.be/<id>
    if "youtu.be" in url:
        path = urlparse(url).path.lstrip("/")
        if path:
            return path.split("?")[0]

    parsed = urlparse(url)

    # youtube.com/watch?v=<id>
    if "v" in parse_qs(parsed.query):
        return parse_qs(parsed.query)["v"][0]

    # youtube.com/embed/<id>, /shorts/<id>, /live/<id>
    match = re.search(r"/(embed|shorts|live)/([A-Za-z0-9_-]{11})", parsed.path)
    if match:
        return match.group(2)

    # Bare 11-character ID passed directly
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url):
        return url

    raise ValueError(f"Could not extract a video ID from: {url}")


def get_transcript(
    video_id: str, languages: Optional[List[str]] = None
) -> List[TranscriptLine]:
    """Fetch the transcript for a video, with start time and duration per line."""
    languages = languages or ["en"]
    try:
        raw = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
    except NoTranscriptFound:
        # Fall back to whatever language is available (e.g. auto-generated)
        raw = YouTubeTranscriptApi.get_transcript(video_id)
    except TranscriptsDisabled as e:
        raise RuntimeError(f"Transcripts are disabled for video {video_id}") from e
    except VideoUnavailable as e:
        raise RuntimeError(f"Video {video_id} is unavailable") from e

    return [
        TranscriptLine(text=item["text"], start=item["start"], duration=item["duration"])
        for item in raw
    ]


def format_transcript(lines: List[TranscriptLine]) -> str:
    """Turn transcript lines into a single readable, timestamped block of text."""
    out = []
    for line in lines:
        mins, secs = divmod(int(line.start), 60)
        hrs, mins = divmod(mins, 60)
        stamp = f"{hrs:02d}:{mins:02d}:{secs:02d}" if hrs else f"{mins:02d}:{secs:02d}"
        out.append(f"[{stamp}] {line.text}")
    return "\n".join(out)


def extract_frames(
    video_id: str,
    interval_seconds: int = 30,
    max_frames: int = 20,
    output_dir: Optional[str] = None,
) -> List[Frame]:
    """
    Download the video (lowest usable quality) with yt-dlp and pull one
    screenshot every `interval_seconds`, up to `max_frames`, using ffmpeg.

    Requires yt-dlp and ffmpeg to be installed and on PATH.
    """
    import cv2  # imported here so transcript-only usage doesn't require opencv

    output_dir = output_dir or tempfile.mkdtemp(prefix="yt_frames_")
    os.makedirs(output_dir, exist_ok=True)

    video_path = os.path.join(output_dir, f"{video_id}.mp4")
    url = f"https://www.youtube.com/watch?v={video_id}"

    download_cmd = [
        "yt-dlp",
        "-f", "worst[ext=mp4][height>=240]/worst",
        "-o", video_path,
        url,
    ]
    result = subprocess.run(download_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed to download video:\n{result.stderr}")

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    duration = total_frames / fps if fps else 0

    frames: List[Frame] = []
    timestamp = 0.0
    while timestamp < duration and len(frames) < max_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(timestamp * fps))
        ok, image = cap.read()
        if ok:
            frame_path = os.path.join(output_dir, f"frame_{int(timestamp)}s.jpg")
            cv2.imwrite(frame_path, image)
            frames.append(Frame(timestamp=timestamp, path=frame_path))
        timestamp += interval_seconds

    cap.release()

    # Clean up the downloaded video, we only needed the frames
    if os.path.exists(video_path):
        os.remove(video_path)

    return frames


def load_video(
    url: str,
    with_frames: bool = False,
    frame_interval: int = 30,
    max_frames: int = 20,
    languages: Optional[List[str]] = None,
) -> VideoData:
    """Run the full extraction step: URL -> video ID -> transcript (+ frames)."""
    video_id = extract_video_id(url)
    transcript = get_transcript(video_id, languages=languages)

    frames: List[Frame] = []
    if with_frames:
        frames = extract_frames(
            video_id, interval_seconds=frame_interval, max_frames=max_frames
        )

    return VideoData(video_id=video_id, url=url, transcript=transcript, frames=frames)
