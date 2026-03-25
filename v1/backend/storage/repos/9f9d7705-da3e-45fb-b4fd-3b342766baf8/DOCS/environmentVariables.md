# Environment Variables Configuration

## Required Variables

### Supabase Configuration
- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_ANON_KEY`: Your Supabase anonymous key
- `SUPABASE_SERVICE_KEY`: Your Supabase service role key

### OpenAI Configuration
- `OPENAI_API_KEY`: Your OpenAI API key
- `OPENAI_CHAT_MODEL`: Chat model (default: gpt-4o-mini)
- `OPENAI_EMBEDDING_MODEL`: Embedding model (default: text-embedding-3-small)
- `OPENAI_EDIT_MODEL`: Image editing model (default: gpt-image-1)
- `OPENAI_IMAGE_MODEL`: Image generation model (default: gpt-image-1)

## Optional Variables

### Groq Configuration
- `GROQ_API_KEY`: Your Groq API key (optional)
- `GROQ_VISION_MODEL`: Vision model (default: llava-v1.5-7b-4096-preview)

### Gemini Configuration
- `GEMINI_API_KEY`: Your Google Gemini API key (optional)
- `GEMINI_IMAGE_MODEL`: Gemini model (default: gemini-1.5-flash)

### Provider Selection
- `IMAGE_GENERATION_PROVIDER`: Choose between "OPENAI" or "GEMINI" (default: OPENAI)

## Example .env File

```bash
# Supabase Configuration
SUPABASE_URL=your_supabase_url_here
SUPABASE_ANON_KEY=your_supabase_anon_key_here
SUPABASE_SERVICE_KEY=your_supabase_service_key_here

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_CHAT_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EDIT_MODEL=gpt-image-1
OPENAI_IMAGE_MODEL=gpt-image-1

# Groq Configuration (Optional)
GROQ_API_KEY=your_groq_api_key_here
GROQ_VISION_MODEL=llava-v1.5-7b-4096-preview

# Gemini Configuration (Optional)
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_IMAGE_MODEL=gemini-1.5-flash

# Image Generation Provider Selection
# Options: "OPENAI" or "GEMINI"
IMAGE_GENERATION_PROVIDER=OPENAI

# Firebase Configuration
FIREBASE_SERVICE_ACCOUNT_KEY_PATH=firebase-service-account.json
```

## Switching Between Providers

To switch from OpenAI to Gemini for image generation:

1. Set your Gemini API key:
   ```bash
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

2. Change the provider:
   ```bash
   IMAGE_GENERATION_PROVIDER=GEMINI
   ```

3. Restart your application

## Notes

- Both providers can be configured simultaneously
- The `IMAGE_GENERATION_PROVIDER` variable controls which service is used for image generation
- If Gemini is selected but no API key is provided, the system will fall back to OpenAI
- Avatar generation and story page image generation both respect this setting
