-- Prompts table for managing LLM prompts
CREATE TABLE IF NOT EXISTS prompts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug TEXT NOT NULL,
  version INT NOT NULL DEFAULT 1,
  is_active BOOLEAN NOT NULL DEFAULT true,
  name TEXT NOT NULL,
  description TEXT,
  system_prompt TEXT NOT NULL,
  user_prompt TEXT NOT NULL,
  provider TEXT NOT NULL DEFAULT 'openai',
  model TEXT NOT NULL DEFAULT 'gpt-4o-mini',
  temperature FLOAT DEFAULT 0.7,
  max_tokens INT,
  response_format JSONB,
  available_variables TEXT[] NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_prompts_active_slug ON prompts (slug) WHERE is_active = true;

-- Seed data: 5 existing prompts

INSERT INTO prompts (slug, version, is_active, name, description, system_prompt, user_prompt, provider, model, temperature, max_tokens, response_format, available_variables)
VALUES
(
  'avatar_description',
  1,
  true,
  'Avatar Description',
  'Analyzes a photo to extract key visual features for creating cartoon-style avatars.',
  'You are a visual analysis assistant that extracts key visual features from photos for creating cartoon-style avatars.',
  E'Analyze the image carefully to extract key visual features of the main subject for creating a cartoon-style avatar.\nFocus *only* on objective, distinct visual features needed for likeness:\n- Hair: Style (e.g., short, curly, straight, ponytail), color.\n- Face Shape: (e.g., round, oval, square).\n- Eyes: Color, shape (e.g., large, almond). Are glasses worn? If so, briefly describe style (e.g., round, rectangular).\n- Nose & Mouth: Basic shape or notable features (e.g., prominent chin).\n- Other Defining Features: Mention ONLY very distinct, visible characteristics like a beard, mustache, prominent freckles, unique mole/scar IF clearly visible.\nDo not infer personality, age, or identity. Keep the description concise (around 50-70 words), factual, and focused purely on visual traits for avatar creation.',
  'groq',
  'meta-llama/llama-4-scout-17b-16e-instruct',
  0.3,
  200,
  NULL,
  '{character_name}'
),
(
  'avatar_image',
  1,
  true,
  'Avatar Image',
  'Generates a cartoon avatar image for a character based on visual description and reference photos.',
  'You are an avatar image generator for a children''s story app.',
  E'Generate a cartoon profile picture/avatar suitable for a children''s story app character named ''@character_name''. Style: Vibrant but simple cartoon illustration, clear lines, friendly expression, head and shoulders view (headshot), simple/neutral/transparent background. Base the appearance *closely* on the visual description: ''@visual_description''. IMPORTANT: Use the provided reference image(s) to capture the likeness, especially key features like hair, eyes, face shape, and any distinct characteristics (like glasses or beard) mentioned in the description or visible in the photos.',
  'openai',
  'gpt-image-1',
  NULL,
  NULL,
  NULL,
  '{character_name,visual_description}'
),
(
  'story_outline',
  1,
  true,
  'Story Outline',
  'Generates a story title and structured outline for a short bedtime story.',
  E'You are a creative assistant specializing in children''s bedtime stories. Generate a suitable story title and a simple, structured outline (JSON object: { ''title'': ''story title here'', ''outline'': [{ ''page'': 1, ''description'': ''...'' }, ...] }) for a short story (3-5 pages) in @language_name. Base it on the user''s prompt and characters involved. Keep descriptions concise.@age_context',
  E'Story idea (in @language_name): @story_prompt\n@character_context',
  'openai',
  'gpt-4o-mini',
  0.2,
  NULL,
  '{"type": "json_object"}',
  '{language_name,story_prompt,character_context,age_context}'
),
(
  'page_text',
  1,
  true,
  'Page Text',
  'Writes the narrative content for a single page of a bedtime story.',
  'You are a talented children''s story author writing in @language_name. Write the content for the current page of a bedtime story, following the provided context. Focus *only* on the text for page @page_number.',
  E'Story Prompt: @story_prompt\n@character_context\n@memory_context\n@outline_summary\nPrevious Pages Summary:\n@previous_pages\n\nWrite the content FOR ONLY page @page_number in @language_name, which has this description: ''@page_description''. Focus *only* on the narrative for this single page. Ensure smooth transition from previous pages if applicable. Keep it engaging.@age_context Aim for 2-4 short paragraphs per page.',
  'openai',
  'gpt-4o-mini',
  0.7,
  350,
  NULL,
  '{language_name,story_prompt,character_context,memory_context,outline_summary,previous_pages,page_number,page_description,age_context}'
),
(
  'image_prompt',
  1,
  true,
  'Image Prompt',
  'Creates an image generation prompt for a children''s storybook illustration.',
  'You are an expert prompt engineer for Openai GPT image generation. Use the character descriptions (including age context from birth date) to guide the visual details.',
  E'Create a Openai GPT image generation prompt for a children''s storybook illustration. Style: @style_keywords.@age_context @character_context @memory_context Generate a prompt based *only* on the following scene text, focusing on key visual elements and emotions: "@page_text". The prompt should be concise and descriptive for image generation.',
  'openai',
  'gpt-4o-mini',
  0.5,
  150,
  NULL,
  '{style_keywords,age_context,character_context,memory_context,page_text}'
);
