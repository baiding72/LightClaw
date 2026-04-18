import { Routes, Route, NavLink } from 'react-router-dom'
import DashboardPage from './pages/DashboardPage'
import TaskRunnerPage from './pages/TaskRunnerPage'
import MemoryPage from './pages/MemoryPage'
import DataPoolPage from './pages/DataPoolPage'
import EvaluationPage from './pages/EvaluationPage'
import ApplicationsPage from './pages/ApplicationsPage'

function App() {
  const navItems = [
    { to: '/', label: 'Dashboard', icon: '📊' },
    { to: '/applications', label: 'Applications', icon: '🧭' },
    { to: '/tasks', label: 'Task Runner', icon: '🤖' },
    { to: '/memory', label: 'Memory', icon: '🧠' },
    { to: '/datapool', label: 'DataPool', icon: '📦' },
    { to: '/eval', label: 'Evaluation', icon: '📈' },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-gray-900">
              🦁 LightClaw
            </h1>
            <span className="text-sm text-gray-500">
              个人效率智能体
            </span>
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4">
          <ul className="flex space-x-1">
            {navItems.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  className={({ isActive }) =>
                    `inline-flex items-center px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                      isActive
                        ? 'border-blue-500 text-blue-600'
                        : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                    }`
                  }
                >
                  <span className="mr-2">{item.icon}</span>
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-6">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/applications" element={<ApplicationsPage />} />
          <Route path="/tasks" element={<TaskRunnerPage />} />
          <Route path="/memory" element={<MemoryPage />} />
          <Route path="/datapool" element={<DataPoolPage />} />
          <Route path="/eval" element={<EvaluationPage />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
