import argparse
import pandas as pd
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
METRIC_FILE = ROOT / "data" / "mock_metrics" / "metrics.csv"


def main():
    parser = argparse.ArgumentParser(description="Search mock AIOps metrics")
    parser.add_argument("--service", type=str, default="", help="service name, e.g. service-15")
    parser.add_argument("--metric", type=str, default="", help="metric name or keyword")
    parser.add_argument("--label", type=str, default="", help="normal/anomaly/unknown")
    parser.add_argument("--top", type=int, default=10, help="show top N by value")
    parser.add_argument("--summary", action="store_true", help="show metric summary")
    args = parser.parse_args()

    if not METRIC_FILE.exists():
        raise FileNotFoundError(f"指标文件不存在: {METRIC_FILE}")

    df = pd.read_csv(METRIC_FILE)

    if args.service:
        df = df[df["service"].astype(str).str.lower() == args.service.lower()]

    if args.metric:
        df = df[df["metric_name"].astype(str).str.lower().str.contains(args.metric.lower(), na=False)]

    if args.label:
        df = df[df["label"].astype(str).str.lower() == args.label.lower()]

    print(f"命中指标条数: {len(df)}")
    print("-" * 100)

    if len(df) == 0:
        return

    if args.summary:
        print("标签分布:")
        print(df["label"].value_counts(dropna=False))
        print("\n服务分布 Top 10:")
        print(df["service"].value_counts().head(10))
        print("\n指标分布 Top 10:")
        print(df["metric_name"].value_counts().head(10))
        print("\n数值统计:")
        print(df["value"].describe())
        return

    result = df.sort_values("value", ascending=False).head(args.top)

    for _, row in result.iterrows():
        print(
            f"[{row['timestamp']}] "
            f"[{row['service']}] "
            f"[{row['metric_name']}] "
            f"value={row['value']} "
            f"label={row['label']} "
            f"case_id={row.get('case_id', '')}"
        )
        print(f"kpi_id: {row['kpi_id']}")
        print(f"source: {row['source_file']}")
        print("-" * 100)


if __name__ == "__main__":
    main()