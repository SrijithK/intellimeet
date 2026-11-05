import { useQuery } from '@tanstack/react-query'
import { MessagesSquare } from 'lucide-react'
import { type ReactNode, useEffect, useRef } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'

import { ApiError, api } from '@/api/client'
import type { MeetingDetail, Turn } from '@/api/types'
import { StatusBadge } from '@/components/StatusBadge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { formatDate, formatTimestamp } from '@/lib/format'
import { cn } from '@/lib/utils'

export function MeetingPage() {
  const { meetingId = '' } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const turnParam = searchParams.get('turn')
  const selectedTurn = turnParam === null ? null : Number(turnParam)

  const { data: meeting, isPending, error } = useQuery({
    queryKey: ['meeting', meetingId],
    queryFn: () => api.getMeeting(meetingId),
    // Extraction runs after the meeting is saved; keep polling until it settles.
    refetchInterval: (query) => (query.state.data?.extraction_status === 'pending' ? 2000 : false),
  })

  const selectTurn = (idx: number) => setSearchParams({ turn: String(idx) }, { replace: true })

  if (isPending) {
    return (
      <div className="space-y-4 p-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40" />
        <Skeleton className="h-96" />
      </div>
    )
  }
  if (error) {
    const notFound = error instanceof ApiError && error.status === 404
    return (
      <div className="p-6">
        <p className="text-destructive">{notFound ? 'This meeting does not exist.' : error.message}</p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 px-4 py-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">{meeting.title}</h1>
          <p className="text-sm text-muted-foreground">
            {meeting.source_name} · uploaded {formatDate(meeting.created_at)} · {meeting.turn_count} turns
          </p>
        </div>
        <Button asChild variant="outline" size="sm">
          <Link to={`/?meeting=${encodeURIComponent(meeting.id)}`}>
            <MessagesSquare /> Ask about this meeting
          </Link>
        </Button>
      </header>

      <ExtractionSummary meeting={meeting} onSelectTurn={selectTurn} />

      <Card>
        <CardHeader>
          <CardTitle>Transcript</CardTitle>
        </CardHeader>
        <CardContent>
          <Transcript turns={meeting.turns} selected={selectedTurn} onSelect={selectTurn} />
        </CardContent>
      </Card>
    </div>
  )
}

function ExtractionSummary({ meeting, onSelectTurn }: { meeting: MeetingDetail; onSelectTurn: (idx: number) => void }) {
  if (meeting.extraction_status !== 'completed') {
    const message = {
      pending: 'Extracting decisions, action items and topics…',
      failed: `Extraction failed${meeting.extraction_error ? `: ${meeting.extraction_error}` : ''}. The transcript is still searchable.`,
      skipped: 'Extraction is disabled. The transcript is still searchable.',
    }[meeting.extraction_status]
    return (
      <div className="flex items-center gap-2 rounded-lg border p-3 text-sm text-muted-foreground">
        <StatusBadge status={meeting.extraction_status} />
        {message}
      </div>
    )
  }

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Section title="Decisions" empty="No decisions recorded." count={meeting.decisions.length}>
        {meeting.decisions.map((decision) => (
          <SourceItem key={`${decision.turn_idx}-${decision.text}`} start={decision.start} onClick={() => onSelectTurn(decision.turn_idx)}>
            {decision.text}
          </SourceItem>
        ))}
      </Section>
      <Section title="Action items" empty="No action items recorded." count={meeting.action_items.length}>
        {meeting.action_items.map((item) => (
          <SourceItem key={`${item.turn_idx}-${item.task}`} start={item.start} onClick={() => onSelectTurn(item.turn_idx)}>
            <span className="font-medium">{item.owner}</span>: {item.task}
            {item.due && <span className="text-muted-foreground"> · due {item.due}</span>}
          </SourceItem>
        ))}
      </Section>
      {meeting.topics.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 md:col-span-2">
          <span className="text-sm text-muted-foreground">Topics:</span>
          {meeting.topics.map((topic) => (
            <button key={topic.label} type="button" onClick={() => onSelectTurn(topic.turn_idx)}>
              <Badge variant="secondary" className="cursor-pointer hover:bg-secondary/70">
                {topic.label}
              </Badge>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function Section({ title, empty, count, children }: { title: string; empty: string; count: number; children: ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {title} <span className="font-normal text-muted-foreground">({count})</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {count === 0 ? <p className="text-sm text-muted-foreground">{empty}</p> : <ul className="space-y-1">{children}</ul>}
      </CardContent>
    </Card>
  )
}

function SourceItem({ start, onClick, children }: { start: number; onClick: () => void; children: ReactNode }) {
  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        className="flex w-full gap-3 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted"
        title="Show in transcript"
      >
        <span className="shrink-0 font-mono text-xs leading-5 text-muted-foreground">{formatTimestamp(start)}</span>
        <span>{children}</span>
      </button>
    </li>
  )
}

function Transcript({ turns, selected, onSelect }: { turns: Turn[]; selected: number | null; onSelect: (idx: number) => void }) {
  const selectedRef = useRef<HTMLLIElement>(null)
  useEffect(() => {
    selectedRef.current?.scrollIntoView?.({ block: 'center', behavior: 'smooth' })
  }, [selected])

  return (
    <ol className="space-y-1">
      {turns.map((turn) => {
        const isSelected = turn.idx === selected
        return (
          <li
            key={turn.idx}
            id={`turn-${turn.idx}`}
            ref={isSelected ? selectedRef : undefined}
            aria-current={isSelected ? 'true' : undefined}
            className={cn(
              'grid grid-cols-[4.5rem_1fr] items-start gap-3 rounded-md px-2 py-1.5 text-sm transition-colors',
              isSelected && 'bg-amber-100 ring-1 ring-amber-300 dark:bg-amber-500/15 dark:ring-amber-500/40',
            )}
          >
            <button
              type="button"
              onClick={() => onSelect(turn.idx)}
              className="text-left font-mono text-xs leading-5 text-muted-foreground hover:text-foreground"
              aria-label={`Link to ${formatTimestamp(turn.start)}`}
            >
              {formatTimestamp(turn.start)}
            </button>
            <p>
              <span className="font-medium">{turn.speaker}: </span>
              {turn.text}
            </p>
          </li>
        )
      })}
    </ol>
  )
}
