import json
import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

CASE_FILE = ROOT / "eval" / "aiops_cases.jsonl"
LOG_FILE = ROOT / "data" / "mock_logs" / "all_logs.jsonl"
METRIC_FILE = ROOT / "data" / "mock_metrics" / "metrics.csv"


def load_cases():
    cases = []
    with open(CASE_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def search_logs(service: str, keywords: list[str], limit: int = 5):
    results = []

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)

            if item.get("service") != service:
                continue

            message = item.get("message", "").lower()

            matched = False
            for kw in keywords:
                if kw.lower() in message:
                    matched = True
                    break

            if matched:
                results.append(item)

            if len(results) >= limit:
                break

    return results


def search_metrics(service: str, label: str = "anomaly", limit: int = 5):
    results = []

    with open(METRIC_FILE, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            if row.get("service") != service:
                continue

            if row.get("label") != label:
                continue

            results.append(row)

            if len(results) >= limit:
                break

    return results


def main():
    if not CASE_FILE.exists():
        raise FileNotFoundError(f"找不到评测案例文件: {CASE_FILE}")

    if not LOG_FILE.exists():
        raise FileNotFoundError(f"找不到日志文件: {LOG_FILE}")

    if not METRIC_FILE.exists():
        raise FileNotFoundError(f"找不到指标文件: {METRIC_FILE}")

    cases = load_cases()

    print(f"评测案例数量: {len(cases)}")
    print("=" * 100)

    passed = 0

    for case in cases:
        case_id = case["case_id"]
        question = case["question"]
        target_service = case["target_service"]
        metric_service = case["related_metric_service"]
        keywords = case.get("expected_log_keywords", [])

        log_hits = search_logs(target_service, keywords, limit=3)
        metric_hits = search_metrics(metric_service, label="anomaly", limit=3)

        log_ok = len(log_hits) > 0
        metric_ok = len(metric_hits) > 0
        case_ok = log_ok and metric_ok

        if case_ok:
            passed += 1

        print(f"[{case_id}] {question}")
        print(f"目标日志服务: {target_service}")
        print(f"关联指标服务: {metric_service}")
        print(f"日志关键词: {keywords}")
        print(f"日志命中: {'✅' if log_ok else '❌'}，数量: {len(log_hits)}")
        print(f"异常指标命中: {'✅' if metric_ok else '❌'}，数量: {len(metric_hits)}")

        if log_hits:
            print("\n日志样例:")
            for item in log_hits:
                print(f"- [{item['timestamp']}] [{item['dataset']}] [{item['level']}] {item['message'][:200]}")

        if metric_hits:
            print("\n指标样例:")
            for row in metric_hits:
                print(
                    f"- [{row['timestamp']}] "
                    f"{row['service']} {row['metric_name']} "
                    f"value={row['value']} label={row['label']}"
                )

        print("-" * 100)

    print(f"通过案例: {passed}/{len(cases)}")


if __name__ == "__main__":
    main()