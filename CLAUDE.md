# SystemUI HProf Analyzer

> Claude Code 하네스가 매 세션에서 읽는 프로젝트 상시 컨텍스트.
> 변경할 때는 의도적으로 변경할 것 (다른 세션의 작업 일관성에 영향).

---

## 한 줄 요약

Android SystemUI 성능 Regression의 **"객체 소속·생성 경로"** 까지 자동 분석하는 AI 보조 도구.

---

## 과제 맥락

- **과제명**: Generative AI 기반 Android SystemUI Memory & Performance Regression 원인 분석 자동화 및 협업 지원 체계 구축
- **소속 과정**: Generative AI Level 4 교육 지원 과제
- **기간**: 2026년 3월 ~ 8월 (6개월)
- **인력**: 4명 (SystemUI 성능 분석 담당자 3명 + 본인=리더)
- **제안서 원본**: `AI_Level4_과제제안서_심사양식_최종.docx` (로컬에만 보관, `.gitignore` 처리되어 GitHub에 안 올라감)

### 본질적 문제

이전 도구로 풀지 못했던 것:

| 시도 | 한계 |
|---|---|
| bugreport diff (텍스트 로그 비교) | leak **의심 객체** 자체를 못 찾음 |
| hprof before/after diff (현재 코드) | "객체가 늘었다"는 알지만 **누구 소속인지** 모름 |
| MAT CLI로 참조 체인 추적 | 사내 Cline SR로 시도, 계속 실패 (OQL 문법 에러 / 빈 결과) |

따라서 이 프로젝트의 진짜 목표:

> "TextView가 +194" 가 아니라
> "QSPanel.mTileLayout.mTiles 리스트에 이전 타일이 안 빠지고 쌓이는 게 원인이다" 까지

= **객체 증가 + GC Root까지의 참조 체인 + 자연어 가설**

---

## 개발 전략 — PoC-first, 멀티 PC

### 밖(집) → 사내 포팅
1. **밖**에서 Claude Code 하네스로 PoC 완성 (이 PC)
2. **사내** PC에서 git pull → `local.yaml` 한 줄 바꾸고 그대로 동작
3. 사내에서 안 풀리던 MAT CLI 문제를 밖에서 먼저 안정화

### 3-PC 토폴로지 (집/강의장/사내)

이 프로젝트는 **세 환경**을 오갑니다:

| 환경 | 도구 | 외부 인터넷 | GitHub.com push | 사내 데이터 |
|---|---|---|---|---|
| (1) 집 PC | Claude Code | ✅ | ✅ | ❌ |
| (2) 회사 강의장 PC (사외망) | Claude Code | ✅ | ✅ | ❌ |
| (3) 사내망 PC | **Cline** (Claude Code 미사용) | ❌ | ❌ (pull은 ✅) | ✅ |

**데이터 흐름**: (1) ⇄ (2) ⇄ GitHub.com → (3). (3)은 편도 (pull only).

→ Cline 환경은 별도 컨텍스트 파일(`.clinerules`)을 사용. 이 `CLAUDE.md`와
일관되어야 하므로, 한쪽 갱신 시 다른 쪽도 동기화할 것.

영속화 계층 (git 추적, 모든 환경에서 공유):
- `CLAUDE.md` — Claude Code(외부 PC)용 상시 컨텍스트 (이 파일)
- `.clinerules` — Cline(사내 PC)용 상시 컨텍스트
- `decisions.md` — 구조적 결정 기록
- `conversation.md` — 대화/맥락 흐름
- `docs/setup-toolchain.md` — 도구 설치 가이드
- `docs/handover-checklist.md` — 외부(1)(2) → 사내(3) 이관 직전 체크리스트
- `config/local.example.yaml` — 환경 경로 템플릿

PC별 (gitignore):
- `config/local.yaml` — 각 PC의 실제 경로
- `.venv/`

### 환경 의존성 격리 원칙
- **사내 경로 하드코딩 절대 금지** — 모두 `config/local.yaml` 경유
- 외부 도구 (hprof-conv, MAT, Java) — `config/local.yaml`에 경로
- LLM provider — provider 추상화 계층으로 분리 (집: Claude API, 사내: 사내 승인 LLM)
- 벡터 DB — 인터페이스만 통일 (집: 로컬 chroma 등, 사내: 사내 승인)

---

## 우선순위 (재설계됨)

```
[1] MAT/hprof PoC 코어 ← 이전에 막혔던 곳
    └ 안 풀리면 나머지 다 의미 없음
[2] hprof + LLM 자연어 보고
    └ "X.Y.Z 경로에서 안 빠짐" 까지 자동 생성
[3] bugreport triage + Agent
    └ 제안서의 메인 파이프라인. (1)(2)가 안정된 후
[4] RAG / 유사 사례 DB
    └ 분석 결과 자산화
[5] 메일 자동화
    └ 사내 가서 사내 메일 시스템과 연동
```

**현재 단계: [1] 진입 직전 (환경 셋업 중).**

---

## 목표 파이프라인

```
1. hprof 캡처
   └ adb shell am dumpheap (PoC) / 사내 regression test 시스템 (사내)
2. hprof-conv 변환
   └ Android hprof → 표준 Java hprof (MAT가 Android 포맷 직접 못 읽음)
3. Python hprof diff (기존 코드)
   └ before vs after → 증가 인스턴스 TOP N
4. MAT CLI OQL ← 매번 실패하던 곳
   └ TOP N 각각에 대해 GC Root까지의 참조 체인 추출
5. LLM 자연어 가설 생성
   └ "QSPanel → mTileLayout → mTiles에서 안 빠짐" 같은 한 줄 결론
6. (Phase 2+) bugreport 전처리 → Agent triage → RAG → 보고서 → 메일
```

---

## PoC 데이터 전략

- **샘플 출처**: 개인 안드로이드 폰 + 직접 작성한 테스트 앱
- **leak 패턴**: Activity가 static 리스트에 자기 자신 추가 같은 전형적 leak
- **캡처**: `adb shell am dumpheap <pkg> <out.hprof>` (자기 앱은 root 없이 가능)
- **검증 가치**: 참조 체인이 예측 가능한 leak이라 도구 출력 정확성 검증 쉬움

> SystemUI 자체 hprof는 보통 root 필요 → PoC 단계에서는 테스트 앱으로 충분.
> 사내 가서 사내 regression test 시스템의 SystemUI hprof로 검증.

---

## 알려진 함정 (MAT CLI)

이전에 실패한 패턴들. **다음 시도 시 반드시 회피.**

1. **힙 메모리 부족**
   - `ParseHeapDump.bat` 기본 힙은 약 1GB
   - 125MB hprof 인덱싱에 보통 4-8GB 필요
   - 해결: `MEMORY_FLAG=-Xmx6g` 환경변수 또는 .ini 파일 수정

2. **Android hprof를 그대로 입력**
   - MAT는 표준 Java hprof만 읽음
   - 반드시 `hprof-conv` 먼저 실행

3. **OQL 문법 버전 차이** (사내 Cline SR 실패 주원인)
   - MAT 버전마다 `path2gc`, `merge_shortest_paths`, `dominators of` 동작이 다름
   - 단일 문법에 의존하지 말고, 실패 시 대체 문법을 순차 시도하는 라이브러리 구축 예정
   - 시도해본 문법과 결과는 `decisions.md` 또는 mat 모듈의 docstring에 기록

4. **인덱스 캐시 충돌**
   - 같은 hprof를 다른 옵션으로 재실행 시 `.index` 파일 꼬임
   - 재실행 전 인덱스 파일 정리 필요

5. **출력 포맷 불안정**
   - OQL 결과가 HTML/CSV/txt 중 어떤 게 안정적인지 검증 필요
   - 난독화된 클래스명 (`aod.m5`)이 그대로 나옴 → 보고서에 그대로 표시 (mapping 없이 복원 불가)

---

## 작업 규칙

### 코드
- 사내 경로 하드코딩 금지 → 항상 `config/local.yaml` 경유
- 외부 의존성 추가 시 신중히 (현재 `requirements.txt`는 pytest만)
- hprof 파싱은 스트리밍 유지 (125MB 메모리 적재 금지)
- MAT 호출은 반드시 timeout (1-5분)
- hprof-conv 변환 파일은 임시 디렉토리에 생성하고 분석 후 정리

### 문서
- 함정/실패 패턴을 새로 발견하면 → **이 파일의 "알려진 함정" 섹션 갱신**
- 구조적 결정(아키텍처, 우선순위, 제외 결정)은 → `decisions.md`
- 작업 흐름 변화/논의 내용은 → `conversation.md`
- 자동 메모리에만 의존하지 말 것 (PC 간 동기화 안 됨)

### 세션 종료 전 체크리스트
- [ ] 새로 발견한 함정 → `CLAUDE.md` 갱신
- [ ] 새로 내린 결정 → `decisions.md` 추가
- [ ] 변경 코드 → `git commit`
- [ ] `config/local.yaml` 항목 추가 → `local.example.yaml` 동기화

---

## 현재 코드 구조

```
systemui_hprof_analyzer/
├── __main__.py
├── cli.py                  ← scan / compare / analyze / hprof-diff / parse-meminfo
├── extractor/
│   └── scanner.py          ← zip 해제, 시나리오/회차 자동 분류
├── parser/
│   ├── meminfo_parser.py   ← AOSP meminfo + Native Allocations
│   └── hprof_parser.py     ← AOSP hprof 바이너리 파서 (순수 Python)
├── analyzer/
│   ├── scenario_analyzer.py   ← meminfo 추이 + hprof diff 통합
│   └── version_comparator.py  ← 두 버전 비교 + regression 자동 심층분석
├── report/
│   └── generator.py        ← Markdown 보고서 (Mermaid 포함)
├── llm/                    ← 빈 폴더 (Phase 2 진입점)
├── extractor/, utils/, tests/
└── ...
```

---

## 곧 추가될 모듈

```
config/                              ← 환경 경로 격리
├── local.example.yaml
└── local.yaml (gitignore)

systemui_hprof_analyzer/
├── config/                          ← config 로더
│   └── loader.py
├── utils/
│   ├── hprof_converter.py           ← hprof-conv 자동 호출
│   └── mat_cli.py                   ← MAT CLI 래퍼 + OQL 라이브러리
└── (Phase 2+)
    ├── bugreport/                   ← 비정형 로그 전처리
    ├── agent/                       ← LLM 분석 단계
    └── rag/                         ← 유사 사례 검색
```

---

## 슬래시 커맨드 (예정)

아직 없음. PoC 코어가 안정된 후 다음을 추가 예정:

- `/env-check` — config/local.yaml 검증 + 모든 외부 도구 정상 동작 확인
- `/capture-hprof` — 폰에서 hprof 뜨기 + hprof-conv 변환까지
- `/diff-hprof <before> <after>` — diff 돌리고 보고서
- `/trace-refs <class>` — MAT OQL로 참조 체인 추출
- `/full-analysis <baseline> <target>` — 전체 파이프라인 일괄 실행

---

## 외부 도구 환경

**상세 설치 절차**: `docs/setup-toolchain.md`

### 집 PC (이 PC, Windows)
| 도구 | 상태 |
|---|---|
| Java | JDK 8 설치됨 (`C:\Program Files (x86)\AdoptOpenJDK\jre-8.0.242.08-hotspot`) — MAT는 보통 Java 11+ 필요, 업그레이드 검토 |
| adb / platform-tools | 미설치 |
| hprof-conv | 미설치 (platform-tools에 포함) |
| MAT | 미설치 |
| Android Studio | 미설치 (Phase 2에서 필요) |

### 사내 PC (참고)
| 도구 | 경로 |
|---|---|
| hprof-conv | `C:/tools/platform-tools-latest-windows/platform-tools/hprof-conv.exe` |
| MAT | 사내 PC 설치본 (ParseHeapDump CLI) |
| Java | OpenJDK Temurin |

각 PC 첫 셋업:
```
1. python -m venv .venv
2. .venv\Scripts\activate   (PowerShell: .venv\Scripts\Activate.ps1)
3. pip install -r requirements.txt
4. cp config/local.example.yaml config/local.yaml
5. 해당 PC의 도구 경로 채워넣기
6. python -m systemui_hprof_analyzer env-check
```

이후 작업 시작 시:
- PowerShell: `.venv\Scripts\Activate.ps1`
- bash (Git Bash 등): `source .venv/Scripts/activate`
- 직접 호출도 가능: `.venv\Scripts\python.exe -m systemui_hprof_analyzer ...`

**venv를 반드시 사용할 것** — 시스템 Python에 의존성을 깔지 말 것. 사내/집 환경 불일치의 흔한 원인.
