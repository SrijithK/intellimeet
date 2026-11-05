import { useCallback, useEffect, useRef, useState } from 'react'

import { streamChat } from '@/api/client'
import type { ChatRequest, CitationSource } from '@/api/types'

export interface ChatExchange {
  id: string
  question: string
  answer: string
  sources: CitationSource[] // everything the answer may cite (for rendering citation links)
  cited: CitationSource[] // what it did cite (filled in when done)
  status: 'streaming' | 'done' | 'error'
  found?: boolean
  error?: string
}

/** Question/answer history. Each question is answered independently by the API. */
export function useChat() {
  const [exchanges, setExchanges] = useState<ChatExchange[]>([])
  const controller = useRef<AbortController | null>(null)

  useEffect(() => () => controller.current?.abort(), [])

  const update = (id: string, change: (exchange: ChatExchange) => Partial<ChatExchange>) =>
    setExchanges((current) => current.map((e) => (e.id === id ? { ...e, ...change(e) } : e)))

  const ask = useCallback(async (request: ChatRequest) => {
    controller.current?.abort()
    const abort = new AbortController()
    controller.current = abort
    const id = crypto.randomUUID()
    setExchanges((current) => [
      ...current,
      { id, question: request.question, answer: '', sources: [], cited: [], status: 'streaming' },
    ])

    try {
      await streamChat(
        request,
        {
          onCitations: ({ sources }) => update(id, () => ({ sources })),
          onToken: (text) => update(id, (e) => ({ answer: e.answer + text })),
          onDone: (done) => update(id, () => ({ answer: done.answer, cited: done.cited, found: done.found, status: 'done' })),
        },
        abort.signal,
      )
      // A stream that ends without `done` (e.g. connection dropped) should not spin forever.
      update(id, (e) => (e.status === 'streaming' ? { status: 'error', error: 'The answer was cut off.' } : {}))
    } catch (error) {
      if (abort.signal.aborted) return
      update(id, () => ({ status: 'error', error: error instanceof Error ? error.message : 'Something went wrong' }))
    }
  }, [])

  const isStreaming = exchanges.some((e) => e.status === 'streaming')
  return { exchanges, ask, isStreaming, clear: () => setExchanges([]) }
}
