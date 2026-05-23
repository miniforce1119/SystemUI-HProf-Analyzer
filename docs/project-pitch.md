# Project Pitch — 발표/심사용 코어 자료

> 이 문서는 **AI Level 4 인증 심사 발표의 단일 진실 출처(Single Source of Truth)**.
> PoC 진행하면서 비어있는 섹션들을 누적으로 채워간다.
> 심사 직전에 새로 쓰지 말고, **지금부터 매 단계 끝날 때마다 갱신**.
>
> 슬라이드 자료(.pptx 등)는 이 문서를 그대로 시각화하는 형태로 만들 것.

---

## 1. 한 줄 요약

> Generative AI 를 활용해 Android SystemUI 성능 Regression 의
> **"객체 소속·생성 경로"** 까지 자동 분석하는 AI 보조 도구.

---

## 2. 과제 배경 (Pain Point)

### 2.1 현재 운영 중인 시스템 (이미 자동화된 부분)
- Android SystemUI 일 단위 자동화 Regression Test 시스템 운영
- 잠금화면 진입/해제, QS 패널 확장/축소, 화면 켜기/끄기 시나리오 자동 측정
- bugreport 자동 수집

### 2.2 막혀있는 부분 (수동)
**Regression 탐지까지는 자동화되어 있으나, 원인 분석은 여전히 수동**.

| 항목 | 현황 |
|---|---|
| bugreport 파일 크기 | 평균 15-30MB (압축 시 3-5MB) |
| 주요 분석 대상 로그 | dumpsys meminfo (~5,000줄), logcat (~10,000줄), activity dump (~3,000줄) |
| **1건당 분석 소요 시간** | **평균 2-4시간** (숙련자 기준) |
| Regression 발생 빈도 | 주 3-5회 |
| **주간 분석 소요 시간** | **약 6-20시간 (업무 시간의 30-50%)** |
| 신규 분석자 투입 기간 | 독립적 분석까지 3-6개월 소요 |

### 2.3 분석 병목 — 초기 Triage 단계
분석자가 매번 답해야 하는 질문:
- 어떤 subsystem (Activity Manager, Window Manager, View System 등) 에서 문제가 발생했는가?
- 어떤 로그 영역을 우선적으로 확인해야 하는가?
- 정상 버전 대비 어떤 변화가 발생했는가? (메모리, 객체 수, 스레드, 로그 패턴 등)
- 변화가 의미 있는 것인가, 노이즈인가?

숙련된 분석자도 초기 triage 에 1-2시간 소요. 여러 Regression 동시 발생 시 분석 품질 저하.

---

## 3. 기존 접근의 한계

이전 PoC 시도들과 막힌 지점:

| 시도 | 한계 | 결과 |
|---|---|---|
| **bugreport 텍스트 diff** | 비정형 로그라 의심 객체 자체를 못 찾음 | 부분 실패 |
| **hprof before/after diff** | "객체가 늘었다"는 알지만 **누구 소속인지** 모름 | 절반의 성공 |
| **MAT CLI 참조 체인 추적** (사내 Cline SR) | OQL 문법 에러 / 빈 결과 반복 | **실패, 한동안 중단** |

→ 즉, 가장 가치 있는 정보 = **객체의 생성 경로 / 보유자 / GC Root 까지의 참조 체인**
이 영역이 자동화되지 못한 상태.

---

## 4. 우리 접근의 차별점

### 4.1 단일 도구가 아니라 다층 방어

```
[1] Python hprof parser (이미 보유)
    └ 인스턴스 증가 TOP N 추출
[2] MAT CLI (안정화)
    └ TOP N 의 GC Root 까지 참조 체인 추출
    └ 실패 시 대체 OQL 문법 순차 시도 (라이브러리화)
[3] Python 참조 그래프 fallback
    └ MAT 가 끝까지 실패할 경우의 마지막 보루
[4] LLM 자연어 가설
    └ "QSPanel.mTileLayout.mTiles 에 누적" 같은 한 줄 결론
```

핵심 원칙: **하나가 실패해도 다음이 받는다.** 이전 PoC 가 단일 경로(OQL) 만 시도하다가 막혔던 교훈.

### 4.2 Human-in-the-Loop

AI 는 최종 판단 주체가 아니라 분석자의 판단을 보조. 보고서에 "분석자 기록" 섹션을 두어 검토/주석 가능.

### 4.3 멀티 환경 작업 일관성 (SW 공학적 기여)
- 집 PC / 강의장 PC / 사내망 PC 세 환경을 오가며 작업
- 모든 컨텍스트를 git 추적 파일에 영속화 (CLAUDE.md, decisions.md, conversation.md)
- 환경 경로 격리 (config/local.yaml), provider 추상화 → 사내 포팅 시 코드 수정 0

---

## 5. 핵심 기능 (LLM 활용 4축)

### ① 로그 전처리 및 구조화 (Phase 3)
- 로컬 PC 에서 bugreport 를 정규식/룰 기반으로 섹션 분리
- 정상/문제 버전 간 변화 지표 (메모리, 로그 패턴 등) 구조화
- LLM 입력을 위한 요약 데이터 생성 (토큰 제한 대응)

### ② AI Agent 기반 비교 분석 (Phase 3)
- Agent Builder 활용 multi-step 분석 워크플로우
- 정상 vs 문제 버전 자동 비교 및 변화 지표 탐지
- 신규 오류 패턴 탐지 및 우선순위 제시
- **SystemUI 관점의 원인 가설 생성** ← 핵심 가치

### ③ 분석 결과 자동 보고서 생성
- 구조화된 Markdown 보고서 (Mermaid 시각화 포함, 이미 구현됨)
- 팀 공유용 메일 초안 자동 작성 (Phase 5)
- 표/차트 자료 자동 생성

### ④ 유사 사례 검색 및 재활용 (Phase 4)
- 분석 결과를 벡터 DB 에 저장
- RAG 로 유사 사례 검색
- 과거 해결 방법 참조

---

## 6. 진행 단계 (PoC 우선순위 재정렬)

제안서 단계 순서가 아니라 다음 우선순위로 진행:

```
[Phase 0] 하네스 셋업 ← ✅ 완료 (2026-05-23)
[Phase 1] MAT/hprof PoC 코어 ← 진행 중
[Phase 2] hprof + LLM 자연어 보고
[Phase 3] bugreport triage + Agent (제안서 메인)
[Phase 4] RAG / 유사 사례 DB
[Phase 5] 메일 자동화 (사내에서)
```

근거: **가장 막혔던 곳(MAT)** 을 1순위로 옮겨야 나머지가 의미 있음.
표면 분석에 머물지 않고 "객체 소속" 까지 가는 것이 본질.

---

## 7. 현재 진행 상황

### 7.1 완료된 것 (✅)

**SW 공학 측면:**
- 멀티 PC (집/강의장/사내) 작업 토폴로지 설계 및 영속화
- 환경 격리 (config/local.yaml, provider 추상화)
- Claude Code 하네스 + Cline 양립 (.clinerules ↔ CLAUDE.md 동기)
- 외부 → 사내 이관 체크리스트 (docs/handover-checklist.md)

**기존 자산 (이전 PoC):**
- Python hprof 바이너리 파서 (순수 stdlib, 외부 의존성 0)
- meminfo 20회 추이 + trimmed 평균 + 이상치 감지
- 시나리오별 분석 + 두 버전 비교 + Mermaid 시각화 보고서

**도구체인:**
- platform-tools (adb, hprof-conv): 설치 완료
- Java 17 (Temurin): 설치 완료
- MAT (ParseHeapDump): 설치 완료, 힙 6GB 설정

### 7.2 진행 중

- [Phase 1] hprof 캡처 → MAT 인덱싱 → OQL 첫 시도

### 7.3 결과 / 측정 (PoC 후 채움)

> 이 섹션은 PoC 진행하면서 단계별로 채운다.

#### 도구 안정화 검증 (예정)
| 항목 | 외부 PoC 결과 | 사내 검증 결과 |
|---|---|---|
| hprof-conv 자동 변환 성공률 | TBD | TBD |
| MAT 인덱싱 성공 (125MB) | TBD | TBD |
| OQL 참조 체인 추출 성공률 | TBD | TBD |
| Python fallback 동작 여부 | TBD | TBD |

#### 분석 시간 단축 (예정, 사내 데이터로 측정)
| 시나리오 | 기존 (수동) | AI 보조 (도구 + 분석자) | 단축률 |
|---|---|---|---|
| (사례 1) | TBD | TBD | TBD |
| (사례 2) | TBD | TBD | TBD |

#### LLM 가설 정확도 (예정)
| 케이스 | LLM 가설 | 실제 원인 | 일치 여부 |
|---|---|---|---|
| (PoC leak 앱) | TBD | ActivityHolder.sActivities | TBD |
| (사내 사례 1) | TBD | TBD | TBD |

---

## 8. 기대 효과

### 8.1 경영 성과
- **분석 시간 단축**: 2-4시간 → 30분 이내 (목표 70%+ 단축)
- **주간 분석 시간**: 6-20시간 → 2-5시간
- 신규 인력 교육 기간: 3-6개월 → 1-2개월

### 8.2 확장 가능성
- 다른 성능 지표 (Battery, CPU, GPU) 로 확장
- 다른 컴포넌트 (Framework, Application) 로 확장
- 타 팀 (Kernel, HAL, Native Service) 으로 확산
- AI Ops 체계 구축의 선례

### 8.3 장기적 가치
- 분석 결과 DB → 조직 지식 자산
- AI 기반 분석 자동화의 사내 표준 모델

---

## 9. 데이터 보안

- 원문 bugreport / hprof 는 **(3) 사내망 PC 내부에서만** 처리
- 외부 (집/강의장 PC) 에서는 의도적으로 생성한 leak 테스트 앱 hprof 만 사용
- LLM 입력은 요약/지표 중심 (원문 전체 전송 금지)
- 분석 결과 DB 에는 요약/지표/근거 발췌만 저장
- 개인 정보 / 민감 정보 필터링

---

## 10. 협업 / 일정

### 10.1 팀
- **본인**: 과제 리더, AI 자동화 담당 (기획, 설계, 구현, PoC 검증)
- **SystemUI 성능 분석 담당자 3명**: 도메인 지식 제공, 실제 사례 검증

### 10.2 일정 (2026-03 ~ 2026-08)
| 단계 | 내용 | 기간 |
|---|---|---|
| 1단계 | 현업 분석 및 요구사항 정의 | 2주 |
| 2단계 | bugreport 전처리 로직 개발 | 4주 |
| 3단계 | AI Agent 분석 구조 설계 | 4주 |
| 4단계 | 로그 비교 분석 PoC | 6주 |
| 5단계 | 메일 자동화 및 협업 공유 | 4주 |
| 6단계 | 유사 사례 DB 구축 | 6주 |

---

## 11. 교육 과정 활용

### 학습 적용 계획
- **AI Agent 설계**: Agent Builder 활용 multi-step 분석 워크플로우 (Phase 3)
- **프롬프트 엔지니어링**: 비정형 로그 분석을 위한 프롬프트 (Phase 2-3)
- **대용량 데이터 처리**: 토큰 제한 대응, 단계적 요약 입력 (Phase 1-2)
- **RAG**: 유사 사례 DB 구축 (Phase 4)
- **AI 모델 선택**: 사내 환경 / 외부 검증 환경 분리, provider 추상화 (Phase 0 완료)

### Best Practice 적용 사례 (지금까지)
- **멀티 환경 컨텍스트 영속화**: Claude Code 하네스 (CLAUDE.md, decisions.md)
- **환경 격리**: config/local.yaml + provider 추상화 → 사내 포팅 시 코드 수정 0
- **다층 방어 설계**: MAT 실패 가정한 fallback 경로 (D8 결정)
- **이관 체크리스트**: 외부 → 사내 편도 이관 사전 점검 (handover-checklist.md)

---

## 12. 발표 시 강조 포인트

1. **"진짜 막혔던 곳을 1순위로"** — 제안서 단계 순서 대신 위험 기반 우선순위
2. **"실패를 자산으로"** — Cline SR 실패 경험을 decisions.md / CLAUDE.md 에 영속화하여
   같은 실수 재방지
3. **"환경이 코드를 망치지 않게"** — 멀티 PC + provider 추상화로 사내 포팅을 무중단 작업으로
4. **"AI는 보조, 사람이 최종 판단"** — Human-in-the-loop 원칙
5. **"객체 소속까지 간다"** — 표면 분석 (객체 수 비교) 을 넘어 참조 체인까지

---

## 13. 참조 문서 (이 리포 내)

- `CLAUDE.md` — Claude Code 상시 컨텍스트 (외부 PC)
- `.clinerules` — Cline 상시 컨텍스트 (사내 PC)
- `decisions.md` — 구조적 결정 D1~D11
- `conversation.md` — 대화/맥락 흐름 (시간순)
- `docs/setup-toolchain.md` — 도구 설치 가이드
- `docs/handover-checklist.md` — 외부 → 사내 이관 체크리스트
- `docs/leak-test-app.md` — PoC 용 leak 앱 가이드

---

> **작성 원칙**: 새 사실/결정/측정 결과가 생길 때마다 즉시 갱신.
> 심사 직전에 한꺼번에 쓰지 말 것.
> 빈 섹션 (TBD) 은 부끄러운 게 아니라 "여기는 아직 진행 중" 의 명시.
