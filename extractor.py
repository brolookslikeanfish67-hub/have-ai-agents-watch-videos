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
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse, parse_qs

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)


@dataclass(frozen=True)
class TranscriptLine:
    text: str
    start: float
    duration: float


@dataclass(frozen=True)
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

    # Bare 11-character ID passed directly
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url):
        return url

    parsed = urlparse(url)
    hostname = parsed.hostname or ""

    # handle youtu.be/<id>
    if "youtu.be" in hostname:
        path = parsed.path.lstrip("/")
        return path.split("?")[0] if path else url

    # handle youtube.com/watch?v=<id> or /watch?vi=<id>
    query_params = parse_qs(parsed.query)
    for key in ("v", "vi"):
        if key in query_params:
            return query_params[key][0]

    # handle youtube.com/embed/<id>, /shorts/<id>, /live/<id>, /v/<id>
    match = re.search(r"/(embed|shorts|live|v)/([A-Za-z0-9_-]{11})", parsed.path)
    if match:
        return match.group(2)

    raise ValueError(f"Could not extract a video ID from: {url}")


def get_transcript(
    video_id: str, languages: Optional[List[str]] = None
) -> List[TranscriptLine]:
    """Fetch the transcript for a video, with start time and duration per line."""
    languages = languages or ["en"]
    try:
        raw = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
    except NoTranscriptFound:
        try:
            # Fall back to whatever language is available (e.g. auto-generated)
            raw = YouTubeTranscriptApi.get_transcript(video_id)
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve fallback transcript for video {video_id}") from e
    except TranscriptsDisabled as e:
        raise RuntimeError(f"Transcripts are disabled for video {video_id}") from e
    except VideoUnavailable as e:
        raise RuntimeError(f"Video {video_id} is unavailable") from e
    except Exception as e:
        raise RuntimeError(f"An unexpected error occurred while fetching transcript: {str(e)}") from e

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
    Download the video (lowest quality) with yt-dlp and pull one
    screenshot every `interval_seconds`, up to `max_frames`, using ffmpeg natively.

    Requires yt-dlp and ffmpeg to be installed on system PATH.
    """
    output_path = Path(output_dir or tempfile.mkdtemp(prefix="yt_frames_"))
    output_path.mkdir(parents=True, exist_ok=True)

    video_file = output_path / f"{video_id}.mp4"
    url = f"https://www.youtube.com/watch?v={video_id}"

    # Step 1: Download low quality video using yt-dlp
    download_cmd = [
        "yt-dlp",
        "-f", "worst[ext=mp4][height>=240]/worst",
        "-o", str(video_file),
        url,
    ]
    result = subprocess.run(download_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed to download video:\n{result.stderr}")

    frames: List[Frame] = []
    
    try:
        # Step 2: Get absolute length duration using ffprobe
        ffprobe_cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(video_file)
        ]
        duration_res = subprocess.run(ffprobe_cmd, capture_output=True, text=True)
        duration = float(duration_res.stdout.strip()) if duration_res.returncode == 0 else 0.0

        # Step 3: Fast and precise seeking frame extraction using native ffmpeg
        timestamp = 0.0
        while timestamp < duration and len(frames) < max_frames:
            frame_file = output_path / f"frame_{int(timestamp)}s.jpg"
            
            ffmpeg_cmd = [
                "ffmpeg", "-y", 
                "-ss", str(timestamp),      # Seek before input is vastly faster
                "-i", str(video_file), 
                "-vframes", "1",            # Extract exactly 1 frame
                "-q:v", "2",                # High quality JPEG output
                str(frame_file)
            ]
            
            # Run silently
            subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            if frame_file.exists():
                frames.append(Frame(timestamp=timestamp, path=str(frame_file)))
                
            timestamp += interval_seconds

    finally:
        # Step 4: Clean up downloaded video file reliably even if extraction crashes
        if video_file.exists():
            video_file.unlink()

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
