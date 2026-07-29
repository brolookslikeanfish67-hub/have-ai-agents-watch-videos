"""
cli.py

Command-line entry point that wires the four pipeline steps together:
URL -> video ID -> transcript (+ frames) -> LLM -> printed / saved output.
"""

import argparse
import json
import sys
from datetime import datetime

from dotenv import load_dotenv

from .extractor import load_video
from .ai_processor import analyze


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Give an LLM the ability to 'watch' a YouTube video and answer questions about it."
    )
    parser.add_argument("url", help="YouTube video URL (or bare video ID)")
    parser.add_argument(
        "prompt",
        nargs="?",
        default="Summarize the main points of this video.",
        help="What you want the AI to do with the video (default: summarize it)",
    )
    parser.add_argument(
        "--frames",
        action="store_true",
        help="Also extract screenshots and send them to a vision-capable model",
    )
    parser.add_argument(
        "--frame-interval",
        type=int,
        default=30,
        help="Seconds between extracted frames (default: 30)",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=20,
        help="Maximum number of frames to extract (default: 20)",
    )
    parser.add_argument(
        "--provider",
        choices=["anthropic", "openai"],
        default="anthropic",
        help="Which LLM provider to use (default: anthropic)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override the default model for the chosen provider",
    )
    parser.add_argument(
        "--lang",
        default="en",
        help="Preferred transcript language code (default: en)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to save the result as JSON (optional)",
    )
    return parser


def main(argv=None) -> int:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)

    print(f"[1/4] Reading URL: {args.url}")
    print(f"[2/4] Fetching transcript" + (" and frames..." if args.frames else "..."))

    try:
        video = load_video(
            args.url,
            with_frames=args.frames,
            frame_interval=args.frame_interval,
            max_frames=args.max_frames,
            languages=[args.lang],
        )
    except Exception as e:
        print(f"Error extracting video data: {e}", file=sys.stderr)
        return 1

    print(f"       -> video ID: {video.video_id}")
    print(f"       -> transcript lines: {len(video.transcript)}")
    if args.frames:
        print(f"       -> frames extracted: {len(video.frames)}")

    print(f"[3/4] Sending to {args.provider} ({args.model or 'default model'})...")
    try:
        result = analyze(
            video.transcript,
            args.prompt,
            frames=video.frames,
            provider=args.provider,
            model=args.model,
        )
    except Exception as e:
        print(f"Error calling AI provider: {e}", file=sys.stderr)
        return 1

    print("[4/4] Done.\n")
    print("=" * 60)
    print(result)
    print("=" * 60)

    if args.output:
        payload = {
            "video_id": video.video_id,
            "url": video.url,
            "prompt": args.prompt,
            "provider": args.provider,
            "model": args.model,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "response": result,
        }
        with open(args.output, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"\nSaved result to {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
