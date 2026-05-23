"""
hprof_converter 단위 테스트.

실제 hprof-conv 바이너리가 필요한 테스트는 RUN_REAL_HPROF_CONV 환경변수로 분리.
기본 테스트 (magic byte 인식, 에러 경로) 는 외부 도구 없이 stdlib만으로 동작.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from systemui_hprof_analyzer.config import Config
from systemui_hprof_analyzer.config.loader import Paths
from systemui_hprof_analyzer.utils.hprof_converter import (
    ANDROID_HPROF_MAGIC,
    STANDARD_HPROF_MAGIC,
    HprofConverterError,
    _read_magic,
    convert,
)


def _make_fake_hprof(path: Path, magic: bytes, padding: int = 100) -> None:
    """주어진 magic + 패딩으로 가짜 hprof 파일 생성."""
    path.write_bytes(magic + b"\x00" + b"\x00" * padding)


class TestReadMagic:
    def test_android_hprof(self, tmp_path):
        p = tmp_path / "android.hprof"
        _make_fake_hprof(p, ANDROID_HPROF_MAGIC)
        assert _read_magic(p) == "1.0.3"

    def test_standard_hprof(self, tmp_path):
        p = tmp_path / "standard.hprof"
        _make_fake_hprof(p, STANDARD_HPROF_MAGIC)
        assert _read_magic(p) == "1.0.2"

    def test_unknown_magic(self, tmp_path):
        p = tmp_path / "garbage.hprof"
        p.write_bytes(b"NOT A HPROF FILE\x00\x00")
        assert _read_magic(p) == "unknown"


def _make_config(hprof_conv_path: str = "") -> Config:
    cfg = Config()
    cfg.paths = Paths(hprof_conv=hprof_conv_path)
    return cfg


class TestConvertErrors:
    """실제 hprof-conv 실행 전에 걸러지는 에러 케이스."""

    def test_missing_input(self, tmp_path):
        cfg = _make_config(hprof_conv_path="C:/nonexistent/hprof-conv.exe")
        with pytest.raises(HprofConverterError, match="입력 hprof 없음"):
            convert(
                input_hprof=tmp_path / "missing.hprof",
                output_hprof=tmp_path / "out.hprof",
                config=cfg,
            )

    def test_missing_hprof_conv_path_in_config(self, tmp_path):
        in_path = tmp_path / "in.hprof"
        _make_fake_hprof(in_path, ANDROID_HPROF_MAGIC)
        cfg = _make_config(hprof_conv_path="")
        with pytest.raises(HprofConverterError, match="paths.hprof_conv 가 설정되지"):
            convert(
                input_hprof=in_path,
                output_hprof=tmp_path / "out.hprof",
                config=cfg,
            )

    def test_missing_hprof_conv_binary(self, tmp_path):
        in_path = tmp_path / "in.hprof"
        _make_fake_hprof(in_path, ANDROID_HPROF_MAGIC)
        cfg = _make_config(hprof_conv_path=str(tmp_path / "no-such-binary.exe"))
        with pytest.raises(HprofConverterError, match="hprof-conv 실행 파일 없음"):
            convert(
                input_hprof=in_path,
                output_hprof=tmp_path / "out.hprof",
                config=cfg,
            )

    def test_input_already_standard(self, tmp_path):
        """이미 1.0.2 인 파일을 입력으로 주면 명확한 에러."""
        in_path = tmp_path / "already_standard.hprof"
        _make_fake_hprof(in_path, STANDARD_HPROF_MAGIC)
        # hprof-conv 경로는 통과시키기 위해 동일 파일로 fake
        cfg = _make_config(hprof_conv_path=str(in_path))
        with pytest.raises(HprofConverterError, match="이미 표준 hprof"):
            convert(
                input_hprof=in_path,
                output_hprof=tmp_path / "out.hprof",
                config=cfg,
            )

    def test_input_not_hprof_at_all(self, tmp_path):
        in_path = tmp_path / "garbage.bin"
        in_path.write_bytes(b"NOT A HPROF\x00" * 10)
        cfg = _make_config(hprof_conv_path=str(in_path))
        with pytest.raises(HprofConverterError, match="hprof 파일이 아닌 것 같습니다"):
            convert(
                input_hprof=in_path,
                output_hprof=tmp_path / "out.hprof",
                config=cfg,
            )

    def test_output_already_exists_without_overwrite(self, tmp_path):
        in_path = tmp_path / "in.hprof"
        out_path = tmp_path / "out.hprof"
        _make_fake_hprof(in_path, ANDROID_HPROF_MAGIC)
        out_path.write_bytes(b"existing")
        cfg = _make_config(hprof_conv_path=str(in_path))
        with pytest.raises(FileExistsError, match="이미 존재"):
            convert(
                input_hprof=in_path,
                output_hprof=out_path,
                config=cfg,
                overwrite=False,
            )
