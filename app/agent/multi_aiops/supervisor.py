from __future__ import annotations

from typing import Dict, Any

from app.agent.multi_aiops.state import MultiAIOpsState
from app.agent.multi_aiops.log_agent import run_log_agent
from app.agent.multi_aiops.metrics_agent import run_metrics_agent
from app.agent.multi_aiops.knowledge_agent import run_knowledge_agent
from app.agent.multi_aiops.root_cause_agent import run_root_cause_agent
from app.agent.multi_aiops.report_agent import run_report_agent


def infer_target_service(question: str) -> str:
    """
    根据用户问题简单推断目标服务。
    第一版先用规则，后续可以升级为 LLM Supervisor。
    """
    q = question.lower()

    if "web-service" in q or "web服务" in question or "web 服务" in question or "网页" in question:
        return "web-service"

    if "cloud-platform" in q or "openstack" in q or "云平台" in question or "实例" in question:
        return "cloud-platform"

    if "linux-host" in q or "linux" in q or "主机" in question or "系统层" in question:
        return "linux-host"

    if "zookeeper" in q or "zk" in q or "中间件" in question:
        return "zookeeper-service"

    # 默认先诊断 web-service，避免没有目标服务导致流程中断
    return "web-service"


def build_initial_state(
    session_id: str,
    question: str,
    target_service: str | None = None,
) -> MultiAIOpsState:
    """
    构建多 Agent 初始状态。
    """
    if not target_service:
        target_service = infer_target_service(question)

    state: MultiAIOpsState = {
        "session_id": session_id,
        "question": question,
        "target_service": target_service,
        "errors": [],
        "finished": False,
        "current_step": "init",
    }

    return state


def run_multi_aiops_diagnosis(
    session_id: str,
    question: str,
    target_service: str | None = None,
) -> MultiAIOpsState:
    """
    多 Agent AIOps 诊断总入口。

    流程：
    1. LogAgent 查询日志证据
    2. MetricsAgent 查询指标证据
    3. KnowledgeAgent 检索知识库
    4. RootCauseAgent 判断根因
    5. ReportAgent 生成最终报告
    """
    state = build_initial_state(
        session_id=session_id,
        question=question,
        target_service=target_service,
    )

    try:
        state = run_log_agent(state)
        state = run_metrics_agent(state)
        state = run_knowledge_agent(state)
        state = run_root_cause_agent(state)
        state = run_report_agent(state)

    except Exception as e:
        state.setdefault("errors", []).append(f"Supervisor 执行失败: {e}")
        state["final_report"] = f"多 Agent 诊断流程执行失败: {e}"
        state["finished"] = True
        state["current_step"] = "failed"

    return state


def run_multi_aiops_report(
    session_id: str,
    question: str,
    target_service: str | None = None,
) -> str:
    """
    只返回最终 Markdown 报告的便捷入口。
    """
    state = run_multi_aiops_diagnosis(
        session_id=session_id,
        question=question,
        target_service=target_service,
    )

    return state.get("final_report", "未生成诊断报告。")