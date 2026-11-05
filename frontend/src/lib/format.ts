export function formatTimestamp(seconds: number): string {
  const total = Math.floor(seconds)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(Math.floor(total / 3600))}:${pad(Math.floor((total % 3600) / 60))}:${pad(total % 60)}`
}

export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(iso))
}

export function meetingLink(meetingId: string, turnIdx?: number): string {
  const base = `/meetings/${encodeURIComponent(meetingId)}`
  return turnIdx === undefined ? base : `${base}?turn=${turnIdx}`
}
