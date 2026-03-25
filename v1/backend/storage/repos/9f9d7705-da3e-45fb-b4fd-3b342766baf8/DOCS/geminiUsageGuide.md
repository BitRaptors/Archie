# Gemini Integration Usage Guide

## Overview

The Bedtime App now supports Google's Gemini model as an alternative to OpenAI for image generation. This allows you to choose between OpenAI and Gemini for generating avatar images and story page illustrations.

## Features

- **Dual Provider Support**: Switch between OpenAI and Gemini for image generation
- **Environment-Based Configuration**: Easy switching via environment variables
- **Seamless Integration**: Both avatar generation and story image generation support Gemini
- **Fallback Support**: Graceful handling when switching between providers
- **Consistent Visual Style**: Unified aesthetic across all generated images with clean, modern, minimal design

## Setup

### 1. Install Dependencies

The required dependencies are already included in the project:

```bash
poetry install
```

### 2. Configure Environment Variables

Add these variables to your `.env` file:

```bash
# Gemini Configuration
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_IMAGE_MODEL=gemini-1.5-flash

# Provider Selection
IMAGE_GENERATION_PROVIDER=GEMINI  # or OPENAI
```

### 3. Get Gemini API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Copy the key to your `.env` file

## Usage

### Switching Providers

To switch from OpenAI to Gemini:

```bash
# Set Gemini as the provider
export IMAGE_GENERATION_PROVIDER=GEMINI
export GEMINI_API_KEY=your_key_here

# Restart your application
```

To switch back to OpenAI:

```bash
# Set OpenAI as the provider
export IMAGE_GENERATION_PROVIDER=OPENAI

# Restart your application
```

### Avatar Generation

When generating character avatars, the system will automatically use the selected provider:

- **OpenAI**: Uses DALL-E image editing with reference photos
- **Gemini**: Uses Gemini's image generation capabilities with reference photos

### Story Image Generation

When generating story page illustrations, the system will:

- **OpenAI**: Use DALL-E image edit/generate based on available character avatars
- **Gemini**: Use Gemini's image generation with or without reference images

### Visual Style Consistency

All generated images (avatars and story illustrations) follow a unified visual style:

- **Clean, modern, and minimal** design approach
- **Bold outlines** and **smooth curves**
- **Solid fill colors** for clarity
- **Playful, approachable, and polished** aesthetic
- **Similar to modern digital avatar creators**
- **Vibrant and friendly** children's book illustration style
- **Soft lighting** for warmth

This ensures a cohesive visual experience across your entire application, whether using OpenAI or Gemini as the image generation provider.

### Current Gemini Status

**Great News**: Gemini now supports image generation! When you select Gemini as the provider:

1. **Native Image Generation**: Gemini can create images directly using its latest models
2. **Reference Image Support**: Gemini can use character photos as reference images for better results
3. **Consistent Styling**: All images follow the same visual style guidelines
4. **Full Integration**: Works seamlessly with both avatar generation and story illustrations

**Model Support**: The integration uses Gemini's latest models that support image generation capabilities.

## Configuration Options

### Environment Variables

| Variable | Description | Default | Options |
|----------|-------------|---------|---------|
| `IMAGE_GENERATION_PROVIDER` | Image generation service | `OPENAI` | `OPENAI`, `GEMINI` |
| `GEMINI_API_KEY` | Gemini API key | `None` | Your API key |
| `GEMINI_IMAGE_MODEL` | Gemini model to use | `gemini-1.5-flash` | Any valid Gemini model |

### Provider-Specific Settings

#### OpenAI
- `OPENAI_EDIT_MODEL`: Model for image editing (default: `gpt-image-1`)
- `OPENAI_IMAGE_MODEL`: Model for image generation (default: `gpt-image-1`)

#### Gemini
- `GEMINI_IMAGE_MODEL`: Gemini model for image generation (default: `gemini-1.5-flash`)

## Code Examples

### Using Gemini Client Directly

```python
from src.utils.gemini_client import generate_image_with_gemini

# Generate image with prompt only
image_bytes = await generate_image_with_gemini(
    prompt="A friendly cartoon character",
    size="1024x1024"
)

# Generate image with reference images
image_bytes = await generate_image_with_gemini(
    prompt="Create an avatar based on this photo",
    reference_images=[(filename, image_bytes, mime_type)],
    size="1024x1024"
)
```

### Checking Current Provider

```python
from src.config import settings

provider = settings.IMAGE_GENERATION_PROVIDER
if provider == "GEMINI":
    print("Using Gemini for image generation")
else:
    print("Using OpenAI for image generation")
```

## Troubleshooting

### Common Issues

1. **Gemini client not initialized**
   - Check that `GEMINI_API_KEY` is set in your environment
   - Verify the API key is valid

2. **Provider not switching**
   - Ensure `IMAGE_GENERATION_PROVIDER` is set correctly
   - Restart your application after changing environment variables

3. **Image generation fails**
   - Check API key validity
   - Verify model names are correct
   - Check API quotas and limits

4. **BytesIO error with reference images**
   - This has been fixed in the latest version
   - The Gemini client now properly handles both bytes and BytesIO objects
   - If you encounter this error, ensure you're using the latest code

5. **Gemini returns text instead of images**
   - This might indicate a model compatibility issue
   - Ensure you're using a Gemini model that supports image generation
   - Check that your API key has access to image generation features
   - Verify the model name in your environment variables

### Debug Mode

Enable debug logging to see which provider is being used:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Performance Considerations

- **Gemini**: Generally faster response times, good for real-time applications
- **OpenAI**: More consistent quality, better for production use
- **Cost**: Compare pricing between providers for your use case

## Best Practices

1. **Environment Management**: Use separate `.env` files for different environments
2. **Provider Testing**: Test both providers before deploying to production
3. **Fallback Strategy**: Consider implementing automatic fallback if one provider fails
4. **Monitoring**: Monitor API usage and costs for both providers

## Migration Guide

### From OpenAI to Gemini

1. Set up Gemini API key
2. Change `IMAGE_GENERATION_PROVIDER` to `GEMINI`
3. Test image generation functionality
4. Monitor quality and performance
5. Update any provider-specific code if needed

### From Gemini to OpenAI

1. Change `IMAGE_GENERATION_PROVIDER` to `OPENAI`
2. Ensure OpenAI API key is configured
3. Test image generation functionality
4. Verify quality and performance

## Support

For issues with Gemini integration:

1. Check the logs for error messages
2. Verify environment variable configuration
3. Test with the provided test scripts
4. Check Gemini API documentation for model-specific issues
