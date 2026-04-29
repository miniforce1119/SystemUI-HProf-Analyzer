"""
시나리오 단위 분석기

하나의 시나리오(예: idle)에 대해:
- 20회 meminfo 통계 분석 (평균, trimmed 평균, 중앙값, 이상치 감지)
- hprof before/after diff
- 두 결과를 합친 통합 분석 결과 생성
"""

import math
from dataclasses import dataclass, field
from typing import Optional

from ..extractor.scanner import ScenarioData
from ..parser.meminfo_parser import MeminfoParser, MeminfoResult
from ..parser.hprof_parser import HprofParser, HprofSummary, HprofDiff


@dataclass
class OutlierInfo:
    """이상치 정보"""
    round_index: int
    pss_value: int
    deviation: float  # 평균 대비 얼마나 벗어났는지 (σ 단위)


@dataclass
class TrendStats:
    """PSS 추이 통계"""
    count: int = 0
    raw_mean: int = 0             # 단순 평균
    trimmed_mean: int = 0         # 상하 10% 제거 평균
    median: int = 0               # 중앙값
    std_dev: float = 0            # 표준편차
    min_value: int = 0
    max_value: int = 0
    first_round: int = 0          # 1회차 PSS
    last_round: int = 0           # 마지막 회차 PSS
    growth_kb: int = 0            # 1회차 → 마지막 회차 변화량
    growth_percent: float = 0     # 변화율
    outliers: list = field(default_factory=list)    # 이상치 목록
    clean_trend: list = field(default_factory=list)  # 이상치 제거 후 추이
    is_leaking: bool = False      # 누수 판정

    def to_dict(self) -> dict:
        return {
            "count": self.count,
            "raw_mean": self.raw_mean,
            "trimmed_mean": self.trimmed_mean,
            "median": self.median,
            "std_dev": round(self.std_dev, 1),
            "min": self.min_value,
            "max": self.max_value,
            "first_round": self.first_round,
            "last_round": self.last_round,
            "growth_kb": self.growth_kb,
            "growth_percent": self.growth_percent,
            "outlier_count": len(self.outliers),
            "outliers": [
                {"round": o.round_index, "pss": o.pss_value, "sigma": round(o.deviation, 1)}
                for o in self.outliers
            ],
            "is_leaking": self.is_leaking,
        }


@dataclass
class ScenarioResult:
    """시나리오 분석 결과"""
    scenario_name: str

    # meminfo 분석
    meminfo_results: list = field(default_factory=list)  # 20회 개별 결과
    meminfo_average: Optional[MeminfoResult] = None
    meminfo_trend: list = field(default_factory=list)  # PSS 추이 (20개 값)
    trend_stats: Optional[TrendStats] = None           # 추이 통계

    # hprof 분석
    hprof_diff: Optional[HprofDiff] = None

    def to_dict(self, hprof_top_n: int = 15) -> dict:
        """통합 요약 딕셔너리"""
        result = {
            "scenario": self.scenario_name,
            "round_count": len(self.meminfo_results),
        }

        # meminfo 요약
        if self.meminfo_average:
            result["meminfo"] = self.meminfo_average.to_dict()
            result["meminfo"]["total_swap_pss"] = self.meminfo_average.total_swap_pss

        # PSS 추이 통계
        if self.trend_stats:
            result["trend_stats"] = self.trend_stats.to_dict()

        # PSS 추이 (20회) - 하위 호환
        if self.meminfo_trend:
            result["pss_trend"] = self.meminfo_trend

        # hprof diff 요약
        if self.hprof_diff:
            result["hprof_diff"] = self.hprof_diff.to_dict(top_n=hprof_top_n)

        return result


class ScenarioAnalyzer:
    """시나리오 분석기"""

    def __init__(self):
        self.meminfo_parser = MeminfoParser()
        self.hprof_parser = HprofParser()

    # 이상치 판정 기준 (평균 ± N*σ)
    OUTLIER_SIGMA = 2.0
    # 누수 판정 기준 (trimmed 평균 기준 1회차→마지막 회차 증가율)
    LEAK_THRESHOLD_PERCENT = 1.0

    def analyze_meminfo_only(self, scenario: ScenarioData) -> ScenarioResult:
        """meminfo만 분석 (hprof 건너뜀, 버전 비교 1단계용)"""
        result = ScenarioResult(scenario_name=scenario.name)
        self._parse_meminfo_rounds(result, scenario)
        if result.meminfo_results:
            result.meminfo_average = self._average_meminfo(result.meminfo_results)
            result.trend_stats = self._compute_trend_stats(result.meminfo_trend)
        return result

    def analyze(self, scenario: ScenarioData) -> ScenarioResult:
        """시나리오 전체 분석 (meminfo + hprof)"""
        result = ScenarioResult(scenario_name=scenario.name)
        self._parse_meminfo_rounds(result, scenario)

        # 2. meminfo 평균 및 통계 계산
        if result.meminfo_results:
            result.trend_stats = self._compute_trend_stats(result.meminfo_trend)
            # 이상치 제거된 결과로 평균 계산
            if result.trend_stats.outliers:
                outlier_indices = {o.round_index for o in result.trend_stats.outliers}
                clean_results = [
                    r for i, r in enumerate(result.meminfo_results) if i not in outlier_indices
                ]
                result.meminfo_average = self._average_meminfo(clean_results or result.meminfo_results)
            else:
                result.meminfo_average = self._average_meminfo(result.meminfo_results)

        # 3. hprof before/after diff
        if scenario.has_hprof:
            print(f"  hprof 분석 중 (before vs after)...")
            try:
                result.hprof_diff = self.hprof_parser.diff(
                    str(scenario.hprof_before),
                    str(scenario.hprof_after),
                )
            except Exception as e:
                print(f"  경고: hprof 분석 실패: {e}")

        return result

    def _compute_trend_stats(self, trend: list) -> TrendStats:
        """PSS 추이 데이터의 통계 분석"""
        if not trend:
            return TrendStats()

        n = len(trend)
        sorted_trend = sorted(trend)
        stats = TrendStats(count=n)

        # 기본 통계
        stats.raw_mean = sum(trend) // n
        stats.min_value = sorted_trend[0]
        stats.max_value = sorted_trend[-1]
        stats.first_round = trend[0]
        stats.last_round = trend[-1]

        # 중앙값
        if n % 2 == 0:
            stats.median = (sorted_trend[n // 2 - 1] + sorted_trend[n // 2]) // 2
        else:
            stats.median = sorted_trend[n // 2]

        # 표준편차
        variance = sum((v - stats.raw_mean) ** 2 for v in trend) / n
        stats.std_dev = math.sqrt(variance)

        # Trimmed Mean (상하 10% 제거)
        trim_count = max(1, n // 10)  # 20회면 상하 2개씩 제거
        trimmed = sorted_trend[trim_count:-trim_count] if trim_count < n // 2 else sorted_trend
        stats.trimmed_mean = sum(trimmed) // len(trimmed)

        # 이상치 감지 (평균 ± 2σ)
        if stats.std_dev > 0:
            for i, v in enumerate(trend):
                deviation = abs(v - stats.raw_mean) / stats.std_dev
                if deviation >= self.OUTLIER_SIGMA:
                    stats.outliers.append(OutlierInfo(
                        round_index=i,
                        pss_value=v,
                        deviation=deviation,
                    ))

        # 이상치 제거된 추이
        outlier_indices = {o.round_index for o in stats.outliers}
        stats.clean_trend = [v for i, v in enumerate(trend) if i not in outlier_indices]

        # 성장률 (trimmed mean 기반, clean_trend의 처음과 끝 비교)
        if stats.clean_trend:
            clean_first = stats.clean_trend[0]
            clean_last = stats.clean_trend[-1]
            stats.growth_kb = clean_last - clean_first
            stats.growth_percent = round(
                (clean_last - clean_first) / clean_first * 100, 1
            ) if clean_first > 0 else 0
        else:
            stats.growth_kb = stats.last_round - stats.first_round
            stats.growth_percent = round(
                (stats.last_round - stats.first_round) / stats.first_round * 100, 1
            ) if stats.first_round > 0 else 0

        # 누수 판정
        stats.is_leaking = stats.growth_percent >= self.LEAK_THRESHOLD_PERCENT

        return stats

    def _parse_meminfo_rounds(self, result: ScenarioResult, scenario: ScenarioData):
        """시나리오의 meminfo 파일들을 파싱하여 result에 채움"""
        for round_num in sorted(scenario.rounds.keys()):
            rd = scenario.rounds[round_num]
            if rd.meminfo_path and rd.meminfo_path.exists():
                try:
                    mr = self.meminfo_parser.parse_file(str(rd.meminfo_path))
                    result.meminfo_results.append(mr)
                    result.meminfo_trend.append(mr.total_pss_kb)
                except Exception as e:
                    print(f"  경고: meminfo 파싱 실패 (회차 {round_num}): {e}")

    def _average_meminfo(self, results: list) -> MeminfoResult:
        """여러 MeminfoResult의 평균 계산"""
        if len(results) == 1:
            return results[0]

        n = len(results)
        avg = MeminfoResult()
        avg.pid = results[0].pid
        avg.process_name = results[0].process_name

        # TOTAL 평균
        if all(r.total for r in results):
            from ..parser.meminfo_parser import MemorySection
            avg.total = MemorySection(
                name="TOTAL",
                pss_total=sum(r.total.pss_total for r in results) // n,
                private_dirty=sum(r.total.private_dirty for r in results) // n,
                private_clean=sum(r.total.private_clean for r in results) // n,
                swap_pss_dirty=sum(r.total.swap_pss_dirty for r in results) // n,
                rss_total=sum(r.total.rss_total for r in results) // n,
                heap_size=sum(r.total.heap_size for r in results) // n,
                heap_alloc=sum(r.total.heap_alloc for r in results) // n,
                heap_free=sum(r.total.heap_free for r in results) // n,
            )

        # App Summary 평균
        if all(r.app_summary for r in results):
            from ..parser.meminfo_parser import AppSummary
            avg.app_summary = AppSummary(
                java_heap_pss=sum(r.app_summary.java_heap_pss for r in results) // n,
                java_heap_rss=sum(r.app_summary.java_heap_rss for r in results) // n,
                native_heap_pss=sum(r.app_summary.native_heap_pss for r in results) // n,
                native_heap_rss=sum(r.app_summary.native_heap_rss for r in results) // n,
                code_pss=sum(r.app_summary.code_pss for r in results) // n,
                code_rss=sum(r.app_summary.code_rss for r in results) // n,
                stack_pss=sum(r.app_summary.stack_pss for r in results) // n,
                stack_rss=sum(r.app_summary.stack_rss for r in results) // n,
                graphics_pss=sum(r.app_summary.graphics_pss for r in results) // n,
                graphics_rss=sum(r.app_summary.graphics_rss for r in results) // n,
                private_other_pss=sum(r.app_summary.private_other_pss for r in results) // n,
                system_pss=sum(r.app_summary.system_pss for r in results) // n,
                total_pss=sum(r.app_summary.total_pss for r in results) // n,
                total_rss=sum(r.app_summary.total_rss for r in results) // n,
            )

        # Objects 평균
        if all(r.objects for r in results):
            from ..parser.meminfo_parser import ObjectsInfo
            avg.objects = ObjectsInfo(
                views=sum(r.objects.views for r in results) // n,
                view_root_impl=sum(r.objects.view_root_impl for r in results) // n,
                app_contexts=sum(r.objects.app_contexts for r in results) // n,
                activities=sum(r.objects.activities for r in results) // n,
                assets=sum(r.objects.assets for r in results) // n,
                asset_managers=sum(r.objects.asset_managers for r in results) // n,
                local_binders=sum(r.objects.local_binders for r in results) // n,
                proxy_binders=sum(r.objects.proxy_binders for r in results) // n,
                parcel_memory=sum(r.objects.parcel_memory for r in results) // n,
                parcel_count=sum(r.objects.parcel_count for r in results) // n,
                death_recipients=sum(r.objects.death_recipients for r in results) // n,
                openssl_sockets=sum(r.objects.openssl_sockets for r in results) // n,
                webviews=sum(r.objects.webviews for r in results) // n,
            )

        # TOTAL SWAP PSS 평균
        avg.total_swap_pss = sum(r.total_swap_pss for r in results) // n

        # Native Allocations 평균
        avg.native_alloc_malloc = sum(r.native_alloc_malloc for r in results) // n
        avg.native_alloc_other = sum(r.native_alloc_other for r in results) // n
        avg.native_alloc_bitmap = sum(r.native_alloc_bitmap for r in results) // n

        # Databases는 첫 번째 결과 사용
        avg.databases = results[0].databases

        return avg
