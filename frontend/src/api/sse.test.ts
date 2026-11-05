import { streamResponse } from '@/test/utils'

import { readSSE } from './sse'

async function collect(chunks: string[]) {
  const out = []
  for await (const message of readSSE(streamResponse(chunks).body!)) out.push(message)
  return out
}

describe('readSSE', () => {
  it('parses events split at arbitrary points across chunks', async () => {
    const messages = await collect(['event: tok', 'en\ndata: {"text"', ': "Hi"}\n', '\nevent: done\ndata: {}\n\n'])

    expect(messages).toEqual([
      { event: 'token', data: '{"text": "Hi"}' },
      { event: 'done', data: '{}' },
    ])
  })

  it('handles CRLF, comments, multi-line data and a missing final blank line', async () => {
    const messages = await collect([': keep-alive\r\n\r\ndata: line one\r\ndata: line two\r\n\r\nevent: done\ndata: x'])

    expect(messages).toEqual([
      { event: 'message', data: 'line one\nline two' },
      { event: 'done', data: 'x' },
    ])
  })

  it('keeps multi-byte characters that straddle chunks', async () => {
    const bytes = new TextEncoder().encode('data: café ☕\n\n')
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(bytes.slice(0, 10)) // splits the "é"
        controller.enqueue(bytes.slice(10))
        controller.close()
      },
    })
    const out = []
    for await (const message of readSSE(body)) out.push(message)

    expect(out).toEqual([{ event: 'message', data: 'café ☕' }])
  })
})
