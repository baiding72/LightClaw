export interface DashboardStats {
  total_tasks: number
  running_tasks: number
  completed_tasks: number
  failed_tasks: number
  task_success_rate: number
  recent_failures: FailureDistribution[]
  total_samples: number
  recent_evaluations: EvaluationSummary[]
}

export interface FailureDistribution {
  failure_type: string
  count: number
  percentage: number
}

export interface EvaluationSummary {
  eval_id: string
  eval_name: string
  total_tasks: number
  task_success_rate: number
  tool_execution_success_rate: number
  recovery_rate: number
  gui_action_accuracy: number
  created_at: string
}
