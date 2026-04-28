"""
두 버전 간 비교 분석기

1단계: 버전 A(기준) vs 버전 B(비교 대상)의 시나리오별 meminfo 평균을 비교
2단계: regression이 감지된 시나리오에 대해 hprof 심층 분석 수행
"""

from dataclasses import dataclass, field
from typing import Optional

from ..extractor.scanner import TestArchive
from ..parser.meminfo_parser import MeminfoParser, MeminfoResult
from ..parser.hprof_parser import HprofParser, HprofDiff
from .scenario_analyzer import ScenarioAnalyzer, ScenarioResult


@dataclass
class ScenarioComparison:
    """시나리오별 버전 비교 결과"""
    scenario_name: str
    baseline_avg_pss: int = 0
    target_avg_pss: int = 0
    diff_kb: int = 0
    diff_percent: float = 0
    severity: str = "normal"  # normal, warning, critical
    # 상세 분석 결과 (regression 감지 시에만)
    target_analysis: Optional[ScenarioResult] = None
    cross_version_hprof_diff: Optional[HprofDiff] = None


@dataclass
class VersionComparisonResult:
    """두 버전 비교 전체 결과"""
    baseline_path: str = ""
    target_path: str = ""
    scenario_comparisons: list = field(default_factory=list)
    regression_scenarios: list = field(default_factory=list)  # severity != normal

    def to_dict(self) -> dict:
        return {
            "baseline": self.baseline_path,
            "target": self.target_path,
            "scenarios": [
                {
                    "scenario": sc.scenario_name,
                    "baseline_avg_pss_kb": sc.baseline_avg_pss,
                    "target_avg_pss_kb": sc.target_avg_pss,
                    "diff_kb": sc.diff_kb,
                    "diff_percent": round(sc.diff_percent, 1),
                    "severity": sc.severity,
                }
                for sc in self.scenario_comparisons
            ],
            "regression_count": len(self.regression_scenarios),
        }


class VersionComparator:
    """두 버전 비교기"""

    # 임계값
    THRESHOLDS = {
        "critical_kb": 30000,    # 30MB 이상 증가
        "critical_pct": 10.0,    # 10% 이상 증가
        "warning_kb": 10000,     # 10MB 이상 증가
        "warning_pct": 3.0,      # 3% 이상 증가
    }

    def __init__(self):
        self.scenario_analyzer = ScenarioAnalyzer()
        self.hprof_parser = HprofParser()

    def compare(
        self,
        baseline: TestArchive,
        target: TestArchive,
        deep_analysis: bool = True,
    ) -> VersionComparisonResult:
        """두 버전의 시나리오별 meminfo 평균을 비교

        Args:
            baseline: 기준 버전 데이터
            target: 비교 대상 버전 데이터
            deep_analysis: regression 감지 시 hprof 분석까지 수행할지
        """
        result = VersionComparisonResult(
            baseline_path=baseline.source_path,
            target_path=target.source_path,
        )

        # 공통 시나리오 찾기
        common_scenarios = (
            set(baseline.scenarios.keys()) & set(target.scenarios.keys())
        )

        for scenario_name in sorted(common_scenarios):
            print(f"  [{scenario_name}] meminfo 비교 중...")

            b_scenario = baseline.scenarios[scenario_name]
            t_scenario = target.scenarios[scenario_name]

            # 각 버전의 meminfo 20회 평균 계산
            b_result = self.scenario_analyzer.analyze_meminfo_only(b_scenario)
            t_result = self.scenario_analyzer.analyze_meminfo_only(t_scenario)

            b_pss = b_result.meminfo_average.total_pss_kb if b_result.meminfo_average else 0
            t_pss = t_result.meminfo_average.total_pss_kb if t_result.meminfo_average else 0

            diff = t_pss - b_pss
            pct = (diff / b_pss * 100) if b_pss > 0 else 0

            sc = ScenarioComparison(
                scenario_name=scenario_name,
                baseline_avg_pss=b_pss,
                target_avg_pss=t_pss,
                diff_kb=diff,
                diff_percent=pct,
                severity=self._classify_severity(diff, pct),
            )

            # regression 감지 시 심층 분석
            if sc.severity != "normal" and deep_analysis:
                print(f"  [{scenario_name}] ⚠️ regression 감지 → 심층 분석 시작...")

                # 방법 A: target 버전 내부 hprof before vs after
                if t_scenario.has_hprof:
                    print(f"  [{scenario_name}] target hprof before vs after 분석 중...")
                    sc.target_analysis = self.scenario_analyzer.analyze(t_scenario)

                # 방법 B: 두 버전의 after hprof 비교 (선택)
                if b_scenario.has_hprof and t_scenario.has_hprof:
                    print(f"  [{scenario_name}] 버전 간 hprof 비교 중...")
                    sc.cross_version_hprof_diff = self.hprof_parser.diff(
                        str(b_scenario.hprof_after),
                        str(t_scenario.hprof_after),
                    )

                result.regression_scenarios.append(sc)

            result.scenario_comparisons.append(sc)

        return result

    def _classify_severity(self, diff_kb: int, diff_pct: float) -> str:
        if diff_kb >= self.THRESHOLDS["critical_kb"] or diff_pct >= self.THRESHOLDS["critical_pct"]:
            return "critical"
        elif diff_kb >= self.THRESHOLDS["warning_kb"] or diff_pct >= self.THRESHOLDS["warning_pct"]:
            return "warning"
        return "normal"
