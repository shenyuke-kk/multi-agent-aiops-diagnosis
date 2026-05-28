from typing import TypedDict, List, Dict, Any, Optional


class MultiAIOpsState(TypedDict, total=False):
    """
    多 Agent AIOps 诊断共享状态。

    Supervisor、LogAgent、MetricsAgent、KnowledgeAgent、
    RootCauseAgent、ReportAgent 都通过这个 state 传递信息。
    """

    # 基础输入
    session_id: str
    question: str
    target_service: str

    # 服务映射，例如 web-service -> service-02
    related_metric_service: Optional[str]

    # 各类证据
    log_evidence: List[Dict[str, Any]]
    metric_evidence: List[Dict[str, Any]]
    knowledge_evidence: List[str]

    # 中间分析结果
    log_summary: str
    metric_summary: str
    knowledge_summary: str

    # 根因和建议
    root_cause: str
    confidence: str
    remediation: List[str]

    # 最终报告
    final_report: str

    # 流程控制
    current_step: str
    finished: bool
    errors: List[str]