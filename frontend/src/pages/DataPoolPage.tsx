import { useState, useEffect } from 'react'
import { api } from '../lib/api'

interface Sample {
  sample_id: string
  sample_type: string
  trajectory_type: string
  task_id: string
  failure_type: string | null
  created_at: string
}

interface DataPoolStats {
  total_samples: number
  by_type: Record<string, number>
  by_trajectory_type: Record<string, number>
  exported_count: number
  unexported_count: number
}

export default function DataPoolPage() {
  const [samples, setSamples] = useState<Sample[]>([])
  const [stats, setStats] = useState<DataPoolStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)

  useEffect(() => {
    loadData()
  }, [page])

  const loadData = async () => {
    try {
      const [samplesRes, statsRes] = await Promise.all([
        api.get('/datapool', { params: { page, page_size: 20 } }),
        api.get<DataPoolStats>('/datapool/stats'),
      ])
      setSamples(samplesRes.data.samples)
      setTotal(samplesRes.data.total)
      setStats(statsRes.data)
    } catch (error) {
      console.error('Failed to load data:', error)
    } finally {
      setLoading(false)
    }
  }

  const exportSamples = async () => {
    try {
      await api.post('/datapool/export', {
        output_format: 'jsonl',
      })
      alert('Export started!')
      loadData()
    } catch (error) {
      console.error('Failed to export:', error)
    }
  }

  const buildFromTrajectories = async () => {
    try {
      await api.post('/datapool/build')
      alert('Building samples from trajectories...')
      loadData()
    } catch (error) {
      console.error('Failed to build:', error)
    }
  }

  if (loading) {
    return <div className="text-center py-8 text-gray-500">Loading...</div>
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-gray-900">DataPool</h2>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm font-medium text-gray-500">Total Samples</div>
          <div className="mt-2 text-3xl font-bold text-gray-900">
            {stats?.total_samples || 0}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm font-medium text-gray-500">Tool-use</div>
          <div className="mt-2 text-3xl font-bold text-blue-600">
            {stats?.by_type?.tool_use || 0}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm font-medium text-gray-500">Self-correction</div>
          <div className="mt-2 text-3xl font-bold text-purple-600">
            {stats?.by_type?.self_correction || 0}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm font-medium text-gray-500">GUI Grounding</div>
          <div className="mt-2 text-3xl font-bold text-green-600">
            {stats?.by_type?.gui_grounding || 0}
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex space-x-4">
          <button
            onClick={buildFromTrajectories}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Build from Trajectories
          </button>
          <button
            onClick={exportSamples}
            className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
          >
            Export Samples
          </button>
        </div>
      </div>

      {/* Samples Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Sample ID
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Type
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Trajectory
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Task
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Failure Type
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Created
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {samples.map((sample) => (
              <tr key={sample.sample_id} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                  {sample.sample_id.substring(0, 20)}...
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  <span className={`px-2 py-1 rounded-full text-xs ${
                    sample.sample_type === 'tool_use' ? 'bg-blue-100 text-blue-800' :
                    sample.sample_type === 'self_correction' ? 'bg-purple-100 text-purple-800' :
                    'bg-green-100 text-green-800'
                  }`}>
                    {sample.sample_type}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {sample.trajectory_type}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {sample.task_id}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {sample.failure_type || '-'}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {new Date(sample.created_at).toLocaleDateString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {samples.length === 0 && (
          <div className="text-center py-8 text-gray-500">
            No samples yet. Run some tasks to generate data.
          </div>
        )}
      </div>

      {/* Pagination */}
      {total > 20 && (
        <div className="flex justify-center space-x-2">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-4 py-2 border rounded-md disabled:opacity-50"
          >
            Previous
          </button>
          <span className="px-4 py-2">Page {page}</span>
          <button
            onClick={() => setPage(p => p + 1)}
            disabled={page * 20 >= total}
            className="px-4 py-2 border rounded-md disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}
