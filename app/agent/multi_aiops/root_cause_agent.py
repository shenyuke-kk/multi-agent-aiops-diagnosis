from __future__ import annotations

from typing import List

from app.agent.multi_aiops.state import MultiAIOpsState


def infer_root_cause_from_evidence(
    question: str,
    target_service: str,
    log_summary: str,
    metric_summary: str,
    knowledge_summary: str,
) -> tuple[str, str, List[str]]:
    """
    基于日志证据、指标证据和知识库证据进行轻量规则根因判断。

    第一版先不用 LLM，保证流程稳定、可控。
    后续可以升级为 LLM RootCauseAgent。
    """
    text = "\n".join(
        [
            question or "",
            target_service or "",
            log_summary or "",
            metric_summary or "",
            knowledge_summary or "",
        ]
    ).lower()

    remediation: List[str] = []

    # Web / Apache / JNI / VM 初始化异常
    if (
        "channel.jni" in text
        or "worker.jni" in text
        or "can't create vm" in text
        or "factory error creating" in text
        or "createbean" in text
    ):
        root_cause = (
            f"{target_service} 存在 Web 服务组件初始化失败迹象。"
            "日志中出现 channel.jni、worker.jni、vm 等组件创建失败，"
            "结合指标侧 anomaly 记录，说明服务运行状态存在异常波动。"
            "可能根因包括 JNI/worker/vm 相关配置错误、运行环境依赖缺失、"
            "Web 容器组件初始化失败或发布后配置不兼容。"
        )
        confidence = "high"
        remediation = [
            "优先检查 Apache/Tomcat/Web 容器的 JNI、worker、vm 相关配置。",
            "核对最近是否有配置变更、版本发布或依赖库变更。",
            "检查启动脚本、环境变量、动态库路径和组件加载路径是否正确。",
            "如果异常发生在发布后，优先回滚到上一个稳定版本。",
            "结合指标异常时间窗口，确认是否存在流量突增或资源波动。",
        ]
        return root_cause, confidence, remediation

    # OpenStack / 云平台实例异常
    if "nova" in text or "instance" in text or "vm stopped" in text or "openstack" in text:
        root_cause = (
            f"{target_service} 可能存在云平台计算服务或实例生命周期异常。"
            "日志中出现 nova、instance、VM lifecycle 等相关信息，"
            "结合异常指标，可能涉及计算节点资源异常、实例状态变化或 nova 组件处理异常。"
        )
        confidence = "medium"
        remediation = [
            "检查 nova-api、nova-compute 相关日志，定位异常 instance id。",
            "检查计算节点 CPU、内存、磁盘和虚拟化组件状态。",
            "确认是否存在实例异常停止、迁移失败或调度失败。",
            "必要时迁移或重建异常实例。",
        ]
        return root_cause, confidence, remediation

    # Linux 主机系统异常
    if "kernel" in text or "syslog" in text or "restart" in text or "linux" in text:
        root_cause = (
            f"{target_service} 可能存在系统层异常或服务重启迹象。"
            "日志中出现 kernel/syslog/restart 等信息，结合指标异常，"
            "需要进一步确认是否存在资源耗尽、内核事件或系统服务异常。"
        )
        confidence = "medium"
        remediation = [
            "检查 syslog、kernel log 和系统服务状态。",
            "查看 CPU、内存、磁盘、文件描述符等资源使用情况。",
            "确认是否存在 OOM、磁盘满、服务重启或系统调用异常。",
            "必要时进行服务迁移或主机隔离。",
        ]
        return root_cause, confidence, remediation

    # Zookeeper / 中间件异常
    if "zookeeper" in text or "quorum" in text or "session" in text or "connection" in text:
        root_cause = (
            f"{target_service} 可能存在 Zookeeper 中间件连接、会话或集群状态异常。"
            "需要重点关注 quorum、session、connection、leader/follower 状态。"
        )
        confidence = "medium"
        remediation = [
            "检查 Zookeeper 集群 quorum 状态。",
            "检查 session、connection、leader/follower 相关日志。",
            "确认节点间网络连通性和端口可达性。",
            "检查 zoo.cfg 配置、数据目录和磁盘状态。",
        ]
        return root_cause, confidence, remediation

    # 通用兜底
    root_cause = (
        f"{target_service} 存在异常迹象，但当前证据不足以定位唯一根因。"
        "日志、指标或知识库中存在异常相关信息，需要继续补充时间窗口、服务拓扑和依赖服务状态。"
    )
    confidence = "low"
    remediation = [
        "继续扩大日志查询时间范围，重点关注 ERROR、FATAL、timeout、failed 等关键字。",
        "检查服务对应的 anomaly 指标时间窗口。",
        "结合依赖服务、数据库、中间件和网络状态进行交叉排查。",
        "补充发布记录、配置变更记录和告警历史。",
    ]

    return root_cause, confidence, remediation


def run_root_cause_agent(state: MultiAIOpsState) -> MultiAIOpsState:
    """
    RootCauseAgent：综合日志、指标和知识库证据，生成根因判断和处理建议。
    """
    question = state.get("question", "")
    target_service = state.get("target_service", "")
    log_summary = state.get("log_summary", "")
    metric_summary = state.get("metric_summary", "")
    knowledge_summary = state.get("knowledge_summary", "")

    if not target_service:
        state.setdefault("errors", []).append("RootCauseAgent 缺少 target_service。")
        state["root_cause"] = "缺少目标服务，无法进行根因判断。"
        state["confidence"] = "low"
        state["remediation"] = []
        return state

    root_cause, confidence, remediation = infer_root_cause_from_evidence(
        question=question,
        target_service=target_service,
        log_summary=log_summary,
        metric_summary=metric_summary,
        knowledge_summary=knowledge_summary,
    )

    state["root_cause"] = root_cause
    state["confidence"] = confidence
    state["remediation"] = remediation
    state["current_step"] = "root_cause_agent_done"

    return state