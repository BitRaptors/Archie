export interface Prompt {
  id: string;
  slug: string;
  version: number;
  is_active: boolean;
  name: string;
  description: string | null;
  system_prompt: string;
  user_prompt: string;
  provider: string;
  model: string;
  temperature: number | null;
  max_tokens: number | null;
  response_format: Record<string, unknown> | null;
  available_variables: string[];
  created_at: string;
  updated_at: string | null;
}

export interface PromptUpdate {
  name: string;
  description?: string | null;
  system_prompt: string;
  user_prompt: string;
  provider: string;
  model: string;
  temperature?: number | null;
  max_tokens?: number | null;
  response_format?: Record<string, unknown> | null;
  available_variables: string[];
}

export interface PromptTestRequest {
  system_prompt: string;
  user_prompt: string;
  provider: string;
  model: string;
  temperature?: number;
  max_tokens?: number | null;
}

export interface PromptTestResponse {
  response: string;
  provider: string;
  model: string;
  usage?: Record<string, unknown>;
}
