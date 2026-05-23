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

## (Template) D? — <제목>

- **날짜**: YYYY-MM-DD
- **결정**:
- **이유**:
- **적용**:
- **상태**: active | superseded by #?
