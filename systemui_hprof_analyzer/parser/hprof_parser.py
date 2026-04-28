"""
Android hprof (Heap Profile) 파서

AOSP 표준 hprof 바이너리 포맷을 파싱하여
클래스별 인스턴스 수와 메모리 점유를 추출합니다.

hprof 파일 포맷 (AOSP):
  - Header: "JAVA PROFILE 1.0.3\0" + identifier size + timestamp
  - Records: TAG(1byte) + TIME(4bytes) + LENGTH(4bytes) + BODY
  - 주요 TAG:
    - 0x01: STRING
    - 0x02: LOAD_CLASS
    - 0x1C: HEAP_DUMP_SEGMENT
    - 내부: 0x21 (CLASS_DUMP), 0x22 (INSTANCE_DUMP), 0x23 (OBJECT_ARRAY_DUMP), etc.

참고: 125MB hprof 파싱은 시간이 걸릴 수 있음 (10-30초 예상)
"""

import struct
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, BinaryIO
from collections import defaultdict


# hprof record tags
TAG_STRING = 0x01
TAG_LOAD_CLASS = 0x02
TAG_HEAP_DUMP = 0x0C
TAG_HEAP_DUMP_SEGMENT = 0x1C
TAG_HEAP_DUMP_END = 0x2C

# heap dump sub-tags
SUB_CLASS_DUMP = 0x20
SUB_INSTANCE_DUMP = 0x21
SUB_OBJECT_ARRAY_DUMP = 0x22
SUB_PRIMITIVE_ARRAY_DUMP = 0x23


# primitive type sizes (type_id → byte size)
_PRIM_SIZES = {
    4: 1,   # boolean
    5: 2,   # char
    6: 4,   # float
    7: 8,   # double
    8: 1,   # byte
    9: 2,   # short
    10: 4,  # int
    11: 8,  # long
}


@dataclass
class ClassStats:
    """클래스별 통계"""
    class_name: str
    instance_count: int = 0
    shallow_size: int = 0  # 인스턴스 자체 크기 합계

    @property
    def avg_size(self) -> int:
        if self.instance_count == 0:
            return 0
        return self.shallow_size // self.instance_count


@dataclass
class HprofSummary:
    """hprof 파싱 요약"""
    file_path: str = ""
    total_instances: int = 0
    total_shallow_size: int = 0
    class_stats: dict = field(default_factory=dict)  # {class_name: ClassStats}
    top_classes_by_count: list = field(default_factory=list)
    top_classes_by_size: list = field(default_factory=list)

    def to_dict(self, top_n: int = 20) -> dict:
        """LLM/보고서용 요약 딕셔너리"""
        return {
            "file": Path(self.file_path).name if self.file_path else "",
            "total_instances": self.total_instances,
            "total_shallow_size_kb": self.total_shallow_size // 1024,
            "top_by_count": [
                {
                    "class": cs.class_name,
                    "count": cs.instance_count,
                    "size_kb": cs.shallow_size // 1024,
                }
                for cs in self.top_classes_by_count[:top_n]
            ],
            "top_by_size": [
                {
                    "class": cs.class_name,
                    "count": cs.instance_count,
                    "size_kb": cs.shallow_size // 1024,
                }
                for cs in self.top_classes_by_size[:top_n]
            ],
        }


@dataclass
class HprofDiff:
    """before/after hprof 비교 결과"""
    before_summary: Optional[HprofSummary] = None
    after_summary: Optional[HprofSummary] = None
    new_classes: list = field(default_factory=list)       # after에만 있는 클래스
    removed_classes: list = field(default_factory=list)    # before에만 있는 클래스
    increased_classes: list = field(default_factory=list)  # 인스턴스 증가한 클래스
    decreased_classes: list = field(default_factory=list)  # 인스턴스 감소한 클래스
    total_instance_diff: int = 0
    total_size_diff: int = 0

    def to_dict(self, top_n: int = 20) -> dict:
        """LLM/보고서용 비교 딕셔너리"""
        return {
            "total_instance_diff": self.total_instance_diff,
            "total_size_diff_kb": self.total_size_diff // 1024,
            "increased_top": [
                {
                    "class": name,
                    "before_count": bc,
                    "after_count": ac,
                    "diff_count": ac - bc,
                    "size_diff_kb": (a_size - b_size) // 1024,
                }
                for name, bc, ac, b_size, a_size in self.increased_classes[:top_n]
            ],
            "decreased_top": [
                {
                    "class": name,
                    "before_count": bc,
                    "after_count": ac,
                    "diff_count": ac - bc,
                }
                for name, bc, ac, _, _ in self.decreased_classes[:top_n]
            ],
            "new_classes": [
                {"class": name, "count": count, "size_kb": size // 1024}
                for name, count, size in self.new_classes[:top_n]
            ],
        }


class HprofParser:
    """Android hprof 바이너리 파서"""

    def parse_file(self, filepath: str) -> HprofSummary:
        """hprof 파일을 파싱하여 클래스별 통계 반환"""
        path = Path(filepath)
        summary = HprofSummary(file_path=str(path))

        with open(path, "rb") as f:
            id_size = self._read_header(f)
            strings = {}      # string_id → string
            class_names = {}   # class_obj_id → string_id
            class_sizes = {}   # class_obj_id → instance_size

            # class_obj_id별 인스턴스 카운트/사이즈 집계
            instance_counts = defaultdict(int)
            instance_sizes = defaultdict(int)

            while True:
                record = self._read_record_header(f)
                if record is None:
                    break

                tag, _, length = record

                if tag == TAG_STRING:
                    str_id = self._read_id(f, id_size)
                    str_bytes = f.read(length - id_size)
                    strings[str_id] = str_bytes.decode("utf-8", errors="replace")

                elif tag == TAG_LOAD_CLASS:
                    _serial = struct.unpack(">I", f.read(4))[0]
                    class_obj_id = self._read_id(f, id_size)
                    _stack_serial = struct.unpack(">I", f.read(4))[0]
                    class_name_id = self._read_id(f, id_size)
                    class_names[class_obj_id] = class_name_id

                elif tag in (TAG_HEAP_DUMP, TAG_HEAP_DUMP_SEGMENT):
                    self._parse_heap_segment(
                        f, length, id_size,
                        class_sizes, instance_counts, instance_sizes,
                    )

                else:
                    f.read(length)

        # 집계 결과를 ClassStats로 변환
        for class_obj_id, count in instance_counts.items():
            name_str_id = class_names.get(class_obj_id)
            if name_str_id is not None:
                raw_name = strings.get(name_str_id, f"unknown_{class_obj_id}")
                class_name = raw_name.replace("/", ".")
            else:
                class_name = f"unknown_{class_obj_id}"

            cs = ClassStats(
                class_name=class_name,
                instance_count=count,
                shallow_size=instance_sizes.get(class_obj_id, 0),
            )
            summary.class_stats[class_name] = cs
            summary.total_instances += count
            summary.total_shallow_size += cs.shallow_size

        # Top 정렬
        all_stats = list(summary.class_stats.values())
        summary.top_classes_by_count = sorted(
            all_stats, key=lambda x: x.instance_count, reverse=True
        )
        summary.top_classes_by_size = sorted(
            all_stats, key=lambda x: x.shallow_size, reverse=True
        )

        return summary

    def diff(self, before_path: str, after_path: str) -> HprofDiff:
        """before/after hprof 비교"""
        before = self.parse_file(before_path)
        after = self.parse_file(after_path)

        result = HprofDiff(
            before_summary=before,
            after_summary=after,
        )

        before_classes = set(before.class_stats.keys())
        after_classes = set(after.class_stats.keys())

        # 새로 추가된 클래스
        for name in (after_classes - before_classes):
            cs = after.class_stats[name]
            result.new_classes.append((name, cs.instance_count, cs.shallow_size))
        result.new_classes.sort(key=lambda x: x[2], reverse=True)

        # 제거된 클래스
        for name in (before_classes - after_classes):
            cs = before.class_stats[name]
            result.removed_classes.append((name, cs.instance_count, cs.shallow_size))

        # 공통 클래스 비교
        for name in (before_classes & after_classes):
            bc = before.class_stats[name].instance_count
            ac = after.class_stats[name].instance_count
            bs = before.class_stats[name].shallow_size
            as_ = after.class_stats[name].shallow_size

            if ac > bc:
                result.increased_classes.append((name, bc, ac, bs, as_))
            elif ac < bc:
                result.decreased_classes.append((name, bc, ac, bs, as_))

        # 증가순 정렬 (인스턴스 증가량 기준)
        result.increased_classes.sort(key=lambda x: x[2] - x[1], reverse=True)
        result.decreased_classes.sort(key=lambda x: x[1] - x[2], reverse=True)

        result.total_instance_diff = after.total_instances - before.total_instances
        result.total_size_diff = after.total_shallow_size - before.total_shallow_size

        return result

    def _read_header(self, f: BinaryIO) -> int:
        """hprof 헤더를 읽고 identifier size 반환"""
        # null-terminated format string
        header = b""
        while True:
            b = f.read(1)
            if b == b"\x00" or not b:
                break
            header += b

        # identifier size (4 or 8 bytes)
        id_size = struct.unpack(">I", f.read(4))[0]

        # timestamp (high + low)
        f.read(8)

        return id_size

    def _read_record_header(self, f: BinaryIO):
        """레코드 헤더 읽기 → (tag, time, length) 또는 None"""
        tag_bytes = f.read(1)
        if not tag_bytes:
            return None
        tag = tag_bytes[0]
        time_bytes = f.read(4)
        length_bytes = f.read(4)
        if len(time_bytes) < 4 or len(length_bytes) < 4:
            return None
        time = struct.unpack(">I", time_bytes)[0]
        length = struct.unpack(">I", length_bytes)[0]
        return (tag, time, length)

    def _read_id(self, f: BinaryIO, id_size: int) -> int:
        """identifier 읽기"""
        data = f.read(id_size)
        if id_size == 4:
            return struct.unpack(">I", data)[0]
        else:
            return struct.unpack(">Q", data)[0]

    def _parse_heap_segment(
        self, f: BinaryIO, segment_length: int, id_size: int,
        class_sizes: dict, instance_counts: dict, instance_sizes: dict,
    ):
        """HEAP_DUMP / HEAP_DUMP_SEGMENT 내부 파싱"""
        end_pos = f.tell() + segment_length

        while f.tell() < end_pos:
            sub_tag_bytes = f.read(1)
            if not sub_tag_bytes:
                break
            sub_tag = sub_tag_bytes[0]

            if sub_tag == SUB_CLASS_DUMP:
                self._parse_class_dump(f, id_size, class_sizes)

            elif sub_tag == SUB_INSTANCE_DUMP:
                obj_id = self._read_id(f, id_size)
                stack_serial = struct.unpack(">I", f.read(4))[0]
                class_obj_id = self._read_id(f, id_size)
                num_bytes = struct.unpack(">I", f.read(4))[0]
                f.read(num_bytes)  # skip instance data

                instance_counts[class_obj_id] += 1
                instance_sizes[class_obj_id] += num_bytes + id_size + 8

            elif sub_tag == SUB_OBJECT_ARRAY_DUMP:
                obj_id = self._read_id(f, id_size)
                stack_serial = struct.unpack(">I", f.read(4))[0]
                num_elements = struct.unpack(">I", f.read(4))[0]
                array_class_id = self._read_id(f, id_size)
                f.read(num_elements * id_size)

                instance_counts[array_class_id] += 1
                instance_sizes[array_class_id] += num_elements * id_size + 16

            elif sub_tag == SUB_PRIMITIVE_ARRAY_DUMP:
                obj_id = self._read_id(f, id_size)
                stack_serial = struct.unpack(">I", f.read(4))[0]
                num_elements = struct.unpack(">I", f.read(4))[0]
                element_type = f.read(1)[0]
                elem_size = _PRIM_SIZES.get(element_type, 1)
                f.read(num_elements * elem_size)

                # primitive array는 별도 클래스로 카운트하지 않음 (옵션)

            elif sub_tag == 0xFF:
                # ROOT_UNKNOWN
                self._read_id(f, id_size)
            elif sub_tag == 0x01:
                # ROOT_JNI_GLOBAL
                self._read_id(f, id_size)
                self._read_id(f, id_size)
            elif sub_tag == 0x02:
                # ROOT_JNI_LOCAL
                self._read_id(f, id_size)
                f.read(8)
            elif sub_tag == 0x03:
                # ROOT_JAVA_FRAME
                self._read_id(f, id_size)
                f.read(8)
            elif sub_tag == 0x04:
                # ROOT_NATIVE_STACK
                self._read_id(f, id_size)
                f.read(4)
            elif sub_tag == 0x05:
                # ROOT_STICKY_CLASS
                self._read_id(f, id_size)
            elif sub_tag == 0x06:
                # ROOT_THREAD_BLOCK
                self._read_id(f, id_size)
                f.read(4)
            elif sub_tag == 0x07:
                # ROOT_MONITOR_USED
                self._read_id(f, id_size)
            elif sub_tag == 0x08:
                # ROOT_THREAD_OBJECT
                self._read_id(f, id_size)
                f.read(8)
            elif sub_tag == 0x89:
                # ROOT_INTERNED_STRING (Android)
                self._read_id(f, id_size)
            elif sub_tag == 0x8A:
                # ROOT_FINALIZING (Android)
                self._read_id(f, id_size)
            elif sub_tag == 0x8B:
                # ROOT_DEBUGGER (Android)
                self._read_id(f, id_size)
            elif sub_tag == 0x8D:
                # ROOT_VM_INTERNAL (Android)
                self._read_id(f, id_size)
            elif sub_tag == 0x8E:
                # ROOT_JNI_MONITOR (Android)
                self._read_id(f, id_size)
                f.read(8)
            elif sub_tag == 0xFE:
                # HEAP_DUMP_INFO (Android)
                f.read(4)
                self._read_id(f, id_size)
            elif sub_tag == 0xC3:
                # ROOT_UNREACHABLE (Android)
                self._read_id(f, id_size)
            else:
                # 알 수 없는 sub-tag → 남은 segment 건너뜀
                remaining = end_pos - f.tell()
                if remaining > 0:
                    f.read(remaining)
                break

    def _parse_class_dump(self, f: BinaryIO, id_size: int, class_sizes: dict):
        """CLASS_DUMP 레코드 파싱"""
        class_obj_id = self._read_id(f, id_size)
        f.read(4)  # stack_serial
        super_class_id = self._read_id(f, id_size)
        class_loader_id = self._read_id(f, id_size)
        signers_id = self._read_id(f, id_size)
        protection_domain_id = self._read_id(f, id_size)
        reserved1 = self._read_id(f, id_size)
        reserved2 = self._read_id(f, id_size)
        instance_size = struct.unpack(">I", f.read(4))[0]

        class_sizes[class_obj_id] = instance_size

        # constant pool
        cp_count = struct.unpack(">H", f.read(2))[0]
        for _ in range(cp_count):
            f.read(2)  # cp_index
            type_id = f.read(1)[0]
            self._skip_value(f, type_id, id_size)

        # static fields
        sf_count = struct.unpack(">H", f.read(2))[0]
        for _ in range(sf_count):
            self._read_id(f, id_size)  # name_id
            type_id = f.read(1)[0]
            self._skip_value(f, type_id, id_size)

        # instance fields
        if_count = struct.unpack(">H", f.read(2))[0]
        for _ in range(if_count):
            self._read_id(f, id_size)  # name_id
            f.read(1)  # type_id

    def _skip_value(self, f: BinaryIO, type_id: int, id_size: int):
        """타입에 따라 값 건너뛰기"""
        if type_id == 2:  # object
            f.read(id_size)
        else:
            size = _PRIM_SIZES.get(type_id, 1)
            f.read(size)
