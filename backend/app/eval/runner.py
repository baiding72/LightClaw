"""
评测运行器
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.core.logger import logger
from app.schemas.eval import EvaluationResponse
from app.tasks.benchmark import BenchmarkRunner


class EvaluationRunner:
    """评测运行器"""

    def __init__(self, output_dir: Optional[str] = None):
        from app.core.config import get_settings
        self.settings = get_settings()
        self.output_dir = Path(output_dir or self.settings.eval_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.benchmark_runner = BenchmarkRunner()

    async def run_evaluation(
        self,
        eval_name: str,
        task_ids: Optional[list[str]] = None,
        categories: Optional[list[str]] = None,
        difficulties: Optional[list[str]] = None,
    ) -> EvaluationResponse:
        """
        运行评测

        Args:
            eval_name: 评测名称
            task_ids: 指定任务 ID
            categories: 类别筛选
            difficulties: 难度筛选

        Returns:
            评测结果
        """
        result = await self.benchmark_runner.run_benchmark(
            eval_name=eval_name,
            task_ids=task_ids,
            categories=categories,
            difficulties=difficulties,
        )

        # 保存结果
        self._save_result(result)

        return result

    def _save_result(self, result: EvaluationResponse) -> str:
        """保存评测结果"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"eval_{result.eval_id}_{timestamp}.json"
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result.model_dump(), f, ensure_ascii=False, default=str, indent=2)

        logger.info(f"Evaluation result saved: {filepath}")
        return str(filepath)

    def load_result(self, eval_id: str) -> Optional[EvaluationResponse]:
        """加载评测结果"""
        for filepath in self.output_dir.glob(f"eval_{eval_id}_*.json"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return EvaluationResponse(**data)
            except Exception as e:
                logger.error(f"Failed to load evaluation: {e}")

        return None

    def list_results(self) -> list[dict[str, Any]]:
        """列出所有评测结果"""
        results = []
        for filepath in sorted(self.output_dir.glob("eval_*.json"), reverse=True):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    results.append({
                        "eval_id": data.get("eval_id"),
                        "eval_name": data.get("eval_name"),
                        "total_tasks": data.get("total_tasks"),
                        "task_success_rate": data.get("metrics", {}).get("task_success_rate"),
                        "created_at": data.get("created_at"),
                        "filepath": str(filepath),
                    })
            except Exception as e:
                logger.warning(f"Failed to read evaluation file: {e}")

        return results

    def get_summary(self) -> dict[str, Any]:
        """获取评测摘要"""
        results = self.list_results()

        if not results:
            return {
                "total_evaluations": 0,
                "avg_success_rate": 0.0,
            }

        success_rates = [r["task_success_rate"] for r in results if r["task_success_rate"]]

        return {
            "total_evaluations": len(results),
            "avg_success_rate": sum(success_rates) / len(success_rates) if success_rates else 0.0,
            "latest_eval": results[0] if results else None,
        }
