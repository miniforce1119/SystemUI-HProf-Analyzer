"""
hprof-conv 자동 호출 래퍼.

Android hprof (`JAVA PROFILE 1.0.3`) → 표준 Java hprof (`JAVA PROFILE 1.0.2`).
MAT 가 표준 1.0.2 만 읽으므로 변환 필수.

손으로 검증된 동작 (2026-05-23):
- 입력: 49,804,854 bytes Android hprof
- 출력: 49,721,415 bytes 표준 hprof
- magic byte: `JAVA PROFILE 1.0.3` → `JAVA PROFILE 1.0.2`
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..config import Config


ANDROID_HPROF_MAGIC = b"JAVA PROFILE 1.0.3"
STANDARD_HPROF_MAGIC = b"JAVA PROFILE 1.0.2"


class HprofConverterError(RuntimeError):
    pass


@dataclass
class ConversionResult:
    input_path: Path
    output_path: Path
    input_size: int
    output_size: int
    input_magic: str   # "1.0.3" 또는 "1.0.2" 또는 "unknown"
    output_magic: str

    @property
    def size_delta(self) -> int:
        return self.output_size - self.input_size


def _read_magic(path: Path) -> str:
    """파일 첫 18바이트를 읽어 hprof 버전 식별."""
    with path.open("rb") as f:
        head = f.read(18)
    if head.startswith(ANDROID_HPROF_MAGIC):
        return "1.0.3"
    if head.startswith(STANDARD_HPROF_MAGIC):
        return "1.0.2"
    return "unknown"


def convert(
    input_hprof: str | Path,
    output_hprof: str | Path,
    config: Config,
    overwrite: bool = False,
) -> ConversionResult:
    """
    Android hprof 를 표준 Java hprof 로 변환.

    Args:
        input_hprof: Android hprof 파일 경로 (보통 `JAVA PROFILE 1.0.3`)
        output_hprof: 출력 표준 hprof 경로
        config: 로드된 config (paths.hprof_conv 사용)
        overwrite: True 면 출력 파일이 이미 있어도 덮어씀

    Returns:
        ConversionResult: 입출력 크기, magic byte 등 변환 결과

    Raises:
        HprofConverterError: 입력 파일 없음, hprof-conv 경로 잘못됨, 변환 실패 등
        FileExistsError: overwrite=False 이고 출력 파일이 이미 있을 때
    """
    in_path = Path(input_hprof).resolve()
    out_path = Path(output_hprof).resolve()

    if not in_path.exists():
        raise HprofConverterError(f"입력 hprof 없음: {in_path}")

    if not config.paths.hprof_conv:
        raise HprofConverterError(
            "config/local.yaml 의 paths.hprof_conv 가 설정되지 않았습니다."
        )

    conv_exe = Path(config.paths.hprof_conv)
    if not conv_exe.exists():
        raise HprofConverterError(f"hprof-conv 실행 파일 없음: {conv_exe}")

    if out_path.exists() and not overwrite:
        raise FileExistsError(
            f"출력 파일이 이미 존재합니다: {out_path}. overwrite=True 로 덮어쓰기."
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)

    input_magic = _read_magic(in_path)
    if input_magic == "1.0.2":
        # 이미 표준 포맷. 그대로 복사할 수도 있지만, 명시적으로 알려줌
        # (사용자가 잘못된 파일을 넘긴 것일 수 있음)
        raise HprofConverterError(
            f"입력이 이미 표준 hprof (1.0.2) 입니다: {in_path}\n"
            f"hprof-conv 변환이 필요하지 않습니다."
        )
    if input_magic == "unknown":
        raise HprofConverterError(
            f"입력이 hprof 파일이 아닌 것 같습니다 (magic 인식 실패): {in_path}"
        )

    # 실행: hprof-conv <input> <output>
    try:
        result = subprocess.run(
            [str(conv_exe), str(in_path), str(out_path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired as e:
        raise HprofConverterError(f"hprof-conv timeout (60s 초과): {e}") from e

    if result.returncode != 0:
        raise HprofConverterError(
            f"hprof-conv 실패 (exit {result.returncode})\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    if not out_path.exists():
        raise HprofConverterError(
            f"hprof-conv 가 0 으로 종료됐지만 출력 파일이 생성되지 않음: {out_path}"
        )

    output_magic = _read_magic(out_path)
    if output_magic != "1.0.2":
        raise HprofConverterError(
            f"변환은 됐지만 출력 magic 이 예상과 다름: {output_magic}\n"
            f"기대: 1.0.2, 실제: {output_magic}\n"
            f"파일: {out_path}"
        )

    return ConversionResult(
        input_path=in_path,
        output_path=out_path,
        input_size=in_path.stat().st_size,
        output_size=out_path.stat().st_size,
        input_magic=input_magic,
        output_magic=output_magic,
    )
