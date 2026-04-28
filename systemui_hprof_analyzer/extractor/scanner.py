"""
2번 테스트 시스템 데이터 스캐너

큰 zip 1개를 해제하면 3개 시나리오 × 20회 반복 데이터가 나옴.
시나리오별로 hprof(before/after), meminfo, gfxinfo 등을 분류.

시나리오: idle, quickpanelopenclose, screenonoff
파일명 패턴:
  java_heap_dump_{scenario}_before_{date}_{time}.hprof
  java_heap_dump_{scenario}_after_{date}_{time}.hprof
  meminfo_{scenario}_{round}_{date}_{time}
  gfxinfo_{scenario}_{round}_{date}_{time}
  showmap_{scenario}_{round}_{date}_{time}
  maps_{scenario}_{round}_{date}_{time}
  smaps_{scenario}_{round}_{date}_{time}
  bugreport_{scenario}_after_{date}_{time}
"""

import re
import zipfile
import tempfile
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


# 알려진 시나리오 목록
KNOWN_SCENARIOS = ["idle", "quickpanelopenclose", "screenonoff"]

# 파일명 패턴들
_HPROF_PATTERN = re.compile(
    r"java_heap_dump_(.+?)_(before|after)_(\d{8})_(\d{6})\.hprof$"
)

_ROUND_FILE_PATTERN = re.compile(
    r"(meminfo|gfxinfo|showmap|maps|smaps)_(.+?)_(\d+)_(\d{8})_(\d{6})$"
)

_BUGREPORT_PATTERN = re.compile(
    r"bugreport_(.+?)_after_(\d{8})_(\d{6})"
)


@dataclass
class RoundData:
    """1회차 측정 데이터"""
    round_num: int
    meminfo_path: Optional[Path] = None
    gfxinfo_path: Optional[Path] = None
    showmap_path: Optional[Path] = None
    maps_path: Optional[Path] = None
    smaps_path: Optional[Path] = None


@dataclass
class ScenarioData:
    """1개 시나리오의 전체 데이터"""
    name: str
    hprof_before: Optional[Path] = None
    hprof_after: Optional[Path] = None
    bugreport_path: Optional[Path] = None
    rounds: dict = field(default_factory=dict)  # {회차번호: RoundData}

    @property
    def round_count(self) -> int:
        return len(self.rounds)

    @property
    def has_hprof(self) -> bool:
        return self.hprof_before is not None and self.hprof_after is not None


@dataclass
class TestArchive:
    """테스트 아카이브 전체"""
    source_path: str
    extract_dir: str
    scenarios: dict = field(default_factory=dict)  # {시나리오명: ScenarioData}

    @property
    def scenario_names(self) -> list:
        return list(self.scenarios.keys())


def scan_test_archive(
    archive_path: str,
    extract_dir: Optional[str] = None,
) -> TestArchive:
    """테스트 아카이브(zip)를 해제하고 시나리오별로 파일 분류

    Args:
        archive_path: 큰 zip 파일 경로
        extract_dir: 해제할 디렉토리 (없으면 임시 디렉토리)

    Returns:
        TestArchive 객체
    """
    archive = Path(archive_path)

    # zip이면 해제, 아니면 폴더로 간주
    if archive.is_file() and archive.suffix == ".zip":
        if extract_dir is None:
            extract_dir = str(archive.parent / archive.stem)
        extract_path = Path(extract_dir)
        extract_path.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(archive, "r") as zf:
            zf.extractall(extract_path)

        scan_dir = extract_path
    else:
        scan_dir = archive
        extract_dir = str(archive)

    result = TestArchive(
        source_path=str(archive),
        extract_dir=extract_dir,
    )

    # 모든 파일 스캔 (하위 폴더 포함)
    all_files = list(scan_dir.rglob("*"))

    for f in all_files:
        if not f.is_file():
            continue

        name = f.name

        # hprof 파일 매칭
        m = _HPROF_PATTERN.search(name)
        if m:
            scenario = m.group(1)
            timing = m.group(2)  # before or after
            _ensure_scenario(result, scenario)
            if timing == "before":
                result.scenarios[scenario].hprof_before = f
            else:
                result.scenarios[scenario].hprof_after = f
            continue

        # 회차별 파일 매칭 (meminfo, gfxinfo, showmap, maps, smaps)
        m = _ROUND_FILE_PATTERN.search(name)
        if m:
            file_type = m.group(1)
            scenario = m.group(2)
            round_num = int(m.group(3))
            _ensure_scenario(result, scenario)
            _ensure_round(result.scenarios[scenario], round_num)
            rd = result.scenarios[scenario].rounds[round_num]
            setattr(rd, f"{file_type}_path", f)
            continue

        # bugreport 매칭
        m = _BUGREPORT_PATTERN.search(name)
        if m:
            scenario = m.group(1)
            _ensure_scenario(result, scenario)
            result.scenarios[scenario].bugreport_path = f
            continue

    # 회차 정렬
    for sd in result.scenarios.values():
        sd.rounds = dict(sorted(sd.rounds.items()))

    return result


def scan_extracted_folder(folder_path: str) -> TestArchive:
    """이미 해제된 폴더를 스캔 (zip 없이)

    Args:
        folder_path: 해제된 폴더 경로

    Returns:
        TestArchive 객체
    """
    return scan_test_archive(folder_path)


def _ensure_scenario(archive: TestArchive, scenario: str):
    if scenario not in archive.scenarios:
        archive.scenarios[scenario] = ScenarioData(name=scenario)


def _ensure_round(scenario: ScenarioData, round_num: int):
    if round_num not in scenario.rounds:
        scenario.rounds[round_num] = RoundData(round_num=round_num)
