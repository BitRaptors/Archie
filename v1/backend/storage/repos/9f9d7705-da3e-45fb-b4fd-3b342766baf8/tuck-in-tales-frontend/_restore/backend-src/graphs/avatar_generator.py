import operator
from typing import TypedDict, Annotated, List, Optional
from uuid import UUID, uuid4
import logging
import httpx # Added for downloading later
import json # Added for WS payload
import base64
import io # <-- Import io module

from langgraph.graph import StateGraph, END, START
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

# Use clients initialized elsewhere (e.g., in utils)
from src.utils.openai_client import async_openai_client
from src.utils.groq_client import async_groq_client, GroqError # Import Groq client
from src.utils.gemini_client import async_gemini_client, generate_image_with_gemini
from src.utils.supabase import get_supabase_client
from supabase import Client
from src.utils.sse import send_sse_event
from src.config import settings

# Constants from characters route (consider moving to config/shared utils)
PHOTOS_BUCKET = "photos"
SIGNED_URL_EXPIRY = 300 # 5 minutes

# --- Graph State Definition (Moved Up) --- 

class AvatarGeneratorState(TypedDict):
    """Defines the state variables tracked across the graph execution."""
    character_id: UUID
    family_id: UUID
    character_name: str
    character_bio: Optional[str]
    photo_paths: List[str] # List of original photo storage paths
    
    # Derived or generated values
    signed_photo_url: Optional[str] 
    visual_description: Optional[str] 
    dalle_prompt: Optional[str] 
    generated_avatar_url: Optional[str]
    final_avatar_path: Optional[str] 
    
    # Control flow
    next_step: Optional[str] # Added: The key returned by the planner

    # Error handling
    error_message: Optional[str]
    
    # For chat refinement (Phase 3)
    # chat_history: List[BaseMessage]
    # user_request: Optional[str]

# --- Nodes --- 

def planner(state: AvatarGeneratorState) -> dict:
    """Decides the next step based on the current state."""
    char_id = state['character_id'] # Get ID for logging
    logging.info(f"[Graph - {char_id}] Planner running. Current state keys: {list(state.keys())}")
    
    return_value = {}
    if not state.get('photo_paths'):
        logging.error(f"[Graph - {char_id}] Planner: No photo paths found.")
        return_value = {"error_message": "Character has no photos to generate avatar from."}
    elif not state.get('visual_description'):
        return_value = {"next_step": "generate_description"}
    elif not state.get('final_avatar_path'):
        return_value = {"next_step": "generate_image"}
    else:
        return_value = {"next_step": "finish"}
        
    logging.info(f"[Graph - {char_id}] Planner returning: {return_value}")
    return return_value


async def generate_description(state: AvatarGeneratorState) -> dict:
    """Generates a visual description from a photo using the specified Groq model."""
    character_id = state['character_id']
    character_name = state.get('character_name', 'the character') 
    logging.info(f"[Graph - {character_id}] Generating description for {character_name} using Groq...")
    await send_sse_event(str(character_id), "status", {"step": "describing", "message": f"Analyzing photo of {character_name} with Groq..."})
    supabase_client: Client = get_supabase_client()

    # Check if Groq client is available
    if not async_groq_client:
        error_msg = "Groq client not initialized. Check GROQ_API_KEY."
        logging.error(f"[Graph - {character_id}] {error_msg}")
        await send_sse_event(str(character_id), "error", {"message": error_msg})
        return {"error_message": error_msg}

    photo_paths = state.get('photo_paths', [])
    if not photo_paths:
        return {"error_message": "No photo paths available to generate description."}
    
    photo_to_use = photo_paths[0]
    signed_photo_url = None
    visual_desc = None

    try:
        # Create signed URL (still needed to pass to Groq API)
        signed_url_response = supabase_client.storage.from_(PHOTOS_BUCKET).create_signed_url(photo_to_use, SIGNED_URL_EXPIRY)
        signed_photo_url = signed_url_response.get('signedURL')
        if not signed_photo_url:
            raise ValueError("Failed to create signed URL for image")
        logging.info(f"[Graph - {character_id}] Generated signed URL for Groq: {signed_photo_url[:50]}...")

        # --- Vision Prompt (using the neutral one) ---
        vision_prompt_parts = [
            f"Analyze the image carefully to extract key visual features of the main subject for creating a cartoon-style avatar.",
            "Focus *only* on objective, distinct visual features needed for likeness:",
            "- Hair: Style (e.g., short, curly, straight, ponytail), color.",
            "- Face Shape: (e.g., round, oval, square).",
            "- Eyes: Color, shape (e.g., large, almond). Are glasses worn? If so, briefly describe style (e.g., round, rectangular).",
            "- Nose & Mouth: Basic shape or notable features (e.g., prominent chin).",
            "- Other Defining Features: Mention ONLY very distinct, visible characteristics like a beard, mustache, prominent freckles, unique mole/scar IF clearly visible.",
            "Do not infer personality, age, or identity. Keep the description concise (around 50-70 words), factual, and focused purely on visual traits for avatar creation."
        ]
        vision_prompt = "\n".join(vision_prompt_parts)
        # --- End Vision Prompt ---
        
        groq_model_name = "meta-llama/llama-4-scout-17b-16e-instruct" # Using the user-requested model
        logging.info(f"[Graph - {character_id}] Calling Groq model '{groq_model_name}' with image URL...")
        
        # Prepare messages for Groq API (OpenAI compatible format)
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": vision_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": signed_photo_url}, # <-- Sending image URL
                    },
                ],
            }
        ]
        
        # Call Groq API (synchronously)
        try:
            vision_response = async_groq_client.chat.completions.create(
                model=groq_model_name,
                messages=messages,
                max_tokens=200, 
            )
            visual_desc = vision_response.choices[0].message.content
            
            if not visual_desc:
                # Handle potential empty response even if API call succeeded
                 raise ValueError("Groq model returned an empty description.")
                 
            # Check for potential refusal messages (adjust keywords as needed)
            refusal_keywords = ["sorry", "cannot analyze", "unable to process", "can't describe"]
            if any(keyword in visual_desc.lower() for keyword in refusal_keywords):
                logging.warning(f"[Graph - {character_id}] Groq model '{groq_model_name}' may have refused the request: '{visual_desc[:100]}...'")
                # Treat refusal as an error for workflow?
                # raise ValueError(f"Model refused request: {visual_desc}") 
            
            logging.info(f"[Graph - {character_id}] Groq ({groq_model_name}) description: {visual_desc}")

        except GroqError as ge:
            logging.error(f"[Graph - {character_id}] Groq API error calling {groq_model_name}: {ge}", exc_info=True)
            # Specific error handling - likely to happen if model doesn't support images
            if "does not support image input" in str(ge).lower() or "invalid input type" in str(ge).lower():
                 error_msg = f"Model '{groq_model_name}' failed: It does not support image input as expected. Try 'llava-v1.5-7b-4096-preview'."
            else:
                 error_msg = f"Groq API error: {ge}"
            await send_sse_event(str(character_id), "error", {"message": error_msg})
            return {"error_message": error_msg}
        except Exception as e:
            # Catch other potential errors during the API call
            logging.error(f"[Graph - {character_id}] Unexpected error calling Groq {groq_model_name}: {e}", exc_info=True)
            error_msg = f"Unexpected error during Groq API call: {e}"
            await send_sse_event(str(character_id), "error", {"message": error_msg})
            return {"error_message": error_msg}

        # Send update with the generated description (if successful)
        await send_sse_event(str(character_id), "status", {"step": "describing_complete", "message": "Visual description generated.", "visual_description": visual_desc})

        # --- NEW: Update database with the description ---\
        try:
            update_response = supabase_client.table("characters")\
                .update({"visual_description": visual_desc}) \
                .eq("id", str(character_id)) \
                .execute()
            # Optional: Check update_response for errors if needed
            logging.info(f"[Graph - {character_id}] Successfully updated visual_description in database.")
        except Exception as db_error:
            # Log the error but don't necessarily stop the whole graph
            logging.error(f"[Graph - {character_id}] Failed to update visual_description in database: {db_error}", exc_info=True)
            # Could potentially send a non-fatal WS warning here?
        # ----------------------------------------------

        return {"visual_description": visual_desc, "signed_photo_url": signed_photo_url}

    except Exception as e:
        # Catch errors from generating signed URL or other setup steps
        logging.error(f"[Graph - {character_id}] Error preparing for Groq description: {e}", exc_info=True)
        error_msg = f"Failed to prepare for visual description: {e}"
        await send_sse_event(str(character_id), "error", {"message": error_msg})
        return {"error_message": error_msg}

async def generate_image(state: AvatarGeneratorState) -> dict:
    """Generates an avatar image using the selected image generation provider (OpenAI or Gemini)."""
    character_id = state['character_id']
    family_id = state['family_id']
    visual_description = state.get('visual_description')
    character_name = state.get('character_name', 'a character')
    photo_paths = state.get('photo_paths', []) # Get the original photo paths
    
    # Determine which provider to use
    provider = settings.IMAGE_GENERATION_PROVIDER
    logging.info(f"[Graph - {character_id}] Generating avatar image for {character_name} using {provider} with reference photos: {photo_paths}")
    await send_sse_event(str(character_id), "status", {"step": "generating", "message": f"Generating avatar for {character_name} using {provider} and reference photos..."})
    supabase_client: Client = get_supabase_client()

    if not visual_description:
        error_msg = "Cannot generate image without visual description."
        await send_sse_event(str(character_id), "error", {"message": error_msg})
        return {"error_message": error_msg}
        
    if not photo_paths:
        error_msg = "Cannot generate edited image without reference photo paths."
        await send_sse_event(str(character_id), "error", {"message": error_msg})
        return {"error_message": error_msg}

    # --- DALL-E Prompt for Image Editing ---
    # This prompt guides the *edit* based on the visual description and reference images.
    edit_prompt = f"Generate a cartoon profile picture/avatar suitable for a children's story app character named '{character_name}'. Style: Vibrant but simple cartoon illustration, clear lines, friendly expression, head and shoulders view (headshot), simple/neutral/transparent background. Base the appearance *closely* on the visual description: '{visual_description}'. IMPORTANT: Use the provided reference image(s) to capture the likeness, especially key features like hair, eyes, face shape, and any distinct characteristics (like glasses or beard) mentioned in the description or visible in the photos."
    logging.info(f"[Graph - {character_id}] Using Image Edit prompt: {edit_prompt[:150]}...")
    
    opened_files = []
    try:
        # Download reference images from Supabase storage
        image_files_content = []
        for photo_path in photo_paths:
            try:
                logging.info(f"[Graph - {character_id}] Downloading reference image: {photo_path}")
                # Assuming photo_path is like 'family_id/character_id/filename.ext'
                # Adjust bucket if original photos are stored elsewhere
                file_content = supabase_client.storage.from_(settings.SUPABASE_BUCKET_PHOTOS).download(photo_path) 
                if not file_content:
                    raise ValueError(f"Failed to download reference photo: {photo_path}")
                image_files_content.append(file_content)
                logging.info(f"[Graph - {character_id}] Downloaded {len(file_content)} bytes for {photo_path}")
            except Exception as download_err:
                 logging.error(f"[Graph - {character_id}] Error downloading reference photo {photo_path}: {download_err}", exc_info=True)
                 # Decide if we should proceed with fewer images or fail
                 error_msg = f"Failed to download reference photo {photo_path}: {download_err}"
                 await send_sse_event(str(character_id), "error", {"message": error_msg})
                 return {"error_message": error_msg} # Fail if any image fails to download

        if not image_files_content:
             error_msg = "No reference images could be successfully downloaded."
             await send_sse_event(str(character_id), "error", {"message": error_msg})
             return {"error_message": error_msg}

        # Prepare a LIST of image tuples (filename, io.BytesIO(content), mime_type) for OpenAI
        images_data_for_api = []
        for i, photo_content in enumerate(image_files_content):
            photo_path = photo_paths[i]
            file_extension = photo_path.split('.')[-1].lower() if '.' in photo_path else 'png'
            mime_type_map = {
                'png': 'image/png',
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'webp': 'image/webp',
            }
            mime_type = mime_type_map.get(file_extension, 'image/png')

            # Construct the tuple: (filename, io.BytesIO(content), mime_type)
            image_tuple = (f"reference_{i}.{file_extension}", io.BytesIO(photo_content), mime_type)
            images_data_for_api.append(image_tuple)
            logging.info(f"[Graph - {character_id}] Prepared reference image {i+1} ('{photo_path}') for API call with MIME type: {mime_type}")

        # Generate image using selected provider
        image_content = None
        
        if provider == "GEMINI":
            logging.info(f"[Graph - {character_id}] Calling Gemini with {len(images_data_for_api)} reference image(s).")
            image_content = await generate_image_with_gemini(
                prompt=edit_prompt,
                reference_images=images_data_for_api,
                size="1024x1024"
            )
            
            if not image_content:
                raise ValueError("Gemini failed to generate image content")
                
            logging.info(f"[Graph - {character_id}] Received image data from Gemini.")
            
        else:  # Default to OpenAI
                logging.info(f"[Graph - {character_id}] Calling OpenAI images.edit with {len(images_data_for_api)} reference image(s) as list of tuples.")
                edit_response = await async_openai_client.images.edit(
                    model=settings.OPENAI_EDIT_MODEL,
                    image=images_data_for_api, # Pass the LIST of image tuples
                    # mask= Optional mask if needed
                    prompt=edit_prompt,
                    n=1,
                    size="1024x1024",
                )

                if not edit_response.data or not edit_response.data[0].b64_json:
                    raise ValueError("OpenAI images.edit response missing image data (b64_json)")
                
                image_base64 = edit_response.data[0].b64_json
                image_content = base64.b64decode(image_base64)
                logging.info(f"[Graph - {character_id}] Received base64 image data from OpenAI images.edit.")

        # image_content is now available from either provider
        if not image_content:
            raise ValueError("No image content received from image generation provider.")

        # Upload avatar to public Supabase bucket (using AVATARS_BUCKET from settings)
        # Use a unique name to avoid collisions and allow updates
        avatar_extension = 'png' # Assuming PNG output from both providers
        final_avatar_path = f"{str(family_id)}/{str(character_id)}/avatar_{uuid4()}.{avatar_extension}"
        
        logging.info(f"[Graph - {character_id}] Uploading generated avatar to Supabase path: {final_avatar_path} in bucket {settings.AVATARS_BUCKET}")
        supabase_client.storage.from_(settings.AVATARS_BUCKET).upload(
            path=final_avatar_path,
            file=image_content,
            file_options={"content-type": f"image/{avatar_extension}", "cache-control": "3600", "upsert": "true"}
        )
        logging.info(f"[Graph - {character_id}] Uploaded avatar successfully.")

        # Send update with the prompt used
        await send_sse_event(str(character_id), "status", {"step": "generating_complete", "message": f"Avatar image generated using {provider} and saved."})
        return {"final_avatar_path": final_avatar_path, "image_prompt": edit_prompt}

    except Exception as e:
        logging.error(f"[Graph - {character_id}] Error in image edit/upload process: {e}", exc_info=True)
        error_msg = f"Failed during image editing or upload: {e}"
        await send_sse_event(str(character_id), "error", {"message": error_msg})
        # Clean up any opened files if error occurs during API call or processing
        # for f in opened_files:
        #     f.close() # Not needed as we are using bytes directly now
        return {"error_message": error_msg}

def update_database(state: AvatarGeneratorState) -> dict:
    """Updates the character record in the database with the final avatar path."""
    character_id = state['character_id']
    family_id = state['family_id'] # Needed for the query
    final_avatar_path = state.get('final_avatar_path')
    logging.info(f"[Graph - {character_id}] Updating database with avatar path: {final_avatar_path}")
    supabase_client: Client = get_supabase_client()
    
    if not final_avatar_path:
        # This case should ideally be caught by the planner/decider
        logging.error(f"[Graph - {character_id}] Update database called without final_avatar_path.")
        return {"error_message": "Cannot update database without final avatar path."}

    try:
        update_response = supabase_client.table("characters")\
            .update({"avatar_url": final_avatar_path}) \
            .eq("id", str(character_id))\
            .eq("family_id", str(family_id)) \
            .execute()
        
        # Basic check if the update seemed to execute without direct error
        # Supabase python client might not give detailed info on rows affected here
        # We rely on the subsequent fetch in the endpoint if needed, or assume success if no exception
        logging.info(f"[Graph - {character_id}] Database update executed for avatar_url.")
        return {} # Indicate success by returning empty dict / no error

    except Exception as e:
        logging.error(f"[Graph - {character_id}] Error updating database: {e}", exc_info=True)
        # Set error message in state so the graph terminates via the error path
        error_msg = f"Failed to update database with avatar path: {e}"
        # await send_sse_event(str(character_id), "error", {"message": error_msg}) # See note above
        return {"error_message": error_msg}

# --- Conditional Edges (Moved Up) --- 

def decide_next_step(state: AvatarGeneratorState) -> str:
    """Determines the next node to execute based on planner output or errors."""
    char_id = state['character_id']
    logging.info(f"[Graph - {char_id}] decide_next_step received state: {state}") # Log entire state
    
    if state.get('error_message'):
        logging.error(f"[Graph - {char_id}] Error state reached: {state['error_message']}")
        return "error"
        
    next_step = state.get('next_step')
    logging.info(f"[Graph - {char_id}] Deciding next step based on value: {next_step}")
    if next_step == "generate_description":
        return "generate_description_node"
    elif next_step == "generate_image":
        return "generate_image_node"
    elif next_step == "finish":
        return "update_db_node" 
    else:
        logging.error(f"[Graph - {char_id}] Unknown next step value: {next_step}")
        return "error" 

# --- Graph Definition --- 

workflow = StateGraph(AvatarGeneratorState)

# Add nodes
workflow.add_node("planner_node", planner)
workflow.add_node("generate_description_node", generate_description)
workflow.add_node("generate_image_node", generate_image)
workflow.add_node("update_db_node", update_database)
workflow.add_node("error_node", lambda state: logging.error("Error node reached."))

# Define edges
workflow.add_edge(START, "planner_node")

# Conditional edge from planner to decide the main action
workflow.add_conditional_edges(
    "planner_node",
    decide_next_step,
    {
        "generate_description_node": "generate_description_node",
        "generate_image_node": "generate_image_node",
        "update_db_node": "update_db_node",
        "error": "error_node" 
    }
)

# Linear flow after generation steps (back to planner to decide next)
workflow.add_edge("generate_description_node", "planner_node") 
workflow.add_edge("generate_image_node", "planner_node")

# Final steps
workflow.add_edge("update_db_node", END)
workflow.add_edge("error_node", END)

# Compile the graph
app = workflow.compile()

print("Avatar Generator Graph Compiled.") 