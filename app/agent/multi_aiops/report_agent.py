from __future__ import annotations

from app.agent.multi_aiops.state import MultiAIOpsState


def run_report_agent(state: MultiAIOpsState) -> MultiAIOpsState:
    """
    ReportAgent：生成最终 AIOps 诊断报告。
    """
    session_id = state.get("session_id", "")
    question = state.get("question", "")
    target_service = state.get("target_service", "")

    log_summary = state.get("log_summary", "未获取到日志证据。")
    metric_summary = state.get("metric_summary", "未获取到指标证据。")
    knowledge_summary = state.get("knowledge_summary", "未获取到知识库参考。")
    root_cause = state.get("root_cause", "暂未形成根因判断。")
    confidence = state.get("confidence", "unknown")
    remediation = state.get("remediation", [])
    errors = state.get("errors", [])

    remediation_text = "\n".join([f"{i + 1}. {item}" for i, item in enumerate(remediation)])
    if not remediation_text:
        remediation_text = "暂无处理建议。"

    error_text = ""
    if errors:
        error_text = "\n\n## 六、流程异常信息\n" + "\n".join([f"- {e}" for e in errors])

    report = f"""# AIOps 多 Agent 诊断报告

## 一、基本信息

- 会话 ID：{session_id}
- 目标服务：{target_service}
- 用户问题：{question}
- 根因置信度：{confidence}

---

## 二、日志证据

{log_summary}

---

## 三、指标证据

{metric_summary}

---

## 四、知识库参考

{knowledge_summary}

---

## 五、根因判断

{root_cause}

---

## 六、处理建议

{remediation_text}
{error_text}
"""

    state["final_report"] = report
    state["current_step"] = "report_agent_done"
    state["finished"] = True

    return state