# YouTube AI Agent

An open-source agent that lets a language model "watch" a YouTube video and answer questions about it, instead of a human sitting through the whole thing.

Give it a URL and a prompt. It pulls the transcript (and optionally screenshots of key moments), packages everything up, and sends it to an LLM for analysis.

## How it works

1. **Video input** — you give it a YouTube URL; it extracts the video ID.
2. **Data extraction** — it downloads the transcript with timestamps, and optionally grabs screenshots at set intervals throughout the video.
3. **AI processing** — it packages the transcript text and any images together with your prompt and sends it to an LLM.
4. **Smart output** — you get a structured answer back in seconds (summary, extracted data, timestamped answers, etc.), optionally saved to a JSON file.

## Setup

```bash
git clone https://github.com/brolookslikeanfish67-hub/have-ai-agents-watch-videos
cd <this-repo>
pip install -r requirements.txt
cp .env.example .env
# then edit .env and add your API key
```

Frame extraction (`--frames`) additionally requires [ffmpeg](https://ffmpeg.org/) and `yt-dlp` to be able to reach YouTube — both are handled by `requirements.txt` / your system package manager (`ffmpeg` isn't a Python package, install it separately, e.g. `brew install ffmpeg` or `apt install ffmpeg`).

## Usage

Basic summary:

```bash
python main.py "https://www.youtube.com/watch?v=VIDEO_ID" "Summarize the main points"
```

Ask a specific question:

```bash
python main.py "https://youtu.be/VIDEO_ID" "Where does the speaker talk about pricing? Give me the timestamp."
```

Include visual frames (for slides, charts, on-screen data):

```bash
python main.py "https://www.youtube.com/watch?v=VIDEO_ID" "Extract every number mentioned in the charts shown" --frames --frame-interval 20
```

Use OpenAI instead of Claude:

```bash
python main.py "https://www.youtube.com/watch?v=VIDEO_ID" "Summarize this" --provider openai --model gpt-4o
```

Save the result to a file:

```bash
python main.py "https://www.youtube.com/watch?v=VIDEO_ID" "Summarize this" --output result.json
```

## CLI options

| Flag | Description | Default |
|---|---|---|
| `url` | YouTube URL or bare video ID | required |
| `prompt` | What you want the AI to do | "Summarize the main points of this video." |
| `--frames` | Also extract and send screenshots | off |
| `--frame-interval` | Seconds between frames | 30 |
| `--max-frames` | Max number of frames to pull | 20 |
| `--provider` | `anthropic` or `openai` | `anthropic` |
| `--model` | Override the default model | provider default |
| `--lang` | Preferred transcript language code | `en` |
| `--output` | Path to save JSON result | none (prints only) |

## Project structure

```
.
├── main.py                # entry point
├── agent/
│   ├── extractor.py       # URL -> video ID -> transcript + frames
│   ├── ai_processor.py    # packages data, calls the LLM
│   └── cli.py             # argument parsing + orchestration
├── requirements.txt
└── .env.example
```

## Using it as a library

```python
from agent.extractor import load_video
from agent.ai_processor import analyze

video = load_video("https://www.youtube.com/watch?v=VIDEO_ID", with_frames=True)
answer = analyze(video.transcript, "Summarize this", frames=video.frames)
print(answer)
```

## Notes

- Only videos with an available transcript (manual or auto-generated) can be processed.
- Frame extraction downloads a low-resolution copy of the video temporarily just to pull screenshots, then deletes it.
- Respect YouTube's Terms of Service and the copyright of video creators when using this tool.

## License

MIT — see [LICENSE](LICENSE).
