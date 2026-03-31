import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Shell from './components/layout/Shell'
import Timeline from './pages/Timeline'
import EntryDetail from './pages/EntryDetail'
import NewEntry from './pages/NewEntry'
import Calendar from './pages/Calendar'
import Search from './pages/Search'
import Stats from './pages/Stats'
import MapView from './pages/MapView'
import Trips from './pages/Trips'
import TripDetail from './pages/TripDetail'

export default function App() {
  return (
    <BrowserRouter>
      <Shell>
        <Routes>
          <Route path="/" element={<Navigate to="/timeline" replace />} />
          <Route path="/timeline" element={<Timeline />} />
          <Route path="/new" element={<NewEntry />} />
          <Route path="/entry/:id" element={<EntryDetail />} />
          <Route path="/calendar" element={<Calendar />} />
          <Route path="/search" element={<Search />} />
          <Route path="/map" element={<MapView />} />
          <Route path="/trips" element={<Trips />} />
          <Route path="/trip/:id" element={<TripDetail />} />
          <Route path="/stats" element={<Stats />} />
          <Route path="*" element={<div className="text-text-secondary">Page not found</div>} />
        </Routes>
      </Shell>
    </BrowserRouter>
  )
}
