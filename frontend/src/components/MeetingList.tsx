import { useQuery } from '@tanstack/react-query'
import { NavLink } from 'react-router-dom'

import { api } from '@/api/client'
import { StatusBadge } from '@/components/StatusBadge'
import { Skeleton } from '@/components/ui/skeleton'
import { formatDate, meetingLink } from '@/lib/format'
import { cn } from '@/lib/utils'

export function MeetingList() {
  const { data, isPending, error } = useQuery({ queryKey: ['meetings'], queryFn: api.listMeetings })

  return (
    <nav aria-label="Meetings">
      <h2 className="px-2 pb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">Meetings</h2>
      {isPending && (
        <div className="space-y-2 px-2">
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
        </div>
      )}
      {error && <p className="px-2 text-sm text-destructive">Could not load meetings: {error.message}</p>}
      {data?.length === 0 && <p className="px-2 text-sm text-muted-foreground">No meetings yet. Upload a transcript.</p>}
      <ul className="space-y-0.5">
        {data?.map((meeting) => (
          <li key={meeting.id}>
            <NavLink
              to={meetingLink(meeting.id)}
              className={({ isActive }) =>
                cn('block rounded-md px-2 py-2 text-sm', isActive ? 'bg-muted font-medium' : 'hover:bg-muted/60')
              }
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate">{meeting.title}</span>
                <StatusBadge status={meeting.extraction_status} />
              </div>
              <div className="text-xs text-muted-foreground">
                {formatDate(meeting.created_at)} · {meeting.turn_count} turns
              </div>
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}
