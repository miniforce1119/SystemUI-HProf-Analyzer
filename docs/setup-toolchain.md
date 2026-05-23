# Toolchain Setup (집/회사 PC 공통)

이 프로젝트의 PoC를 굴리려면 다음 외부 도구 4개가 필요합니다.

| 도구 | 용도 | 필수 여부 |
|---|---|---|
| **platform-tools** (adb, hprof-conv) | hprof 캡처/변환 | 필수 |
| **Java 11+** (Temurin) | MAT 실행 환경 | 필수 |
| **MAT** (Eclipse Memory Analyzer) | 참조 체인 추출 (Path to GC Roots) | 필수 |
| **Android Studio** | 테스트 앱 빌드 (Phase 2) | 권장 |

설치 후에는 `config/local.yaml`의 `paths` 항목을 갱신하고 `python -m systemui_hprof_analyzer env-check` 로 검증합니다.

---

## 1. platform-tools (adb, hprof-conv)

### 다운로드
- 공식: https://developer.android.com/tools/releases/platform-tools
- 직접 다운로드 (Windows): https://dl.google.com/android/repository/platform-tools-latest-windows.zip

### 설치
1. zip 다운로드
2. 압축 해제 → 예: `C:\tools\platform-tools\`
3. `adb.exe`, `hprof-conv.exe` 둘 다 그 폴더 안에 있는지 확인
4. (선택) `C:\tools\platform-tools` 를 시스템 PATH 에 추가

### local.yaml 갱신
```yaml
paths:
  adb: C:\tools\platform-tools\adb.exe
  hprof_conv: C:\tools\platform-tools\hprof-conv.exe
```

### 검증
```powershell
C:\tools\platform-tools\adb.exe version
C:\tools\platform-tools\hprof-conv.exe
# hprof-conv는 인자 없으면 사용법만 출력함 (정상)
```

### 사내 PC 기준 경로 (참고)
- `C:/tools/platform-tools-latest-windows/platform-tools/`

---

## 2. Java 11+ (Eclipse Temurin)

### 왜 필요한가
- MAT는 Java 11+ 권장. JDK 8에서는 일부 OQL 또는 인덱싱 단계가 실패할 수 있음
- 이 PC 현재 상태: JDK 8 → 업그레이드 필요

### 다운로드
- 공식: https://adoptium.net/temurin/releases/?version=17
- 권장: **Temurin 17 LTS** (Windows x64 MSI 설치 파일)

### 설치
1. MSI 다운로드 후 실행
2. 설치 옵션에서 **"Set JAVA_HOME variable"** 와 **"Add to PATH"** 를 체크 권장
3. 기본 설치 경로: `C:\Program Files\Eclipse Adoptium\jdk-17.x.x.x-hotspot\`

### local.yaml 갱신
```yaml
paths:
  java: C:\Program Files\Eclipse Adoptium\jdk-17.0.x-hotspot\bin\java.exe
```
실제 버전 폴더명은 설치 후 확인 (`ls "C:\Program Files\Eclipse Adoptium"`).

### 검증
```powershell
java -version
# openjdk version "17.x.x"...
```

### 기존 JDK 8 처리
- 다른 도구가 JDK 8 에 의존하지 않으면 제거해도 됨
- 의존하는 다른 도구가 있다면 그대로 두고 PATH/JAVA_HOME 만 17 로 가리키게

---

## 3. MAT (Eclipse Memory Analyzer)

### 다운로드
- 공식: https://eclipse.dev/mat/downloads.php
- **Standalone Memory Analyzer** 의 **Windows x86_64** 버전 zip
- 크기: 약 80MB

### 설치
1. zip 다운로드
2. 압축 해제 → 예: `C:\tools\mat\`
3. 그 폴더 안에 `MemoryAnalyzer.exe`, `ParseHeapDump.bat`, `MemoryAnalyzer.ini` 등이 있어야 함

### 힙 메모리 설정 (필수)
125MB hprof 인덱싱은 기본 1GB 힙으로 불가능. **반드시 늘려야 함.**

#### 방법 A: MemoryAnalyzer.ini 수정 (영구)
`C:\tools\mat\MemoryAnalyzer.ini` 파일을 텍스트 에디터로 열고 `-Xmx` 라인을 다음으로 변경:
```
-Xmx6g
```
(라인이 없으면 추가. `-vmargs` 아래에 위치)

#### 방법 B: 환경변수 (CLI 한정)
`ParseHeapDump.bat` 호출 시 환경변수 `MEMORY_FLAG=-Xmx6g` 를 set.

config/local.yaml 의 `mat.memory_flag` 항목과 일치시키는 게 좋습니다.

### local.yaml 갱신
```yaml
paths:
  mat_parse_heap_dump: C:\tools\mat\ParseHeapDump.bat
mat:
  memory_flag: -Xmx6g
  timeout_seconds: 600
```

### Java 연결 확인
MAT가 위에서 설치한 Java 17 을 쓰는지 확인:
- `MemoryAnalyzer.ini` 의 `-vm` 라인 또는 PATH 의 java 가 17 이어야 함

### 검증
```powershell
C:\tools\mat\ParseHeapDump.bat
# 인자 없이 실행하면 사용법 출력 (정상)
```

---

## 4. Android Studio (Phase 2 - 테스트 앱 빌드용)

### 다운로드
- 공식: https://developer.android.com/studio

### 설치
1. 설치 파일 다운로드 → 실행
2. 기본값으로 진행 (SDK Manager 가 함께 설치됨)
3. 첫 실행 시 SDK 다운로드 (수 GB, 시간 걸림)
4. 권장 SDK: Android 14 (API 34) 또는 그 이상

### 이 단계는 platform-tools/Java/MAT 설치 후 미뤄도 됨
- PoC Phase 1 (MAT 안정화) 까지는 Android Studio 불필요
- Phase 2 진입 시 테스트 leak 앱 작성할 때 설치

---

## 최종 검증

전부 설치 후:
```powershell
.venv\Scripts\Activate.ps1
python -m systemui_hprof_analyzer env-check
```

다음 출력이 목표:
```
TOOL                 PATH                ...  STATUS
adb                  ...\adb.exe         ...  [OK ] ok
hprof_conv           ...\hprof-conv.exe  ...  [OK ] ok
mat_parse_heap_dump  ...\ParseHeapDump.bat ... [OK ] ok
java                 ...\java.exe        ...  [OK ] ok
work_dir             ...                 ...  [OK ] ...
samples_dir          ...                 ...  [OK ] ...

java -version: openjdk version "17.x.x"

LLM provider: anthropic
RAG backend:  chroma
Mail enabled: False

[OK] 모든 필수 도구가 준비되었습니다.
```

---

## 사내 PC 셋업 시 참고

- 사내 PC 에서는 이미 일부 도구가 다른 경로에 깔려있을 수 있음
- 예: `C:/tools/platform-tools-latest-windows/platform-tools/` (사내 표준)
- 새로 설치하지 말고 기존 경로를 `local.yaml` 에 등록할 것
- 사내 정책으로 인터넷 다운로드가 막혀있을 수 있음 → 사내 미러/SCCM 활용
