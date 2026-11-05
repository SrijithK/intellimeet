import type { CitationSource } from '@/api/types'

export type Segment = { kind: 'text'; text: string } | { kind: 'citation'; text: string; source: CitationSource }

// The server renders citations as "[meeting title, hh:mm:ss, speaker]".
const CITATION_RE = /\[[^[\]]+?, \d{2}:\d{2}:\d{2}, [^[\]]+?\]/g

/** Split answer text into plain text and citations that link to a known source. */
export function splitCitations(text: string, sources: CitationSource[]): Segment[] {
  const byCitation = new Map(sources.map((source) => [source.citation, source]))
  const segments: Segment[] = []
  let last = 0
  for (const match of text.matchAll(CITATION_RE)) {
    const source = byCitation.get(match[0])
    if (!source) continue // looks like a citation but isn't one of ours: leave as text
    if (match.index > last) segments.push({ kind: 'text', text: text.slice(last, match.index) })
    segments.push({ kind: 'citation', text: match[0], source })
    last = match.index + match[0].length
  }
  if (last < text.length) segments.push({ kind: 'text', text: text.slice(last) })
  return segments
}
