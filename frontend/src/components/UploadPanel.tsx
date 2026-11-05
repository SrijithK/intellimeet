import { useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, FileUp, Loader2, XCircle } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '@/api/client'
import { meetingLink } from '@/lib/format'
import { cn } from '@/lib/utils'

const ACCEPT = '.txt,.vtt'

interface Upload {
  key: string
  fileName: string
  jobId?: string
  error?: string
}

export function UploadPanel() {
  const [uploads, setUploads] = useState<Upload[]>([])
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  async function upload(files: FileList | File[]) {
    for (const file of Array.from(files)) {
      const key = `${file.name}-${Date.now()}-${Math.random()}`
      setUploads((current) => [{ key, fileName: file.name }, ...current].slice(0, 5))
      try {
        const { job_id } = await api.uploadMeeting(file)
        setUploads((current) => current.map((u) => (u.key === key ? { ...u, jobId: job_id } : u)))
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Upload failed'
        setUploads((current) => current.map((u) => (u.key === key ? { ...u, error: message } : u)))
      }
    }
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => {
          event.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragging(false)
          if (event.dataTransfer.files.length) void upload(event.dataTransfer.files)
        }}
        className={cn(
          'flex w-full flex-col items-center gap-1 rounded-lg border border-dashed px-3 py-4 text-center text-sm transition-colors',
          dragging ? 'border-primary bg-primary/5' : 'hover:bg-muted/60',
        )}
      >
        <FileUp className="size-5 text-muted-foreground" aria-hidden />
        <span className="font-medium">Upload transcript</span>
        <span className="text-xs text-muted-foreground">Drop .txt or .vtt files, or click to browse</span>
      </button>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        multiple
        hidden
        data-testid="upload-input"
        onChange={(event) => {
          if (event.target.files?.length) void upload(event.target.files)
          event.target.value = ''
        }}
      />
      {uploads.length > 0 && (
        <ul className="mt-2 space-y-1">
          {uploads.map((item) => (
            <UploadRow key={item.key} upload={item} />
          ))}
        </ul>
      )}
    </div>
  )
}

function UploadRow({ upload }: { upload: Upload }) {
  const queryClient = useQueryClient()
  const { data: job } = useQuery({
    queryKey: ['job', upload.jobId],
    queryFn: () => api.getJob(upload.jobId!),
    enabled: Boolean(upload.jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'completed' || status === 'failed' ? false : 1000
    },
  })

  const status = upload.error ? 'failed' : (job?.status ?? 'queued')
  useEffect(() => {
    if (status === 'completed') void queryClient.invalidateQueries({ queryKey: ['meetings'] })
  }, [status, queryClient])

  const error = upload.error ?? job?.error
  const meetingId = job?.result?.meeting_id
  const extractionFailed = job?.result?.extraction_status === 'failed'

  return (
    <li className="flex items-start gap-2 rounded-md px-1 py-1 text-xs">
      {status === 'completed' ? (
        <CheckCircle2 className="mt-px size-3.5 shrink-0 text-emerald-600" aria-label="Completed" />
      ) : status === 'failed' ? (
        <XCircle className="mt-px size-3.5 shrink-0 text-destructive" aria-label="Failed" />
      ) : (
        <Loader2 className="mt-px size-3.5 shrink-0 animate-spin text-muted-foreground" aria-label="Processing" />
      )}
      <div className="min-w-0">
        {meetingId ? (
          <Link to={meetingLink(meetingId)} className="block truncate font-medium hover:underline">
            {upload.fileName}
          </Link>
        ) : (
          <span className="block truncate font-medium">{upload.fileName}</span>
        )}
        {error && <span className="text-destructive">{error}</span>}
        {status === 'processing' && <span className="text-muted-foreground">Parsing, embedding and extracting…</span>}
        {job?.result?.deduplicated && <span className="text-muted-foreground">Already uploaded</span>}
        {extractionFailed && <span className="text-amber-700">Searchable, but extraction failed</span>}
      </div>
    </li>
  )
}
