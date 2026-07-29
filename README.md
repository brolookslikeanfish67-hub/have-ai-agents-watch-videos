# AI YouTube Agent 

An open-source AI agent that allows language models to "watch," understand, and analyze YouTube videos automatically. 

Instead of a human sitting through a 20-minute video, this agent processes the video data in seconds and passes it to an AI (like GPT or Claude) to answer questions, write summaries, or extract data.

---

##  How It Works (The Core Pipeline)

The agent operates in four simple steps to convert a video into AI-readable data:

### 1. Video Input 
* You give the agent a standard YouTube URL.
* The agent extracts the unique Video ID to locate the source files.

### 2. Data Extraction 
The agent acts as the "eyes and ears" for the AI by grabbing two main types of data:
* **The Transcript:** It downloads the text of what is being said in the video, along with precise timestamps.
* **Visual Frames (Optional):** It takes screenshots of key moments in the video (like slides, charts, or scene changes) for visual AI models to look at.

### 3. AI Processing 
* The agent packages the transcript text and images together.
* It sends this organized package to a Large Language Model (LLM) along with your specific prompt (e.g., *"Summarize the main points"* or *"Find where the speaker talks about pricing"*).

### 4. Smart Output 
* The AI reads the data and returns a structured response to you in seconds.

---

## 🛠️ System Architecture

