from __future__ import annotations

from typing import Dict, Any

from app.agent.multi_aiops.state import MultiAIOpsState
from app.tools.knowledge_tool import retrieve_knowledge


def run_knowledge_agent(state: MultiAIOpsState) -> MultiAIOpsState:
    """
    KnowledgeAgent：检索 AIOps 知识库中的排障经验。

    输入:
        state["question"]
        state["target_service"]

    输出:
        state["knowledge_evidence"]
        state["knowledge_summary"]
    """
    question = state.get("question", "")
    target_service = state.get("target_service", "")

    if not question:
        state.setdefault("errors", []).append("KnowledgeAgent 缺少 question，无法检索知识库。")
        state["knowledge_summary"] = "未提供问题，无法检索知识库。"
        return state

    query = f"{target_service} {question} 故障诊断 排查步骤 处理建议"

    try:
        result = retrieve_knowledge.invoke(
            {
                "query": query
            }
        )

        evidence: Dict[str, Any] = {
            "agent": "KnowledgeAgent",
            "query": query,
            "result": result,
        }

        state["knowledge_evidence"] = [evidence]
        state["knowledge_summary"] = result
        state["current_step"] = "knowledge_agent_done"

    except Exception as e:
        state.setdefault("errors", []).append(f"KnowledgeAgent 检索失败: {e}")
        state["knowledge_summary"] = f"知识库检索失败: {e}"

    return state