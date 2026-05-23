# Decisions

> 이 프로젝트의 **구조적 결정** 영속화 기록.
> 멀티 PC(집↔회사) 작업의 동기화 핵심. 자동 메모리는 PC별로 따로 쌓이므로 여기에 명시적으로 남긴다.
>
> 형식:
> - 결정마다 ID, 날짜, 결정, 이유, 적용 범위
> - 번복할 때는 새 항목을 추가하고 이전 항목에 "Superseded by #N" 표시

---

## D1 — 멀티 PC 작업 전제

- **날짜**: 2026-05-23
- **결정**: 이 프로젝트는 집 PC와 회사 PC를 오가며 진행한다. 두 환경에서 동일한 Claude Code 하네스 컨텍스트로 작업한다.
- **이유**: 사내 데이터/도구에 접근하려면 회사 PC가 필요하지만, PoC와 도구 안정화는 집에서 자유롭게 하는 것이 효율적. 같은 컨텍스트가 두 환경에서 일관되어야 시간 낭비가 없다.
- **적용**:
  - Git 추적: `CLAUDE.md`, `decisions.md`, `conversation.md`, `config/local.example.yaml`
  - PC별: `config/local.yaml` (gitignore)
  - 자동 메모리(`~/.claude/...`)는 보조 수단으로만 사용. 중요한 학습은 위 파일들에 명시.

---

## D2 — PoC-first 개발 전략

- **날짜**: 2026-05-23
- **결정**: 밖(집)에서 모든 핵심 기능을 PoC로 검증한 후, 사내 PC로 포팅한다. 사내 환경 의존성은 모두 config로 격리한다.
- **이유**: 사내에서 Cline SR로 MAT CLI 연동을 시도했으나 계속 실패했다(주증상: OQL 문법 에러 / 빈 결과). 사내는 데이터/도구 접근에 제약이 있어 실험 속도가 느리다. 밖에서 도구 체인을 안정화한 뒤 포팅하면 사내에서는 "경로만 바꿔 동작"하는 상태가 된다.
- **적용**:
  - 코드 내 사내 경로 하드코딩 금지
  - LLM provider, 벡터 DB 등은 인터페이스 추상화 (집/사내 구현 교체 가능)
  - PoC 검증 항목: hprof 캡처 → hprof-conv → MAT CLI → OQL → 자연어 보고

---

## D3 — 작업 우선순위 재정렬

- **날짜**: 2026-05-23
- **결정**: 제안서 단계 순서가 아니라 다음 우선순위로 진행한다.
  1. MAT/hprof PoC 코어 (객체 소속·참조 체인 추출)
  2. hprof 결과 + LLM 자연어 보고
  3. bugreport triage + Agent
  4. RAG / 유사 사례 DB
  5. 메일 자동화
- **이유**: 제안서의 진짜 가치는 "객체가 누구 소속인지" 까지 가는 것이다. 그게 안 풀리면 bugreport triage나 RAG가 다 표면 분석에 머문다. 따라서 가장 막혔던 곳을 1순위로 옮긴다.
- **적용**: Phase 1은 MAT/hprof 안정화에 집중. bugreport 파이프라인은 Phase 2부터.

---

## D4 — hprof 자체를 메인 입력으로, bugreport는 보조

- **날짜**: 2026-05-23
- **결정**: 제안서가 bugreport 중심이지만, **PoC 단계에서는 hprof를 메인 입력으로** 진행한다. bugreport 분석은 hprof 분석이 안정된 후 그 위에 triage 레이어로 얹는다.
- **이유**: bugreport 텍스트 diff로는 leak 의심 객체조차 찾기 어렵다는 게 이미 확인됨. hprof는 팩트 기반이라 검증 가능하고, 이미 만들어진 코드 자산이 있다.
- **적용**:
  - 기존 hprof 코드 (parser/, analyzer/) 유지·확장
  - bugreport 모듈은 Phase 2에 신규 추가
- **참고**: 제안서 자체를 수정하는 게 아니라, PoC 진행 순서를 조정하는 결정. 최종 결과물은 제안서 4단계 모두 포함.

---

## D5 — PoC 샘플 데이터: 개인 폰 + 테스트 앱

- **날짜**: 2026-05-23
- **결정**: 집 PC에서 PoC할 때 hprof 샘플은 본인 안드로이드 폰에 직접 작성한 테스트 앱을 통해 확보한다. 의도적 leak(예: Activity가 static 리스트에 자신 추가)을 일으키고 `adb shell am dumpheap` 으로 캡처.
- **이유**: SystemUI 자체 hprof는 보통 root 권한이 필요. 도구 체인 검증이 목적이라면 일반 앱의 leak도 동일하게 유효하다. 참조 체인이 예측 가능한 leak이면 도구 출력의 정확성도 검증하기 좋다.
- **적용**:
  - 테스트 앱 코드는 별도 폴더 (또는 별도 리포)
  - 캡처한 hprof는 `samples/` 아래 두되 크기상 gitignore
  - 사내 검증은 사내 regression test 시스템의 실제 SystemUI hprof로

---

## D6 — 환경 격리: config/local.yaml 방식

- **날짜**: 2026-05-23
- **결정**: 외부 도구 경로(hprof-conv, MAT, Java, 작업 디렉토리 등)는 `config/local.yaml`에 모은다. `local.example.yaml`만 git 추적.
- **이유**: 환경변수 방식보다 한곳에 모여 가시성이 좋고, 새 PC에서 한 번에 셋업 가능. YAML 한 파일을 보면 이 PC가 어떻게 셋업됐는지 알 수 있다.
- **적용**:
  - 새 PC 셋업: `cp config/local.example.yaml config/local.yaml` → 경로 채움 → `env-check`
  - 코드 내 모든 외부 도구 호출은 config 로더 경유
  - 환경 정보가 늘면 `local.example.yaml`도 동시 갱신

---

## D7 — decisions.md 별도 운영 (conversation.md와 분리)

- **날짜**: 2026-05-23
- **결정**: 구조적 결정은 이 `decisions.md`, 대화 흐름/맥락은 `conversation.md`로 분리.
- **이유**: 두 파일이 섞이면 결정사항을 빠르게 찾기 어렵다. 시간 순서로 누적되는 대화와 시점 무관한 결정은 성격이 다르다.
- **적용**:
  - 결정 = 시점 무관, 번호로 참조 가능, 번복 가능 → 여기
  - 대화/논의 = 시간순, 컨텍스트 → conversation.md

---

## D8 — MAT 실패 우회 전략

- **날짜**: 2026-05-23
- **결정**: MAT CLI는 1차 시도로 사용. 실패 시 OQL 대체 문법을 순차 시도. 그래도 실패하면 Python hprof 파서를 확장해 참조 그래프를 직접 구축하는 fallback 경로를 둔다.
- **이유**: 사내에서 MAT가 계속 실패한 경험이 있다. 하나의 도구에만 의존하면 또 막힌다. 다층 방어가 필요.
- **적용**:
  - `utils/mat_cli.py`: OQL 문법 라이브러리, 실패 시 다음 문법 시도
  - 모든 OQL 시도(성공/실패) 로깅 → 다음 세션이 같은 실패 안 밟게
  - Phase 1 후반 또는 Phase 2 초반에 Python fallback 구현 결정

---

## D9 — Python 의존성은 표준 venv로 격리

- **날짜**: 2026-05-23
- **결정**: 모든 PC에서 `python -m venv .venv`로 가상환경을 만들어 작업한다. 시스템 Python에 의존성을 절대 깔지 않는다.
- **이유**:
  - 멀티 PC (집↔회사) 작업의 가장 흔한 함정이 시스템 Python의 패키지 차이.
  - 사내 PC는 다른 사내 도구가 시스템 Python에 영향을 줄 수 있음.
  - `.gitignore`에 `.venv/`가 이미 있어 컨벤션은 정해져 있음.
  - 표준 venv 선택 이유: stdlib 포함이라 사내 PC에서 추가 설치 불필요. uv/Poetry는 사내 정책상 막힐 위험.
- **적용**:
  - 새 PC 첫 셋업: `python -m venv .venv` → activate → `pip install -r requirements.txt`
  - CLAUDE.md의 셋업 절차에 명시됨
  - 모든 `python -m systemui_hprof_analyzer ...` 호출은 venv 활성화 상태에서

---

## D10 — 3-PC 토폴로지: 외부(1)(2) → 사내(3) 단방향

- **날짜**: 2026-05-23
- **결정**: 이 프로젝트는 세 환경에서 운영된다.
  - (1) 집 PC: Claude Code, 자유
  - (2) 회사 강의장 PC (사외망): Claude Code, 집과 동등
  - (3) 사내망 PC: **Cline 사용** (Claude Code 미사용/미설치), 외부 push 불가
  - 데이터 흐름: (1) ⇄ (2) ⇄ GitHub.com → (3) 단방향 pull
  - (3)에서의 commit/push는 사내 GitLab으로만
- **이유**:
  - 사내 보안 정책상 (3)에서 외부 GitHub.com push 금지
  - (3)에서는 사내 SystemUI hprof, bugreport 등 민감 데이터를 다루므로
    한 번 들어가면 그 데이터/변경 사항은 외부로 못 나옴
  - 따라서 외부에서 최대한 PoC를 완성한 후 (3)으로 이관해 사내 데이터로 최종 검증
- **적용**:
  - `CLAUDE.md` 와 `.clinerules` 두 파일 동기 유지 (Cline은 CLAUDE.md 안 읽음)
  - (3)에서는 git remote 구분 필수: `origin`=GitHub.com (push 금지), `internal`=사내 GitLab (push 가능)
  - 외부 PoC 코드의 모든 환경 의존성은 `config/local.yaml`로 격리 (이미 D6)
  - 외부에서 LLM provider 추상화 필수, 사내(3)에서 `internal` provider 구현 바인딩
  - 외부 → 사내 이관 직전 체크리스트는 `docs/handover-checklist.md`에 영속화 (PoC 진행 후 작성 예정)

---

## D11 — .clinerules 와 CLAUDE.md 동기 유지

- **날짜**: 2026-05-23
- **결정**: Cline은 `CLAUDE.md`를 자동으로 읽지 않고 `.clinerules`만 읽는다.
  따라서 두 파일은 같은 프로젝트의 같은 상태를 반영해야 하며, 한쪽 변경 시 다른 쪽도 동기화.
- **이유**:
  - (3) 사내 PC에서 Cline이 옛 컨텍스트(예: 멀티 PC 전제 없음)로 시작하면 잘못된 결정을 함
  - 이번 세션에서 발견된 차이: 기존 `.clinerules`는 4월 29일자, `CLAUDE.md`는 5월 23일자였음
- **적용**:
  - `.clinerules`를 `CLAUDE.md` 기준으로 재작성 (이번 세션에서 처리됨)
  - 향후 컨텍스트 변경 시 두 파일 동시 갱신
  - `.clinerules` 톤은 사내 환경(3) 관점 (Cline이 읽기 좋게)
  - `CLAUDE.md` 톤은 외부 환경(1)(2) 관점
  - 공통 내용 (과제 맥락, MAT 함정, 우선순위 등)은 두 파일에 모두

---

## D12 — 외부 PoC 1차 검증 성공 (사내에서 막혔던 영역)

- **날짜**: 2026-05-23
- **결정/사실**: Samsung Galaxy S24 Ultra + LeakTest 앱 으로 외부 PoC 도구 체인 전체 검증 완료.
  사내 Cline SR 에서 막혀있던 MAT/OQL 영역이 외부에서 정상 동작함을 확인.
- **검증된 단계**:
  1. `adb shell am dumpheap` 으로 Android hprof 캡처 (49.8MB → 66.1MB)
  2. `hprof-conv` 로 Android 1.0.3 → 표준 1.0.2 변환 (magic byte 검증)
  3. `ParseHeapDump.bat` 인덱싱 (`-Xmx6g`, 11개 .index 파일 생성)
  4. MAT GUI 에서 OQL 실행: `SELECT * FROM com.example.leaktest.MainActivity` → **Total: 12 entries**
  5. Merge Shortest Paths to GC Roots → leak 진원지 (`ActivityHolder.sActivities`) 까지 트리 추출
- **증거**:
  - `docs/screenshots/poc_01_path_to_gc_roots.png`
  - `docs/screenshots/poc_02_oql_12_instances.png`
  - `samples/leak_first.hprof`, `samples/leak_second.hprof` (gitignore 이지만 로컬에 보존)
- **함의**:
  - **이 시점부터 D8(MAT 실패 우회) 의 "Python fallback" 우선순위가 낮아짐.** MAT 가 동작하므로 1차 경로로 충분.
  - Python fallback 은 사내에서 다시 실패할 경우의 보험으로만 남김.
  - 발표 자료에서 "사내 막힘 → 외부 PoC 로 돌파" 라는 서사의 결정적 증거.
- **다음**: CLI 자동화 (utils/hprof_converter.py, utils/mat_cli.py) 로 GUI 검증 단계를 코드화.

### 외부 PoC 중 발견한 추가 함정
- **PowerShell → cmd .bat 인용 충돌**: ParseHeapDump.bat 에 OQL 같은 복잡한 인자를 PowerShell 에서 전달하면
  큰따옴표/별표/공백 이 깨짐. `--%` 도 완전히 해결 못 함. → CLI 자동화는 GUI 처럼
  Eclipse 의 OQL endpoint 를 다른 방법으로 호출하거나, MAT report ID 방식 또는 Python 자체 그래프 추적
  으로 우회 필요.
- **Auto Blocker (Samsung)**: One UI 6+ 에서 USB 디버깅이 그레이 처리되는 원인.
  설정 → 보안 및 개인정보 → Auto Blocker OFF 로 해제.
- **Git Bash 의 `/data/local/tmp` 경로 자동 변환**: `MSYS_NO_PATHCONV=1` 필요.

---

## (Template) D? — <제목>

- **날짜**: YYYY-MM-DD
- **결정**:
- **이유**:
- **적용**:
- **상태**: active | superseded by #?
