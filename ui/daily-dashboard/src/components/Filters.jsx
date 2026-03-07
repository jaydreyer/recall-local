const SCORE_OPTIONS = [
  { value: 'all', label: 'All scores' },
  { value: '75-plus', label: '75+' },
  { value: '50-74', label: '50-74' },
  { value: 'under-50', label: 'Under 50' },
]

const SOURCE_OPTIONS = [
  { value: '', label: 'All sources' },
  { value: 'jobspy', label: 'JobSpy' },
  { value: 'career_page', label: 'Career Pages' },
  { value: 'chrome_extension', label: 'Chrome Extension' },
]

const TIER_OPTIONS = [
  { value: '', label: 'All tiers' },
  { value: '1', label: 'Tier 1' },
  { value: '2', label: 'Tier 2' },
  { value: '3', label: 'Tier 3' },
]

const STATUS_OPTIONS = [
  { value: 'all', label: 'All statuses' },
  { value: 'new', label: 'New' },
  { value: 'evaluated', label: 'Evaluated' },
  { value: 'applied', label: 'Applied' },
  { value: 'dismissed', label: 'Dismissed' },
]

function FilterSelect({ label, value, options, onChange }) {
  return (
    <label className="filter-field">
      <span className="filter-label">{label}</span>
      <select className="filter-select" value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => (
          <option key={option.label} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  )
}

export default function Filters({ filters, onChange }) {
  return (
    <section className="filters-bar">
      <FilterSelect label="Score range" value={filters.scoreRange} options={SCORE_OPTIONS} onChange={(value) => onChange('scoreRange', value)} />
      <FilterSelect label="Source" value={filters.source} options={SOURCE_OPTIONS} onChange={(value) => onChange('source', value)} />
      <FilterSelect label="Company tier" value={filters.companyTier} options={TIER_OPTIONS} onChange={(value) => onChange('companyTier', value)} />
      <FilterSelect label="Status" value={filters.status} options={STATUS_OPTIONS} onChange={(value) => onChange('status', value)} />
    </section>
  )
}
