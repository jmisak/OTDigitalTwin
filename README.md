---
title: OTDigitalTwin2.0
emoji: 🏢
colorFrom: yellow
colorTo: indigo
sdk: gradio
sdk_version: 5.49.1
app_file: app.py
pinned: false
---

# OT Mental Health Training Simulator

An interactive training simulator for Occupational Therapy students to practice therapeutic communication with realistic client personas.

## 🚀 Now with Local AI Models!

This version runs completely locally using small, fast transformer models - **no API keys required!**

### Features

- **Local AI Generation**: Uses optimized transformer models (350M-2.7B parameters)
- **Fast Responses**: 2-5 seconds per response on CPU, under 2 seconds on GPU
- **Privacy First**: All processing happens locally, no data sent to external APIs
- **Multiple Personas**: Jack, Maya, Robert, and Angela with unique backgrounds
- **Dynamic Emotional States**: Track anxiety, trust, and openness over time
- **Teaching Feedback**: Get educational insights on your therapeutic approach
- **Session Transcripts**: Download complete session records

### Quick Start

1. The app automatically loads on HF Spaces
2. Select a client persona (Jack, Maya, Robert, or Angela)
3. Choose a contextual scenario
4. Start the conversation as if you were an OT practitioner
5. Observe emotional state changes and receive teaching feedback

### Response Modes

- **AI Mode** (Recommended): Dynamic responses using local transformer models
- **Templates Mode**: Fast pre-written responses for lower resource environments

### Requirements

See `requirements.txt` for full dependencies. Key packages:
- `transformers` - For local AI model inference
- `torch` - Deep learning framework
- `gradio` - Web interface
- `accelerate` - Optimized model loading

### Setup & Configuration

For detailed setup instructions, see [SETUP_LOCAL_MODEL.md](SETUP_LOCAL_MODEL.md)

### Performance

**First Load**: 30-60 seconds (model download and caching)
**Subsequent Loads**: Instant (models are cached)
**Response Time**: 2-5 seconds per message

### Models Used

The system tries these models in order (first successful load is used):
1. **microsoft/phi-2** (2.7B) - Best quality
2. **TinyLlama/TinyLlama-1.1B-Chat-v1.0** (1.1B) - Good balance
3. **facebook/opt-350m** (350M) - Fast fallback
4. **distilgpt2** (82M) - Minimal resource usage

### Credits

Developed for Occupational Therapy education at NYIT.

Check out the configuration reference at https://huggingface.co/docs/hub/spaces-config-reference
