from __future__ import annotations

from typing import Dict, Any

from app.agent.multi_aiops.state import MultiAIOpsState
from app.tools.mock_observability_tools import query_mock_logs


def infer_log_keyword(question: str) -> str:
    """
    根据用户问题推断日志查询关键词。
    这里先做轻量规则，后续可以交给 Supervisor 或 LLM 来判断。
    """
    q = question.lower()

    if "超时" in question or "timeout" in q:
        return "timeout"

    if "失败" in question or "failed" in q or "fail" in q:
        return "failed"

    if "错误" in question or "异常" in question or "error" in q:
        return "error"

    if "连接" in question or "connection" in q:
        return "connection"

    # 默认不指定关键词，让 query_mock_logs 内部优先返回 ERROR/WARN 等异常日志
    return ""


def run_log_agent(state: MultiAIOpsState) -> MultiAIOpsState:
    """
    LogAgent：查询目标服务日志证据。

    输入:
        state["question"]
        state["target_service"]

    输出:
        state["log_evidence"]
        state["log_summary"]
    """
    question = state.get("question", "")
    target_service = state.get("target_service", "")

    if not target_service:
        state.setdefault("errors", []).append("LogAgent 缺少 target_service，无法查询日志。")
        state["log_summary"] = "未提供目标服务，无法查询日志证据。"
        return state

    # 诊断场景下默认不强行指定 keyword，
    # 让 query_mock_logs 内部优先返回 ERROR/WARN/FATAL/failed/exception/timeout 等异常日志。
    keyword = ""

    try:
        result = query_mock_logs.invoke(
            {
                "service": target_service,
                "keyword": keyword,
                "limit": 5,
            }
        )

        evidence: Dict[str, Any] = {
            "agent": "LogAgent",
            "service": target_service,
            "keyword": keyword,
            "result": result,
        }

        state["log_evidence"] = [evidence]
        state["log_summary"] = result
        state["current_step"] = "log_agent_done"

    except Exception as e:
        state.setdefault("errors", []).append(f"LogAgent 查询失败: {e}")
        state["log_summary"] = f"日志查询失败: {e}"

    return state