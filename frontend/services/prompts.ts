import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface Prompt {
  id: string
  user_id: string | null
  name: string
  description: string | null
  category: string
  prompt_template: string
  variables: string[]
  is_default: boolean
  created_at: string
  updated_at: string | null
  key: string | null
  type: string
}

export interface PromptRevision {
  id: string
  prompt_id: string
  revision_number: number
  prompt_template: string
  variables: string[]
  name: string | null
  description: string | null
  change_summary: string | null
  created_by: string | null
  created_at: string
}

export interface UpdatePromptPayload {
  name?: string
  description?: string
  prompt_template?: string
  variables?: string[]
  change_summary?: string
}

export const promptsService = {
  async list(): Promise<Prompt[]> {
    const response = await axios.get(`${API_URL}/api/v1/prompts/`)
    return response.data
  },

  async get(id: string): Promise<Prompt> {
    const response = await axios.get(`${API_URL}/api/v1/prompts/${id}`)
    return response.data
  },

  async update(id: string, data: UpdatePromptPayload): Promise<Prompt> {
    const response = await axios.put(`${API_URL}/api/v1/prompts/${id}`, data)
    return response.data
  },

  async getRevisions(id: string): Promise<PromptRevision[]> {
    const response = await axios.get(`${API_URL}/api/v1/prompts/${id}/revisions`)
    return response.data
  },

  async revert(promptId: string, revisionId: string): Promise<Prompt> {
    const response = await axios.post(
      `${API_URL}/api/v1/prompts/${promptId}/revert/${revisionId}`
    )
    return response.data
  },
}
