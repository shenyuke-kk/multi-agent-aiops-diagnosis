import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOG_FILE = ROOT / "data" / "mock_logs" / "all_logs.jsonl"


def match_filter(item, args):
    if args.dataset and item.get("dataset", "").lower() != args.dataset.lower():
        return False

    if args.service and item.get("service", "").lower() != args.service.lower():
        return False

    if args.category and item.get("category", "").lower() != args.category.lower():
        return False

    if args.level and item.get("level", "").lower() != args.level.lower():
        return False

    if args.label and item.get("label", "").lower() != args.label.lower():
        return False

    if args.keyword:
        keyword = args.keyword.lower()
        message = item.get("message", "").lower()
        if keyword not in message:
            return False

    return True


def main():
    parser = argparse.ArgumentParser(description="Search mock AIOps logs")
    parser.add_argument("--dataset", type=str, default="", help="Apache/Linux/OpenStack/Zookeeper")
    parser.add_argument("--service", type=str, default="", help="web-service/linux-host/cloud-platform/zookeeper-service")
    parser.add_argument("--category", type=str, default="", help="application/system/middleware")
    parser.add_argument("--level", type=str, default="", help="INFO/WARN/ERROR/FATAL")
    parser.add_argument("--label", type=str, default="", help="normal/anomaly/unknown")
    parser.add_argument("--keyword", type=str, default="", help="keyword in log message")
    parser.add_argument("--limit", type=int, default=10, help="max results")

    args = parser.parse_args()

    if not LOG_FILE.exists():
        raise FileNotFoundError(f"日志文件不存在: {LOG_FILE}")

    results = []

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)

            if match_filter(item, args):
                results.append(item)

                if len(results) >= args.limit:
                    break

    print(f"命中日志条数: {len(results)}")
    print("-" * 80)

    for item in results:
        print(f"[{item['timestamp']}] [{item['dataset']}] [{item['service']}] [{item['level']}] [{item['label']}]")
        print(item["message"])
        print("-" * 80)


if __name__ == "__main__":
    main()