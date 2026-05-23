# Leak Test App — PoC 용 hprof 생성기

> **목적**: SystemUI-HProf-Analyzer 의 PoC 도구체인(hprof-conv → MAT → OQL)을
> 검증하기 위한 **의도적 leak** 을 만드는 최소 Android 앱.
>
> 원리: Activity 가 static 리스트에 자기 자신을 추가 → finish() 해도 GC 안 됨.
> "ActivityHolder.sActivities (ArrayList) → MainActivity" 라는 명확한 참조 체인
> 발생 → MAT OQL 결과가 예측 가능 → 도구 출력 정확성 검증.

---

## 1. 프로젝트 생성 (Android Studio)

Android Studio 첫 실행 → **New Project** → 다음 옵션:

| 항목 | 값 |
|---|---|
| Template | Empty Views Activity |
| Language | Kotlin |
| Name | LeakTest |
| Package name | com.example.leaktest |
| Save location | (어디든 OK, 예: `C:\project\leak_test_app`) |
| Minimum SDK | API 24 (Android 7.0) |
| Build configuration language | Kotlin DSL (기본) |

Finish → 첫 빌드까지 기다림 (Gradle sync 수 분 걸림).

---

## 2. 파일 3개 교체

Android Studio 가 자동 생성한 파일들을 아래 내용으로 **그대로 덮어쓰기**.

### 2-1. `app/src/main/java/com/example/leaktest/MainActivity.kt`

```kotlin
package com.example.leaktest

import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {

    // leak 핵심: 회사명 + 큰 데이터를 함께 보유하는 객체
    private val payload = LeakablePayload(this)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        val statusText = findViewById<TextView>(R.id.statusText)
        val leakButton = findViewById<Button>(R.id.leakButton)
        val gcButton = findViewById<Button>(R.id.gcButton)
        val refreshButton = findViewById<Button>(R.id.refreshButton)

        leakButton.setOnClickListener {
            // 의도적 leak: 자기 자신을 static 리스트에 추가
            ActivityHolder.leak(this)
            updateStatus(statusText)
        }

        gcButton.setOnClickListener {
            // GC 강제 — leak 여부 검증용
            Runtime.getRuntime().gc()
            updateStatus(statusText)
        }

        refreshButton.setOnClickListener {
            updateStatus(statusText)
        }

        updateStatus(statusText)
    }

    private fun updateStatus(tv: TextView) {
        tv.text = """
            누적 leak 카운트: ${ActivityHolder.size()}
            현재 인스턴스: ${this.hashCode()}
            payload size: ${payload.bigData.size} bytes
        """.trimIndent()
    }
}

/**
 * Activity 와 함께 보유되는 큰 데이터.
 * MAT 에서 retained heap 측정 시 의미 있게 보이도록 1MB 크기.
 */
class LeakablePayload(val holder: MainActivity) {
    val bigData: ByteArray = ByteArray(1024 * 1024) { it.toByte() }  // 1MB
}

/**
 * Activity leak 의 진원지.
 * 정적 리스트에 MainActivity 인스턴스를 누적 → 절대 GC 안 됨.
 * MAT OQL 로 추적 시 GC Root 가 이 클래스의 static field 가 됨.
 */
object ActivityHolder {
    private val sActivities = mutableListOf<MainActivity>()

    fun leak(activity: MainActivity) {
        sActivities.add(activity)
    }

    fun size(): Int = sActivities.size
}
```

### 2-2. `app/src/main/res/layout/activity_main.xml`

```xml
<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:orientation="vertical"
    android:padding="24dp"
    android:gravity="center">

    <TextView
        android:id="@+id/statusText"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:textSize="16sp"
        android:padding="12dp"
        android:background="#EEEEEE"
        android:fontFamily="monospace"
        android:layout_marginBottom="24dp"/>

    <Button
        android:id="@+id/leakButton"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:text="LEAK 1개 추가"
        android:layout_marginBottom="8dp"/>

    <Button
        android:id="@+id/gcButton"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:text="GC 강제 실행"
        android:layout_marginBottom="8dp"/>

    <Button
        android:id="@+id/refreshButton"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:text="상태 새로고침"/>

</LinearLayout>
```

### 2-3. `app/src/main/AndroidManifest.xml`

`<application>` 태그에 **`android:debuggable="true"`** 와 **`tools:ignore="HardcodedDebugMode"`** 만 추가하면 됨.
(debug 빌드는 자동으로 debuggable 이지만, 명시적으로 표기해서 헷갈리지 않게)

```xml
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:tools="http://schemas.android.com/tools">

    <application
        android:allowBackup="true"
        android:debuggable="true"
        android:icon="@mipmap/ic_launcher"
        android:label="@string/app_name"
        android:roundIcon="@mipmap/ic_launcher_round"
        android:supportsRtl="true"
        android:theme="@style/Theme.AppCompat.Light.DarkActionBar"
        tools:ignore="HardcodedDebugMode">

        <activity
            android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>

</manifest>
```

> 이미 자동 생성된 manifest 의 `<activity>` 부분이 유사하면 그대로 두고
> `android:debuggable="true"` 만 추가해도 OK.
> `Theme.AppCompat...` 테마는 `androidx.appcompat:appcompat` 의존성이 있으면 됨
> (기본 생성 시 추가됨).

---

## 3. 실행 및 leak 발생시키기

1. 폰을 USB 로 연결, USB 디버깅 켠 상태
2. Android Studio 상단 **Device 드롭다운** 에서 본인 폰 선택 (SM-S948N)
3. **Run 버튼 (녹색 ▶)** 클릭
4. 폰에 앱 자동 설치 + 실행
5. 앱에서:
   - **"LEAK 1개 추가"** 버튼을 **10번 정도 탭** → leak 카운트 = 10
   - **"GC 강제 실행"** 한 번 탭 (실제 GC 안 되는 걸 확인)

이 시점에서 **MainActivity 인스턴스 ≥ 10개** 가 메모리에 잡혀있고,
각각 1MB payload 까지 보유 → 약 10MB 의 leak.

---

## 4. hprof 캡처

PowerShell 또는 bash 에서:

```bash
# 1. 폰 내부 임시 경로에 hprof 떠뜨림
adb shell am dumpheap com.example.leaktest /data/local/tmp/leak.hprof

# 2. 폰 → PC 로 가져오기
adb pull /data/local/tmp/leak.hprof ./samples/leak_first.hprof

# 3. 폰 임시 파일 정리
adb shell rm /data/local/tmp/leak.hprof
```

→ `samples/leak_first.hprof` 가 생기면 1차 캡처 완료.

추가 leak 일으키고 (5번 더 탭) → `leak_second.hprof` 로 다시 캡처하면
**before/after** diff 도 가능.

---

## 5. 기대되는 MAT 분석 결과

이 hprof 를 MAT 로 열면:

- **Histogram** 에서 `MainActivity` 가 10개 이상 (1개여야 정상)
- **Path to GC Roots** → `MainActivity` 가 `ActivityHolder.sActivities` (static field 의 ArrayList) 로 잡혀있음
- **Retained Heap** 큰 객체 → `MainActivity` 또는 `LeakablePayload` (1MB 씩)

OQL 로 다음과 같이 추적 가능 (예상 문법):
```
SELECT * FROM com.example.leaktest.MainActivity
```
또는
```
SELECT * FROM merge_shortest_paths(
  outbound(com.example.leaktest.MainActivity),
  'GC Roots'
)
```

→ 이게 우리 PoC 도구가 "QSPanel.mTileLayout.mTiles" 같은 체인을 추출하는 패턴을
검증하는 출발점.
