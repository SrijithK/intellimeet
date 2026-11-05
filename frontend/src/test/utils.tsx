import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import type { CitationSource } from '@/api/types'
import { TooltipProvider } from '@/components/ui/tooltip'

export function renderRoute(path: string, routes: Record<string, ReactElement>) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <TooltipProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            {Object.entries(routes).map(([routePath, element]) => (
              <Route key={routePath} path={routePath} element={element} />
            ))}
          </Routes>
        </MemoryRouter>
      </TooltipProvider>
    </QueryClientProvider>,
  )
}

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

/** A streamed SSE response; each string is delivered as its own network chunk. */
export function streamResponse(chunks: string[]): Response {
  const encoder = new TextEncoder()
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
      controller.close()
    },
  })
  return new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
}

export const sse = (event: string, data: unknown) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`

export const SOURCE: CitationSource = {
  ref: 1,
  meeting_id: 'm1',
  meeting_title: 'planning',
  turn_idx: 3,
  speaker: 'Priya',
  start: 104,
  text: 'The launch moves to November 17th.',
  timestamp: '00:01:44',
  citation: '[planning, 00:01:44, Priya]',
}
