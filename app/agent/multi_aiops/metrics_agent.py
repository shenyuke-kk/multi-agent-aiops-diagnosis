from __future__ import annotations

from typing import Dict, Any

from app.agent.multi_aiops.state import MultiAIOpsState
from app.tools.mock_observability_tools import query_mock_metrics


def run_metrics_agent(state: MultiAIOpsState) -> MultiAIOpsState:
    """
    MetricsAgent：查询目标服务对应的异常指标证据。

    输入:
        state["target_service"]

    输出:
        state["metric_evidence"]
        state["metric_summary"]
    """
    target_service = state.get("target_service", "")

    if not target_service:
        state.setdefault("errors", []).append("MetricsAgent 缺少 target_service，无法查询指标。")
        state["metric_summary"] = "未提供目标服务，无法查询指标证据。"
        return state

    try:
        result = query_mock_metrics.invoke(
            {
                "service": target_service,
                "label": "anomaly",
                "top": 5,
            }
        )

        evidence: Dict[str, Any] = {
            "agent": "MetricsAgent",
            "service": target_service,
            "label": "anomaly",
            "result": result,
        }

        state["metric_evidence"] = [evidence]
        state["metric_summary"] = result
        state["current_step"] = "metrics_agent_done"

    except Exception as e:
        state.setdefault("errors", []).append(f"MetricsAgent 查询失败: {e}")
        state["metric_summary"] = f"指标查询失败: {e}"

    return state