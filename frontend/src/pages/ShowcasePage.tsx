import { useEffect, useState } from 'react'
import { api } from '../lib/api'

interface ShowcaseReport {
  generated_at: string
  passed: boolean
  summary: {
    p0_recruiting_safe_dry_run: {
      status: string
      metrics: Record<string, any>
    }
    p1_skill_progressive_loading: {
      status: string
      metrics: Record<string, any>
    }
    p2_training_export_quality: {
      status: string
      data_card: Record<string, any>
    }
  }
  paths: Record<string, string>
  replays: {
    recruiting?: string
    self_correction_wrong_args?: string
  }
}

function StatusBadge({ status }: { status: string }) {
  const ok = status === 'passed'
  return (
    <span className={`rounded px-2 py-1 text-xs font-medium ${ok ? 'bg-green-50 text-green-700' : 'bg-amber-50 text-amber-700'}`}>
      {ok ? '通过' : status}
    </span>
  )
}

function MetricCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="text-sm text-gray-500">{label}</div>
      <div className="mt-1 text-xl font-semibold text-gray-900">{value}</div>
    </div>
  )
}

export default function ShowcasePage() {
  const [report, setReport] = useState<ShowcaseReport | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/eval/showcase/latest')
      .then((response) => setReport(response.data))
      .catch(() => setReport(null))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return <div className="text-center py-8 text-gray-500">加载演示报告中...</div>
  }

  if (!report) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-6 text-amber-800">
        尚未生成演示报告。请在 backend 目录运行：
        <pre className="mt-3 rounded bg-white p-3 text-sm text-gray-800">uv run python ../scripts/run_showcase.py</pre>
      </div>
    )
  }

  const recruiting = report.summary.p0_recruiting_safe_dry_run.metrics
  const skills = report.summary.p1_skill_progressive_loading.metrics
  const dataCard = report.summary.p2_training_export_quality.data_card

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">项目演示闭环</h2>
          <p className="mt-1 text-sm text-gray-500">
            汇总 P0 safe dry-run、P1 skill 渐进加载、P2 training export 质量检查。
          </p>
        </div>
        <StatusBadge status={report.passed ? 'passed' : 'failed'} />
      </div>

      <section className="rounded-lg bg-white p-6 shadow">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-medium text-gray-900">P0 招聘 Safe Dry-run</h3>
          <StatusBadge status={report.summary.p0_recruiting_safe_dry_run.status} />
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard label="抽取岗位" value={recruiting.jobs_extracted_count ?? 0} />
          <MetricCard label="申请步骤" value={recruiting.apply_flow_steps_count ?? 0} />
          <MetricCard label="安全停止数" value={recruiting.safe_stop_count ?? 0} />
          <MetricCard label="安全停止率" value={`${((recruiting.safe_stop_rate ?? 0) * 100).toFixed(1)}%`} />
        </div>
        <pre className="mt-4 max-h-72 overflow-auto rounded bg-gray-950 p-4 text-sm text-gray-100">
          {report.replays.recruiting}
        </pre>
      </section>

      <section className="rounded-lg bg-white p-6 shadow">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-medium text-gray-900">P1 Skill 渐进加载</h3>
          <StatusBadge status={report.summary.p1_skill_progressive_loading.status} />
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard label="注册 Skill" value={skills.registered_skill_count ?? 0} />
          <MetricCard label="已加载工具" value={skills.loaded_tool_count ?? 0} />
          <MetricCard label="平均选中 Skill" value={(skills.avg_selected_skills ?? 0).toFixed(1)} />
          <MetricCard label="平均新增工具" value={(skills.avg_newly_loaded_tools ?? 0).toFixed(1)} />
        </div>
        <pre className="mt-4 max-h-64 overflow-auto rounded bg-gray-50 p-4 text-sm text-gray-700">
          {JSON.stringify(skills.skill_distribution ?? {}, null, 2)}
        </pre>
      </section>

      <section className="rounded-lg bg-white p-6 shadow">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-medium text-gray-900">P2 训练数据质量</h3>
          <StatusBadge status={report.summary.p2_training_export_quality.status} />
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <MetricCard label="SFT" value={dataCard.sft_count ?? 0} />
          <MetricCard label="DPO Pair" value={dataCard.dpo_pair_count ?? 0} />
          <MetricCard label="GRPO Group" value={dataCard.grpo_group_count ?? 0} />
          <MetricCard label="Self-correction" value={dataCard.self_correction_count ?? 0} />
          <MetricCard label="Schema 通过率" value={`${((dataCard.schema_validation_pass_rate ?? 0) * 100).toFixed(1)}%`} />
        </div>
        <pre className="mt-4 max-h-72 overflow-auto rounded bg-gray-950 p-4 text-sm text-gray-100">
          {report.replays.self_correction_wrong_args}
        </pre>
      </section>

      <section className="rounded-lg bg-white p-6 shadow">
        <h3 className="text-lg font-medium text-gray-900">输出文件</h3>
        <div className="mt-3 space-y-2 text-sm text-gray-600">
          {Object.entries(report.paths).map(([key, value]) => (
            <div key={key}>
              <span className="font-medium text-gray-900">{key}</span>: <code>{value}</code>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
