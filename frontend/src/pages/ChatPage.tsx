import { useQuery } from '@tanstack/react-query'
import { AlertCircle, ArrowUp, Loader2, SearchX } from 'lucide-react'
import { type FormEvent, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { api } from '@/api/client'
import { AnswerText, CitationLink } from '@/components/AnswerText'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { type ChatExchange, useChat } from '@/hooks/useChat'

const ALL = 'all'
const SUGGESTIONS = [
  'What decisions were made?',
  'What action items are open, and who owns them?',
  'When is the launch, and why did it move?',
]

export function ChatPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const scope = searchParams.get('meeting') ?? ALL
  const { data: meetings } = useQuery({ queryKey: ['meetings'], queryFn: api.listMeetings })
  const { exchanges, ask, isStreaming } = useChat()
  const [question, setQuestion] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  const lastAnswer = exchanges.at(-1)?.answer
  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ block: 'end' })
  }, [exchanges.length, lastAnswer])

  function submit(text: string) {
    const trimmed = text.trim()
    if (!trimmed || isStreaming) return
    setQuestion('')
    void ask({ question: trimmed, meeting_ids: scope === ALL ? null : [scope] })
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    submit(question)
  }

  return (
    <div className="mx-auto flex min-h-full max-w-3xl flex-col px-4 py-6">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Ask about your meetings</h1>
          <p className="text-sm text-muted-foreground">Answers come only from the transcripts, with sources.</p>
        </div>
        <Select
          value={scope}
          onValueChange={(value) => setSearchParams(value === ALL ? {} : { meeting: value })}
        >
          <SelectTrigger className="w-56" aria-label="Meetings to search">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All meetings</SelectItem>
            {meetings?.map((meeting) => (
              <SelectItem key={meeting.id} value={meeting.id}>
                {meeting.title}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </header>

      <div className="flex-1 space-y-8">
        {exchanges.length === 0 && (
          <div className="rounded-lg border border-dashed p-6 text-center">
            <p className="mb-3 text-sm text-muted-foreground">Try asking:</p>
            <div className="flex flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((suggestion) => (
                <Button key={suggestion} variant="outline" size="sm" onClick={() => submit(suggestion)}>
                  {suggestion}
                </Button>
              ))}
            </div>
          </div>
        )}
        {exchanges.map((exchange) => (
          <Exchange key={exchange.id} exchange={exchange} />
        ))}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={onSubmit} className="sticky bottom-0 mt-6 bg-background pt-2 pb-1">
        <div className="relative">
          <Textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                submit(question)
              }
            }}
            placeholder="Ask a question about your meetings…"
            aria-label="Question"
            rows={2}
            maxLength={2000}
            className="resize-none pr-12"
          />
          <Button
            type="submit"
            size="icon"
            className="absolute right-2 bottom-2"
            disabled={!question.trim() || isStreaming}
            aria-label="Send"
          >
            {isStreaming ? <Loader2 className="animate-spin" /> : <ArrowUp />}
          </Button>
        </div>
      </form>
    </div>
  )
}

function Exchange({ exchange }: { exchange: ChatExchange }) {
  const waiting = exchange.status === 'streaming' && !exchange.answer
  return (
    <article className="space-y-3">
      <div className="ml-auto w-fit max-w-[85%] rounded-2xl bg-primary px-4 py-2 text-primary-foreground">
        {exchange.question}
      </div>
      <div className="space-y-3">
        {waiting && (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" /> Searching transcripts…
          </p>
        )}
        {exchange.found === false && exchange.status === 'done' ? (
          <p className="flex items-center gap-2 text-muted-foreground">
            <SearchX className="size-4 shrink-0" aria-hidden />
            {exchange.answer}
          </p>
        ) : (
          exchange.answer && <AnswerText text={exchange.answer} sources={exchange.sources} />
        )}
        {exchange.status === 'error' && (
          <p className="flex items-center gap-2 text-sm text-destructive" role="alert">
            <AlertCircle className="size-4 shrink-0" aria-hidden />
            {exchange.error}
          </p>
        )}
        {exchange.cited.length > 0 && (
          <details className="text-sm">
            <summary className="cursor-pointer text-muted-foreground select-none">
              {exchange.cited.length} source{exchange.cited.length > 1 ? 's' : ''}
            </summary>
            <ul className="mt-2 space-y-2 border-l pl-3">
              {exchange.cited.map((source) => (
                <li key={source.ref}>
                  <CitationLink source={source} />
                  <p className="mt-1 text-muted-foreground">“{source.text}”</p>
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </article>
  )
}
