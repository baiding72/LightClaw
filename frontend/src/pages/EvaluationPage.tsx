import { useState, useEffect } from 'react'
import { api } from '../lib/api'

interface Evaluation {
  eval_id: string
  eval_name: string
  total_tasks: number
  task_success_rate: number
  tool_execution_success_rate: number
  recovery_rate: number
  gui_action_accuracy: number
  created_at: string
}

export default function EvaluationPage() {
  const [evaluations, setEvaluations] = useState<Evaluation[]>([])
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [evalName, setEvalName] = useState('')

  useEffect(() => {
    loadEvaluations()
  }, [])

  const loadEvaluations = async () => {
    try {
      const response = await api.get('/eval')
      setEvaluations(response.data.evaluations)
    } catch (error) {
      console.error('Failed to load evaluations:', error)
    } finally {
      setLoading(false)
    }
  }

  const runBenchmark = async () => {
    if (!evalName) {
      alert('Please enter an evaluation name')
      return
    }

    setRunning(true)
    try {
      await api.post('/eval/run', {
        eval_name: evalName,
      })
      setEvalName('')
      loadEvaluations()
    } catch (error) {
      console.error('Failed to run benchmark:', error)
    } finally {
      setRunning(false)
    }
  }

  if (loading) {
    return <div className="text-center py-8 text-gray-500">Loading...</div>
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-gray-900">Evaluation</h2>

      {/* Run Benchmark */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Run Benchmark</h3>
        <div className="flex space-x-4">
          <input
            type="text"
            placeholder="Evaluation name"
            value={evalName}
            onChange={(e) => setEvalName(e.target.value)}
            className="flex-1 px-3 py-2 border border-gray-300 rounded-md"
          />
          <button
            onClick={runBenchmark}
            disabled={running}
            className="px-6 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50"
          >
            {running ? 'Running...' : 'Run Benchmark'}
          </button>
        </div>
        <p className="mt-2 text-sm text-gray-500">
          This will run all built-in tasks and collect metrics.
        </p>
      </div>

      {/* Evaluations List */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 border-b">
          <h3 className="text-lg font-medium text-gray-900">
            Evaluation Results ({evaluations.length})
          </h3>
        </div>

        {evaluations.length > 0 ? (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Tasks
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Success Rate
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Tool Success
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Recovery
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  GUI Accuracy
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Date
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {evaluations.map((eval_) => (
                <tr key={eval_.eval_id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    {eval_.eval_name}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {eval_.total_tasks}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <span className={`font-bold ${
                      eval_.task_success_rate >= 0.8 ? 'text-green-600' :
                      eval_.task_success_rate >= 0.5 ? 'text-yellow-600' :
                      'text-red-600'
                    }`}>
                      {(eval_.task_success_rate * 100).toFixed(1)}%
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {(eval_.tool_execution_success_rate * 100).toFixed(1)}%
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {(eval_.recovery_rate * 100).toFixed(1)}%
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {(eval_.gui_action_accuracy * 100).toFixed(1)}%
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(eval_.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="text-center py-8 text-gray-500">
            No evaluations yet. Run a benchmark to get started.
          </div>
        )}
      </div>

      {/* Metrics Explanation */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Metrics Explained</h3>
        <dl className="space-y-4">
          <div>
            <dt className="font-medium text-gray-700">Task Success Rate</dt>
            <dd className="text-sm text-gray-500">
              Percentage of tasks completed successfully.
            </dd>
          </div>
          <div>
            <dt className="font-medium text-gray-700">Tool Execution Success Rate</dt>
            <dd className="text-sm text-gray-500">
              Percentage of tool calls that executed without errors.
            </dd>
          </div>
          <div>
            <dt className="font-medium text-gray-700">Recovery Rate</dt>
            <dd className="text-sm text-gray-500">
              Percentage of errors that were successfully recovered.
            </dd>
          </div>
          <div>
            <dt className="font-medium text-gray-700">GUI Action Accuracy</dt>
            <dd className="text-sm text-gray-500">
              Accuracy of GUI element targeting and actions.
            </dd>
          </div>
        </dl>
      </div>
    </div>
  )
}
