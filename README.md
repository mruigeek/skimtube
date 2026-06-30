# YouTube Channel Summarizer

A local-first Python automation project that monitors specific YouTube channels for new videos within the last 24 hours, fetches transcripts, and generates concise summaries locally using Gemma 3 4B via Ollama.

## Features
- **Local-first**: Uses local Ollama instance to generate summaries, keeping your data private.
- **Deduplication**: Remembers processed videos in a `state.json` file.
- **Transcript Fetching**: Utilizes `youtube-transcript-api` to pull available captions. 
  - *Note:* `youtube-transcript-api` may fail (e.g. "no element found"). In this case, the script falls back to downloading subtitles using `yt-dlp` to improve reliability. Audio transcription is intentionally not implemented yet.
- **Markdown Outputs**: Saves clean, formatted summaries for each video.
- **Cron-friendly**: Designed to be run periodically via a scheduler.

## Setup Instructions

### 1. Prerequisites
- **Python 3.8+**
- **Ollama**: Download and install Ollama from [ollama.com](https://ollama.com).

### 2. Install Ollama and Pull Model
Once Ollama is installed, run the following in your terminal to pull the Gemma 3 4B model:
```bash
ollama run gemma3:4b
```
*(You can exit the interactive prompt by pressing Ctrl+D once the model is downloaded).*

Ensure the Ollama application is running in the background. It typically serves the API on `http://localhost:11434`.

### 3. Install Python Dependencies
Create a virtual environment (optional but recommended) and install the dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Configuration
Edit the `channels.json` file to include the YouTube channels you wish to monitor:
```json
{
  "channels": [
    {
      "name": "Channel Name",
      "channel_id": "UCxxxxxxx"
    }
  ]
}
```

### 5. Running the Script
Run the script manually:
```bash
python main.py
```
You will see output in the console, and summaries will be saved as Markdown files in the `summaries/` directory.

## Cron Setup Example
To run the script safely every hour, you can add it to your crontab.
Open your crontab by typing:
```bash
crontab -e
```
Add the following line (make sure to replace `/path/to/project` with the actual absolute path to your project, and the python path with the absolute path to your virtual environment's python executable):

```bash
0 * * * * cd /path/to/project && /path/to/project/venv/bin/python main.py >> output.log 2>&1
```

## Troubleshooting

- **Connection Error to Ollama:** Ensure Ollama is running and accessible at `http://localhost:11434`.
- **"Model not found" Error:** Make sure you have pulled the correct model: `ollama pull gemma3:4b`.
- **Transcript not found:** Some videos do not have captions enabled or are restricted. The script will simply skip summarization for these.



few channels 

