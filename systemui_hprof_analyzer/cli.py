"""
SystemUI HProf Analyzer CLI

사용법:
  # 테스트 아카이브 스캔 (시나리오 목록 확인)
  python -m systemui_hprof_analyzer scan ./test_data

  # 특정 시나리오 분석 (meminfo 20회 + hprof diff)
  python -m systemui_hprof_analyzer analyze ./test_data --scenario idle

  # 전체 시나리오 분석
  python -m systemui_hprof_analyzer analyze ./test_data --all

  # hprof만 빠르게 비교
  python -m systemui_hprof_analyzer hprof-diff before.hprof after.hprof

  # meminfo만 파싱
  python -m systemui_hprof_analyzer parse-meminfo meminfo.txt
"""

import argparse
import json
import sys

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from .extractor import scan_test_archive
from .parser import MeminfoParser, HprofParser
from .analyzer import ScenarioAnalyzer
from .report import ReportGenerator


def cmd_scan(args):
    """테스트 아카이브 스캔"""
    archive = scan_test_archive(args.path)

    print(f"=== 테스트 아카이브 스캔 결과 ===")
    print(f"소스: {archive.source_path}")
    print(f"시나리오: {len(archive.scenarios)}개")
    print()

    for name, sd in archive.scenarios.items():
        hprof_status = "O" if sd.has_hprof else "X"
        bugreport_status = "O" if sd.bugreport_path else "X"
        print(f"  [{name}]")
        print(f"    회차: {sd.round_count}회")
        print(f"    hprof (before/after): {hprof_status}")
        print(f"    bugreport: {bugreport_status}")
        print()


def cmd_analyze(args):
    """시나리오 분석"""
    archive = scan_test_archive(args.path)

    if not archive.scenarios:
        print("오류: 시나리오를 찾을 수 없습니다.")
        return

    analyzer = ScenarioAnalyzer()
    report_gen = ReportGenerator()

    # 분석 대상 결정
    if args.all:
        targets = list(archive.scenarios.keys())
    elif args.scenario:
        if args.scenario in archive.scenarios:
            targets = [args.scenario]
        else:
            print(f"오류: '{args.scenario}' 시나리오를 찾을 수 없습니다.")
            print(f"가능한 시나리오: {', '.join(archive.scenarios.keys())}")
            return
    else:
        print("오류: --scenario 또는 --all을 지정하세요.")
        return

    for scenario_name in targets:
        sd = archive.scenarios[scenario_name]
        print(f"=== {scenario_name} 분석 ===")
        print(f"  meminfo {sd.round_count}회 파싱 중...")

        result = analyzer.analyze(sd)

        if result.meminfo_average:
            print(f"  평균 PSS: {result.meminfo_average.total_pss_kb:,} KB")

        if result.meminfo_trend:
            first = result.meminfo_trend[0]
            last = result.meminfo_trend[-1]
            diff = last - first
            print(f"  PSS 추이: {first:,} → {last:,} KB ({diff:+,})")

        if result.hprof_diff:
            d = result.hprof_diff
            print(f"  hprof 인스턴스 변화: {d.total_instance_diff:+,}")
            print(f"  hprof 크기 변화: {d.total_size_diff // 1024:+,} KB")

        # 보고서 생성
        report = report_gen.generate_markdown(result)

        if args.output:
            if len(targets) > 1:
                filename = f"report_{scenario_name}.md"
            else:
                filename = args.output
            filepath = report_gen.save_report(report, filename=filename)
            print(f"  보고서: {filepath}")
        else:
            print()
            print(report)

        if args.json:
            print(f"\n=== {scenario_name} JSON ===")
            print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))

        print()


def cmd_hprof_diff(args):
    """hprof before/after 비교"""
    parser = HprofParser()

    print("hprof 파싱 중... (파일 크기에 따라 10-30초 소요)")
    diff = parser.diff(args.before, args.after)

    print(f"\n=== hprof diff 결과 ===")
    print(f"인스턴스 변화: {diff.total_instance_diff:+,}")
    print(f"크기 변화: {diff.total_size_diff // 1024:+,} KB")
    print()

    if diff.increased_classes:
        print("인스턴스 증가 TOP 15:")
        print(f"{'클래스':<60} {'Before':>8} {'After':>8} {'증가':>8}")
        print("-" * 88)
        for name, bc, ac, _, _ in diff.increased_classes[:15]:
            print(f"{name:<60} {bc:>8,} {ac:>8,} {ac - bc:>+8,}")

    if diff.new_classes:
        print(f"\n새로 생성된 클래스: {len(diff.new_classes)}개")
        for name, count, size in diff.new_classes[:10]:
            print(f"  {name}: {count}개 ({size // 1024} KB)")


def cmd_parse_meminfo(args):
    """meminfo 파일 파싱"""
    parser = MeminfoParser()
    result = parser.parse_file(args.file)

    print(f"=== {result.process_name} (PID: {result.pid}) ===")
    print(f"Total PSS: {result.total_pss_kb:,} KB")
    print(f"Total RSS: {result.total_rss_kb:,} KB")
    print(f"Total SWAP PSS: {result.total_swap_pss:,} KB")

    if args.json:
        print("\n=== JSON ===")
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(
        description="SystemUI HProf & Memory Analyzer (2번 테스트 시스템용)",
    )
    subparsers = parser.add_subparsers(dest="command", help="명령어")

    # scan
    scan_parser = subparsers.add_parser("scan", help="테스트 아카이브 스캔")
    scan_parser.add_argument("path", help="아카이브 zip 또는 해제된 폴더")

    # analyze
    analyze_parser = subparsers.add_parser("analyze", help="시나리오 분석")
    analyze_parser.add_argument("path", help="아카이브 zip 또는 해제된 폴더")
    analyze_parser.add_argument("--scenario", help="분석할 시나리오 (예: idle)")
    analyze_parser.add_argument("--all", action="store_true", help="전체 시나리오 분석")
    analyze_parser.add_argument("-o", "--output", help="보고서 출력 파일명")
    analyze_parser.add_argument("--json", action="store_true", help="JSON도 출력")

    # hprof-diff
    hprof_parser = subparsers.add_parser("hprof-diff", help="hprof before/after 비교")
    hprof_parser.add_argument("before", help="before hprof 파일")
    hprof_parser.add_argument("after", help="after hprof 파일")

    # parse-meminfo
    meminfo_parser = subparsers.add_parser("parse-meminfo", help="meminfo 파일 파싱")
    meminfo_parser.add_argument("file", help="meminfo 파일")
    meminfo_parser.add_argument("--json", action="store_true", help="JSON 출력")

    args = parser.parse_args()

    if args.command == "scan":
        cmd_scan(args)
    elif args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "hprof-diff":
        cmd_hprof_diff(args)
    elif args.command == "parse-meminfo":
        cmd_parse_meminfo(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
