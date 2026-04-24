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

interface LatestEvalReport {
  eval_id: string
  eval_name: string
  mode?: string
  source?: string
  total_tasks: number
  metrics: {
    task_success_rate: number
    tool_execution_success_rate: number
    recovery_rate: number
    gui_action_accuracy: number
    invalid_tool_call_rate?: number
    wrong_args_rate?: number
    policy_violation_rate?: number
    avg_steps?: number
    avg_latency_ms: number
  }
}

export default function EvaluationPage() {
  const [evaluations, setEvaluations] = useState<Evaluation[]>([])
  const [latestReport, setLatestReport] = useState<LatestEvalReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [evalName, setEvalName] = useState('')

  useEffect(() => {
    loadEvaluations()
    loadLatestReport()
  }, [])

  const loadEvaluations = async () => {
    try {
      const response = await api.get('/eval')
      setEvaluations(response.data.evaluations)
    } catch (error) {
      console.error('加载评测结果失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadLatestReport = async () => {
    try {
      const response = await api.get('/eval/report/latest')
      setLatestReport(response.data)
    } catch (error: any) {
      if (error.response?.status !== 404) {
        console.error('加载最新评测报告失败:', error)
      }
      setLatestReport(null)
    }
  }

  const runBenchmark = async () => {
    if (!evalName) {
      alert('请输入评测名称。')
      return
    }

    setRunning(true)
    try {
      await api.post('/eval/run', {
        eval_name: evalName,
        mode: 'deterministic',
      })
      setEvalName('')
      loadEvaluations()
      loadLatestReport()
    } catch (error) {
      console.error('运行评测失败:', error)
    } finally {
      setRunning(false)
    }
  }

  if (loading) {
    return <div className="text-center py-8 text-gray-500">加载中...</div>
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-gray-900">评测</h2>

      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">最新本地评测报告</h3>
        {latestReport ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <div className="text-gray-500">模式</div>
              <div className="font-semibold text-gray-900">{latestReport.mode || 'deterministic'}</div>
            </div>
            <div>
              <div className="text-gray-500">任务成功率</div>
              <div className="font-semibold text-gray-900">
                {(latestReport.metrics.task_success_rate * 100).toFixed(1)}%
              </div>
            </div>
            <div>
              <div className="text-gray-500">错误参数率</div>
              <div className="font-semibold text-gray-900">
                {((latestReport.metrics.wrong_args_rate || 0) * 100).toFixed(1)}%
              </div>
            </div>
            <div>
              <div className="text-gray-500">GUI Grounding</div>
              <div className="font-semibold text-gray-900">
                {(latestReport.metrics.gui_action_accuracy * 100).toFixed(1)}%
              </div>
            </div>
            <div>
              <div className="text-gray-500">无效调用率</div>
              <div className="font-semibold text-gray-900">
                {((latestReport.metrics.invalid_tool_call_rate || 0) * 100).toFixed(1)}%
              </div>
            </div>
            <div>
              <div className="text-gray-500">策略违规率</div>
              <div className="font-semibold text-gray-900">
                {((latestReport.metrics.policy_violation_rate || 0) * 100).toFixed(1)}%
              </div>
            </div>
            <div>
              <div className="text-gray-500">平均步骤</div>
              <div className="font-semibold text-gray-900">
                {(latestReport.metrics.avg_steps || 0).toFixed(1)}
              </div>
            </div>
            <div>
              <div className="text-gray-500">平均延迟</div>
              <div className="font-semibold text-gray-900">
                {latestReport.metrics.avg_latency_ms.toFixed(0)}ms
              </div>
            </div>
          </div>
        ) : (
          <div className="text-sm text-gray-500">
            暂无本地评测报告。运行 <code>uv run python ../scripts/run_eval.py --mode deterministic</code> 后会在这里显示。
          </div>
        )}
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">运行基准测试</h3>
        <div className="flex space-x-4">
          <input
            type="text"
            placeholder="评测名称"
            value={evalName}
            onChange={(e) => setEvalName(e.target.value)}
            className="flex-1 px-3 py-2 border border-gray-300 rounded-md"
          />
          <button
            onClick={runBenchmark}
            disabled={running}
            className="px-6 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50"
          >
            {running ? '运行中...' : '运行评测'}
          </button>
        </div>
        <p className="mt-2 text-sm text-gray-500">
          这会执行所有内置任务并收集评测指标。
        </p>
      </div>

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 border-b">
          <h3 className="text-lg font-medium text-gray-900">
            评测结果（{evaluations.length}）
          </h3>
        </div>

        {evaluations.length > 0 ? (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  名称
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  任务数
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  成功率
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  工具成功率
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  恢复率
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  GUI 准确率
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  日期
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
            暂无评测结果。先运行一次评测。
          </div>
        )}
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">指标说明</h3>
        <dl className="space-y-4">
          <div>
            <dt className="font-medium text-gray-700">任务成功率</dt>
            <dd className="text-sm text-gray-500">
              成功完成任务的比例。
            </dd>
          </div>
          <div>
            <dt className="font-medium text-gray-700">工具执行成功率</dt>
            <dd className="text-sm text-gray-500">
              工具调用无报错完成的比例。
            </dd>
          </div>
          <div>
            <dt className="font-medium text-gray-700">恢复率</dt>
            <dd className="text-sm text-gray-500">
              错误发生后成功恢复的比例。
            </dd>
          </div>
          <div>
            <dt className="font-medium text-gray-700">GUI 动作准确率</dt>
            <dd className="text-sm text-gray-500">
              GUI 元素定位与动作执行的准确程度。
            </dd>
          </div>
        </dl>
      </div>
    </div>
  )
}
