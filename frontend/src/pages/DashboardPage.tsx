import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { DashboardStats } from '../types'

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadStats()
  }, [])

  const loadStats = async () => {
    try {
      const response = await api.get<DashboardStats>('/eval/dashboard/stats')
      setStats(response.data)
    } catch (error) {
      console.error('Failed to load stats:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-gray-900">Dashboard</h2>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm font-medium text-gray-500">Total Tasks</div>
          <div className="mt-2 text-3xl font-bold text-gray-900">
            {stats?.total_tasks || 0}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm font-medium text-gray-500">Completed</div>
          <div className="mt-2 text-3xl font-bold text-green-600">
            {stats?.completed_tasks || 0}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm font-medium text-gray-500">Running</div>
          <div className="mt-2 text-3xl font-bold text-blue-600">
            {stats?.running_tasks || 0}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm font-medium text-gray-500">Success Rate</div>
          <div className="mt-2 text-3xl font-bold text-gray-900">
            {((stats?.task_success_rate || 0) * 100).toFixed(1)}%
          </div>
        </div>
      </div>

      {/* Recent Evaluations */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b">
          <h3 className="text-lg font-medium text-gray-900">Recent Evaluations</h3>
        </div>
        <div className="p-6">
          {stats?.recent_evaluations && stats.recent_evaluations.length > 0 ? (
            <div className="space-y-4">
              {stats.recent_evaluations.map((eval_) => (
                <div key={eval_.eval_id} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div>
                    <div className="font-medium text-gray-900">{eval_.eval_name}</div>
                    <div className="text-sm text-gray-500">{eval_.total_tasks} tasks</div>
                  </div>
                  <div className="text-right">
                    <div className="text-lg font-bold text-green-600">
                      {(eval_.task_success_rate * 100).toFixed(1)}%
                    </div>
                    <div className="text-sm text-gray-500">Success Rate</div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center text-gray-500 py-8">
              No evaluations yet. Run a benchmark to see results.
            </div>
          )}
        </div>
      </div>

      {/* Quick Actions */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Quick Actions</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <a
            href="/tasks"
            className="flex flex-col items-center p-4 bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors"
          >
            <span className="text-2xl mb-2">🤖</span>
            <span className="text-sm font-medium text-gray-700">Run Task</span>
          </a>
          <a
            href="/eval"
            className="flex flex-col items-center p-4 bg-green-50 rounded-lg hover:bg-green-100 transition-colors"
          >
            <span className="text-2xl mb-2">📈</span>
            <span className="text-sm font-medium text-gray-700">Run Benchmark</span>
          </a>
          <a
            href="/datapool"
            className="flex flex-col items-center p-4 bg-purple-50 rounded-lg hover:bg-purple-100 transition-colors"
          >
            <span className="text-2xl mb-2">📦</span>
            <span className="text-sm font-medium text-gray-700">View Data</span>
          </a>
          <a
            href="/memory"
            className="flex flex-col items-center p-4 bg-yellow-50 rounded-lg hover:bg-yellow-100 transition-colors"
          >
            <span className="text-2xl mb-2">🧠</span>
            <span className="text-sm font-medium text-gray-700">View Memory</span>
          </a>
        </div>
      </div>
    </div>
  )
}
