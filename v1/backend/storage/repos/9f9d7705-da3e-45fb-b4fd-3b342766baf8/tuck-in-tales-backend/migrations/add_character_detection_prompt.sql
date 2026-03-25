INSERT INTO prompts (slug, version, is_active, name, description, system_prompt, user_prompt, provider, model, temperature, max_tokens, response_format, available_variables)
VALUES (
    'character_detection', 1, true,
    'Character Detection',
    'Analyzes page text to detect which known characters appear on the page',
    'You are a text analysis assistant. Given a page of a children''s story and a list of known character names, identify which characters appear or are referenced on this page. Return ONLY a JSON object with a single key ''characters'' containing an array of character names that appear on this page. Only include names from the provided known characters list.',
    'Known characters: @character_names

Characters already identified from the outline for this page: @outline_characters

Page text:
@page_text

Analyze the text and return a JSON object with ALL characters from the known list that appear, are mentioned, or are clearly referenced on this page (including the outline characters if they are indeed present).',
    'openai', 'gpt-4o-mini', 0.1, 150,
    '{"type": "json_object"}',
    ARRAY['character_names', 'outline_characters', 'page_text']
);
