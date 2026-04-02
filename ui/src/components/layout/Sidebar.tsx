import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'

const NAV_ITEMS = [
  { to: '/timeline', label: 'Timeline', icon: '◫' },
  { to: '/calendar', label: 'Calendar', icon: '◰' },
  { to: '/search', label: 'Search', icon: '⊙' },
  { to: '/map', label: 'Map', icon: '◈' },
  { to: '/trips', label: 'Trips', icon: '◇' },
  { to: '/events', label: 'Events', icon: '◉' },
  { to: '/travel', label: 'Travel', icon: '▷' },
  { to: '/event-types', label: 'Event Types', icon: '◔' },
  { to: '/places', label: 'Places', icon: '◎' },
  { to: '/stats', label: 'Stats', icon: '⊞' },
]

export default function Sidebar() {
  const { data: user } = useAuth()
  const navigate = useNavigate()

  return (
    <aside className="w-52 bg-bg-secondary border-r border-border flex flex-col shrink-0">
      <div className="p-4 border-b border-border">
        <h1 className="text-lg font-bold text-accent">Journal</h1>
      </div>
      <div className="p-2">
        <button
          onClick={() => navigate('/new')}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-md text-sm font-medium bg-accent text-white hover:bg-accent-hover transition-colors"
        >
          + New Entry
        </button>
      </div>
      <nav className="flex-1 p-2 space-y-1">
        {NAV_ITEMS.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                isActive
                  ? 'bg-accent/15 text-accent font-medium'
                  : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover'
              }`
            }
          >
            <span className="text-base">{icon}</span>
            {label}
          </NavLink>
        ))}
      </nav>
      {user && (
        <div className="p-3 border-t border-border">
          <div className="text-sm text-text-primary truncate">{user.display_name}</div>
          <div className="text-xs text-text-secondary truncate">{user.email}</div>
        </div>
      )}
    </aside>
  )
}
