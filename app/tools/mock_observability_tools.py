import csv
import json
from pathlib import Path

import pandas as pd
from langchain_core.tools import tool
from loguru import logger

IMPORTANT_LEVELS = {"ERROR", "WARN", "WARNING", "FATAL", "CRITICAL"}

SERVICE_METRIC_ALIAS = {
    "web-service": "service-02",
    "cloud-platform": "service-15",
    "linux-host": "service-15",
    "zookeeper-service": "service-02",
}

def resolve_metric_service(service: str) -> str:
    """将业务服务名映射到指标系统中的服务名，支持中英文和模糊匹配。"""
    if not service:
        return service

    s = service.lower().strip()

    # 1. 精确映射
    if s in SERVICE_METRIC_ALIAS:
        return SERVICE_METRIC_ALIAS[s]

    # 2. 包含英文服务名
    for app_service, metric_service in SERVICE_METRIC_ALIAS.items():
        if app_service in s:
            return metric_service

    # 3. 常见中文 / 模糊表达映射
    if "web" in s or "apache" in s or "网页" in s or "网站" in s:
        return "service-02"

    if "cloud" in s or "openstack" in s or "云平台" in s or "实例" in s:
        return "service-15"

    if "linux" in s or "主机" in s or "系统" in s:
        return "service-15"

    if "zookeeper" in s or "zk" in s or "中间件" in s:
        return "service-02"

    return service

ROOT = Path(__file__).resolve().parents[2]
LOG_FILE = ROOT / "data" / "mock_logs" / "all_logs.jsonl"
METRIC_FILE = ROOT / "data" / "mock_metrics" / "metrics.csv"


@tool
def query_mock_logs(
    service: str = "",
    keyword: str = "",
    level: str = "",
    label: str = "",
    limit: int = 5,
) -> str:
    """
    查询本地模拟日志数据。

    适用于排查 Web 服务、Linux 主机、OpenStack 云平台、Zookeeper 中间件等异常。
    可按 service、keyword、level、label 过滤日志。
    当没有指定 keyword/level 时，默认优先返回 ERROR/WARN/FATAL/failed/exception/timeout 等异常日志。
    """

    if not LOG_FILE.exists():
        return f"日志文件不存在: {LOG_FILE}"

    service = (service or "").strip()
    keyword = (keyword or "").strip()
    level = (level or "").strip()
    label = (label or "").strip()

    matched = []

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                item = json.loads(line)

                item_service = str(item.get("service", "")).strip()
                item_level = str(item.get("level", "")).strip()
                item_label = str(item.get("label", "")).strip()
                message = str(item.get("message", "")).strip()

                if service and item_service.lower() != service.lower():
                    continue

                if level and item_level.lower() != level.lower():
                    continue

                if label and item_label.lower() != label.lower():
                    continue

                if keyword and keyword.lower() not in message.lower():
                    continue

                matched.append(item)

        if not matched:
            return (
                "没有查询到符合条件的日志。"
                f"\n收到的查询参数: service={service}, keyword={keyword}, level={level}, label={label}"
                f"\n日志文件路径: {LOG_FILE}"
            )

        if not level and not keyword:
            important = [
                x for x in matched
                if str(x.get("level", "")).upper() in IMPORTANT_LEVELS
                or "error" in str(x.get("message", "")).lower()
                or "failed" in str(x.get("message", "")).lower()
                or "exception" in str(x.get("message", "")).lower()
                or "timeout" in str(x.get("message", "")).lower()
                or "can't create" in str(x.get("message", "")).lower()
            ]

            results = important[:limit] if important else matched[:limit]
        else:
            results = matched[:limit]

    except Exception as e:
        logger.exception("查询本地日志失败")
        return f"查询本地日志失败: {e}"

    lines = [f"命中日志 {len(results)} 条："]

    for i, item in enumerate(results, 1):
        lines.append(
            f"\n【日志 {i}】\n"
            f"时间: {item.get('timestamp')}\n"
            f"数据集: {item.get('dataset')}\n"
            f"服务: {item.get('service')}\n"
            f"级别: {item.get('level')}\n"
            f"标签: {item.get('label')}\n"
            f"内容: {item.get('message')}"
        )

    return "\n".join(lines)



@tool
def query_mock_metrics(
    service: str = "",
    metric_keyword: str = "",
    label: str = "anomaly",
    top: int = 5,
    summary: bool = False,
) -> str:
    """
    查询本地模拟指标数据。

    适用于排查服务指标异常、KPI 异常、延迟升高、错误率升高、资源波动等问题。
    可按 service、metric_keyword、label 过滤指标。
    """

    if not METRIC_FILE.exists():
        return f"指标文件不存在: {METRIC_FILE}"

    try:
        df = pd.read_csv(METRIC_FILE)

        mapped_service = ""

        if service:
            mapped_service = resolve_metric_service(service)
            df = df[df["service"].astype(str).str.lower() == mapped_service.lower()]

        if metric_keyword:
            df = df[
                df["metric_name"]
                .astype(str)
                .str.lower()
                .str.contains(metric_keyword.lower(), na=False)
            ]

        if label:
            df = df[df["label"].astype(str).str.lower() == label.lower()]

        # 兜底：如果模型传入了不规范 service，且没有查到结果，
        # 诊断场景下默认优先返回 anomaly 指标，避免直接误判“没有指标异常”。
        if len(df) == 0 and service and label:
            fallback_service = resolve_metric_service(service)
            df_all = pd.read_csv(METRIC_FILE)
            df = df_all[
                (df_all["service"].astype(str).str.lower() == fallback_service.lower())
                & (df_all["label"].astype(str).str.lower() == label.lower())
            ]
            mapped_service = fallback_service

        if len(df) == 0:
            return "没有查询到符合条件的指标。"

        if summary:
            parts = [
                f"命中指标条数: {len(df)}",
                "\n标签分布:",
                str(df["label"].value_counts(dropna=False)),
                "\n服务分布 Top 10:",
                str(df["service"].value_counts().head(10)),
                "\n指标分布 Top 10:",
                str(df["metric_name"].value_counts().head(10)),
                "\n数值统计:",
                str(df["value"].describe()),
            ]
            return "\n".join(parts)

        result = df.sort_values("value", ascending=False).head(top)

        lines = [f"命中指标 {len(df)} 条，展示 Top {len(result)}："]

        if service and mapped_service and mapped_service != service:
            lines.append(f"\n服务映射: {service} -> {mapped_service}")

        for i, (_, row) in enumerate(result.iterrows(), 1):
            lines.append(
                f"\n【指标 {i}】\n"
                f"时间: {row['timestamp']}\n"
                f"服务: {row['service']}\n"
                f"指标: {row['metric_name']}\n"
                f"数值: {row['value']}\n"
                f"标签: {row['label']}\n"
                f"case_id: {row.get('case_id', '')}\n"
                f"kpi_id: {row['kpi_id']}\n"
                f"来源: {row['source_file']}"
            )

        return "\n".join(lines)

    except Exception as e:
        logger.exception("查询本地指标失败")
        return f"查询本地指标失败: {e}"