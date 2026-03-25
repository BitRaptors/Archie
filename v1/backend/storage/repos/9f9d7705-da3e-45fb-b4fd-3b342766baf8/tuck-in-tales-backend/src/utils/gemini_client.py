import google.generativeai as genai
import logging
from typing import Optional, List, Tuple
import base64
import io
from src.config import settings

# Initialize Gemini client
async_gemini_client: Optional[genai.GenerativeModel] = None

def init_gemini_client():
    """Initialize the Gemini client with API key."""
    global async_gemini_client
    
    if not settings.GEMINI_API_KEY:
        logging.warning("GEMINI_API_KEY not set. Gemini client will not be available.")
        return
    
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        # Use Gemini Pro Vision for image generation
        async_gemini_client = genai.GenerativeModel(settings.GEMINI_IMAGE_MODEL)
        logging.info(f"Gemini client initialized with model: {settings.GEMINI_IMAGE_MODEL}")
    except Exception as e:
        logging.error(f"Failed to initialize Gemini client: {e}")
        async_gemini_client = None

async def generate_image_with_gemini(
    prompt: str,
    reference_images: Optional[List[Tuple[str, any, str]]] = None,
    size: str = "1024x1024"
) -> Optional[bytes]:
    """
    Generate an image using Gemini's image generation capabilities.
    
    Args:
        prompt: Text prompt describing the image to generate
        reference_images: Optional list of reference images as (filename, bytes, mime_type) tuples
        size: Image size (e.g., "1024x1024")
    
    Returns:
        Image bytes if successful, None otherwise
    """
    if not async_gemini_client:
        logging.error("Gemini client not initialized")
        return None
    
    try:
        # Prepare the content for Gemini
        content_parts = [prompt]
        
        # Add reference images if provided
        if reference_images:
            for filename, image_data, mime_type in reference_images:
                # Handle both bytes and BytesIO objects
                if hasattr(image_data, 'read'):  # BytesIO object
                    image_bytes = image_data.read()
                    # Reset position for potential reuse
                    image_data.seek(0)
                else:  # Direct bytes
                    image_bytes = image_data
                
                # Convert bytes to base64 for Gemini
                image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                content_parts.append({
                    "mime_type": mime_type,
                    "data": image_base64
                })
        
        # Generate image using Gemini's new image generation capabilities
        response = await async_gemini_client.generate_content_async(content_parts)
        
        if response.candidates and response.candidates[0].content:
            # Extract image data from response
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    return part.inline_data.data
                elif hasattr(part, 'text') and part.text:
                    # If Gemini returns text describing the image, we might need to handle differently
                    logging.warning("Gemini returned text instead of image data")
                    continue
        
        logging.error("No image data found in Gemini response")
        return None
        
    except Exception as e:
        logging.error(f"Error generating image with Gemini: {e}")
        return None

# Initialize client when module is imported
init_gemini_client()
