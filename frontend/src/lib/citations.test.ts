import { SOURCE } from '@/test/utils'

import { splitCitations } from './citations'

describe('splitCitations', () => {
  it('turns known citations into citation segments', () => {
    const segments = splitCitations('Launch moves [planning, 00:01:44, Priya]. Done.', [SOURCE])

    expect(segments).toEqual([
      { kind: 'text', text: 'Launch moves ' },
      { kind: 'citation', text: '[planning, 00:01:44, Priya]', source: SOURCE },
      { kind: 'text', text: '. Done.' },
    ])
  })

  it('leaves unknown citation-like text and other brackets as text', () => {
    const text = 'See [other, 00:00:01, Bob] and [draft].'

    expect(splitCitations(text, [SOURCE])).toEqual([{ kind: 'text', text }])
  })

  it('handles adjacent citations and empty text', () => {
    const two = '[planning, 00:01:44, Priya][planning, 00:01:44, Priya]'

    expect(splitCitations(two, [SOURCE]).map((s) => s.kind)).toEqual(['citation', 'citation'])
    expect(splitCitations('', [SOURCE])).toEqual([])
  })
})
