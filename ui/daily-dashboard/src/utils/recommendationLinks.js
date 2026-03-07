const SEARCH_URLS = [
  { match: 'coursera', url: 'https://www.coursera.org/search?query=' },
  { match: 'edx', url: 'https://www.edx.org/search?q=' },
  { match: 'udemy', url: 'https://www.udemy.com/courses/search/?q=' },
  { match: 'pluralsight', url: 'https://www.pluralsight.com/search?q=' },
  { match: 'kodekloud', url: 'https://kodekloud.com/courses/?search=' },
  { match: 'aws', url: 'https://skillbuilder.aws/search?query=' },
  { match: 'youtube', url: 'https://www.youtube.com/results?search_query=' },
  { match: 'stanford', url: 'https://online.stanford.edu/search-catalog?keywords=' },
  { match: 'mit', url: 'https://ocw.mit.edu/search/?q=' },
  { match: 'amazon web services', url: 'https://skillbuilder.aws/search?query=' },
]

function encodedQuery(recommendation) {
  return encodeURIComponent(
    [recommendation?.title || '', recommendation?.source || ''].join(' ').trim()
  )
}

export function recommendationUrl(recommendation) {
  const raw = String(recommendation?.url || recommendation?.source || '').trim()
  if (/^https?:\/\//i.test(raw)) {
    return raw
  }

  const query = encodedQuery(recommendation)
  if (!query) {
    return ''
  }

  const source = String(recommendation?.source || '').toLowerCase()
  const matched = SEARCH_URLS.find((entry) => source.includes(entry.match))
  if (matched) {
    return `${matched.url}${query}`
  }

  return `https://www.google.com/search?q=${query}`
}
