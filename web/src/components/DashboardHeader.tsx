import { formatDate } from '../utils/format'

export function DashboardHeader({ latestDate }: { latestDate?: string | null }) {
  return (
    <header className="site-header">
      <a className="brand" href="/" aria-label="LakArthika home">
        <span className="brand-mark" aria-hidden="true">LA</span>
        <span>
          <strong>LakArthika</strong>
          <small>ආර්ථික දත්ත · Economic evidence</small>
        </span>
      </a>
      <div className="header-status">
        <span className="pulse-dot" aria-hidden="true" />
        <span>{latestDate ? `Data through ${formatDate(latestDate)}` : 'Connecting to data'}</span>
      </div>
    </header>
  )
}
