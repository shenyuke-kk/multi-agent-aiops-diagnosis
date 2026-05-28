import csv
import hashlib
from pathlib import Path
from datetime import datetime, timedelta


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "kpi"
OUT_DIR = ROOT / "data" / "mock_metrics"
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_FILE = OUT_DIR / "metrics.csv"


TIMESTAMP_CANDIDATES = ["timestamp", "time", "datetime", "date", "ts"]
VALUE_CANDIDATES = ["value", "kpi_value", "metric_value", "metric", "val"]
LABEL_CANDIDATES = ["label", "is_anomaly", "anomaly", "y"]
KPI_ID_CANDIDATES = ["kpi_id", "kpi id", "id", "metric_id", "name"]


def normalize_name(name: str) -> str:
    return name.strip().lower().replace("-", "_").replace(" ", "_")


def pick_column(fieldnames, candidates):
    normalized = {normalize_name(c): c for c in fieldnames}
    for cand in candidates:
        key = normalize_name(cand)
        if key in normalized:
            return normalized[key]
    return None


def parse_timestamp(value, fallback_index: int):
    if value is None or str(value).strip() == "":
        base = datetime(2026, 5, 26, 10, 0, 0)
        return base + timedelta(minutes=fallback_index)

    text = str(value).strip()

    # Unix 时间戳：秒 / 毫秒
    try:
        num = float(text)
        if num > 10_000_000_000:
            num = num / 1000
        return datetime.fromtimestamp(num)
    except Exception:
        pass

    # 常见时间字符串
    for fmt in [
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y/%m/%d",
    ]:
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            continue

    base = datetime(2026, 5, 26, 10, 0, 0)
    return base + timedelta(minutes=fallback_index)


def normalize_label(value):
    if value is None or str(value).strip() == "":
        return "unknown"

    text = str(value).strip().lower()

    if text in {"1", "true", "yes", "anomaly", "abnormal"}:
        return "anomaly"

    if text in {"0", "false", "no", "normal"}:
        return "normal"

    return text


def stable_service_name(kpi_id: str, file_stem: str) -> str:
    raw = kpi_id or file_stem
    h = hashlib.md5(raw.encode("utf-8")).hexdigest()
    idx = int(h[:4], 16) % 20 + 1
    return f"service-{idx:02d}"


def infer_metric_name(file_path: Path, kpi_id: str) -> str:
    name = file_path.stem.lower()

    if "cpu" in name:
        return "cpu_usage_percent"
    if "memory" in name or "mem" in name:
        return "memory_usage_percent"
    if "latency" in name or "delay" in name:
        return "p95_latency_ms"
    if "error" in name:
        return "error_rate_percent"

    if kpi_id:
        short_id = kpi_id.replace("-", "_")[:16]
        return f"kpi_{short_id}"

    return "kpi_value"


def iter_csv_files():
    for file in RAW_DIR.rglob("*.csv"):
        if "__MACOSX" in file.parts:
            continue
        if file.is_file():
            yield file


def convert(max_rows_per_file=50000):
    if not RAW_DIR.exists():
        raise FileNotFoundError(f"找不到 KPI 数据目录: {RAW_DIR}")

    total = 0
    file_counts = {}

    with open(OUT_FILE, "w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(
            out,
            fieldnames=[
                "timestamp",
                "service",
                "metric_name",
                "value",
                "label",
                "case_id",
                "source_file",
                "kpi_id",
            ],
        )
        writer.writeheader()

        for file in iter_csv_files():
            count = 0

            with open(file, "r", encoding="utf-8-sig", errors="ignore", newline="") as f:
                reader = csv.DictReader(f)

                if not reader.fieldnames:
                    continue

                timestamp_col = pick_column(reader.fieldnames, TIMESTAMP_CANDIDATES)
                value_col = pick_column(reader.fieldnames, VALUE_CANDIDATES)
                label_col = pick_column(reader.fieldnames, LABEL_CANDIDATES)
                kpi_id_col = pick_column(reader.fieldnames, KPI_ID_CANDIDATES)

                if value_col is None:
                    print(f"跳过文件，没有找到 value 列: {file}")
                    continue

                for idx, row in enumerate(reader):
                    if idx >= max_rows_per_file:
                        break

                    raw_value = row.get(value_col)
                    if raw_value is None or str(raw_value).strip() == "":
                        continue

                    try:
                        value = float(raw_value)
                    except Exception:
                        continue

                    kpi_id = row.get(kpi_id_col, "") if kpi_id_col else file.stem
                    timestamp_raw = row.get(timestamp_col, "") if timestamp_col else ""

                    timestamp = parse_timestamp(timestamp_raw, total)
                    label = normalize_label(row.get(label_col, "")) if label_col else "unknown"
                    service = stable_service_name(kpi_id, file.stem)
                    metric_name = infer_metric_name(file, kpi_id)

                    case_id = ""
                    if label == "anomaly":
                        case_id = f"case_metric_{service}"

                    writer.writerow(
                        {
                            "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                            "service": service,
                            "metric_name": metric_name,
                            "value": value,
                            "label": label,
                            "case_id": case_id,
                            "source_file": str(file.relative_to(ROOT)),
                            "kpi_id": kpi_id,
                        }
                    )

                    total += 1
                    count += 1

            file_counts[str(file.relative_to(ROOT))] = count

    print("KPI 指标整理完成")
    print(f"总指标条数: {total}")
    print(f"输出文件: {OUT_FILE}")
    print("-" * 80)

    for name, count in file_counts.items():
        print(f"{name}: {count}")


if __name__ == "__main__":
    convert()