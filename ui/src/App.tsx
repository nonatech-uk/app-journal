import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Shell from './components/layout/Shell'
import { usePageTracking } from './hooks/usePageTracking'
import Timeline from './pages/Timeline'
import EntryDetail from './pages/EntryDetail'
import NewEntry from './pages/NewEntry'
import Calendar from './pages/Calendar'
import Search from './pages/Search'
import Stats from './pages/Stats'
import MapView from './pages/MapView'
import Trips from './pages/Trips'
import TripDetail from './pages/TripDetail'
import Events from './pages/Events'
import EventDetail from './pages/EventDetail'
import EventTypes from './pages/EventTypes'
import Places from './pages/Places'
import Travel from './pages/Travel'
import ActivityTypes from './pages/ActivityTypes'
import Activities from './pages/Activities'
import ActivityDetail from './pages/ActivityDetail'
import AircraftDetail from './pages/AircraftDetail'
import FlightDetail from './pages/FlightDetail'
import GaFlightDetail from './pages/GaFlightDetail'
import RailDetail from './pages/RailDetail'
import Memoirs from './pages/Memoirs'
import MemoirDetail from './pages/MemoirDetail'

export default function App() {
  return (
    <BrowserRouter>
      <PageTracker />
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
          <Route path="/events" element={<Events />} />
          <Route path="/event/:id" element={<EventDetail />} />
          <Route path="/event-types" element={<EventTypes />} />
          <Route path="/travel" element={<Travel />} />
          <Route path="/travel/flights/:id" element={<FlightDetail />} />
          <Route path="/travel/ga/:id" element={<GaFlightDetail />} />
          <Route path="/travel/rail/:id" element={<RailDetail />} />
          <Route path="/aircraft/:registration" element={<AircraftDetail />} />
          <Route path="/activities" element={<Activities />} />
          <Route path="/activity/:id" element={<ActivityDetail />} />
          <Route path="/activity-types" element={<ActivityTypes />} />
          <Route path="/memoirs" element={<Memoirs />} />
          <Route path="/memoir/:id" element={<MemoirDetail />} />
          <Route path="/places" element={<Places />} />
          <Route path="/stats" element={<Stats />} />
          <Route path="*" element={<div className="text-text-secondary">Page not found</div>} />
        </Routes>
      </Shell>
    </BrowserRouter>
  )
}

function PageTracker() {
  usePageTracking()
  return null
}
