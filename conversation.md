# SystemUI HProf Analyzer 프로젝트 대화 로그

> AI(Claude)와의 대화를 통해 프로젝트를 설계하고 구현한 과정을 기록합니다.

---

## 1. 2번 테스트 시스템 발견

> 날짜: 2026-04-28

**사용자:**
회사에 regression 테스트가 두 군데 있었음. 1번 시스템(기존 systemui-analyzer)은 meminfo만 있는데, 2번 시스템은 hprof까지 수집하고 있었음.

**AI:**
hprof가 있으면 LLM 추측이 아닌 팩트 기반 분석 가능. 2번 시스템 기준으로 별도 프로젝트를 만들자고 제안.

---

## 2. 2번 시스템 데이터 구조 파악

> 날짜: 2026-04-28

**사용자:**
사진 캡쳐를 통해 파일 구조 공유:
- 큰 zip 1개를 다운로드
- 시나리오 3개: idle, quickpanelopenclose, screenonoff
- 각 시나리오 20회 반복
- hprof는 시나리오 시작 전(before) 1장 + 완료 후(after) 1장
- 그 사이에 20회 반복 당 meminfo, gfxinfo, showmap, maps, smaps 파일

**AI:**
파일 크기 확인:
- hprof before/after: 각 약 125MB
- meminfo: 573KB
- gfxinfo: 10KB
- showmap: 212KB
- smaps: 5.3MB

시나리오별 의미:
- idle: 홈스크린 대기 → 메모리 안정성
- quickpanelopenclose: QS패널 열고 닫기 → QS 타일 View leak
- screenonoff: 화면 켜기/끄기 → 삼성의 경우 AOD (SystemUI 프로세스에서 실행)

---

## 3. meminfo 포맷 차이 확인

> 날짜: 2026-04-28

**사용자:**
2번 시스템의 meminfo는 `dumpsys meminfo com.android.systemui` 단일 프로세스 출력. 사진 첨부로 포맷 공유.

**AI:**
1번 시스템과 거의 같지만 추가 필드 확인:
- TOTAL SWAP PSS 행 존재
- Native Allocations 섹션 (malloc, other, bitmap)
- Mapped Bitmap 정보
- POOL STATS 섹션

meminfo 파서에 해당 필드 추가 구현 완료.

---

## 4. 프로젝트 분리 결정

> 날짜: 2026-04-28

**사용자:**
기존 systemui-analyzer와 분리해서 새로운 프로젝트로 할까?

**AI:**
분리 추천. 이유:
- 데이터 구조가 다름 (1번: 버전별 3회, 2번: 시나리오별 20회 + hprof)
- 분석 방식이 다름 (1번: LLM 추측, 2번: hprof 팩트)
- 같은 레포에 넣으면 코드가 복잡해짐

새 프로젝트: `SystemUI-HProf-Analyzer`
레포: https://github.com/miniforce1119/SystemUI-HProf-Analyzer

---

## 5. 초기 구현

> 날짜: 2026-04-28

**AI:**
전체 프로젝트 구현:

```
systemui_hprof_analyzer/
├── cli.py                          # scan, compare, analyze, hprof-diff, parse-meminfo
├── extractor/
│   └── scanner.py                  # zip 해제, 시나리오/회차 자동 분류
├── parser/
│   ├── meminfo_parser.py           # AOSP + TOTAL SWAP PSS, Native Allocations 보강
│   └── hprof_parser.py             # AOSP hprof 바이너리 파서 (순수 Python, 외부 의존성 0)
├── analyzer/
│   ├── scenario_analyzer.py        # meminfo 20회 평균 + hprof diff 통합
│   └── version_comparator.py       # 두 버전 비교 + regression 시 자동 심층분석
├── report/
│   └── generator.py                # Mermaid 시각화 보고서
└── .clinerules                     # Cline 포팅 규칙
```

---

## 6. 두 버전 비교(compare) 기능 추가

> 날짜: 2026-04-28

**사용자:**
실제 사용 흐름은 regression 시스템에서 두 버전을 선택 → 비교 화면 → 각 버전별 다운로드. 한 버전 내부 분석도 하고, 기준 버전과 비교도 하고.

**AI:**
2단계 분석 흐름 설계:

```
1단계: compare — 시나리오별 meminfo 20회 평균 비교
  → regression 감지 시 자동으로 2단계 진입

2단계: 심층 분석
  ├── 방법 A: Target 내부 hprof before vs after
  └── 방법 B: Baseline after vs Target after 비교
```

CLI:
```bash
python -m systemui_hprof_analyzer compare ./versionA ./versionB -o report.md
python -m systemui_hprof_analyzer compare ./versionA ./versionB --no-deep  # meminfo만
python -m systemui_hprof_analyzer analyze ./versionB --scenario idle -o report.md
```

---

## 7. Agent Builder 호출 횟수 확인

> 날짜: 2026-04-29

**사용자:**
Agent Builder로 request하는 횟수는 몇 번?

**AI:**
**0회 또는 1회.** meminfo 분석과 hprof 분석은 전부 Python 로컬에서 수행.
Agent Builder는 필요하면 메일 발송용으로만 사용 (선택).

1번 프로젝트와의 차이:
| | 1번 프로젝트 | 2번 프로젝트 |
|---|---|---|
| LLM 역할 | 핵심 (원인 추측) | 불필요 (팩트) |
| Agent Builder | 필수 | 메일 발송용 (선택) |

---

## 8. PSS 추이 통계 분석 추가

> 날짜: 2026-04-29

**사용자:**
20회 테스트 중 한번씩 튀는 경우가 있거든. 어떤 관점으로 보는게 좋을까?

**AI:**
Trimmed Mean + 이상치 감지 제안. 사용자 동의 후 구현:

- **TrendStats** 데이터클래스: 단순 평균, trimmed 평균(상하 10% 제거), 중앙값, 표준편차
- **이상치 감지**: 평균 ± 2σ 초과 시 이상치로 판정, 평균 계산에서 제외
- **누수 판정**: 이상치 제거 후에도 1% 이상 증가 시 `is_leaking = True`

테스트 결과 (시뮬레이션):
```
20회 중 3회차에 512,000 KB 튀는 값
→ 4.3σ 이상치로 감지
→ 이상치 제거 후 성장률: +1.6%
→ 누수 판정: True
```

---

## 9. hprof 참조 체인 분석 방향 결정

> 날짜: 2026-04-29

**사용자:**
Cline으로 분석 결과 만들었는데 인스턴스 증가 의심 객체 TOP 15를 뽑아주거든. 이 오브젝트가 어디서 생성됐는지 관계도 찾아줄 수 있을까?

**AI:**
두 가지 방법 제안:
- A안: Python 파서에 직접 구현 → 난이도 높음, 125MB 전체 파싱 필요
- B안: MAT(Eclipse Memory Analyzer) CLI → 20년 검증, 정확, Java 필요

### Java 설치
사용자: Java 설치 시 라이센스 이슈?
AI: Oracle JDK만 피하면 됨. **OpenJDK Adoptium Temurin** → 기업 완전 무료.
사용자: OpenJDK Temurin 설치 완료.

### MAT 설치 및 테스트
- hprof-conv 필요: Android hprof → 표준 Java hprof 변환 (MAT가 Android 포맷 직접 못 읽음)
- MAT Strictness를 **Permissive**로 변경해야 삼성 hprof 열림
- hprof-conv 경로: `C:/tools/platform-tools-latest-windows/platform-tools/hprof-conv.exe`

### MAT GUI 테스트 결과
1. **Leak Suspects 리포트**: Problem Suspect 1 = java.lang.Class (런타임 기본, 실제 leak 아닐 가능성)
2. **before vs after Compare**: 정상 동작. idle 시나리오에서 대부분 객체가 감소 → 이 시나리오는 깨끗

### 핵심 결정: TOP 15 전부 참조 체인 추적

**사용자:**
TOP 15에 SystemUI 전용 클래스 외에 framework 클래스도 있잖아. 이건 빼고?

**AI:**
필터링하면 안 됨. 이유:
```
Bitmap (+72) → framework 클래스이지만 SystemUI가 만든 것
참조 체인 추적하면:
  Bitmap → ImageView → QSTileView → QSPanel
  → 결국 SystemUI 코드가 나옴
```

**최종 결정:** TOP 15 전부 참조 체인 추적. 필터링 없음.

### 최종 보고서 형태
```
인스턴스 증가 TOP 15 테이블 (Python hprof 파서)
  +
각 TOP 15 객체의 참조 체인 (MAT CLI)
  → 개발자가 보고서만 보면 어떤 코드를 수정해야 하는지 바로 알 수 있음
```

### Cline으로 위임
MAT는 사내 PC에 설치, 실제 hprof도 사내에만 있으므로 MAT CLI 연동은 Cline이 구현.
`.clinerules`와 `USAGE_GUIDE.md`에 연동 가이드 반영 완료.

Cline 작업 항목:
1. `utils/hprof_converter.py` — hprof-conv 자동 호출
2. `utils/mat_cli.py` — MAT CLI로 TOP 15 참조 체인 추출
3. `report/generator.py` — 보고서에 참조 체인 섹션 추가

---

## 다음 단계 (예정)

- [ ] (Cline) hprof-conv 자동 변환 구현
- [ ] (Cline) MAT CLI 연동 (ParseHeapDump + 결과 파싱)
- [ ] (Cline) 보고서에 참조 체인 섹션 추가
- [ ] (Cline) 전체 파이프라인 E2E 테스트 (실제 사내 데이터)
- [ ] mkdocs 연동 (보고서 → GitHub Pages 배포)
- [ ] (선택) Agent Builder 메일 발송 연동
