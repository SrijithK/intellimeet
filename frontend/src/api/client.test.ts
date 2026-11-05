import { jsonResponse, SOURCE, sse, streamResponse } from '@/test/utils'

import { ApiError, api, streamChat } from './client'

const handlers = () => ({ onCitations: vi.fn(), onToken: vi.fn(), onDone: vi.fn() })

afterEach(() => vi.unstubAllGlobals())

describe('streamChat', () => {
  it('posts the question and dispatches events in order', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      streamResponse([sse('citations', { sources: [SOURCE] }), sse('token', { text: 'Hi ' }), sse('token', { text: 'there' }), sse('done', { answer: 'Hi there', found: true })]),
    )
    vi.stubGlobal('fetch', fetchMock)
    const h = handlers()

    await streamChat({ question: 'When?', meeting_ids: ['m1'] }, h)

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/chat')
    expect(JSON.parse(init.body)).toEqual({ question: 'When?', meeting_ids: ['m1'] })
    expect(h.onCitations).toHaveBeenCalledWith({ sources: [SOURCE] })
    expect(h.onToken.mock.calls.map((c) => c[0])).toEqual(['Hi ', 'there'])
    expect(h.onDone).toHaveBeenCalledWith({ answer: 'Hi there', found: true })
  })

  it('throws the server message on an error event', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(streamResponse([sse('error', { message: 'Could not reach Ollama', query_id: 'q' })])))

    await expect(streamChat({ question: 'x' }, handlers())).rejects.toThrow('Could not reach Ollama')
  })

  it('surfaces validation errors from a non-2xx response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail: [{ msg: 'String should have at least 1 character' }] }, 422)))

    await expect(streamChat({ question: '' }, handlers())).rejects.toThrow('at least 1 character')
  })
})

describe('api', () => {
  it('raises ApiError with the detail message and status', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail: 'Meeting x not found' }, 404)))

    const error = await api.getMeeting('x').catch((e) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBe(404)
    expect(error.message).toBe('Meeting x not found')
  })
})
