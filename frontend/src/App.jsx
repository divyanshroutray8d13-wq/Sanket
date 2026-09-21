import { BrowserRouter, HashRouter, Navigate, Route, Routes } from 'react-router-dom'
import { MotionConfig } from 'framer-motion'
import Navbar from './components/Navbar'
import Footer from './components/Footer'
import MapBackdrop from './components/MapBackdrop'
import TrainPage from './pages/TrainPage'
import StationPage from './pages/StationPage'
import CorridorsPage from './pages/CorridorsPage'
import AboutPage from './pages/AboutPage'

// Hash routing only in the single-file preview build
const Router = import.meta.env.VITE_HASH_ROUTER ? HashRouter : BrowserRouter

export default function App() {
  return (
    <MotionConfig reducedMotion="user">
      <Router>
        <MapBackdrop />
        <div className="relative z-10 flex min-h-full flex-col">
          <Navbar />
          <div className="flex-1">
            <Routes>
              <Route path="/" element={<Navigate to="/train/12951" replace />} />
              <Route path="/train/:trainNo" element={<TrainPage />} />
              <Route path="/station" element={<Navigate to="/station/ST" replace />} />
              <Route path="/station/:code" element={<StationPage />} />
              <Route path="/corridors" element={<CorridorsPage />} />
              <Route path="/about" element={<AboutPage />} />
              <Route path="*" element={<Navigate to="/train/12951" replace />} />
            </Routes>
          </div>
          <Footer />
        </div>
      </Router>
    </MotionConfig>
  )
}
