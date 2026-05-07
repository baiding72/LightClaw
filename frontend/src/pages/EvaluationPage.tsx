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
  self_correction_metrics?: {
    correction_attempt_rate?: number
    recovery_success_rate?: number
    over_correction_rate?: number
    revision_valid_rate?: number
    revision_improves_reward_rate?: number
    first_error_type_distribution?: Record<string, number>
  }
  recruiting_metrics?: {
    jobs_extracted_count?: number
    apply_flow_steps_count?: number
    blocked_by_login?: boolean
    blocked_by_captcha?: boolean
    safe_stop_count?: number
    stop_reason_distribution?: Record<string, number>
    safe_stop_rate?: number
    extraction_schema_pass_rate?: number
  }
  skill_metrics?: {
    registered_skill_count?: number
    loaded_tool_count?: number
    avg_selected_skills?: number
    avg_newly_loaded_tools?: number
    skill_distribution?: Record<string, number>
  }
}

interface DataCard {
  source?: string
  sft_count?: number
  dpo_pair_count?: number
  grpo_group_count?: number
  self_correction_count?: number
  schema_validation_pass_rate?: number
  invalid_sample_count?: number
  suspicious_pair_count?: number
  low_signal_group_count?: number
  chosen_reward_avg?: number
  rejected_reward_avg?: number
}

export default function EvaluationPage() {
  const [evaluations, setEvaluations] = useState<Evaluation[]>([])
  const [latestReport, setLatestReport] = useState<LatestEvalReport | null>(null)
  const [dataCard, setDataCard] = useState<DataCard | null>(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [evalName, setEvalName] = useState('')

  useEffect(() => {
    loadEvaluations()
    loadLatestReport()
    loadDataCard()
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

  const loadDataCard = async () => {
    try {
      const response = await api.get('/eval/data-card/latest')
      setDataCard(response.data)
    } catch (error: any) {
      if (error.response?.status !== 404) {
        console.error('加载训练数据卡失败:', error)
      }
      setDataCard(null)
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
      loadDataCard()
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
          <div className="space-y-5">
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
            <div className="border-t pt-4">
              <h4 className="font-medium text-gray-900 mb-3">Skill 渐进加载</h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <div className="text-gray-500">注册 Skill</div>
                  <div className="font-semibold text-gray-900">
                    {latestReport.skill_metrics?.registered_skill_count ?? 0}
                  </div>
                </div>
                <div>
                  <div className="text-gray-500">已加载工具</div>
                  <div className="font-semibold text-gray-900">
                    {latestReport.skill_metrics?.loaded_tool_count ?? 0}
                  </div>
                </div>
                <div>
                  <div className="text-gray-500">平均选中 Skill</div>
                  <div className="font-semibold text-gray-900">
                    {(latestReport.skill_metrics?.avg_selected_skills ?? 0).toFixed(1)}
                  </div>
                </div>
                <div>
                  <div className="text-gray-500">平均新增工具</div>
                  <div className="font-semibold text-gray-900">
                    {(latestReport.skill_metrics?.avg_newly_loaded_tools ?? 0).toFixed(1)}
                  </div>
                </div>
              </div>
              {latestReport.skill_metrics?.skill_distribution && (
                <div className="mt-3 flex flex-wrap gap-2 text-xs">
                  {Object.entries(latestReport.skill_metrics.skill_distribution).map(([skill, count]) => (
                    <span key={skill} className="rounded border border-gray-200 bg-gray-50 px-2 py-1 text-gray-600">
                      {skill}: {count}
                    </span>
                  ))}
                </div>
              )}
            </div>
            <div className="border-t pt-4">
              <h4 className="font-medium text-gray-900 mb-3">Self-correction</h4>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
                <div>
                  <div className="text-gray-500">修正尝试率</div>
                  <div className="font-semibold text-gray-900">
                    {((latestReport.self_correction_metrics?.correction_attempt_rate || 0) * 100).toFixed(1)}%
                  </div>
                </div>
                <div>
                  <div className="text-gray-500">恢复成功率</div>
                  <div className="font-semibold text-gray-900">
                    {((latestReport.self_correction_metrics?.recovery_success_rate || 0) * 100).toFixed(1)}%
                  </div>
                </div>
                <div>
                  <div className="text-gray-500">过度修正率</div>
                  <div className="font-semibold text-gray-900">
                    {((latestReport.self_correction_metrics?.over_correction_rate || 0) * 100).toFixed(1)}%
                  </div>
                </div>
                <div>
                  <div className="text-gray-500">修正有效率</div>
                  <div className="font-semibold text-gray-900">
                    {((latestReport.self_correction_metrics?.revision_valid_rate || 0) * 100).toFixed(1)}%
                  </div>
                </div>
                <div>
                  <div className="text-gray-500">Reward 改善率</div>
                  <div className="font-semibold text-gray-900">
                    {((latestReport.self_correction_metrics?.revision_improves_reward_rate || 0) * 100).toFixed(1)}%
                  </div>
                </div>
              </div>
            </div>
            <div className="border-t pt-4">
              <h4 className="font-medium text-gray-900 mb-3">招聘流程 Safe Dry-run</h4>
              <div className="grid grid-cols-2 md:grid-cols-6 gap-4 text-sm">
                <div>
                  <div className="text-gray-500">抽取岗位数</div>
                  <div className="font-semibold text-gray-900">
                    {latestReport.recruiting_metrics?.jobs_extracted_count ?? 0}
                  </div>
                </div>
                <div>
                  <div className="text-gray-500">申请步骤数</div>
                  <div className="font-semibold text-gray-900">
                    {latestReport.recruiting_metrics?.apply_flow_steps_count ?? 0}
                  </div>
                </div>
                <div>
                  <div className="text-gray-500">登录拦截</div>
                  <div className="font-semibold text-gray-900">
                    {latestReport.recruiting_metrics?.blocked_by_login ? '是' : '否'}
                  </div>
                </div>
                <div>
                  <div className="text-gray-500">验证码拦截</div>
                  <div className="font-semibold text-gray-900">
                    {latestReport.recruiting_metrics?.blocked_by_captcha ? '是' : '否'}
                  </div>
                </div>
                <div>
                  <div className="text-gray-500">安全停止数</div>
                  <div className="font-semibold text-gray-900">
                    {latestReport.recruiting_metrics?.safe_stop_count ?? 0}
                  </div>
                </div>
                <div>
                  <div className="text-gray-500">安全停止率</div>
                  <div className="font-semibold text-gray-900">
                    {((latestReport.recruiting_metrics?.safe_stop_rate || 0) * 100).toFixed(1)}%
                  </div>
                </div>
                <div>
                  <div className="text-gray-500">抽取 Schema 通过率</div>
                  <div className="font-semibold text-gray-900">
                    {((latestReport.recruiting_metrics?.extraction_schema_pass_rate || 0) * 100).toFixed(1)}%
                  </div>
                </div>
              </div>
              {latestReport.recruiting_metrics?.stop_reason_distribution && (
                <div className="mt-3 flex flex-wrap gap-2 text-xs">
                  {Object.entries(latestReport.recruiting_metrics.stop_reason_distribution).map(([reason, count]) => (
                    <span key={reason} className="rounded border border-gray-200 bg-gray-50 px-2 py-1 text-gray-600">
                      {reason}: {count}
                    </span>
                  ))}
                </div>
              )}
              <p className="mt-3 text-sm text-gray-500">
                当前招聘流程只运行 fixture / safe dry-run：记录 open、extract、click job、detect stop，不会提交申请、登录或上传简历。
              </p>
            </div>
            <div className="border-t pt-4">
              <h4 className="font-medium text-gray-900 mb-3">训练数据卡</h4>
              {dataCard ? (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div>
                    <div className="text-gray-500">来源</div>
                    <div className="font-semibold text-gray-900">{dataCard.source || 'unknown'}</div>
                  </div>
                  <div>
                    <div className="text-gray-500">SFT 样本</div>
                    <div className="font-semibold text-gray-900">{dataCard.sft_count ?? 0}</div>
                  </div>
                  <div>
                    <div className="text-gray-500">DPO Pair</div>
                    <div className="font-semibold text-gray-900">{dataCard.dpo_pair_count ?? 0}</div>
                  </div>
                  <div>
                    <div className="text-gray-500">GRPO Group</div>
                    <div className="font-semibold text-gray-900">{dataCard.grpo_group_count ?? 0}</div>
                  </div>
                  <div>
                    <div className="text-gray-500">Self-correction</div>
                    <div className="font-semibold text-gray-900">{dataCard.self_correction_count ?? 0}</div>
                  </div>
                  <div>
                    <div className="text-gray-500">Schema 通过率</div>
                    <div className="font-semibold text-gray-900">
                      {((dataCard.schema_validation_pass_rate || 0) * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div>
                    <div className="text-gray-500">可疑 Pair</div>
                    <div className="font-semibold text-gray-900">{dataCard.suspicious_pair_count ?? 0}</div>
                  </div>
                  <div>
                    <div className="text-gray-500">低信号 Group</div>
                    <div className="font-semibold text-gray-900">{dataCard.low_signal_group_count ?? 0}</div>
                  </div>
                </div>
              ) : (
                <div className="text-sm text-gray-500">
                  暂无训练数据卡。运行 <code>uv run python ../scripts/export_training_data.py --fixtures --with-data-card --output-dir data/training_exports/latest</code> 后会在这里显示。
                </div>
              )}
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
