"""
시나리오 단위 분석기

하나의 시나리오(예: idle)에 대해:
- 20회 meminfo를 평균 계산
- hprof before/after diff
- 두 결과를 합친 통합 분석 결과 생성
"""

from dataclasses import dataclass, field
from typing import Optional

from ..extractor.scanner import ScenarioData
from ..parser.meminfo_parser import MeminfoParser, MeminfoResult
from ..parser.hprof_parser import HprofParser, HprofSummary, HprofDiff


@dataclass
class ScenarioResult:
    """시나리오 분석 결과"""
    scenario_name: str

    # meminfo 분석
    meminfo_results: list = field(default_factory=list)  # 20회 개별 결과
    meminfo_average: Optional[MeminfoResult] = None
    meminfo_trend: list = field(default_factory=list)  # PSS 추이 (20개 값)

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

        # PSS 추이 (20회)
        if self.meminfo_trend:
            result["pss_trend"] = self.meminfo_trend
            first = self.meminfo_trend[0]
            last = self.meminfo_trend[-1]
            result["pss_growth"] = {
                "first_round": first,
                "last_round": last,
                "diff_kb": last - first,
                "diff_percent": round((last - first) / first * 100, 1) if first > 0 else 0,
            }

        # hprof diff 요약
        if self.hprof_diff:
            result["hprof_diff"] = self.hprof_diff.to_dict(top_n=hprof_top_n)

        return result


class ScenarioAnalyzer:
    """시나리오 분석기"""

    def __init__(self):
        self.meminfo_parser = MeminfoParser()
        self.hprof_parser = HprofParser()

    def analyze(self, scenario: ScenarioData) -> ScenarioResult:
        """시나리오 데이터를 분석"""
        result = ScenarioResult(scenario_name=scenario.name)

        # 1. meminfo 파싱 (20회)
        for round_num in sorted(scenario.rounds.keys()):
            rd = scenario.rounds[round_num]
            if rd.meminfo_path and rd.meminfo_path.exists():
                try:
                    mr = self.meminfo_parser.parse_file(str(rd.meminfo_path))
                    result.meminfo_results.append(mr)
                    result.meminfo_trend.append(mr.total_pss_kb)
                except Exception as e:
                    print(f"  경고: meminfo 파싱 실패 (회차 {round_num}): {e}")

        # 2. meminfo 평균 계산
        if result.meminfo_results:
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
