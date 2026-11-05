import { Badge } from '@/components/ui/badge'

const LABELS: Record<string, { label: string; variant: 'secondary' | 'destructive' | 'outline' }> = {
  queued: { label: 'Queued', variant: 'outline' },
  processing: { label: 'Processing', variant: 'outline' },
  pending: { label: 'Extracting', variant: 'outline' },
  failed: { label: 'Failed', variant: 'destructive' },
  skipped: { label: 'No extraction', variant: 'secondary' },
}

/** Shows only non-happy states; a completed item needs no badge. */
export function StatusBadge({ status, title }: { status: string; title?: string }) {
  const entry = LABELS[status]
  if (!entry) return null
  return (
    <Badge variant={entry.variant} title={title}>
      {entry.label}
    </Badge>
  )
}
