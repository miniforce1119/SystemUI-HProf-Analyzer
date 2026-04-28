"""
시나리오 분석 보고서 생성기

meminfo 20회 추이 + hprof before/after diff를 포함한
Mermaid 시각화 보고서를 생성합니다.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from ..analyzer.scenario_analyzer import ScenarioResult


class ReportGenerator:
    """분석 보고서 생성기"""

    def generate_markdown(self, result: ScenarioResult) -> str:
        """시나리오 분석 결과를 Markdown 보고서로 생성"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            f"# SystemUI Memory 분석 보고서 — {result.scenario_name}",
            f"",
            f"**생성일시:** {now}  ",
            f"**시나리오:** {result.scenario_name}  ",
            f"**측정 횟수:** {len(result.meminfo_results)}회",
            f"",
            f"---",
            f"",
        ]

        # 1. meminfo 요약
        if result.meminfo_average:
            lines += self._section_meminfo_summary(result)

        # 2. PSS 추이 (20회)
        if result.meminfo_trend:
            lines += self._section_pss_trend(result)

        # 3. hprof diff (핵심)
        if result.hprof_diff:
            lines += self._section_hprof_diff(result)

        # 4. 분석자 기록
        lines += self._section_human_in_the_loop()

        lines.append("---")
        lines.append(f"*이 보고서는 SystemUI HProf Analyzer에 의해 자동 생성되었습니다.*")

        return "\n".join(lines)

    def save_report(self, content: str, output_dir: str = ".", filename: str = "") -> str:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"report_{timestamp}.md"
        filepath = output_path / filename
        filepath.write_text(content, encoding="utf-8")
        return str(filepath)

    def _section_meminfo_summary(self, result: ScenarioResult) -> list:
        avg = result.meminfo_average
        lines = [
            "## 1. 메모리 요약 (20회 평균)",
            "",
        ]
        if avg.app_summary:
            s = avg.app_summary
            lines += [
                "| 영역 | PSS (KB) |",
                "|------|----------|",
                f"| **Total PSS** | **{avg.total_pss_kb:,}** |",
                f"| Java Heap | {s.java_heap_pss:,} |",
                f"| Native Heap | {s.native_heap_pss:,} |",
                f"| Code | {s.code_pss:,} |",
                f"| Stack | {s.stack_pss:,} |",
                f"| Graphics | {s.graphics_pss:,} |",
                f"| Private Other | {s.private_other_pss:,} |",
                f"| System | {s.system_pss:,} |",
                f"| TOTAL SWAP PSS | {avg.total_swap_pss:,} |",
                "",
            ]
        if avg.objects:
            o = avg.objects
            lines += [
                "### Objects",
                "",
                f"| Views | ViewRootImpl | Activities | AppContexts | Binders (L/P) |",
                f"|-------|-------------|------------|-------------|---------------|",
                f"| {o.views} | {o.view_root_impl} | {o.activities} | {o.app_contexts} | {o.local_binders}/{o.proxy_binders} |",
                "",
            ]
        return lines

    def _section_pss_trend(self, result: ScenarioResult) -> list:
        trend = result.meminfo_trend
        first = trend[0]
        last = trend[-1]
        diff = last - first
        pct = (diff / first * 100) if first > 0 else 0

        lines = [
            "## 2. PSS 추이 (20회 반복)",
            "",
            f"| 항목 | 값 |",
            f"|------|-----|",
            f"| 1회차 PSS | {first:,} KB |",
            f"| 20회차 PSS | {last:,} KB |",
            f"| 변화량 | {diff:+,} KB ({pct:+.1f}%) |",
            "",
        ]

        # Mermaid 라인 차트
        trend_str = ", ".join(str(v) for v in trend)
        x_labels = ", ".join(f'"{i}"' for i in range(len(trend)))
        lines += [
            f"```mermaid",
            f"xychart-beta",
            f'    title "PSS 추이 — {result.scenario_name} (KB)"',
            f"    x-axis [{x_labels}]",
            f'    y-axis "KB" {min(trend) - 1000} --> {max(trend) + 1000}',
            f"    line [{trend_str}]",
            f"```",
            "",
        ]

        # 증가 추세 판정
        if pct > 5:
            lines.append(f"> ⚠️ **20회 반복 동안 PSS가 {pct:.1f}% 증가** — 메모리 누수 가능성 있음")
        elif pct > 1:
            lines.append(f"> ℹ️ PSS가 소폭 증가 ({pct:.1f}%) — 모니터링 필요")
        else:
            lines.append(f"> ✅ PSS 안정적 (변화율 {pct:.1f}%)")
        lines.append("")

        return lines

    def _section_hprof_diff(self, result: ScenarioResult) -> list:
        diff = result.hprof_diff
        lines = [
            "## 3. Heap 객체 분석 (hprof before vs after)",
            "",
            f"| 항목 | 값 |",
            f"|------|-----|",
            f"| 전체 인스턴스 변화 | {diff.total_instance_diff:+,} |",
            f"| 전체 Shallow Size 변화 | {diff.total_size_diff // 1024:+,} KB |",
            "",
        ]

        # 증가한 클래스 TOP
        if diff.increased_classes:
            lines += [
                "### 인스턴스 증가 TOP 15 (leak 의심)",
                "",
                "| 클래스 | Before | After | 증가량 | 크기 변화 (KB) |",
                "|--------|--------|-------|--------|---------------|",
            ]
            for name, bc, ac, b_size, a_size in diff.increased_classes[:15]:
                size_diff = (a_size - b_size) // 1024
                lines.append(
                    f"| `{name}` | {bc:,} | {ac:,} | **+{ac - bc:,}** | {size_diff:+,} |"
                )
            lines.append("")

            # 파이 차트 - 증가 기여도
            top5 = diff.increased_classes[:5]
            if top5:
                lines.append("### 객체 증가 기여도")
                lines.append("")
                lines.append("```mermaid")
                lines.append("pie title 인스턴스 증가 기여도")
                for name, bc, ac, _, _ in top5:
                    short_name = name.split(".")[-1] if "." in name else name
                    lines.append(f'    "{short_name}" : {ac - bc}')
                lines.append("```")
                lines.append("")

        # 새로 추가된 클래스
        if diff.new_classes:
            lines += [
                "### 새로 생성된 클래스 (before에 없었음)",
                "",
                "| 클래스 | 인스턴스 수 | 크기 (KB) |",
                "|--------|-----------|-----------|",
            ]
            for name, count, size in diff.new_classes[:10]:
                lines.append(f"| `{name}` | {count:,} | {size // 1024:,} |")
            lines.append("")

        return lines

    def _section_human_in_the_loop(self) -> list:
        return [
            "## 4. 분석자 기록 (Human-in-the-loop)",
            "",
            "> 아래 항목은 분석자가 직접 기록합니다.",
            "",
            "| 항목 | 내용 |",
            "|------|------|",
            "| **실제 원인** | |",
            "| **원인 코드 변경** | |",
            "| **해결 조치** | |",
            "| **추가 확인 데이터** | |",
            "| **카테고리** | |",
            "",
        ]
