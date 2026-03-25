from openai import OpenAI, AsyncOpenAI
from src.config import settings

# Ensure API key is set
if not settings.OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY must be set in environment variables or .env file")

# Initialize the synchronous client (if needed elsewhere)
sync_openai_client: OpenAI = OpenAI(api_key=settings.OPENAI_API_KEY)

# Initialize the asynchronous client for FastAPI routes
async_openai_client: AsyncOpenAI = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

async def get_openai_client() -> AsyncOpenAI:
    """Dependency injector for the asynchronous OpenAI client."""
    return async_openai_client

# Helper function to get embeddings (optional, but convenient)
async def get_embedding(text: str, model: str = settings.OPENAI_EMBEDDING_MODEL) -> list[float]:
    """Generates an embedding for the given text using the configured model."""
    text = text.replace("\n", " ") # OpenAI recommends replacing newlines
    try:
        response = await async_openai_client.embeddings.create(input=[text], model=model)
        return response.data[0].embedding
    except Exception as e:
        # Log error e
        print(f"Error getting embedding from OpenAI: {e}") # Basic print logging
        raise # Re-raise the exception to be handled by the route 