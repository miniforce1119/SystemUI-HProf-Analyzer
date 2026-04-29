# SystemUI HProf Analyzer 사용 가이드

> 이 문서는 분석자와 Cline이 참고하는 실제 사용 흐름 가이드입니다.

---

## 전체 분석 흐름

```
[사람] regression 시스템에서 두 버전 선택 → 비교 화면 진입
   ↓
[사람] 각 버전 Download → zip 2개 다운로드
   ↓
[사람] zip을 폴더에 해제
   ↓
[도구] 1단계: compare — 시나리오별 meminfo 비교 → regression 감지
   ↓
   ├── 정상 → 끝 (보고서에 "이상 없음" 기록)
   │
   └── regression 감지 → 2단계 자동 진입
         ├── Target 내부 hprof before vs after → leak 객체 특정
         └── Baseline vs Target hprof 비교 → 새로 추가된 객체 특정
   ↓
[산출물] Markdown 보고서 (Mermaid 시각화 포함)
```

---

## 사용 시나리오

### 시나리오 1: 두 버전 비교 (가장 일반적)

**상황:** 새 버전이 나왔고, 기존 버전 대비 메모리가 증가했는지 확인

```bash
# 1. regression 시스템에서 다운로드
#    - 기준 버전 (예: AZDD) → versionA.zip
#    - 비교 버전 (예: AZDE) → versionB.zip

# 2. 각각 해제
#    C:\분석\versionA\  ← AZDD zip 해제
#    C:\분석\versionB\  ← AZDE zip 해제

# 3. 비교 분석 실행
python -m systemui_hprof_analyzer compare C:\분석\versionA C:\분석\versionB -o report.md
```

**도구가 하는 일:**

```
1단계: 시나리오별 meminfo 20회 평균 비교
┌──────────────────────────────────────────────────────────────┐
│ 시나리오              Baseline    Target     변화      판정   │
│ idle                 458,000    475,000   +17,000   ⚠️ 주의  │
│ quickpanelopenclose  462,000    463,000     +1,000   ✅ 정상  │
│ screenonoff          455,000    456,000     +1,000   ✅ 정상  │
└──────────────────────────────────────────────────────────────┘
        ↓ idle에서 regression 감지!

2단계: idle 심층 분석 (자동)
  ├── Target(AZDE)의 idle hprof before vs after 비교
  │     → "QSTileView 64→128개 (+64), 미해제"
  │
  └── Baseline(AZDD) after vs Target(AZDE) after 비교
        → "Target에 SemQSCustomTile 32개 새로 존재"
```

**산출물:** `report.md`에 위 내용이 모두 포함 (테이블 + Mermaid 차트)

---

### 시나리오 2: 한 버전 내부 분석

**상황:** 특정 버전에서 메모리 누수가 의심되어 상세 분석

```bash
# 해당 버전 폴더에서 특정 시나리오 분석
python -m systemui_hprof_analyzer analyze C:\분석\versionB --scenario idle -o report_idle.md

# 전체 시나리오 한 번에 분석
python -m systemui_hprof_analyzer analyze C:\분석\versionB --all
```

**도구가 하는 일:**

```
idle 시나리오:
  1. meminfo 20회 파싱 → 평균 PSS: 475,000 KB
  2. PSS 추이: 458,711 → 475,500 KB (+3.7%) → ⚠️ 반복 시 증가
  3. hprof before vs after 비교:
     - QSTileView: 64 → 128개 (+64)
     - TextView: 420 → 614개 (+194)
     - Bitmap: 340 → 412개 (+72)
     → "QSTileView 1세트(64개)가 해제되지 않음"
```

---

### 시나리오 3: 빠른 meminfo 비교만 (hprof 분석 건너뛰기)

**상황:** hprof 파싱이 오래 걸려서 meminfo 비교만 먼저 확인

```bash
python -m systemui_hprof_analyzer compare C:\분석\versionA C:\분석\versionB --no-deep
```

hprof 분석 없이 **시나리오별 meminfo 평균 비교표만** 빠르게 출력됩니다.
regression이 감지된 시나리오가 있으면 이후에 `analyze`로 심층 분석하면 됩니다.

---

### 시나리오 4: hprof 단독 비교

**상황:** 두 hprof 파일을 직접 비교하고 싶을 때

```bash
# 같은 버전의 before vs after
python -m systemui_hprof_analyzer hprof-diff \
  C:\분석\versionB\java_heap_dump_idle_before_*.hprof \
  C:\분석\versionB\java_heap_dump_idle_after_*.hprof

# 다른 버전의 after끼리 비교
python -m systemui_hprof_analyzer hprof-diff \
  C:\분석\versionA\java_heap_dump_idle_after_*.hprof \
  C:\분석\versionB\java_heap_dump_idle_after_*.hprof
```

---

## 폴더 구조 기대값

```
C:\분석\
├── versionA\              ← 기준 버전 zip 해제
│   ├── java_heap_dump_idle_before_*.hprof
│   ├── meminfo_idle_0_* ~ meminfo_idle_19_*
│   ├── gfxinfo_idle_0_* ~ gfxinfo_idle_19_*
│   ├── ...
│   ├── java_heap_dump_idle_after_*.hprof
│   ├── bugreport_idle_after_*
│   ├── (quickpanelopenclose 동일 구조)
│   └── (screenonoff 동일 구조)
│
└── versionB\              ← 비교 대상 버전 zip 해제
    └── (동일 구조)
```

---

## 산출물 보고서 구성

### compare 명령 (두 버전 비교)

```
1단계: 시나리오별 비교 요약
  ├── 시나리오별 평균 PSS 비교 테이블
  └── Mermaid 막대 차트 (Baseline vs Target)

2단계: regression 시나리오 심층 분석 (자동)
  ├── Target 내부 hprof diff
  │   ├── 인스턴스 증가 TOP 15 테이블
  │   └── 객체 증가 기여도 파이 차트
  ├── 버전 간 hprof diff
  │   ├── 인스턴스 증가 TOP 10
  │   └── Target에만 존재하는 새 클래스
  └── Target PSS 추이 (20회 라인 차트)

분석자 기록 (Human-in-the-loop)
```

### analyze 명령 (한 버전 내부 분석)

```
메모리 요약 (20회 평균)
PSS 추이 (20회 라인 차트 + 증가 판정)
hprof before vs after
  ├── 인스턴스 증가 TOP 15
  └── 객체 증가 기여도 파이 차트
분석자 기록 (Human-in-the-loop)
```

---

## 임계값 기준

| 조건 | 판정 |
|------|------|
| PSS 증가 ≥ 30MB 또는 ≥ 10% | 🔴 Critical → 즉시 심층 분석 |
| PSS 증가 ≥ 10MB 또는 ≥ 3% | ⚠️ Warning → 심층 분석 권장 |
| 그 외 | ✅ Normal |

임계값은 `analyzer/version_comparator.py`의 `THRESHOLDS`에서 조정 가능합니다.

---

## MAT CLI 연동 (참조 체인 분석)

### 사내 환경
```
hprof-conv: C:/tools/platform-tools-latest-windows/platform-tools/hprof-conv.exe
MAT: 사내 PC에 설치됨 (ParseHeapDump CLI)
Java: OpenJDK Temurin 설치됨
```

### hprof 변환이 필요한 이유
Android에서 뜬 hprof는 Android 전용 포맷이므로 MAT가 직접 읽지 못합니다.
`hprof-conv`로 표준 Java hprof로 변환해야 합니다.

### 전체 파이프라인 (MAT 포함)

```
zip 해제
  ↓
[1] meminfo 20회 추이 → 누수 감지 (이상치 제거, trimmed 평균)
  ↓ 누수 있으면
[2] hprof-conv 실행 → Android hprof를 표준 Java hprof로 변환
  ↓
[3] Python hprof 파서 → before vs after diff → 인스턴스 증가 TOP 15
  ↓
[4] MAT CLI → TOP 15 각각에 대해 참조 체인(Path to GC Roots) 추적
  ↓
[5] 보고서 생성

최종 보고서:
  ├── 인스턴스 증가 TOP 15 테이블
  └── 각 객체의 참조 체인
       → 개발자가 어떤 코드를 수정해야 하는지 바로 보임
```

### 보고서 예시 (MAT 참조 체인 포함)

```markdown
## 인스턴스 증가 TOP 15

| # | 클래스 | Before | After | 증가량 |
|---|--------|--------|-------|--------|
| 1 | TextView | 420 | 614 | +194 |
| 2 | ImageView | 280 | 396 | +116 |
| 3 | Bitmap | 340 | 412 | +72 |
| 4 | QSTileView | 64 | 128 | +64 |

## 참조 체인 분석

### #1. TextView (+194)
GC Root → QSPanel → mTileLayout → QSTileView → mLabel → TextView
→ QSTileView 내부 라벨이 해제되지 않음

### #2. ImageView (+116)
GC Root → QSPanel → mTileLayout → QSTileView → mIconView → ImageView
→ QSTileView 내부 아이콘이 해제되지 않음

### #3. Bitmap (+72)
GC Root → QSPanel → mTileLayout → QSTileView → mIconView → mDrawable → Bitmap
→ 타일 아이콘 Bitmap이 GC되지 않음

### #4. QSTileView (+64)
GC Root → QSPanel → mTileLayout → mTiles (ArrayList) → QSTileView
→ QSPanel.mTileLayout.mTiles에서 이전 타일 미제거가 root cause
```

### 중요: framework 클래스도 필터링하지 말 것
Bitmap, TextView, ImageView 등 framework 클래스도 참조 체인을 추적하면
결국 SystemUI 코드(QSPanel, QSTileView 등)로 연결됩니다.
필터링하면 실제 메모리를 많이 차지하는 객체를 놓칠 수 있습니다.
