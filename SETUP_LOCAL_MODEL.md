# Local Model Setup Guide

This guide explains how to run the OT Mental Health Simulator with local AI models on Hugging Face Spaces.

## What Changed

The application now uses **small, fast local models** instead of external APIs:

- **Before**: Used Claude API or large 7B parameter models
- **After**: Uses optimized models (350M - 2.7B parameters) that run efficiently on HF Spaces

## Models Used (in priority order)

1. **microsoft/phi-2** (2.7B) - Best quality, needs ~6GB RAM
2. **TinyLlama/TinyLlama-1.1B-Chat-v1.0** (1.1B) - Good balance, ~3GB RAM
3. **facebook/opt-350m** (350M) - Fast fallback, ~1.5GB RAM
4. **distilgpt2** (82M) - Extremely fast, minimal RAM

The system automatically tries models in order and uses the first one that loads successfully.

## Installation

### For HF Spaces

1. Upload your files to HF Spaces
2. Ensure `requirements.txt` is in the root directory
3. HF Spaces will automatically install dependencies
4. The first run will download the model (this can take a few minutes)
5. Subsequent runs will be much faster as models are cached

### For Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
```

## Performance Optimizations

The code includes several optimizations for HF Spaces:

1. **Smaller Models**: Uses models under 3B parameters for faster inference
2. **Inference Mode**: Uses `torch.inference_mode()` for 20-30% speedup
3. **Reduced Token Count**: Generates up to 150 tokens (vs 300) for faster responses
4. **Better Sampling**: Uses top-k and repetition penalty for better quality
5. **Memory Efficiency**: Uses `low_cpu_mem_usage=True` during model loading
6. **Auto Device Selection**: Automatically uses GPU if available, CPU otherwise

## Response Modes

Users can choose between two modes in the UI:

- **AI Mode** (default): Uses local transformer model for dynamic, contextual responses
- **Templates Mode**: Uses pre-written response templates (faster but less dynamic)

## Expected Performance

### On HF Spaces (CPU):
- **Model Loading**: 30-60 seconds (first time only)
- **Response Generation**: 2-5 seconds per response
- **Memory Usage**: 1.5-6GB depending on model

### On HF Spaces (GPU):
- **Model Loading**: 10-20 seconds (first time only)
- **Response Generation**: 0.5-2 seconds per response
- **Memory Usage**: 2-8GB VRAM depending on model

## Troubleshooting

### Model won't load
- Check that you have enough RAM/disk space
- The system will try progressively smaller models
- If all fail, it falls back to template mode

### Responses are slow
- First response is always slower (model needs to load)
- Consider using a GPU-enabled HF Space
- Or switch to "Templates (Local)" mode for instant responses

### Out of memory errors
- The system will automatically try smaller models
- Restart the space to clear memory
- Use the smallest model (distilgpt2) by removing larger ones from MODEL_CANDIDATES

## Customizing Models

To use different models, edit `engine/responder.py`:

```python
MODEL_CANDIDATES = [
    "your-preferred-model",
    "fallback-model-1",
    "fallback-model-2",
]
```

Good model options:
- `Qwen/Qwen2-1.5B-Instruct` - Excellent quality for size
- `stabilityai/stablelm-2-1_6b-chat` - Good conversation model
- `google/gemma-2b-it` - Google's instruction-tuned model

## API Keys (Not Required)

You **do not need** any API keys for local model operation. The following are optional:

- `HF_TOKEN`: Only needed for gated models (not used by default)
- `ANTHROPIC_API_KEY`: Not used in local mode

## Memory Usage

Model sizes (approximate):
- Phi-2: ~5.5GB
- TinyLlama: ~2.2GB
- OPT-350m: ~700MB
- DistilGPT2: ~330MB

Choose based on your HF Space tier:
- **Free tier**: Use OPT-350m or DistilGPT2
- **Upgraded tier**: Use TinyLlama or Phi-2

## Additional Notes

- Models are automatically cached by HuggingFace
- First response after loading model might be slower
- All processing happens locally - no data sent to external APIs
- Audio features are currently disabled to reduce dependencies
