<p align="center">
  <img src="custom_components/neis_school/brand/icon@2x.png" alt="홈어시스턴트 나이스 학교생활" width="168">
</p>

<h1 align="center">홈어시스턴트 나이스 학교생활</h1>

<p align="center">
  우리 학교의 급식, 시간표, 학사일정과 등교 정보를 Home Assistant에서 확인하고 자동화하세요.
  <br>School meals, timetables, and academic schedules from Korea's public NEIS data.
</p>

<p align="center">
  <a href="https://github.com/mahlernim/ha-neis-school/releases"><img alt="최신 릴리스" src="https://img.shields.io/github/v/release/mahlernim/ha-neis-school"></a>
  <a href="https://github.com/mahlernim/ha-neis-school/actions/workflows/validate.yml"><img alt="검증 상태" src="https://github.com/mahlernim/ha-neis-school/actions/workflows/validate.yml/badge.svg"></a>
  <img alt="Home Assistant 2025.12 이상" src="https://img.shields.io/badge/Home%20Assistant-2025.12%2B-18BCF2?logo=home-assistant&logoColor=white">
  <img alt="HACS 사용자 지정 저장소" src="https://img.shields.io/badge/HACS-Custom-41BDF5?logo=home-assistant-community-store&logoColor=white">
  <a href="LICENSE"><img alt="MIT 라이선스" src="https://img.shields.io/github/license/mahlernim/ha-neis-school"></a>
</p>

<p align="center">
  <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=mahlernim&repository=ha-neis-school&category=integration">
    <img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="HACS에서 저장소 열기">
  </a>
  <a href="https://my.home-assistant.io/redirect/config_flow_start/?domain=neis_school">
    <img src="https://my.home-assistant.io/badges/config_flow_start.svg" alt="Home Assistant에 통합 구성요소 추가하기">
  </a>
</p>

<p align="center"><a href="#한국어">한국어</a> · <a href="#english">English</a></p>

## 한국어

**홈어시스턴트 나이스 학교생활**은 교육부 NEIS 교육정보 개방 포털의 공개
데이터를 Home Assistant에 연결하는 비공식 통합 구성요소입니다. 학교를 한 번
등록하면 급식, 시간표, 학사일정과 등교 정보를 자동으로 갱신하며 대시보드,
알림과 음성 안내 자동화에 활용할 수 있습니다.

## 주요 기능

- 학교 이름을 검색해 학교, 학년과 반을 간편하게 설정
- 오늘과 내일의 조식·중식·석식 메뉴와 영양 정보 제공
- 오늘과 내일의 등교 여부 및 다음 등교일 확인
- 오늘의 학사일정과 다음 학교행사 확인
- 오늘과 내일의 교시별 시간표 제공
- 급식, 시간표와 학사일정을 자연스럽게 읽는 TTS 문장 제공
- 필요한 경우 활성화할 수 있는 학사일정 캘린더
- Home Assistant에서 내려받을 수 있는 개인정보 보호 진단 정보

## 요구 사항

- Home Assistant 2025.12.0 이상
- NEIS에 등록된 국내 초등학교·중학교·고등학교·특수학교
- NEIS 서비스에 연결할 수 있는 인터넷 환경
- 완전한 데이터 조회를 위한 무료 NEIS 인증키 사용 권장

## 설치

### HACS

1. 위의 **HACS에서 저장소 열기** 버튼을 선택합니다.
2. HACS에서 찾을 수 없으면 점 3개 메뉴의 **사용자 지정 저장소**에
   `https://github.com/mahlernim/ha-neis-school`을 **통합 구성요소** 유형으로 추가하세요.
3. **홈어시스턴트 나이스 학교생활**을 다운로드합니다.
4. Home Assistant를 다시 시작합니다.
5. 위의 **Home Assistant에 추가** 버튼을 선택하거나 **설정 → 기기 및 서비스
   → 통합 구성요소 추가**에서 **홈어시스턴트 나이스 학교생활**을 검색합니다.

> **Home Assistant에 추가** 버튼은 통합 구성요소를 다운로드하지 않습니다.
> HACS 설치와 Home Assistant 재시작을 먼저 완료해야 합니다.

### 수동 설치

`custom_components/neis_school` 폴더를 Home Assistant 설정 폴더의
`custom_components` 안에 복사하고 Home Assistant를 다시 시작한 뒤 통합
구성요소를 추가합니다.

## 처음 설정하기

1. NEIS 인증키를 입력하거나, 인증키 없이 사용할 경우 제한 모드의 주의사항을
   확인합니다.
2. 시도교육청을 선택하고 학교 이름을 검색합니다.
3. 검색 결과의 학교 이름과 주소를 확인하세요. 결과가 일부만 반환되면 학교
   이름을 더 구체적으로 입력해 다시 검색하세요.
4. 화면에 표시된 학년도에 맞는 학년과 반을 선택하세요. 1~2월에는 이전 연도
   학년을 사용합니다. 제한 모드에서는 반 이름을 직접 입력합니다.
5. 마지막 화면에서 학교·주소·학년도·학년·반과 연결 모드를 확인하고 사용할
   급식 유형을 선택하세요. 기본값은 중식이며 학사일정 캘린더는 기본 비활성입니다.

인증키 오류가 나면 같은 설정 과정에서 키를 고칠 수 있습니다. 학교 검색어,
학년과 반 선택은 유지됩니다. 반 목록 조회가 실패하면 같은 학년으로 다시
제출하거나 학년을 바꿔 조회하세요. 새 학년도 자료가 아직 공개되지 않았다면
나중에 다시 시도해야 합니다.

설정이 끝나면 선택한 학교·학년·반이 하나의 기기로 추가되고 관련 엔티티가
자동으로 생성됩니다. 같은 학교에 다니는 자녀도 학년이나 반이 다르면 각각
추가할 수 있습니다. 학년, 반과 급식 유형은 **구성**에서 변경하고, 인증키는
통합 구성요소의 **재구성**에서 교체하거나 제한 모드로 전환할 수 있습니다.

## NEIS 인증키

인증키 없이 제한 모드로 설정할 수도 있지만, NEIS가 일부 요청에서 전체 결과
대신 제한된 샘플만 반환할 수 있습니다. 이 경우 통합 구성요소는 불완전한 값을
자동화에 사용하지 않도록 관련 엔티티를 `unavailable`로 표시합니다.

안정적인 시간표, 학사일정과 캘린더 사용을 위해 무료 인증키를 권장합니다.
캘린더와 다음 학교행사·다음 등교일 조회에는 인증키가 필요합니다.

인증키를 사용하는 전체 모드에서는 7일간의 급식·시간표와 90일간의 학사일정을 날짜별로 저장하고
매일 오전과 오후에 갱신합니다. 날짜가 바뀔 때는 저장된 다음 날 자료를 즉시
표시하므로 자정의 일시적인 NEIS 장애 때문에 모든 엔티티가 사라지지 않습니다.
연결이 실패하면 짧은 간격으로 다시 시도하며, 일부 자료만 실패한 경우에는 정상
조회된 다른 자료와 완전한 기존 자료를 유지합니다.

- [NEIS 인증키 신청](https://open.neis.go.kr/portal/guide/actKeyPage.do)
- [NEIS 개발자 가이드](https://open.neis.go.kr/portal/guide/apiGuidePage.do)

## 제공 엔티티

엔티티 ID는 Home Assistant 언어와 학교 이름에 따라 달라질 수 있습니다.
자동화를 만들기 전에 **개발자 도구 → 상태**에서 실제 엔티티 ID를 확인하세요.

| 종류 | 제공 정보 | 자동화에 유용한 속성 |
|---|---|---|
| 급식 센서 | 오늘·내일 조식, 중식, 석식 | `menu_tts`, 열량, 영양성분, 알레르기, 원산지 |
| 시간표 센서 | 오늘·내일 교시별 과목 | `timetable_tts`, 교시 목록 |
| 학사일정 센서 | 오늘 일정, 다음 학교행사 | `schedule_tts`, 행사 목록 |
| 등교일 센서 | 오늘·내일 등교 여부, 다음 등교일 | 판정 이유와 관련 행사 |
| 캘린더 | 학년별 학사일정 | 읽기 전용, 기본 비활성 |

주요 센서 상태는 자동화에서 바로 조건으로 사용할 수 있습니다.

- 급식 센서: `available`(급식 있음), `no_meal`(급식 없음)
- 시간표 센서: 유효한 교시 수. 시간표가 없으면 `0`
- 학사일정 센서: `scheduled`(일정 있음), `none`(일정 없음)
- 등교일 센서: 등교일이면 `on`, 아니면 `off`

캘린더는 모든 일정을 자동으로 등록하지 않도록 기본적으로 꺼져 있습니다.
필요하면 통합 구성요소의 엔티티 목록에서 **학사일정** 캘린더를 활성화하세요.

> 등교일 판정은 학교가 NEIS 학사일정에 등록한 주말·공휴일·방학·휴업일을
> 기준으로 합니다. 학교별 입력 방식이나 갱신 시점에 따라 실제 일정과 차이가
> 날 수 있으므로, 중요한 기상·등교 자동화에서는 학교 공지도 함께 확인하세요.

## 음성 안내와 자동화

급식, 시간표와 학사일정 센서는 스마트 스피커에서 바로 사용할 수 있는 TTS
문장을 제공합니다. 급식 문장에서는 알레르기 번호와 장식 문자를 정리하고,
누락된 시간표 항목은 읽지 않습니다.

다음 예제는 Home Assistant 자동화의 **YAML로 편집** 화면에 붙여 넣은 뒤 센서,
TTS 엔진과 스피커 엔티티 ID만 바꾸어 사용할 수 있습니다.

- [매일 급식 메뉴 안내](docs/automation-examples.md#급식-메뉴-안내)
- [오늘 시간표 안내](docs/automation-examples.md#오늘-시간표-안내)
- [급식·학사일정·시간표 아침 브리핑](docs/automation-examples.md#아침-학교생활-브리핑)

## 문제 해결

- 데이터가 `unavailable`이면 인터넷 연결과 NEIS 인증키를 확인합니다.
- 인증키가 만료되거나 제한되면 Home Assistant가 **재인증 필요**를 표시합니다.
  새 인증키를 입력하거나 제한 모드 사용을 확인하세요.
- 학교나 반을 찾을 수 없으면 학교 이름, 교육청, 학년과 반을 다시 확인합니다.
  새 학년도 자료가 아직 공개되지 않은 경우도 있습니다.
- 재시작 후 통합 구성요소가 검색되지 않으면 Home Assistant 화면을 새로 고치거나
  브라우저 캐시를 지운 뒤 다시 검색합니다.
- 문제가 계속되면 **설정 → 기기 및 서비스 → 홈어시스턴트 나이스 학교생활
  → 점 3개 메뉴 → 진단 정보 다운로드**에서 진단 파일을 저장합니다.
- [GitHub Issues](https://github.com/mahlernim/ha-neis-school/issues)에 Home
  Assistant 버전, 통합 구성요소 버전, 증상과 진단 파일을 첨부합니다.
  한국어와 영어 모두 사용할 수 있습니다.

진단 정보에서는 인증키, 학교 코드·이름, 홈페이지와 주소를 자동으로 가립니다.

### 업데이트

HACS에서 업데이트한 뒤 Home Assistant를 다시 시작하세요. 0.1.4에서는 기존
설정과 엔티티 ID를 유지하며, 이전 버전의 캐시는 첫 실행 때 새로 조회합니다.
이때 NEIS 연결이 실패하면 처음 데이터를 표시하기까지 시간이 걸릴 수 있습니다.

## 개인정보 보호

이 통합 구성요소는 공개 NEIS 데이터만 사용합니다. 학생 이름, 출결, 성적,
생활기록부, 담임교사, 숙제와 가정통신문에는 접근하지 않습니다. NEIS 인증키는
엔티티 상태, 로그와 다운로드 진단 정보에 노출하지 않습니다.

## English

NEIS School is an unofficial Home Assistant integration for Korea's public
education data. It provides school search, meals, schooldays, academic events,
class timetables, TTS-ready text, and an optional read-only calendar.

### Requirements and installation

Home Assistant 2025.12.0 or newer, internet access to NEIS, and an elementary,
middle, high, or special school in Korea with published NEIS records are required.
A [free NEIS API key](https://open.neis.go.kr/portal/guide/actKeyPage.do) is recommended.

1. Open the repository using the HACS button above. If it is not found, add
   `https://github.com/mahlernim/ha-neis-school` under HACS **Custom repositories**
   with type **Integration**.
2. Download NEIS School and restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration** and select
   **NEIS School**, or use the Add integration button above. The button starts
   setup; it does not download the integration.

For manual installation, copy `custom_components/neis_school` into your Home
Assistant configuration's `custom_components` directory, then restart and add
the integration.

### First setup and everyday use

1. Enter an API key or acknowledge the limitations of using no key.
2. Choose an education office and search for the school's Korean name. Check the
   name and address. If results are incomplete, use a more specific name.
3. Select the grade and class for the academic year shown. January and February
   belong to the previous calendar year's academic year. Limited mode requires
   entering the class name manually.
4. Check the final school, address, academic year, grade, class, and connection-mode
   summary, then select meals. Lunch is selected by default.

You can correct a rejected key without restarting setup. Non-secret inputs are
retained after errors. If class lookup fails, submit the same grade to retry or
change the grade to load another list. New academic-year records may not be
published yet.

Each school/grade/class profile becomes a device; different classes can have
separate entries. Use **Configure** to change grade, class, or meals and
**Reconfigure** to change the API key or switch to limited mode. The read-only
academic calendar starts disabled; enable it from the entity list if needed.

Meals expose `available` or `no_meal`, timetables report the number of valid
lessons, schedules expose `scheduled` or `none`, and schoolday binary sensors use
`on` or `off`. Check actual entity IDs in **Developer tools → States** before
creating automations. The `menu_tts`, `timetable_tts`, and `schedule_tts` attributes
provide Korean announcement text; [automation examples](docs/automation-examples.md)
are available in Korean.

### Data availability and privacy

Without a key, NEIS may return incomplete samples. Affected entities become
`unavailable`; the calendar, upcoming events, and next schoolday require a key.
With a key, the integration caches seven days of meals and timetables and 90 days
of schedules, refreshes twice daily, and switches to the next cached date at
midnight. Temporary failures trigger retries while retaining complete cached data
for the current profile.

Schoolday estimates depend on published school schedules and may differ from
actual attendance days. Check school notices for important wake-up or attendance
automations.

Only public NEIS data is used. The integration cannot access student names,
attendance records, grades, teachers, homework, or private school notices. API keys
are excluded from entity states, logs, and diagnostics. Downloaded diagnostics
also redact school identifiers, names, websites, and addresses.

### Updates and support

Update through HACS, then restart Home Assistant. Version 0.1.4 preserves existing
settings and entity IDs but fetches fresh data instead of restoring older cache
files on the first startup. A NEIS outage can delay this first successful load.

For `unavailable` data, check the NEIS connection and API key. Follow Home
Assistant's reauthentication prompt when a key is rejected. If the integration is
missing after installation and restart, refresh the browser or clear its cache.

Report persistent problems in [GitHub Issues](https://github.com/mahlernim/ha-neis-school/issues)
in Korean or English. Include both Home Assistant and integration versions,
reproduction steps, and a diagnostic download from the integration's three-dot
menu. Never include your API key. See the [changelog](CHANGELOG.md) for release history.

## 라이선스

[MIT License](LICENSE)
