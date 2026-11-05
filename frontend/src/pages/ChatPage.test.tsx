import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { jsonResponse, renderRoute, SOURCE, sse, streamResponse } from '@/test/utils'

import { ChatPage } from './ChatPage'

function mockApi(chatChunks: string[]) {
  const fetchMock = vi.fn(async (url: string, _init?: RequestInit) => {
    if (url === '/api/meetings') return jsonResponse([])
    if (url === '/api/chat') return streamResponse(chatChunks)
    throw new Error(`unexpected ${url}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => vi.unstubAllGlobals())

async function ask(question: string) {
  await userEvent.type(screen.getByLabelText('Question'), `${question}{Enter}`)
}

describe('ChatPage', () => {
  it('streams an answer and links citations to the transcript line', async () => {
    const answer = 'The launch moves to November 17th [planning, 00:01:44, Priya].'
    mockApi([
      sse('citations', { sources: [SOURCE] }),
      sse('token', { text: 'The launch moves to November 17th ' }),
      sse('token', { text: '[planning, 00:01:44, Priya].' }),
      sse('done', { answer, found: true, cited: [SOURCE], retrieved_chunk_ids: [1], latency_ms: 5, query_id: 'q1' }),
    ])
    renderRoute('/', { '/': <ChatPage /> })

    await ask('When is the launch?')

    expect(await screen.findByText('When is the launch?')).toBeInTheDocument()
    const links = await screen.findAllByRole('link', { name: 'Source: planning at 00:01:44, Priya' })
    expect(links[0]).toHaveAttribute('href', '/meetings/m1?turn=3')
    expect(screen.getByText('1 source')).toBeInTheDocument()
    expect(screen.getByLabelText('Question')).toHaveValue('')
  })

  it('shows the not-found reply distinctly, without sources', async () => {
    const notFound = "I couldn't find anything about that in the meeting transcripts."
    mockApi([
      sse('citations', { sources: [] }),
      sse('token', { text: notFound }),
      sse('done', { answer: notFound, found: false, cited: [], retrieved_chunk_ids: [], latency_ms: 1, query_id: 'q2' }),
    ])
    renderRoute('/', { '/': <ChatPage /> })

    await ask('Weather in Paris?')

    expect(await screen.findByText(notFound)).toBeInTheDocument()
    expect(screen.queryByText(/^\d+ sources?$/)).not.toBeInTheDocument()
  })

  it('shows server errors from the stream', async () => {
    mockApi([sse('citations', { sources: [] }), sse('error', { message: 'Could not reach Ollama', query_id: 'q3' })])
    renderRoute('/', { '/': <ChatPage /> })

    await ask('Anything?')

    expect(await screen.findByRole('alert')).toHaveTextContent('Could not reach Ollama')
  })

  it('scopes the question to the meeting in the URL', async () => {
    const fetchMock = mockApi([sse('done', { answer: 'ok', found: false, cited: [], retrieved_chunk_ids: [], latency_ms: 1, query_id: 'q' })])
    renderRoute('/?meeting=m1', { '/': <ChatPage /> })

    await ask('What was decided?')

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/chat', expect.anything()))
    const init = fetchMock.mock.calls.find(([url]) => url === '/api/chat')?.[1]
    const body = JSON.parse(String(init?.body))
    expect(body).toEqual({ question: 'What was decided?', meeting_ids: ['m1'] })
  })

  it('sends a suggested question when clicked', async () => {
    mockApi([sse('done', { answer: 'ok', found: false, cited: [], retrieved_chunk_ids: [], latency_ms: 1, query_id: 'q' })])
    renderRoute('/', { '/': <ChatPage /> })

    await userEvent.click(screen.getByRole('button', { name: 'What decisions were made?' }))

    const article = (await screen.findByText('What decisions were made?', { selector: 'div' })).closest('article')!
    expect(within(article).getByText('What decisions were made?')).toBeInTheDocument()
  })
})
