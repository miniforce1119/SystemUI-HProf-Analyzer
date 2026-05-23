# Handover Checklist — 외부(1)(2) → 사내(3)

> 외부 PoC 가 어느 정도 완성됐다고 판단했을 때, 사내(3) 으로 넘기기 전에 확인해야 할 사항.
> 한 번 (3) 으로 넘어가면 외부에서 수정할 수 없으므로 (단방향), 빠뜨림 없이 점검.
>
> **이 문서는 PoC 진행하면서 발견되는 항목을 누적하는 방식으로 채워간다.**
> 지금은 큰 카테고리만 잡아두고, 세부 항목은 작업하면서 추가.

---

## 사용 방법

1. (1)/(2) 에서 PoC 가 "충분히 완성됐다" 싶을 때 이 체크리스트 전체를 위에서 아래로 점검
2. 모든 [ ] 가 [x] 가 되어야 (3) 으로 이관
3. 진행 중 새로 알게 된 함정/주의사항은 곧바로 이 파일에 항목 추가
   - 그래야 다음 이관 시 같은 실수 안 함
4. 이관 직전 마지막 커밋의 hash 와 날짜를 이 파일 하단에 기록

---

## A. 환경 격리 (사내 경로 하드코딩 차단)

핵심: **(3) 에서 git pull 받았을 때 코드 자체는 손도 안 대고 `local.yaml` 만 바꿔서 동작해야 함.**

- [ ] 코드 내 사내 경로 (`C:/tools/...` 등) 직접 참조 없음 → `grep -ri "C:/tools" systemui_hprof_analyzer/` 가 0건
- [ ] 모든 외부 도구 호출이 `config.loader.load_config()` 경유
- [ ] LLM provider 가 추상화되어 있어 `internal` provider 만 추가하면 사내 LLM 으로 전환 가능
- [ ] 벡터 DB backend 도 인터페이스 분리 (chroma → 사내 DB 교체 가능)
- [ ] (추가 발견 시 여기에 누적)

---

## B. 도구체인 검증 (외부에서 안정화 완료)

핵심: **사내에서 "또 안 돌아간다" 가 없게.**

- [ ] `env-check` 모든 항목 [OK] (외부 PC 기준)
- [ ] hprof-conv 자동 호출 (`utils/hprof_converter.py`) — 정상 hprof 변환 확인됨
- [ ] MAT CLI 인덱싱 — 125MB hprof 정상 인덱싱 (`-Xmx6g` 실효성 확인)
- [ ] MAT CLI OQL — 적어도 한 종류의 참조 체인 추출 성공
- [ ] OQL 실패 시 대체 문법 라이브러리 동작 확인 (실패 패턴 로깅 포함)
- [ ] (추가 발견 시 여기에 누적)

---

## C. 코어 파이프라인 동작 (PoC 단위 테스트)

핵심: **외부 테스트 hprof 로 end-to-end 흐름이 한 줄 명령으로 통과.**

- [ ] 의도적 leak 테스트 앱 (또는 동등 샘플) 에서 hprof 캡처 가능
- [ ] hprof 캡처 → 변환 → diff → MAT 참조 체인 → 자연어 보고 까지 한 번에 실행
- [ ] LLM 자연어 가설 출력 품질 합리적 (테스트 앱의 알려진 leak 패턴을 식별)
- [ ] (Phase 2 이후) bugreport 전처리 모듈 동작
- [ ] (Phase 4 이후) RAG 유사 사례 저장/검색 동작
- [ ] (추가 발견 시 여기에 누적)

---

## D. 사내 보안 / 데이터 처리 규칙

핵심: **(3) 에서 사고 안 나게 미리 설계에 박아두기.**

- [ ] 코드가 원문 hprof / bugreport 를 외부 (LLM API, 외부 DB 등) 로 전송하지 않음
- [ ] LLM 입력은 요약/지표 중심 (원문 전체 전송 X)
- [ ] 개인정보/민감정보 필터링 로직 (이메일, 디바이스 ID 등) — 필요 시
- [ ] 분석 결과 DB 스키마에 민감 필드 분리되어 있음
- [ ] `.gitignore` 가 사내 데이터 (`samples/`, `.work/`) 를 제대로 제외
- [ ] (추가 발견 시 여기에 누적)

---

## E. 문서 일관성

핵심: **(3) 에서 Cline 이 옛 정보로 시작하지 않게.**

- [ ] `.clinerules` 가 `CLAUDE.md` 최신 내용 반영 (D11 규칙)
- [ ] `decisions.md` 의 모든 결정이 코드와 일치
- [ ] `conversation.md` 마지막 세션이 최신 작업 반영
- [ ] `docs/setup-toolchain.md` 가 실제 설치 절차와 일치
- [ ] (3) 환경 특이 사항이 `.clinerules` 에 명시되어 있음 (사내 GitLab 주소, 사내 LLM endpoint 등)
- [ ] (추가 발견 시 여기에 누적)

---

## F. Git 상태

핵심: **마지막 push 가 GitHub.com 에 정상 반영, (3) 에서 pull 하면 100% 동일한 상태가 됨.**

- [ ] `git status` 깨끗 (uncommitted 없음)
- [ ] 마지막 commit 이 `origin/master` 에 push 되어 있음
- [ ] CI / 테스트 (있다면) 통과
- [ ] `.gitignore` 가 의도한 파일들만 제외
- [ ] (추가 발견 시 여기에 누적)

---

## G. (3) 진입 직후 1회성 체크

> 이건 (3) 에서 처음 git pull 받은 직후 즉시 확인.

- [ ] git clone (또는 pull) 성공 — 사내 GitHub Enterprise / 외부 GitHub 미러 경유
- [ ] git remote 확인 — `origin` 이 GitHub.com 인 경우, **사내 GitLab 을 `internal` 등 다른 이름으로 추가**
- [ ] `git config branch.master.pushRemote internal` 같은 안전장치로 실수 push 방지
- [ ] 새 venv 생성, `requirements.txt` 설치
- [ ] `cp config/local.example.yaml config/local.yaml` → 사내 경로로 채움
- [ ] `python -m systemui_hprof_analyzer env-check` 통과
- [ ] 실제 사내 hprof 한 건으로 코어 파이프라인 동작 확인
- [ ] 사내 특이 케이스 발견 시 `.clinerules` / `decisions.md` 추가 후 사내 git 에 push

---

## 이관 이력

> 이관할 때마다 한 줄 추가.

| 날짜 | 마지막 commit | 비고 |
|---|---|---|
| (아직 이관 안 됨) | — | — |
