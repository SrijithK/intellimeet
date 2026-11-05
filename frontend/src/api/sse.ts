export interface SSEMessage {
  event: string
  data: string
}

/**
 * Parse a Server-Sent Events stream. EventSource only supports GET, and /api/chat is a POST,
 * so we read the fetch body ourselves. Network chunks can split events anywhere.
 */
export async function* readSSE(stream: ReadableStream<Uint8Array>): AsyncGenerator<SSEMessage> {
  const reader = stream.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      // stream: true keeps multi-byte characters that straddle chunks intact
      buffer = (buffer + decoder.decode(value, { stream: true })).replace(/\r\n?/g, '\n')
      let boundary: number
      while ((boundary = buffer.indexOf('\n\n')) !== -1) {
        const message = parseBlock(buffer.slice(0, boundary))
        buffer = buffer.slice(boundary + 2)
        if (message) yield message
      }
    }
    const last = parseBlock(buffer + decoder.decode())
    if (last) yield last
  } finally {
    reader.releaseLock()
  }
}

function parseBlock(block: string): SSEMessage | null {
  let event = 'message'
  const data: string[] = []
  for (const line of block.split('\n')) {
    if (!line || line.startsWith(':')) continue
    const colon = line.indexOf(':')
    const field = colon === -1 ? line : line.slice(0, colon)
    const value = colon === -1 ? '' : line.slice(colon + 1).replace(/^ /, '')
    if (field === 'event') event = value
    else if (field === 'data') data.push(value)
  }
  return data.length ? { event, data: data.join('\n') } : null
}
