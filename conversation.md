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

---

## 26. Claude Code 하네스 전환 + 재설계 (2026-05-23)

> 사내 Cline SR 로 진행하다 막힌 부분(MAT CLI 연동 실패)을 풀기 위해
> 집/회사 멀티 PC 환경에서 Claude Code 하네스 기반으로 재출발.

### 26.1 전환 배경

**사용자:**
회사 안에서는 Cline SR 이라는 AI code assistant 를 사용했음. MAT CLI 를 붙이려고 했는데
계속 에러가 나서 한동안 안 하다가 다시 해 보려고 함. 이번엔 Claude Code 하네스로 가고
싶음. 그리고 집에서 만들다가 회사 PC 에서 이어 작업할 수도 있어서, 같은 환경이 유지돼야 함.

**AI (Claude):**
멀티 PC 작업이 전제라면 하네스 가치가 더 큼. 자동 메모리만으로는 PC 간 동기화가 안 되므로
구조적 결정은 git 추적 파일에 명시적으로 남겨야 함. 그래서 다음 영속화 계층을 도입:

| 파일 | 역할 |
|---|---|
| CLAUDE.md | 매 세션 자동 로드되는 프로젝트 컨텍스트 |
| decisions.md | 구조적 결정 기록 (D1~D9) |
| conversation.md | 대화/맥락 흐름 (시간순) |
| config/local.example.yaml | 환경 경로 템플릿 |
| config/local.yaml | 각 PC 실제 설정 (gitignore) |

### 26.2 본질 문제 재정의

이전 도구로 풀지 못했던 것을 재확인:

| 시도 | 한계 |
|---|---|
| bugreport diff | leak 의심 객체 자체를 못 찾음 |
| hprof before/after diff | "객체가 늘었다" 까지만, 누구 소속인지 모름 |
| MAT CLI 참조 체인 추적 | 사내 Cline SR 로 시도, OQL 문법 에러 / 빈 결과 계속 |

→ 진짜 목표: "TextView +194" 가 아니라
**"QSPanel.mTileLayout.mTiles 에 이전 타일이 안 빠지고 쌓이는 게 원인"** 까지.
객체 증가 + GC Root 까지의 참조 체인 + 자연어 가설.

### 26.3 우선순위 재정렬

제안서 단계 순서 대신:

```
[1] MAT/hprof PoC 코어 ← 이전에 막혔던 곳, 안 풀리면 나머지 무의미
[2] hprof + LLM 자연어 보고
[3] bugreport triage + Agent  (제안서 메인 파이프라인은 (1)(2) 후로)
[4] RAG / 유사 사례 DB
[5] 메일 자동화
```

### 26.4 PoC-first 전략

집에서 PoC 끝낸 후 사내 포팅. 사내 환경 의존성은 모두 config 로 격리.

- hprof 샘플: 본인 안드로이드 폰 + 직접 작성한 테스트 앱 (Activity 가 static
  리스트에 자기 자신 추가하는 전형적 leak)
- adb shell am dumpheap 으로 캡처 (자기 앱은 root 없이 가능)
- 사내 검증은 사내 regression test 시스템의 실제 SystemUI hprof 로

### 26.5 멀티 PC 셋업 절차 확정

새 PC 첫 셋업 (집/회사 동일):

```
1. git clone (회사의 경우) 또는 git pull
2. python -m venv .venv
3. .venv\Scripts\Activate.ps1
4. pip install -r requirements.txt
5. cp config\local.example.yaml config\local.yaml
6. local.yaml 의 paths 를 해당 PC 경로로 채움
7. python -m systemui_hprof_analyzer env-check
```

추가된 코드:
- `systemui_hprof_analyzer/config/loader.py`: YAML config 로더
- `cli.py` 에 `env-check` 서브커맨드: 도구 경로/Java 버전 검증
- `requirements.txt` 에 PyYAML 추가
- `.gitignore`: `config/local.yaml`, `.venv/`, `.work/`, `samples/`, `.rag/`,
  `*.docx` (제안서 포함) 등 추가

### 26.6 도구체인 설치 (집 PC)

설치 가이드를 `docs/setup-toolchain.md` 에 영구 문서화. 이 문서가 회사 PC 에서도
같은 절차를 보장.

설치 진행 결과:

| 도구 | 결과 |
|---|---|
| platform-tools | `C:\tools\platform-tools\` (adb 1.0.41, hprof-conv) |
| Java 17 | `C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot\` (Temurin) |
| → 기존 JDK 8 | 제거 완료 (PATH 자동 정리) |
| MAT | `C:\tools\mat\` (Standalone, Windows x86_64) |
| → MemoryAnalyzer.ini | `-Xmx1024m` → `-Xmx6g` 로 변경 |
| Android Studio | 보류 (Phase 2 진입 시) |

`env-check` 최종: **[OK] 모든 필수 도구가 준비되었습니다.**

ParseHeapDump.bat 빈 인자 실행으로 살아있음 확인 (`java.version=17.0.19`,
`Usage: [options] <snapshot>` 메시지 = 정상 의도된 출력).

### 26.7 알려진 함정 누적

CLAUDE.md "알려진 함정" 섹션에 다음 기록:
- ParseHeapDump 기본 힙 1GB → 6GB 이상 필요
- Android hprof 그대로 입력 시 깨짐 (hprof-conv 필수)
- OQL 문법 버전 차이 → 단일 문법에 의존 말고 라이브러리화
- 인덱스 캐시 충돌 / 출력 포맷 불안정

### 26.8 결정사항 D1~D9

`decisions.md` 에 영속화:
- D1: 멀티 PC 작업 전제
- D2: PoC-first 개발 전략
- D3: 작업 우선순위 재정렬
- D4: hprof 메인 입력, bugreport 보조
- D5: PoC 샘플은 개인 폰 + 테스트 앱
- D6: config/local.yaml 방식
- D7: decisions.md / conversation.md 분리
- D8: MAT 실패 우회 (OQL 대체 + Python fallback)
- D9: 표준 venv (uv/Poetry 아님)

### 26.9 git 이력

이 세션의 커밋:
- `f048280` feat: Claude Code 하네스 셋업 (멀티 PC 작업 지원)
- `99345c1` docs: 외부 도구 설치 가이드 추가 (집/회사 PC 공통)

### 26.10 다음 단계 (Phase 1 진입)

- [ ] 폰 USB 연결 → `adb devices` 동작 확인
- [ ] 아무 앱이나 `adb shell am dumpheap` 으로 첫 hprof 캡처
- [ ] `hprof-conv` 로 변환 후 MAT 인덱싱 → 6GB 설정 실효성 검증
- [ ] OQL 첫 시도 (사내에서 막혔던 패턴 재현 또는 돌파)
- [ ] `utils/hprof_converter.py` 작성 (hprof-conv 래퍼)
- [ ] `utils/mat_cli.py` 작성 (MAT CLI 래퍼 + OQL 라이브러리 + 실패 패턴 로깅)
- [ ] (Phase 2 진입 직전) Android Studio 설치 + 테스트 leak 앱

### 26.11 회사 PC 에서 이어 작업할 때

```
[처음 한 번]
git clone https://github.com/miniforce1119/SystemUI-HProf-Analyzer.git
cd SystemUI-HProf-Analyzer
claude          # Claude Code 시작 → CLAUDE.md 자동 로드 (/init 불필요)
# 위의 26.5 절차로 venv + config 셋업
# 사내는 도구가 이미 설치되어 있을 가능성 높음 → 경로만 local.yaml 에 등록

[이후 매번]
cd SystemUI-HProf-Analyzer
git pull
claude          # Claude 가 CLAUDE.md/decisions.md/conversation.md 읽고 시작
```

**중요:** GitHub MCP 와 git clone 은 다른 것. GitHub MCP 는 Claude 가 GitHub API
를 다루는 도구이고, 리포 로컬 복제는 git clone 이 함. `/init` 슬래시 커맨드는
CLAUDE.md 가 없을 때 새로 만드는 명령이므로, 이미 있는 우리 리포에서는 쓸 필요 없음
(오히려 덮어쓸 위험).

---

## 27. Phase 1 PoC — 도구 체인 외부 검증 (2026-05-23 후반)

> 같은 날 오후, 하네스 셋업 + 도구 설치 마친 직후 실제 PoC 진입.
> 사내에서 막혔던 MAT/OQL 영역이 외부에서 동작 확인됨.

### 27.1 도구 설치 (집 PC)

가이드(`docs/setup-toolchain.md`) 따라 진행:

| 도구 | 설치 경로 | 비고 |
|---|---|---|
| platform-tools | `C:\tools\platform-tools\` | adb 1.0.41, hprof-conv 포함 |
| Java 17 (Temurin) | `C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot\` | 이미 설치되어 있었음. JDK 8 제거 완료 |
| MAT | `C:\tools\mat\` | Standalone, Windows x86_64. MemoryAnalyzer.ini 의 `-Xmx1024m` → `-Xmx6g` 변경 |
| Android Studio | 기본 경로 | LeakTest 빌드용 |

`env-check` 모든 항목 [OK].

### 27.2 LeakTest 앱 작성 및 빌드

- 가이드: `docs/leak-test-app.md`
- 위치: `C:\Users\head1\AndroidStudioProjects\LeakTest`
- 패턴: `ActivityHolder.sActivities` (static ArrayList) 에 MainActivity 인스턴스 누적
- 각 인스턴스 1MB `LeakablePayload` 보유 → retained heap 측정 명확

### 27.3 hprof 캡처

폰 (Samsung Galaxy S24 Ultra, SM-S948N, Android 16):
- 1차 hprof: 49.8MB (인스턴스 1개만 — 단순 LEAK 탭은 같은 인스턴스 반복 추가였음)
- 2차 hprof: 66.1MB (회전 + LEAK 조합으로 12개 인스턴스 누적)

발견된 함정 (decisions.md D12 에 영속화):
- Samsung Auto Blocker → USB 디버깅 그레이 처리 (해제 절차 기록)
- Git Bash 의 `/data/local/tmp` 자동 변환 → `MSYS_NO_PATHCONV=1` 필요

### 27.4 hprof-conv 변환

`hprof-conv.exe samples/leak_first.hprof .work/leak_first_converted.hprof`

- Android 1.0.3 → 표준 1.0.2 (magic byte 변환 확인)
- 크기 49,804,854 → 49,721,415 bytes (-83KB)

### 27.5 MAT 인덱싱 (사내에서 막혔던 첫 지점)

`ParseHeapDump.bat leak_first_converted.hprof`

- 약 1-2분 소요
- 11개 .index 파일 정상 생성 (a2s, domIn, domOut, idx, inbound, outbound, ...)
- `Calculating minimum retained heap size for classes` 까지 정상 종료
- → **사내 Cline SR 에서 막혔던 인덱싱 단계 외부에서 성공**

### 27.6 OQL 시도 — CLI 실패, GUI 성공

CLI 시도 (`ParseHeapDump.bat -command="oql ..."`):
- PowerShell → cmd → .bat 인용 충돌로 OQL 토큰들이 따로 보고서 ID 로 해석됨
- 여러 우회 시도 모두 실패: `--%`, `\"..\"`, 변수 변수
- 결론: **ParseHeapDump.bat 의 `-command=oql` 경로는 PowerShell 환경에서 안정적이지 않음**

GUI 시도:
- MAT GUI 에서 hprof 열기 (인덱스 이미 있어 즉시 로드)
- OQL 패널에서 `SELECT * FROM com.example.leaktest.MainActivity` 실행
- **Total: 12 entries** — 12개 MainActivity 인스턴스 검출
- 각 인스턴스 retained heap ≈ 1,055KB (1MB payload 정확히 잡힘)
- 1개 인스턴스 우클릭 → Merge Shortest Paths to GC Roots → 트리 추출 성공:
  ```
  Thread → contextClassLoader → ActivityHolder → sActivities → elementData → MainActivity
  ```

### 27.7 PoC 검증 결과 영구화

증거 영구 저장:
- `docs/screenshots/poc_01_path_to_gc_roots.png`
- `docs/screenshots/poc_02_oql_12_instances.png`
- `project-pitch.md` 7.3 결과 섹션 — TBD → 실측 데이터로 갱신
- `decisions.md` D12 — 외부 PoC 1차 검증 성공 + 발견 함정 3개
- `handover-checklist.md` B 섹션 — 항목별 체크 표시

### 27.8 hprof_converter.py 코드화

손으로 검증된 hprof-conv 호출을 Python 래퍼로:
- `systemui_hprof_analyzer/utils/hprof_converter.py` (162 lines)
- `cli.py` 에 `convert-hprof` 서브커맨드 추가
- 9개 단위 테스트 (`tests/test_hprof_converter.py`) 모두 통과
- 손으로 만든 파일과 코드로 만든 파일이 바이트 단위 정확히 동일 (`cmp` 검증)

### 27.9 ★ 미완성 인지 — OQL 자동화 (중단)

사용자가 정확히 지적: "MAT GUI 로 하면 자동화가 안 되는 거 아니야?"

→ 정확. GUI 동작 확인 = MAT 의 인덱싱/OQL 엔진이 살아있다는 증거지만,
**"자동화 도구"의 PoC 로는 절반만 완료된 상태.** OQL CLI 자동화는 사내 Cline SR
실패 지점 그대로. 이걸 풀어야 발표 자료의 핵심인 "사람 없이 결과 추출" 이 됨.

후보 경로:
- **A**: ParseHeapDump.bat `-command=oql` 의 인용 문제를 다양한 패턴으로 다시 시도 (가장 단순)
- **B**: ParseHeapDump.bat 의 report ID 방식 (임의 OQL 안 됨, 제한적)
- **C**: MAT Headless / Java 클래스 직접 호출 (정석, Java 깊이 필요)
- **D**: shark-cli (Square) — OQL 은 아니지만 leak 분석 가능
- **E**: Python 자체 hprof 그래프 추적 (MAT 의존 0, 시간 많이 듦)

D8 (다층 방어) 정신에 따라 A → C → E 순차 시도가 자연스러움.
**다음 세션에서 이 결정부터.**

### 27.10 이번 세션 git 이력 (Phase 0 + Phase 1 일부)

| 커밋 | 내용 |
|---|---|
| `f048280` | feat: 하네스 셋업 (CLAUDE.md, decisions.md, config, env-check) |
| `99345c1` | docs: 외부 도구 설치 가이드 |
| `770c52d` | docs: conversation.md 세션 26 |
| `32fa16a` | docs: 3-PC 토폴로지 반영 (.clinerules ↔ CLAUDE.md) |
| `6ad259a` | docs: handover 체크리스트 |
| `efa30c9` | docs: project-pitch + leak 앱 가이드 |
| `cad3639` | docs: PoC 1차 검증 영구화 (스크린샷 + D12) |
| `d41a410` | feat: hprof_converter 코드화 + 9개 단위 테스트 |

### 27.11 다음 세션 (집 PC 또는 강의장 PC) 진입 시 할 일

1. **OQL 자동화 경로 결정** (위 후보 A~E 중 A 부터)
2. A 가 풀리면 `utils/mat_cli.py` 작성:
   - 인덱싱 호출 (`ParseHeapDump.bat` subprocess)
   - OQL 호출 + 결과 파싱
   - 실패 OQL 패턴 로깅
3. `cli.py` 에 `trace-refs <class>` 서브커맨드 추가
4. (Phase 1 마무리) `analyze-leak <hprof>` 통합 명령 — 캡처는 별도, 변환 + 인덱싱 + OQL + 보고서까지

### 27.12 다음 세션 시작 절차 (어느 PC 든)

```powershell
cd <repo path>
git pull
.venv\Scripts\Activate.ps1     # 이미 venv 있으면
# (회사 강의장 PC 처음이면 setup-toolchain.md 따라 셋업)
python -m systemui_hprof_analyzer env-check  # 도구 OK 확인
```

Claude Code 가 CLAUDE.md / decisions.md / conversation.md 자동 로드 →
"27.9 미완성 인지" 부터 이어서 작업.
