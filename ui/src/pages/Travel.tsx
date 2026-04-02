import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchFlights, fetchGaFlights, fetchRailJourneys } from '../api/transport'

type Tab = 'flights' | 'ga' | 'rail'

function formatDate(d: string) {
  return new Date(d + 'T00:00:00').toLocaleDateString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric',
  })
}

function formatTime(t: string | null) {
  if (!t) return ''
  return String(t).slice(0, 5)
}

function YearFilter({ years, selected, onChange }: {
  years: { year: number; count: number }[]
  selected: number | undefined
  onChange: (y: number | undefined) => void
}) {
  return (
    <div className="flex flex-wrap gap-1.5 mb-4">
      <button
        className={`px-2 py-1 text-xs rounded ${
          !selected ? 'bg-accent text-white' : 'bg-bg-secondary text-text-secondary hover:bg-bg-hover'
        }`}
        onClick={() => onChange(undefined)}
      >
        All
      </button>
      {years.map(y => (
        <button
          key={y.year}
          className={`px-2 py-1 text-xs rounded ${
            selected === y.year ? 'bg-accent text-white' : 'bg-bg-secondary text-text-secondary hover:bg-bg-hover'
          }`}
          onClick={() => onChange(y.year)}
        >
          {y.year} ({y.count})
        </button>
      ))}
    </div>
  )
}

function FlightsTab() {
  const [year, setYear] = useState<number | undefined>()
  const { data, isLoading } = useQuery({
    queryKey: ['flights', year],
    queryFn: () => fetchFlights(year),
  })

  if (isLoading) return <div className="text-text-secondary text-sm">Loading...</div>
  const flights = data?.items ?? []

  return (
    <>
      <YearFilter years={data?.years ?? []} selected={year} onChange={setYear} />
      <div className="text-xs text-text-secondary mb-3">{data?.total ?? 0} flights</div>
      <div className="bg-bg-card border border-border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-bg-secondary">
              <th className="text-left px-3 py-2 text-xs text-text-secondary font-medium">Date</th>
              <th className="text-left px-3 py-2 text-xs text-text-secondary font-medium">Route</th>
              <th className="text-left px-3 py-2 text-xs text-text-secondary font-medium">Flight</th>
              <th className="text-left px-3 py-2 text-xs text-text-secondary font-medium">Airline</th>
              <th className="text-left px-3 py-2 text-xs text-text-secondary font-medium">Aircraft</th>
              <th className="text-left px-3 py-2 text-xs text-text-secondary font-medium">Time</th>
              <th className="text-right px-3 py-2 text-xs text-text-secondary font-medium">Dist</th>
            </tr>
          </thead>
          <tbody>
            {flights.map(f => (
              <tr key={f.id} className="border-b border-border last:border-0 hover:bg-bg-hover">
                <td className="px-3 py-2 text-text-secondary text-xs whitespace-nowrap">{formatDate(f.date)}</td>
                <td className="px-3 py-2 font-medium text-text-primary">
                  {f.dep_airport} → {f.arr_airport}
                </td>
                <td className="px-3 py-2 text-text-secondary">{f.flight_number || '—'}</td>
                <td className="px-3 py-2 text-text-secondary">{f.airline || '—'}</td>
                <td className="px-3 py-2 text-text-secondary">{f.aircraft_type || '—'}</td>
                <td className="px-3 py-2 text-text-secondary text-xs">
                  {formatTime(f.dep_time)}{f.dep_time && f.arr_time ? `–${formatTime(f.arr_time)}` : ''}
                </td>
                <td className="px-3 py-2 text-text-secondary text-right text-xs">
                  {f.distance_km ? `${f.distance_km.toLocaleString()} km` : ''}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {flights.length === 0 && (
          <div className="text-center text-text-secondary py-8">No flights found</div>
        )}
      </div>
    </>
  )
}

function GaFlightsTab() {
  const [year, setYear] = useState<number | undefined>()
  const { data, isLoading } = useQuery({
    queryKey: ['ga-flights', year],
    queryFn: () => fetchGaFlights(year),
  })

  if (isLoading) return <div className="text-text-secondary text-sm">Loading...</div>
  const flights = data?.items ?? []

  return (
    <>
      <YearFilter years={data?.years ?? []} selected={year} onChange={setYear} />
      <div className="text-xs text-text-secondary mb-3">{data?.total ?? 0} GA flights</div>
      <div className="bg-bg-card border border-border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-bg-secondary">
              <th className="text-left px-3 py-2 text-xs text-text-secondary font-medium">Date</th>
              <th className="text-left px-3 py-2 text-xs text-text-secondary font-medium">Route</th>
              <th className="text-left px-3 py-2 text-xs text-text-secondary font-medium">Aircraft</th>
              <th className="text-left px-3 py-2 text-xs text-text-secondary font-medium">Reg</th>
              <th className="text-left px-3 py-2 text-xs text-text-secondary font-medium">Captain</th>
              <th className="text-left px-3 py-2 text-xs text-text-secondary font-medium">Exercise</th>
              <th className="text-right px-3 py-2 text-xs text-text-secondary font-medium">Hours</th>
            </tr>
          </thead>
          <tbody>
            {flights.map(f => (
              <tr key={f.id} className="border-b border-border last:border-0 hover:bg-bg-hover">
                <td className="px-3 py-2 text-text-secondary text-xs whitespace-nowrap">{formatDate(f.date)}</td>
                <td className="px-3 py-2 font-medium text-text-primary">
                  {f.dep_airport || '?'} → {f.arr_airport || '?'}
                </td>
                <td className="px-3 py-2 text-text-secondary">{f.aircraft_type || '—'}</td>
                <td className="px-3 py-2 text-text-secondary">{f.registration || '—'}</td>
                <td className="px-3 py-2 text-text-secondary">{f.captain || '—'}</td>
                <td className="px-3 py-2 text-text-secondary text-xs">{f.exercise || '—'}</td>
                <td className="px-3 py-2 text-text-secondary text-right">{f.hours_total ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {flights.length === 0 && (
          <div className="text-center text-text-secondary py-8">No GA flights found</div>
        )}
      </div>
    </>
  )
}

function RailTab() {
  const [year, setYear] = useState<number | undefined>()
  const { data, isLoading } = useQuery({
    queryKey: ['rail-journeys', year],
    queryFn: () => fetchRailJourneys(year),
  })

  if (isLoading) return <div className="text-text-secondary text-sm">Loading...</div>
  const journeys = data?.items ?? []

  return (
    <>
      <YearFilter years={data?.years ?? []} selected={year} onChange={setYear} />
      <div className="text-xs text-text-secondary mb-3">{data?.total ?? 0} rail journeys</div>
      <div className="bg-bg-card border border-border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-bg-secondary">
              <th className="text-left px-3 py-2 text-xs text-text-secondary font-medium">Date</th>
              <th className="text-left px-3 py-2 text-xs text-text-secondary font-medium">Route</th>
              <th className="text-left px-3 py-2 text-xs text-text-secondary font-medium">Operator</th>
              <th className="text-left px-3 py-2 text-xs text-text-secondary font-medium">Time</th>
              <th className="text-left px-3 py-2 text-xs text-text-secondary font-medium">Via</th>
              <th className="text-right px-3 py-2 text-xs text-text-secondary font-medium">Price</th>
            </tr>
          </thead>
          <tbody>
            {journeys.map(rj => (
              <tr key={rj.id} className="border-b border-border last:border-0 hover:bg-bg-hover">
                <td className="px-3 py-2 text-text-secondary text-xs whitespace-nowrap">{formatDate(rj.date)}</td>
                <td className="px-3 py-2 font-medium text-text-primary">
                  {rj.from_station} → {rj.to_station}
                </td>
                <td className="px-3 py-2 text-text-secondary">{rj.operator || '—'}</td>
                <td className="px-3 py-2 text-text-secondary text-xs">{formatTime(rj.time)}</td>
                <td className="px-3 py-2 text-text-secondary text-xs">{rj.via || ''}</td>
                <td className="px-3 py-2 text-text-secondary text-right text-xs">
                  {rj.price != null ? `${rj.currency === 'GBP' ? '£' : rj.currency || ''}${Number(rj.price).toFixed(2)}` : ''}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {journeys.length === 0 && (
          <div className="text-center text-text-secondary py-8">No rail journeys found</div>
        )}
      </div>
    </>
  )
}

const TABS: { key: Tab; label: string }[] = [
  { key: 'flights', label: 'Flights' },
  { key: 'ga', label: 'GA Flying' },
  { key: 'rail', label: 'Rail' },
]

export default function Travel() {
  const [tab, setTab] = useState<Tab>('flights')

  return (
    <div className="p-6 max-w-6xl">
      <h2 className="text-xl font-bold text-text-primary mb-4">Travel</h2>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b border-border">
        {TABS.map(t => (
          <button
            key={t.key}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t.key
                ? 'border-accent text-accent'
                : 'border-transparent text-text-secondary hover:text-text-primary'
            }`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'flights' && <FlightsTab />}
      {tab === 'ga' && <GaFlightsTab />}
      {tab === 'rail' && <RailTab />}
    </div>
  )
}
