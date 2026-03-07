import { useEffect, useMemo, useState } from 'react'

const GENERIC_HOSTS = new Set([
  'greenhouse.io',
  'job-boards.greenhouse.io',
  'boards-api.greenhouse.io',
  'lever.co',
  'jobs.lever.co',
  'workdayjobs.com',
  'myworkdayjobs.com',
  'smartrecruiters.com',
  'ashbyhq.com',
])

const DOMAIN_OVERRIDES = {
  '3m': '3m.com',
  aisera: 'aisera.com',
  airtable: 'airtable.com',
  airbnb: 'airbnb.com',
  anthropic: 'anthropic.com',
  atlassian: 'atlassian.com',
  bestbuy: 'bestbuy.com',
  cohere: 'cohere.com',
  datadog: 'datadoghq.com',
  deloitte: 'deloitte.com',
  medtronic: 'medtronic.com',
  miro: 'miro.com',
  openai: 'openai.com',
  postman: 'postman.com',
  servicenow: 'servicenow.com',
  smartsheet: 'smartsheet.com',
  target: 'target.com',
  unitedhealth: 'unitedhealthgroup.com',
  writer: 'writer.com',
}

const MONOGRAM_ONLY_SLUGS = new Set(['optum'])

function parseHostname(value) {
  const raw = String(value || '').trim()
  if (!raw) {
    return ''
  }
  try {
    return new URL(raw).hostname.replace(/^www\./, '').toLowerCase()
  } catch {
    return raw.replace(/^www\./, '').toLowerCase()
  }
}

function normalizeSlug(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/&/g, 'and')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

function companySlug(company) {
  return normalizeSlug(company.company_id || company.company_name)
}

function monogram(company) {
  return (
    company.monogram ||
    String(company.company_name || '')
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0])
      .join('')
      .toUpperCase() ||
    '?'
  )
}

function sourceLooksGeneric(url) {
  const host = parseHostname(url)
  if (!host) {
    return false
  }

  if (host === 'logo.clearbit.com') {
    return true
  }

  if (GENERIC_HOSTS.has(host)) {
    return true
  }

  try {
    const parsed = new URL(url)
    const nested = parseHostname(parsed.searchParams.get('url') || parsed.searchParams.get('domain'))
    if (nested && GENERIC_HOSTS.has(nested)) {
      return true
    }
  } catch {
    return false
  }

  return false
}

function inferredCompanyDomain(company) {
  const overrideDomain = DOMAIN_OVERRIDES[companySlug(company)]
  if (overrideDomain) {
    return overrideDomain
  }

  const storedDomain = parseHostname(company.domain)
  if (storedDomain && !GENERIC_HOSTS.has(storedDomain)) {
    return storedDomain
  }

  const careersHost = parseHostname(company.careers_url || company.url)
  if (careersHost && !GENERIC_HOSTS.has(careersHost)) {
    return careersHost
  }

  const slug = normalizeSlug(company.company_id || company.company_name)
  return slug ? `${slug}.com` : ''
}

function candidateLogos(company) {
  if (MONOGRAM_ONLY_SLUGS.has(companySlug(company))) {
    return []
  }

  const guessedDomain = inferredCompanyDomain(company)
  const explicitLogo = String(company.logo_url || '').trim()
  const explicitFavicon = String(company.favicon_url || '').trim()
  const urls = []

  if (explicitLogo && !sourceLooksGeneric(explicitLogo)) {
    urls.push(explicitLogo)
  }
  if (explicitFavicon && !sourceLooksGeneric(explicitFavicon)) {
    urls.push(explicitFavicon)
  }

  if (guessedDomain) {
    urls.push(`https://www.google.com/s2/favicons?domain=${guessedDomain}&sz=128`)
  }

  return Array.from(new Set(urls.filter(Boolean)))
}

export default function CompanyLogo({ company, className = 'company-logo' }) {
  const sources = useMemo(() => candidateLogos(company), [company])
  const [index, setIndex] = useState(0)

  useEffect(() => {
    setIndex(0)
  }, [sources])

  const source = sources[index] || ''
  if (source) {
    return (
      <img
        className={className}
        src={source}
        alt={`${company.company_name} logo`}
        loading="lazy"
        referrerPolicy="no-referrer"
        onError={() => setIndex((current) => current + 1)}
      />
    )
  }

  return <div className={`${className} mono`}>{monogram(company)}</div>
}
