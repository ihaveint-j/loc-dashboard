"""CLI entry point for loc-dashboard."""

import argparse
import shutil
import sys
import time
from pathlib import Path

from loc_dashboard.extractor import collect_snapshots
from loc_dashboard.visualizer import generate_report


def main():
    parser = argparse.ArgumentParser(
        description="Generate LOC growth dashboard using cloc snapshots from git history"
    )
    parser.add_argument(
        "repo_path",
        help="Path to git repository",
    )
    parser.add_argument(
        "--branch",
        default="main",
        help="Branch to analyze (default: main)",
    )
    parser.add_argument(
        "--subdirs",
        default="",
        help="Comma-separated subdirectories to track (e.g. apps/coral-web,apps/api)",
    )
    parser.add_argument(
        "--output",
        default="./loc-output",
        help="Output directory (default: ./loc-output)",
    )

    args = parser.parse_args()

    repo_path = Path(args.repo_path).resolve()
    output_dir = Path(args.output).resolve()

    # Parse subdirs
    subdirs = [s.strip() for s in args.subdirs.split(",") if s.strip()] if args.subdirs else []

    # Validate
    if not (repo_path / ".git").exists():
        print(f"Error: {repo_path} is not a git repository")
        sys.exit(1)

    if not shutil.which("cloc"):
        print("Error: cloc is not installed. Install with: brew install cloc")
        sys.exit(1)

    repo_name = repo_path.name

    print(f"Repository : {repo_path}")
    print(f"Branch     : {args.branch}")
    if subdirs:
        print(f"Subdirs    : {', '.join(subdirs)}")
    print(f"Output     : {output_dir}")
    print()

    def on_progress(current, total, month):
        print(f"  [{current}/{total}] Scanning {month}...")

    print("Collecting LOC snapshots (git archive + cloc)...")
    start = time.time()
    snapshots = collect_snapshots(
        str(repo_path), branch=args.branch, subdirs=subdirs, on_progress=on_progress
    )
    elapsed = time.time() - start
    print(f"\n  Collected {len(snapshots)} monthly snapshots in {elapsed:.1f}s")

    if not snapshots:
        print("No data found. Exiting.")
        sys.exit(0)

    latest = snapshots[-1]
    print(f"  Latest: {latest.month} — repo={latest.repo_total:,}")
    for sd in subdirs:
        sd_label = sd.strip("/")
        print(f"    {sd_label}={latest.subdir_totals.get(sd.strip('/') + '/', 0):,}")
    print()

    # Generate report
    output_dir.mkdir(parents=True, exist_ok=True)

    # Normalize subdirs for display (the extractor adds trailing slashes)
    norm_subdirs = [sd.strip("/") + "/" for sd in subdirs]

    report_path = output_dir / "report.html"
    print("Generating HTML dashboard...")
    generate_report(snapshots, str(report_path), subdirs=norm_subdirs, repo_name=repo_name)

    # CSV
    csv_path = output_dir / "loc-data.csv"
    with open(csv_path, "w") as f:
        header_parts = ["month", "repo_total"]
        for sd in norm_subdirs:
            header_parts.append(sd.strip("/").replace("/", "_"))
        f.write(",".join(header_parts) + "\n")

        for s in snapshots:
            row = [s.month, str(s.repo_total)]
            for sd in norm_subdirs:
                row.append(str(s.subdir_totals.get(sd, 0)))
            f.write(",".join(row) + "\n")

    print(f"\nDone!")
    print(f"  Dashboard : {report_path}")
    print(f"  CSV data  : {csv_path}")
    print(f"\nOpen in browser:")
    print(f"  open {report_path}")


if __name__ == "__main__":
    main()
