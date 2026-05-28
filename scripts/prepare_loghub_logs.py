import json
import re
from pathlib import Path
from datetime import datetime, timedelta


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "loghub"
OUT_DIR = ROOT / "data" / "mock_logs"
OUT_DIR.mkdir(parents=True, exist_ok=True)


LEVEL_PATTERN = re.compile(r"\b(DEBUG|INFO|WARN|WARNING|ERROR|FATAL|CRITICAL)\b", re.I)


def detect_level(line: str) -> str:
    match = LEVEL_PATTERN.search(line)
    if not match:
        return "INFO"
    level = match.group(1).upper()
    if level == "WARNING":
        return "WARN"
    if level == "CRITICAL":
        return "FATAL"
    return level


def infer_service(dataset: str) -> str:
    mapping = {
        "Apache": "web-service",
        "Linux": "linux-host",
        "OpenStack": "cloud-platform",
        "Zookeeper": "zookeeper-service",
    }
    return mapping.get(dataset, dataset.lower())


def infer_category(dataset: str) -> str:
    if dataset == "Apache":
        return "application"
    if dataset == "OpenStack":
        return "application"
    if dataset == "Linux":
        return "system"
    if dataset == "Zookeeper":
        return "middleware"
    return "unknown"


def infer_label(dataset: str, file_name: str) -> str:
    name = file_name.lower()
    if dataset == "OpenStack":
        if "abnormal" in name:
            return "anomaly"
        if "normal" in name:
            return "normal"
    return "unknown"


def iter_log_files():
    for dataset_dir in RAW_DIR.iterdir():
        if not dataset_dir.is_dir():
            continue
        dataset = dataset_dir.name

        for file in dataset_dir.iterdir():
            if file.suffix.lower() != ".log":
                continue
            yield dataset, file


def convert():
    base_time = datetime(2026, 5, 26, 10, 0, 0)

    outputs = {
        "application": OUT_DIR / "application_logs.jsonl",
        "system": OUT_DIR / "system_logs.jsonl",
        "middleware": OUT_DIR / "middleware_logs.jsonl",
        "all": OUT_DIR / "all_logs.jsonl",
    }

    writers = {k: open(v, "w", encoding="utf-8") for k, v in outputs.items()}

    total = 0
    counts = {}

    try:
        for dataset, file in iter_log_files():
            category = infer_category(dataset)
            service = infer_service(dataset)
            label = infer_label(dataset, file.name)

            count = 0
            with open(file, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    timestamp = base_time + timedelta(seconds=total)

                    item = {
                        "id": f"{dataset.lower()}_{total:08d}",
                        "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                        "dataset": dataset,
                        "source_file": file.name,
                        "category": category,
                        "service": service,
                        "level": detect_level(line),
                        "message": line,
                        "label": label,
                        "case_id": "",
                    }

                    text = json.dumps(item, ensure_ascii=False)
                    writers[category].write(text + "\n")
                    writers["all"].write(text + "\n")

                    total += 1
                    count += 1

            counts[f"{dataset}/{file.name}"] = count

    finally:
        for w in writers.values():
            w.close()

    print("日志整理完成")
    print(f"总日志条数: {total}")
    for name, count in counts.items():
        print(f"{name}: {count}")

    print("\n输出文件:")
    for k, v in outputs.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    convert()