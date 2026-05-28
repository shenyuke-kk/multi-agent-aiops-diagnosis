from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import requests


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASE_FILE = ROOT / "eval" / "aiops_cases.jsonl"
RESULT_DIR = ROOT / "eval" / "results"


REQUIRED_SECTIONS = [
    "日志证据",
    "指标证据",
    "知识库参考",
    "根因判断",
    "处理建议",
]


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    """读取 jsonl 评测案例。"""
    if not path.exists():
        raise FileNotFoundError(f"评测文件不存在: {path}")

    cases = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"{path} 第 {line_no} 行不是合法 JSON: {e}")

    return cases


def normalize_text(text: Any) -> str:
    """统一转成小写字符串，方便匹配。"""
    if text is None:
        return ""
    return str(text).lower()


def contains_any(text: str, keywords: List[str]) -> bool:
    """判断文本是否命中任意关键词。"""
    t = normalize_text(text)
    for kw in keywords:
        if not kw:
            continue
        if normalize_text(kw) in t:
            return True
    return False


def count_keyword_hits(text: str, keywords: List[str]) -> int:
    """统计命中的关键词数量。"""
    t = normalize_text(text)
    count = 0

    for kw in keywords:
        if not kw:
            continue
        if normalize_text(kw) in t:
            count += 1

    return count


def split_chinese_phrases(text: str) -> List[str]:
    """
    将中文根因描述切成若干短语，用于粗略匹配。
    不依赖 jieba，避免额外安装。
    """
    if not text:
        return []

    parts = re.split(r"[，。；;、,.!\s]+", text)

    stop_phrases = {
        "导致",
        "可能",
        "异常",
        "服务",
        "系统",
        "需要",
        "结合",
        "存在",
        "问题",
        "原因",
        "根因",
        "判断",
    }

    results = []

    for p in parts:
        p = p.strip()
        if not p:
            continue

        # 过滤太短、太泛的词
        if len(p) < 2:
            continue
        if p in stop_phrases:
            continue

        results.append(p)

    return results


def root_cause_hit(expected_root_cause: str, report_text: str) -> bool:
    """
    判断根因是否大致命中。
    优先完整包含；否则用短语重叠粗略判断。
    """
    expected = normalize_text(expected_root_cause)
    report = normalize_text(report_text)

    if not expected:
        return True

    if expected in report:
        return True

    phrases = split_chinese_phrases(expected_root_cause)

    if not phrases:
        return False

    hit_count = count_keyword_hits(report, phrases)

    # 至少命中 1 个关键短语，或者命中比例达到 30%
    return hit_count >= 1 or hit_count / max(len(phrases), 1) >= 0.3


def call_multi_aiops_api(
    endpoint: str,
    case: Dict[str, Any],
    timeout: int = 120,
) -> Dict[str, Any]:
    """调用 /api/aiops_multi 接口。"""
    payload = {
        "session_id": case.get("case_id", f"eval-{int(time.time())}"),
        "question": case.get("question", ""),
        "target_service": case.get("target_service"),
    }

    response = requests.post(endpoint, json=payload, timeout=timeout)

    try:
        body = response.json()
    except Exception:
        body = {
            "code": response.status_code,
            "message": response.text,
            "data": {},
        }

    return {
        "http_status": response.status_code,
        "payload": payload,
        "response": body,
    }


def evaluate_case(case: Dict[str, Any], api_result: Dict[str, Any]) -> Dict[str, Any]:
    """对单条 case 的返回结果进行评估。"""
    response_body = api_result.get("response", {})
    data = response_body.get("data", {}) if isinstance(response_body, dict) else {}

    final_report = data.get("final_report", "") or ""
    log_summary = data.get("log_summary", "") or ""
    metric_summary = data.get("metric_summary", "") or ""
    knowledge_summary = data.get("knowledge_summary", "") or ""
    root_cause = data.get("root_cause", "") or ""

    all_text = "\n".join(
        [
            final_report,
            log_summary,
            metric_summary,
            knowledge_summary,
            root_cause,
        ]
    )

    expected_log_keywords = case.get("expected_log_keywords", [])
    expected_metric_labels = case.get("expected_metric_labels", [])
    expected_root_cause = case.get("expected_root_cause", "")

    section_hits = {
        section: section in final_report
        for section in REQUIRED_SECTIONS
    }

    log_keyword_hit_count = count_keyword_hits(all_text, expected_log_keywords)
    metric_label_hit_count = count_keyword_hits(all_text, expected_metric_labels)

    api_success = (
        api_result.get("http_status") == 200
        and isinstance(response_body, dict)
        and response_body.get("code") == 200
    )

    has_final_report = bool(final_report.strip())

    log_hit = log_keyword_hit_count > 0
    metric_hit = metric_label_hit_count > 0
    root_hit = root_cause_hit(expected_root_cause, all_text)

    section_score = sum(1 for v in section_hits.values() if v) / len(REQUIRED_SECTIONS)

    # 简单总分：接口成功 + 报告结构 + 日志命中 + 指标命中 + 根因命中
    score_items = [
        api_success,
        has_final_report,
        section_score >= 0.8,
        log_hit,
        metric_hit,
        root_hit,
    ]

    score = sum(1 for x in score_items if x) / len(score_items)

    passed = score >= 0.75

    return {
        "case_id": case.get("case_id"),
        "question": case.get("question"),
        "target_service": case.get("target_service"),
        "api_success": api_success,
        "has_final_report": has_final_report,
        "section_hits": section_hits,
        "section_score": round(section_score, 4),
        "expected_log_keywords": expected_log_keywords,
        "log_keyword_hit_count": log_keyword_hit_count,
        "log_hit": log_hit,
        "expected_metric_labels": expected_metric_labels,
        "metric_label_hit_count": metric_label_hit_count,
        "metric_hit": metric_hit,
        "expected_root_cause": expected_root_cause,
        "root_cause_hit": root_hit,
        "score": round(score, 4),
        "passed": passed,
        "final_report": final_report,
        "raw_api_result": api_result,
    }


def save_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    """保存 jsonl。"""
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_markdown_report(results: List[Dict[str, Any]], output_file: Path) -> str:
    """生成 Markdown 评测报告。"""
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    api_success = sum(1 for r in results if r["api_success"])
    log_hit = sum(1 for r in results if r["log_hit"])
    metric_hit = sum(1 for r in results if r["metric_hit"])
    root_hit = sum(1 for r in results if r["root_cause_hit"])

    avg_score = sum(r["score"] for r in results) / max(total, 1)

    lines = [
        "# Multi-Agent AIOps 评测报告",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 评测案例数：{total}",
        f"- 通过案例数：{passed}/{total}",
        f"- 平均得分：{avg_score:.4f}",
        "",
        "## 一、总体指标",
        "",
        "| 指标 | 数量 | 比例 |",
        "|---|---:|---:|",
        f"| API 调用成功 | {api_success}/{total} | {api_success / max(total, 1):.2%} |",
        f"| 日志证据命中 | {log_hit}/{total} | {log_hit / max(total, 1):.2%} |",
        f"| 指标证据命中 | {metric_hit}/{total} | {metric_hit / max(total, 1):.2%} |",
        f"| 根因判断命中 | {root_hit}/{total} | {root_hit / max(total, 1):.2%} |",
        f"| 最终通过 | {passed}/{total} | {passed / max(total, 1):.2%} |",
        "",
        "## 二、逐案例结果",
        "",
        "| Case ID | 目标服务 | API | 日志 | 指标 | 根因 | 分数 | 通过 |",
        "|---|---|---|---|---|---|---:|---|",
    ]

    for r in results:
        lines.append(
            "| {case_id} | {target_service} | {api} | {log} | {metric} | {root} | {score:.4f} | {passed} |".format(
                case_id=r["case_id"],
                target_service=r["target_service"],
                api="✅" if r["api_success"] else "❌",
                log="✅" if r["log_hit"] else "❌",
                metric="✅" if r["metric_hit"] else "❌",
                root="✅" if r["root_cause_hit"] else "❌",
                score=r["score"],
                passed="✅" if r["passed"] else "❌",
            )
        )

    lines.extend(
        [
            "",
            "## 三、失败案例详情",
            "",
        ]
    )

    failed = [r for r in results if not r["passed"]]

    if not failed:
        lines.append("所有案例均通过。")
    else:
        for r in failed:
            lines.extend(
                [
                    f"### {r['case_id']}",
                    "",
                    f"- 问题：{r['question']}",
                    f"- 目标服务：{r['target_service']}",
                    f"- 分数：{r['score']}",
                    f"- API 成功：{r['api_success']}",
                    f"- 日志命中：{r['log_hit']}，命中数量：{r['log_keyword_hit_count']}",
                    f"- 指标命中：{r['metric_hit']}，命中数量：{r['metric_label_hit_count']}",
                    f"- 根因命中：{r['root_cause_hit']}",
                    "",
                ]
            )

    output_file.write_text("\n".join(lines), encoding="utf-8")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Evaluate Multi-Agent AIOps API")
    parser.add_argument(
        "--case-file",
        type=str,
        default=str(DEFAULT_CASE_FILE),
        help="评测案例 jsonl 文件路径",
    )
    parser.add_argument(
        "--endpoint",
        type=str,
        default="http://localhost:9900/api/aiops_multi",
        help="多 Agent AIOps 接口地址",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="单个请求超时时间，单位秒",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.5,
        help="每个 case 之间的等待秒数",
    )

    args = parser.parse_args()

    case_file = Path(args.case_file)
    cases = load_jsonl(case_file)

    if not cases:
        raise ValueError(f"没有读取到任何评测案例: {case_file}")

    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    jsonl_output = RESULT_DIR / f"multi_aiops_eval_{timestamp}.jsonl"
    md_output = RESULT_DIR / f"multi_aiops_eval_{timestamp}.md"

    results = []

    print(f"评测案例文件: {case_file}")
    print(f"评测接口: {args.endpoint}")
    print(f"案例数量: {len(cases)}")
    print("=" * 100)

    for idx, case in enumerate(cases, 1):
        case_id = case.get("case_id", f"case_{idx}")
        question = case.get("question", "")

        print(f"[{idx}/{len(cases)}] Running {case_id}: {question}")

        try:
            api_result = call_multi_aiops_api(
                endpoint=args.endpoint,
                case=case,
                timeout=args.timeout,
            )
            eval_result = evaluate_case(case, api_result)

        except Exception as e:
            eval_result = {
                "case_id": case_id,
                "question": question,
                "target_service": case.get("target_service"),
                "api_success": False,
                "has_final_report": False,
                "section_hits": {},
                "section_score": 0.0,
                "expected_log_keywords": case.get("expected_log_keywords", []),
                "log_keyword_hit_count": 0,
                "log_hit": False,
                "expected_metric_labels": case.get("expected_metric_labels", []),
                "metric_label_hit_count": 0,
                "metric_hit": False,
                "expected_root_cause": case.get("expected_root_cause", ""),
                "root_cause_hit": False,
                "score": 0.0,
                "passed": False,
                "final_report": "",
                "error": str(e),
            }

        results.append(eval_result)

        print(
            f"  score={eval_result['score']:.4f}, "
            f"passed={eval_result['passed']}, "
            f"log={eval_result['log_hit']}, "
            f"metric={eval_result['metric_hit']}, "
            f"root={eval_result['root_cause_hit']}"
        )
        print("-" * 100)

        time.sleep(args.sleep)

    save_jsonl(jsonl_output, results)
    build_markdown_report(results, md_output)

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    avg_score = sum(r["score"] for r in results) / max(total, 1)

    print("\n评测完成")
    print(f"通过案例: {passed}/{total}")
    print(f"平均得分: {avg_score:.4f}")
    print(f"JSONL 结果: {jsonl_output}")
    print(f"Markdown 报告: {md_output}")


if __name__ == "__main__":
    main()