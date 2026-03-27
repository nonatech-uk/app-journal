import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Shell from './components/layout/Shell'
import Timeline from './pages/Timeline'
import EntryDetail from './pages/EntryDetail'
import Calendar from './pages/Calendar'
import Search from './pages/Search'
import Stats from './pages/Stats'
import MapView from './pages/MapView'

export default function App() {
  return (
    <BrowserRouter>
      <Shell>
        <Routes>
          <Route path="/" element={<Navigate to="/timeline" replace />} />
          <Route path="/timeline" element={<Timeline />} />
          <Route path="/entry/:id" element={<EntryDetail />} />
          <Route path="/calendar" element={<Calendar />} />
          <Route path="/search" element={<Search />} />
          <Route path="/map" element={<MapView />} />
          <Route path="/stats" element={<Stats />} />
          <Route path="*" element={<div className="text-text-secondary">Page not found</div>} />
        </Routes>
      </Shell>
    </BrowserRouter>
  )
}
