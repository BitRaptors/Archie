export interface PromptVariable {
  name: string;
  description: string;
  sample: string;
}

export const PROMPT_VARIABLES: Record<string, PromptVariable[]> = {
  avatar_description: [
    { name: "character_name", description: "Character name", sample: "Luna" },
  ],
  avatar_image: [
    { name: "character_name", description: "Character name", sample: "Luna" },
    { name: "visual_description", description: "AI-generated visual description from photo", sample: "Short curly brown hair, round face, large green eyes, small button nose, friendly smile. Wears round glasses." },
  ],
  story_outline: [
    { name: "language_name", description: "Story language (full name)", sample: "Hungarian" },
    { name: "story_prompt", description: "User's story idea", sample: "Egy történet egy varázslatos kertről" },
    { name: "character_context", description: "Formatted character info", sample: "Characters: Luna (Born: 2021-03-15) - Loves adventures; Max (Born: 2019-07-20) - Brave and curious" },
    { name: "age_context", description: "Age-appropriate guidance", sample: " The story should be appropriate for a 4-year-old child." },
  ],
  page_text: [
    { name: "language_name", description: "Story language", sample: "Hungarian" },
    { name: "story_prompt", description: "User's story idea", sample: "Egy történet egy varázslatos kertről" },
    { name: "character_context", description: "Character info with visual descriptions", sample: "Characters potentially involved: Luna (Born: 2021-03-15) - Loves adventures - Looks: Short curly brown hair..." },
    { name: "memory_context", description: "Relevant family memories", sample: "No specific memories provided." },
    { name: "outline_summary", description: "Full story outline", sample: "Story Outline Overview:\n- Page 1: Luna discovers a hidden door\n- Page 2: She enters the magical garden" },
    { name: "previous_pages", description: "Summary of previous pages", sample: "Page 1 Content Summary: Luna was playing in the backyard when she noticed..." },
    { name: "page_number", description: "Current page number", sample: "2" },
    { name: "page_description", description: "Outline description for this page", sample: "She enters the magical garden and meets talking flowers" },
    { name: "age_context", description: "Age-appropriate guidance", sample: " Keep the language and themes appropriate for a 4-year-old child." },
  ],
  image_prompt: [
    { name: "style_keywords", description: "Image style description", sample: "watercolor, cartoonish, soft lighting, vibrant, friendly, children's book illustration style" },
    { name: "age_context", description: "Age-appropriate visual guidance", sample: " Ensure visuals are suitable for a 4-year-old, avoiding anything scary." },
    { name: "character_context", description: "Characters on this page with descriptions", sample: "Characters featured on this page: Luna (Born: 2021-03-15) - Looks: Short curly brown hair, round face" },
    { name: "memory_context", description: "Relevant memories for visual context", sample: "" },
    { name: "page_text", description: "Story text for this page", sample: "Luna pushed open the garden gate and gasped. Flowers of every color swayed gently..." },
  ],
};

export const AVAILABLE_PROVIDERS = [
  { value: "openai", label: "OpenAI" },
  { value: "groq", label: "Groq" },
  { value: "gemini", label: "Google Gemini" },
];

export const AVAILABLE_MODELS: Record<string, { value: string; label: string }[]> = {
  openai: [
    { value: "gpt-4o-mini", label: "GPT-4o Mini" },
    { value: "gpt-4o", label: "GPT-4o" },
    { value: "gpt-4.1-mini", label: "GPT-4.1 Mini" },
    { value: "gpt-4.1", label: "GPT-4.1" },
    { value: "gpt-image-1", label: "GPT Image 1 (image only)" },
  ],
  groq: [
    { value: "meta-llama/llama-4-scout-17b-16e-instruct", label: "Llama 4 Scout 17B" },
    { value: "llava-v1.5-7b-4096-preview", label: "LLaVA v1.5 7B" },
    { value: "llama-3.3-70b-versatile", label: "Llama 3.3 70B" },
  ],
  gemini: [
    { value: "gemini-1.5-flash", label: "Gemini 1.5 Flash" },
    { value: "gemini-2.0-flash", label: "Gemini 2.0 Flash" },
  ],
};
