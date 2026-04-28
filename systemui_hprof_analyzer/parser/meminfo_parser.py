"""
dumpsys meminfo systemui 출력을 파싱하는 모듈

Android dumpsys meminfo 출력 포맷을 구조화된 딕셔너리로 변환합니다.
AOSP 표준 포맷 + 삼성 추가 필드를 모두 지원합니다.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class MemorySection:
    """개별 메모리 영역 데이터"""
    name: str
    pss_total: int = 0
    private_dirty: int = 0
    private_clean: int = 0
    swap_pss_dirty: int = 0
    rss_total: int = 0
    heap_size: int = 0
    heap_alloc: int = 0
    heap_free: int = 0


@dataclass
class AppSummary:
    """App Summary 섹션 데이터"""
    java_heap_pss: int = 0
    java_heap_rss: int = 0
    native_heap_pss: int = 0
    native_heap_rss: int = 0
    code_pss: int = 0
    code_rss: int = 0
    stack_pss: int = 0
    stack_rss: int = 0
    graphics_pss: int = 0
    graphics_rss: int = 0
    private_other_pss: int = 0
    system_pss: int = 0
    total_pss: int = 0
    total_rss: int = 0


@dataclass
class ObjectsInfo:
    """Objects 섹션 데이터"""
    views: int = 0
    view_root_impl: int = 0
    app_contexts: int = 0
    activities: int = 0
    assets: int = 0
    asset_managers: int = 0
    local_binders: int = 0
    proxy_binders: int = 0
    parcel_memory: int = 0
    parcel_count: int = 0
    death_recipients: int = 0
    openssl_sockets: int = 0
    webviews: int = 0


@dataclass
class DatabaseInfo:
    """개별 데이터베이스 정보"""
    page_size: int = 0
    db_size: int = 0
    lookaside: int = 0
    cache: str = ""
    db_name: str = ""


@dataclass
class MeminfoResult:
    """dumpsys meminfo 전체 파싱 결과"""
    pid: int = 0
    process_name: str = ""
    uptime: int = 0
    realtime: int = 0
    sections: list = field(default_factory=list)
    total: Optional[MemorySection] = None
    app_summary: Optional[AppSummary] = None
    objects: Optional[ObjectsInfo] = None
    total_swap_pss: int = 0
    sql_memory_used: int = 0
    sql_pagecache_overflow: int = 0
    sql_malloc_size: int = 0
    databases: list = field(default_factory=list)
    # Native Allocations (2번 시스템)
    native_alloc_malloc: int = 0
    native_alloc_other: int = 0
    native_alloc_bitmap: int = 0
    # Mapped Bitmap
    mapped_bitmap_count: int = 0
    mapped_bitmap_size: int = 0
    # 삼성 추가 필드가 있으면 여기에 저장
    extra_sections: dict = field(default_factory=dict)

    @property
    def total_pss_kb(self) -> int:
        if self.total:
            return self.total.pss_total
        if self.app_summary:
            return self.app_summary.total_pss
        return 0

    @property
    def total_rss_kb(self) -> int:
        if self.total:
            return self.total.rss_total
        if self.app_summary:
            return self.app_summary.total_rss
        return 0

    def to_dict(self) -> dict:
        """LLM 입력용 요약 딕셔너리 생성"""
        result = {
            "pid": self.pid,
            "process": self.process_name,
            "total_pss_kb": self.total_pss_kb,
            "total_rss_kb": self.total_rss_kb,
        }

        if self.app_summary:
            result["app_summary"] = {
                "java_heap_pss": self.app_summary.java_heap_pss,
                "native_heap_pss": self.app_summary.native_heap_pss,
                "code_pss": self.app_summary.code_pss,
                "stack_pss": self.app_summary.stack_pss,
                "graphics_pss": self.app_summary.graphics_pss,
                "private_other_pss": self.app_summary.private_other_pss,
                "system_pss": self.app_summary.system_pss,
            }

        if self.objects:
            result["objects"] = {
                "views": self.objects.views,
                "view_root_impl": self.objects.view_root_impl,
                "app_contexts": self.objects.app_contexts,
                "activities": self.objects.activities,
                "local_binders": self.objects.local_binders,
                "proxy_binders": self.objects.proxy_binders,
            }

        # 주요 메모리 섹션
        sections_dict = {}
        for sec in self.sections:
            sections_dict[sec.name] = {
                "pss_total": sec.pss_total,
                "private_dirty": sec.private_dirty,
                "rss_total": sec.rss_total,
            }
            if sec.heap_size > 0:
                sections_dict[sec.name]["heap_size"] = sec.heap_size
                sections_dict[sec.name]["heap_alloc"] = sec.heap_alloc
                sections_dict[sec.name]["heap_free"] = sec.heap_free
        result["sections"] = sections_dict

        result["databases"] = [
            {"name": db.db_name, "size": db.db_size} for db in self.databases
        ]

        if self.extra_sections:
            result["extra_sections"] = self.extra_sections

        return result


class MeminfoParser:
    """dumpsys meminfo systemui 출력 파서"""

    # 메모리 섹션 행 패턴 (8컬럼: Pss Private Private SwapPss Rss Heap Heap Heap)
    _SECTION_PATTERN = re.compile(
        r"^\s*(.+?)\s{2,}"        # 섹션 이름
        r"(\d+)\s+"               # Pss Total
        r"(\d+)\s+"               # Private Dirty
        r"(\d+)\s+"               # Private Clean
        r"(\d+)\s+"               # SwapPss Dirty
        r"(\d+)"                  # Rss Total
        r"(?:\s+(\d+)\s+(\d+)\s+(\d+))?"  # Heap Size/Alloc/Free (optional)
    )

    # TOTAL 행 패턴
    _TOTAL_PATTERN = re.compile(
        r"^\s*TOTAL\s+"
        r"(\d+)\s+"               # Pss Total
        r"(\d+)\s+"               # Private Dirty
        r"(\d+)\s+"               # Private Clean
        r"(\d+)\s+"               # SwapPss Dirty
        r"(\d+)"                  # Rss Total
        r"(?:\s+(\d+)\s+(\d+)\s+(\d+))?"  # Heap Size/Alloc/Free (optional)
    )

    # PID/프로세스명 패턴
    _PID_PATTERN = re.compile(
        r"\*\* MEMINFO in pid (\d+) \[(.+?)\] \*\*"
    )

    # Uptime 패턴
    _UPTIME_PATTERN = re.compile(
        r"Uptime:\s*(\d+)\s+Realtime:\s*(\d+)"
    )

    # App Summary 패턴들
    _SUMMARY_PATTERNS = {
        "java_heap": re.compile(r"Java Heap:\s*(\d+)\s+(\d+)"),
        "native_heap": re.compile(r"Native Heap:\s*(\d+)\s+(\d+)"),
        "code": re.compile(r"Code:\s*(\d+)\s+(\d+)"),
        "stack": re.compile(r"Stack:\s*(\d+)\s+(\d+)"),
        "graphics": re.compile(r"Graphics:\s*(\d+)\s+(\d+)"),
        "private_other": re.compile(r"Private Other:\s*(\d+)"),
        "system": re.compile(r"System:\s*(\d+)"),
        "total_pss": re.compile(r"TOTAL PSS:\s*(\d+)"),
        "total_rss": re.compile(r"TOTAL RSS:\s*(\d+)"),
    }

    # Objects 패턴들
    _OBJECT_PATTERNS = {
        "views": re.compile(r"(?<!Web)Views:\s*(\d+)"),
        "view_root_impl": re.compile(r"ViewRootImpl:\s*(\d+)"),
        "app_contexts": re.compile(r"AppContexts:\s*(\d+)"),
        "activities": re.compile(r"Activities:\s*(\d+)"),
        "assets": re.compile(r"Assets:\s*(\d+)"),
        "asset_managers": re.compile(r"AssetManagers:\s*(\d+)"),
        "local_binders": re.compile(r"Local Binders:\s*(\d+)"),
        "proxy_binders": re.compile(r"Proxy Binders:\s*(\d+)"),
        "parcel_memory": re.compile(r"Parcel memory:\s*(\d+)"),
        "parcel_count": re.compile(r"Parcel count:\s*(\d+)"),
        "death_recipients": re.compile(r"Death Recipients:\s*(\d+)"),
        "openssl_sockets": re.compile(r"OpenSSL Sockets:\s*(\d+)"),
        "webviews": re.compile(r"WebViews:\s*(\d+)"),
    }

    # Database 행 패턴
    _DB_PATTERN = re.compile(
        r"^\s*(\d+)\s+(\d+)\s+(\d+)\s+([\d/]+)\s+(.+)$"
    )

    # SQL 패턴
    _SQL_PATTERNS = {
        "memory_used": re.compile(r"MEMORY_USED:\s*(\d+)"),
        "pagecache_overflow": re.compile(r"PAGECACHE_OVERFLOW:\s*(\d+)"),
        "malloc_size": re.compile(r"MALLOC_SIZE:\s*(\d+)"),
    }

    def parse_file(self, filepath: str) -> MeminfoResult:
        """파일에서 meminfo를 파싱"""
        path = Path(filepath)
        content = path.read_text(encoding="utf-8")
        return self.parse(content)

    def parse(self, content: str) -> MeminfoResult:
        """meminfo 텍스트를 파싱하여 MeminfoResult 반환"""
        result = MeminfoResult()
        lines = content.splitlines()

        current_section = None  # 현재 파싱 중인 섹션

        for line in lines:
            # Uptime/Realtime
            m = self._UPTIME_PATTERN.search(line)
            if m:
                result.uptime = int(m.group(1))
                result.realtime = int(m.group(2))
                continue

            # PID & 프로세스명
            m = self._PID_PATTERN.search(line)
            if m:
                result.pid = int(m.group(1))
                result.process_name = m.group(2)
                current_section = "memory_table"
                continue

            # TOTAL SWAP PSS 파싱
            swap_m = re.search(r"TOTAL SWAP PSS:\s*(\d+)", line)
            if swap_m:
                result.total_swap_pss = int(swap_m.group(1))
                continue

            # 섹션 전환 감지
            if "App Summary" in line:
                current_section = "app_summary"
                result.app_summary = AppSummary()
                continue
            elif "Native Allocations" in line:
                current_section = "native_alloc"
                continue
            elif "Objects" in line and "-----" not in line and "Native" not in line:
                current_section = "objects"
                result.objects = ObjectsInfo()
                continue
            elif line.strip() == "SQL":
                current_section = "sql"
                continue
            elif "DATABASES" in line:
                current_section = "databases"
                continue

            # 메모리 테이블 파싱
            if current_section == "memory_table":
                # TOTAL 행
                m = self._TOTAL_PATTERN.match(line)
                if m:
                    result.total = MemorySection(
                        name="TOTAL",
                        pss_total=int(m.group(1)),
                        private_dirty=int(m.group(2)),
                        private_clean=int(m.group(3)),
                        swap_pss_dirty=int(m.group(4)),
                        rss_total=int(m.group(5)),
                        heap_size=int(m.group(6)) if m.group(6) else 0,
                        heap_alloc=int(m.group(7)) if m.group(7) else 0,
                        heap_free=int(m.group(8)) if m.group(8) else 0,
                    )
                    continue

                # 일반 메모리 섹션 행
                m = self._SECTION_PATTERN.match(line)
                if m:
                    section = MemorySection(
                        name=m.group(1).strip(),
                        pss_total=int(m.group(2)),
                        private_dirty=int(m.group(3)),
                        private_clean=int(m.group(4)),
                        swap_pss_dirty=int(m.group(5)),
                        rss_total=int(m.group(6)),
                        heap_size=int(m.group(7)) if m.group(7) else 0,
                        heap_alloc=int(m.group(8)) if m.group(8) else 0,
                        heap_free=int(m.group(9)) if m.group(9) else 0,
                    )
                    result.sections.append(section)
                    continue

            # App Summary 파싱
            if current_section == "app_summary" and result.app_summary:
                for key, pattern in self._SUMMARY_PATTERNS.items():
                    m = pattern.search(line)
                    if m:
                        if key == "java_heap":
                            result.app_summary.java_heap_pss = int(m.group(1))
                            result.app_summary.java_heap_rss = int(m.group(2))
                        elif key == "native_heap":
                            result.app_summary.native_heap_pss = int(m.group(1))
                            result.app_summary.native_heap_rss = int(m.group(2))
                        elif key == "code":
                            result.app_summary.code_pss = int(m.group(1))
                            result.app_summary.code_rss = int(m.group(2))
                        elif key == "stack":
                            result.app_summary.stack_pss = int(m.group(1))
                            result.app_summary.stack_rss = int(m.group(2))
                        elif key == "graphics":
                            result.app_summary.graphics_pss = int(m.group(1))
                            result.app_summary.graphics_rss = int(m.group(2))
                        elif key == "private_other":
                            result.app_summary.private_other_pss = int(m.group(1))
                        elif key == "system":
                            result.app_summary.system_pss = int(m.group(1))
                        elif key == "total_pss":
                            result.app_summary.total_pss = int(m.group(1))
                        elif key == "total_rss":
                            result.app_summary.total_rss = int(m.group(1))
                        break

            # Native Allocations 파싱
            if current_section == "native_alloc":
                malloc_m = re.search(r"malloc[()ed]*:\s*(\d+)", line, re.IGNORECASE)
                if malloc_m:
                    result.native_alloc_malloc = int(malloc_m.group(1))
                other_m = re.search(r"other:\s*(\d+)", line, re.IGNORECASE)
                if other_m:
                    result.native_alloc_other = int(other_m.group(1))
                bitmap_m = re.search(r"bitmap:\s*(\d+)", line, re.IGNORECASE)
                if bitmap_m:
                    result.native_alloc_bitmap = int(bitmap_m.group(1))

            # Mapped Bitmap 파싱
            mapped_m = re.search(r"Mapped Bitmap.*?(\d+)\s+(\d+)", line)
            if mapped_m:
                result.mapped_bitmap_count = int(mapped_m.group(1))
                result.mapped_bitmap_size = int(mapped_m.group(2))

            # Objects 파싱
            if current_section == "objects" and result.objects:
                for key, pattern in self._OBJECT_PATTERNS.items():
                    m = pattern.search(line)
                    if m:
                        setattr(result.objects, key, int(m.group(1)))

            # SQL 파싱
            if current_section == "sql":
                for key, pattern in self._SQL_PATTERNS.items():
                    m = pattern.search(line)
                    if m:
                        if key == "memory_used":
                            result.sql_memory_used = int(m.group(1))
                        elif key == "pagecache_overflow":
                            result.sql_pagecache_overflow = int(m.group(1))
                        elif key == "malloc_size":
                            result.sql_malloc_size = int(m.group(1))

            # Databases 파싱
            if current_section == "databases":
                m = self._DB_PATTERN.match(line)
                if m:
                    db = DatabaseInfo(
                        page_size=int(m.group(1)),
                        db_size=int(m.group(2)),
                        lookaside=int(m.group(3)),
                        cache=m.group(4),
                        db_name=m.group(5).strip(),
                    )
                    result.databases.append(db)

        return result
