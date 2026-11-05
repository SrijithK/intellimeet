import { Link } from 'react-router-dom'

import type { CitationSource } from '@/api/types'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { splitCitations } from '@/lib/citations'
import { meetingLink } from '@/lib/format'

/** Answer text with `[meeting, hh:mm:ss, speaker]` citations turned into links to the transcript line. */
export function AnswerText({ text, sources }: { text: string; sources: CitationSource[] }) {
  return (
    <p className="leading-relaxed whitespace-pre-wrap">
      {splitCitations(text, sources).map((segment, i) =>
        segment.kind === 'text' ? (
          <span key={i}>{segment.text}</span>
        ) : (
          <CitationLink key={i} source={segment.source} />
        ),
      )}
    </p>
  )
}

export function CitationLink({ source }: { source: CitationSource }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Link
          to={meetingLink(source.meeting_id, source.turn_idx)}
          className="mx-0.5 inline-flex items-center rounded border bg-muted px-1.5 py-px align-baseline text-xs font-medium text-foreground no-underline hover:border-primary hover:bg-primary/5"
          aria-label={`Source: ${source.meeting_title} at ${source.timestamp}, ${source.speaker}`}
        >
          {source.meeting_title} · {source.timestamp} · {source.speaker}
        </Link>
      </TooltipTrigger>
      <TooltipContent className="max-w-sm">
        <span className="font-medium">{source.speaker}:</span> {source.text}
      </TooltipContent>
    </Tooltip>
  )
}
