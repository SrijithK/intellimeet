import { MessagesSquare } from 'lucide-react'
import { Link, NavLink, Outlet } from 'react-router-dom'

import { MeetingList } from '@/components/MeetingList'
import { UploadPanel } from '@/components/UploadPanel'
import { cn } from '@/lib/utils'

export function Layout() {
  return (
    <div className="flex min-h-svh flex-col bg-background text-foreground lg:h-svh lg:flex-row">
      <aside className="flex shrink-0 flex-col border-b bg-muted/30 lg:w-80 lg:border-r lg:border-b-0">
        <div className="flex items-center justify-between px-4 py-4">
          <Link to="/" className="text-lg font-semibold tracking-tight">
            IntelliMeet
          </Link>
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              cn(
                'inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm font-medium',
                isActive ? 'bg-primary text-primary-foreground' : 'hover:bg-muted',
              )
            }
          >
            <MessagesSquare className="size-4" aria-hidden />
            Ask
          </NavLink>
        </div>
        <div className="px-4 pb-4">
          <UploadPanel />
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-4">
          <MeetingList />
        </div>
      </aside>
      <main className="min-w-0 flex-1 lg:overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
