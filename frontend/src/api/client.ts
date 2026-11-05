import type { ChatRequest, CitationsEvent, DoneEvent, Job, MeetingDetail, MeetingSummary, UploadResponse } from './types'
import { readSSE } from './sse'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function errorFrom(response: Response): Promise<ApiError> {
  let message = `Request failed (${response.status})`
  try {
    const body = await response.json()
    if (typeof body?.detail === 'string') message = body.detail
    else if (Array.isArray(body?.detail) && body.detail[0]?.msg) message = body.detail[0].msg
  } catch {
    // not JSON; keep the generic message
  }
  return new ApiError(response.status, message)
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path)
  if (!response.ok) throw await errorFrom(response)
  return response.json() as Promise<T>
}

export const api = {
  listMeetings: () => getJson<MeetingSummary[]>('/api/meetings'),
  getMeeting: (id: string) => getJson<MeetingDetail>(`/api/meetings/${encodeURIComponent(id)}`),
  getJob: (id: string) => getJson<Job>(`/api/jobs/${encodeURIComponent(id)}`),

  async uploadMeeting(file: File): Promise<UploadResponse> {
    const body = new FormData()
    body.append('file', file)
    const response = await fetch('/api/meetings', { method: 'POST', body })
    if (!response.ok) throw await errorFrom(response)
    return response.json()
  },
}

export interface ChatHandlers {
  onCitations: (event: CitationsEvent) => void
  onToken: (text: string) => void
  onDone: (event: DoneEvent) => void
}

/** POST /api/chat and dispatch its Server-Sent Events. Throws on HTTP errors and `error` events. */
export async function streamChat(request: ChatRequest, handlers: ChatHandlers, signal?: AbortSignal): Promise<void> {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(request),
    signal,
  })
  if (!response.ok) throw await errorFrom(response)
  if (!response.body) throw new ApiError(response.status, 'The server returned an empty response.')

  for await (const message of readSSE(response.body)) {
    const data = JSON.parse(message.data)
    switch (message.event) {
      case 'citations':
        handlers.onCitations(data)
        break
      case 'token':
        handlers.onToken(data.text)
        break
      case 'done':
        handlers.onDone(data)
        break
      case 'error':
        throw new ApiError(500, data.message ?? 'The answer could not be generated.')
    }
  }
}
