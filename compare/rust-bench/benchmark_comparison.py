#!/usr/bin/env python3
"""
Benchmark Comparison Tool for Rust vs C++ Performance Analysis

Extracts and compares runtime performance data from Criterion benchmark results.
"""

import json
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from typing import Dict, List, Tuple, Optional


class BenchmarkComparator:
    def __init__(self, criterion_dir: str = "criterion"):
        self.criterion_dir = Path(criterion_dir)
        self.results = {}

    def extract_benchmark_data(self, benchmark_path: Path) -> Optional[Dict]:
        """Extract timing data from a benchmark directory."""
        estimates_file = benchmark_path / "base" / "estimates.json"
        benchmark_file = benchmark_path / "base" / "benchmark.json"

        if not estimates_file.exists() or not benchmark_file.exists():
            return None

        try:
            with open(estimates_file) as f:
                estimates = json.load(f)
            with open(benchmark_file) as f:
                benchmark_info = json.load(f)

            return {
                "mean_time_ns": estimates["mean"]["point_estimate"],
                "mean_confidence_lower": estimates["mean"]["confidence_interval"][
                    "lower_bound"
                ],
                "mean_confidence_upper": estimates["mean"]["confidence_interval"][
                    "upper_bound"
                ],
                "std_dev": estimates["std_dev"]["point_estimate"],
                "median_time_ns": estimates["median"]["point_estimate"],
                "throughput_bytes": benchmark_info.get("throughput", {}).get(
                    "Bytes", 0
                ),
                "group_id": benchmark_info["group_id"],
                "function_id": benchmark_info["function_id"],
                "test_case": benchmark_info.get("value_str", "default"),
            }
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error reading {benchmark_path}: {e}")
            return None

    def scan_benchmarks(self) -> Dict[str, List[Dict]]:
        """Scan all benchmark directories and extract data."""
        results = {}

        for group_dir in self.criterion_dir.iterdir():
            if not group_dir.is_dir():
                continue

            group_name = group_dir.name
            results[group_name] = []

            for benchmark_dir in group_dir.iterdir():
                if not benchmark_dir.is_dir():
                    continue

                # Handle nested test cases
                if (benchmark_dir / "base").exists():
                    # Direct benchmark directory
                    data = self.extract_benchmark_data(benchmark_dir)
                    if data:
                        results[group_name].append(data)
                else:
                    # Test case subdirectories
                    for test_dir in benchmark_dir.iterdir():
                        if test_dir.is_dir() and (test_dir / "base").exists():
                            data = self.extract_benchmark_data(test_dir)
                            if data:
                                results[group_name].append(data)

        return results

    def find_best_rust_config(
        self, group_name: Optional[str] = None
    ) -> Dict[str, Dict]:
        """Find the best performing Rust configuration for each test case."""
        all_results = self.scan_benchmarks()
        best_configs = {}

        for group, benchmarks in all_results.items():
            if group_name is not None and group != group_name:
                continue

            # Group by test case
            test_cases = {}
            for bench in benchmarks:
                test_case = bench.get("test_case", "default")
                if test_case not in test_cases:
                    test_cases[test_case] = {}
                test_cases[test_case][bench["function_id"]] = bench

            # Find best Rust implementation for each test case
            for test_case, implementations in test_cases.items():
                rust_impls = {}
                cpp_impl = None

                for func_id, data in implementations.items():
                    if "cpp" in func_id.lower():
                        cpp_impl = data
                    else:
                        rust_impls[func_id] = data

                if rust_impls and cpp_impl:
                    # Find fastest Rust implementation
                    best_rust = min(
                        rust_impls.items(), key=lambda x: x[1]["mean_time_ns"]
                    )
                    key = f"{group}_{test_case}"
                    best_configs[key] = {
                        "group": group,
                        "test_case": test_case,
                        "best_rust": best_rust[1],
                        "cpp": cpp_impl,
                        "all_rust_configs": rust_impls,
                    }

        return best_configs

    def compare_cpp_vs_best_rust(
        self, group_name: Optional[str] = None
    ) -> pd.DataFrame:
        """Compare C++ vs only the best Rust configuration for each test case."""
        best_configs = self.find_best_rust_config(group_name)

        comparison_data = []

        for key, config in best_configs.items():
            cpp_impl = config["cpp"]
            best_rust = config["best_rust"]

            speedup = cpp_impl["mean_time_ns"] / best_rust["mean_time_ns"]

            comparison_data.append(
                {
                    "group": config["group"],
                    "test_case": config["test_case"],
                    "cpp_impl": cpp_impl["function_id"],
                    "best_rust_impl": best_rust["function_id"],
                    "cpp_time_ns": cpp_impl["mean_time_ns"],
                    "rust_time_ns": best_rust["mean_time_ns"],
                    "cpp_time_ms": cpp_impl["mean_time_ns"] / 1_000_000,
                    "rust_time_ms": best_rust["mean_time_ns"] / 1_000_000,
                    "speedup_factor": speedup,
                    "faster_language": "Rust" if speedup > 1 else "C++",
                    "performance_diff_percent": (
                        (cpp_impl["mean_time_ns"] - best_rust["mean_time_ns"])
                        / cpp_impl["mean_time_ns"]
                    )
                    * 100,
                    "throughput_bytes": best_rust["throughput_bytes"],
                    "total_rust_configs_tested": len(config["all_rust_configs"]),
                }
            )

        return pd.DataFrame(comparison_data)

    def generate_summary_report(self, df: pd.DataFrame) -> str:
        """Generate a text summary of the comparison."""
        report = []
        report.append("=" * 70)
        report.append("BEST RUST vs C++ BENCHMARK COMPARISON SUMMARY")
        report.append("=" * 70)

        if df.empty:
            report.append("No comparison data found.")
            return "\n".join(report)

        # Overall statistics
        rust_wins = len(df[df["faster_language"] == "Rust"])
        cpp_wins = len(df[df["faster_language"] == "C++"])
        total_comparisons = len(df)

        report.append(f"\nTotal Test Cases: {total_comparisons}")
        report.append(
            f"Best Rust Config Wins: {rust_wins} ({rust_wins/total_comparisons*100:.1f}%)"
        )
        report.append(f"C++ Wins: {cpp_wins} ({cpp_wins/total_comparisons*100:.1f}%)")

        # Show total configs tested
        total_rust_configs = df["total_rust_configs_tested"].sum()
        report.append(f"Total Rust Configurations Tested: {total_rust_configs}")
        report.append(f"Showing only best performing Rust config per test case")

        # Best performance gains
        if not df.empty:
            best_rust = df.loc[df["speedup_factor"].idxmax()]
            best_cpp = df.loc[df["speedup_factor"].idxmin()]

            report.append(f"\nBiggest Rust Victory:")
            report.append(f"  {best_rust['best_rust_impl']} vs {best_rust['cpp_impl']}")
            report.append(f"  Speedup: {best_rust['speedup_factor']:.2f}x faster")
            report.append(f"  Test: {best_rust['test_case']}")

            if best_cpp["speedup_factor"] < 1:
                report.append(f"\nBiggest C++ Victory:")
                report.append(
                    f"  {best_cpp['cpp_impl']} vs {best_cpp['best_rust_impl']}"
                )
                report.append(f"  Speedup: {1/best_cpp['speedup_factor']:.2f}x faster")
                report.append(f"  Test: {best_cpp['test_case']}")

        # Group-by-group breakdown
        report.append(f"\nDetailed Results by Group:")
        report.append("-" * 50)

        for group in df["group"].unique():
            group_data = df[df["group"] == group]
            report.append(f"\n{group.upper()}:")

            for _, row in group_data.iterrows():
                winner = "🦀 Rust" if row["faster_language"] == "Rust" else "🏎️  C++"
                configs_note = (
                    f" (best of {row['total_rust_configs_tested']} Rust configs)"
                )
                report.append(f"  {row['test_case']}:")
                report.append(
                    f"    Best Rust ({row['best_rust_impl']}): {row['rust_time_ms']:.2f}ms{configs_note}"
                )
                report.append(
                    f"    C++ ({row['cpp_impl']}): {row['cpp_time_ms']:.2f}ms"
                )
                report.append(
                    f"    Winner: {winner} ({abs(row['performance_diff_percent']):.1f}% faster)"
                )

        return "\n".join(report)

    def plot_comparison(
        self, df: pd.DataFrame, save_path: str = "benchmark_comparison.png"
    ):
        """Create visualization of the comparison results."""
        if df.empty:
            print("No data to plot.")
            return

        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))

        # 1. Speedup factors
        colors = ["green" if x > 1 else "red" for x in df["speedup_factor"]]
        bars = ax1.barh(range(len(df)), df["speedup_factor"], color=colors, alpha=0.7)
        ax1.set_yticks(range(len(df)))
        ax1.set_yticklabels(
            [
                f"{row['best_rust_impl']}\nvs\n{row['cpp_impl']}"
                for _, row in df.iterrows()
            ],
            fontsize=8,
        )
        ax1.axvline(x=1, color="black", linestyle="--", alpha=0.5)
        ax1.set_xlabel("Speedup Factor (Rust time / C++ time)")
        ax1.set_title(
            "Performance Comparison: Best Rust vs C++\n(>1 = Rust faster, <1 = C++ faster)"
        )

        # 2. Runtime comparison
        x = range(len(df))
        width = 0.35
        ax2.bar(
            [i - width / 2 for i in x],
            df["rust_time_ms"],
            width,
            label="Rust",
            alpha=0.8,
            color="orange",
        )
        ax2.bar(
            [i + width / 2 for i in x],
            df["cpp_time_ms"],
            width,
            label="C++",
            alpha=0.8,
            color="blue",
        )
        ax2.set_xlabel("Test Cases")
        ax2.set_ylabel("Runtime (ms)")
        ax2.set_title("Absolute Runtime Comparison")
        ax2.legend()
        ax2.set_xticks(x)
        ax2.set_xticklabels(
            [f"{row['test_case']}" for _, row in df.iterrows()], rotation=45, ha="right"
        )

        # 3. Performance difference percentage
        colors = ["green" if x > 0 else "red" for x in df["performance_diff_percent"]]
        ax3.bar(range(len(df)), df["performance_diff_percent"], color=colors, alpha=0.7)
        ax3.axhline(y=0, color="black", linestyle="-", alpha=0.3)
        ax3.set_xlabel("Test Cases")
        ax3.set_ylabel("Performance Difference (%)")
        ax3.set_title("Performance Difference\n(Positive = Rust faster)")
        ax3.set_xticks(range(len(df)))
        ax3.set_xticklabels(
            [f"{row['test_case']}" for _, row in df.iterrows()], rotation=45, ha="right"
        )

        # 4. Win distribution
        win_counts = df["faster_language"].value_counts()
        colors_pie = [
            "orange" if lang == "Rust" else "blue" for lang in win_counts.index
        ]
        ax4.pie(
            win_counts.values,
            labels=win_counts.index,
            autopct="%1.1f%%",
            colors=colors_pie,
        )
        ax4.set_title("Overall Winner Distribution")

        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"Comparison plot saved to {save_path}")
        return fig


def main():
    """Main execution function."""
    comparator = BenchmarkComparator()

    # Get comparison data - only best Rust configs vs C++
    comparison_df = comparator.compare_cpp_vs_best_rust()

    if comparison_df.empty:
        print("No benchmark data found for comparison.")
        return

    # Generate and display summary
    summary = comparator.generate_summary_report(comparison_df)
    print(summary)

    # Save detailed results to CSV
    # comparison_df.to_csv('benchmark_results.csv', index=False)
    # print(f"\nDetailed results saved to benchmark_results.csv")

    # Create visualization
    comparator.plot_comparison(comparison_df)

    # Show top performers
    print("\n" + "=" * 60)
    print("TOP RUST CONFIGURATIONS:")
    rust_wins = comparison_df[comparison_df["faster_language"] == "Rust"].nlargest(
        3, "speedup_factor"
    )
    for _, row in rust_wins.iterrows():
        print(
            f"  {row['best_rust_impl']}: {row['speedup_factor']:.2f}x faster than {row['cpp_impl']}"
        )

    if len(comparison_df[comparison_df["faster_language"] == "C++"]) > 0:
        print("\nC++ STILL WINS AGAINST BEST RUST:")
        cpp_wins = comparison_df[comparison_df["faster_language"] == "C++"].nsmallest(
            3, "speedup_factor"
        )
        for _, row in cpp_wins.iterrows():
            print(
                f"  {row['cpp_impl']}: {1/row['speedup_factor']:.2f}x faster than best Rust ({row['best_rust_impl']})"
            )


if __name__ == "__main__":
    main()

