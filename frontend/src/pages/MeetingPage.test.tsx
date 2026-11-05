import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import type { MeetingDetail } from '@/api/types'
import { jsonResponse, renderRoute } from '@/test/utils'

import { MeetingPage } from './MeetingPage'

const MEETING: MeetingDetail = {
  id: 'm1',
  title: 'planning',
  source_name: 'planning.txt',
  source_type: 'txt',
  created_at: '2026-11-05T10:00:00Z',
  extraction_status: 'completed',
  extraction_error: null,
  media_uri: null,
  turn_count: 2,
  chunk_count: 1,
  decisions: [{ text: 'Launch moves to November 17th', turn_idx: 0, speaker: 'Priya', start: 104 }],
  action_items: [{ owner: 'Dana', task: 'Update the press release', due: 'by Wednesday', turn_idx: 1, speaker: 'Dana', start: 121 }],
  topics: [{ label: 'Launch date', turn_idx: 0, speaker: 'Priya', start: 104 }],
  turns: [
    { idx: 0, speaker: 'Priya', text: 'The launch moves to November 17th.', start: 104, end: null },
    { idx: 1, speaker: 'Dana', text: "I'll update the press release by Wednesday.", start: 121, end: null },
  ],
}

afterEach(() => vi.unstubAllGlobals())

function mockMeeting(meeting: MeetingDetail | null) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => (meeting ? jsonResponse(meeting) : jsonResponse({ detail: 'Meeting m1 not found' }, 404))),
  )
}

describe('MeetingPage', () => {
  it('shows extracted records and the transcript', async () => {
    mockMeeting(MEETING)
    renderRoute('/meetings/m1', { '/meetings/:meetingId': <MeetingPage /> })

    expect(await screen.findByRole('heading', { name: 'planning' })).toBeInTheDocument()
    expect(screen.getByText('Launch moves to November 17th')).toBeInTheDocument()
    expect(screen.getByText(/Update the press release/)).toBeInTheDocument()
    expect(screen.getByText(/due by Wednesday/)).toBeInTheDocument()
    expect(screen.getByText("I'll update the press release by Wednesday.")).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Ask about this meeting/ })).toHaveAttribute('href', '/?meeting=m1')
  })

  it('highlights the cited turn from the URL', async () => {
    mockMeeting(MEETING)
    renderRoute('/meetings/m1?turn=1', { '/meetings/:meetingId': <MeetingPage /> })

    const turn = (await screen.findByText("I'll update the press release by Wednesday.")).closest('li')!
    expect(turn).toHaveAttribute('aria-current', 'true')
  })

  it('jumps to the source turn when an extracted record is clicked', async () => {
    mockMeeting(MEETING)
    renderRoute('/meetings/m1', { '/meetings/:meetingId': <MeetingPage /> })

    await userEvent.click(await screen.findByText('Launch moves to November 17th'))

    const turn = screen.getByText('The launch moves to November 17th.').closest('li')!
    expect(turn).toHaveAttribute('aria-current', 'true')
  })

  it('explains failed extraction and still shows the transcript', async () => {
    mockMeeting({ ...MEETING, extraction_status: 'failed', extraction_error: 'Could not reach Ollama', decisions: [], action_items: [], topics: [] })
    renderRoute('/meetings/m1', { '/meetings/:meetingId': <MeetingPage /> })

    expect(await screen.findByText(/Extraction failed: Could not reach Ollama/)).toBeInTheDocument()
    expect(screen.getByText('The launch moves to November 17th.')).toBeInTheDocument()
  })

  it('shows not found for an unknown meeting', async () => {
    mockMeeting(null)
    renderRoute('/meetings/m1', { '/meetings/:meetingId': <MeetingPage /> })

    expect(await screen.findByText('This meeting does not exist.')).toBeInTheDocument()
  })
})
