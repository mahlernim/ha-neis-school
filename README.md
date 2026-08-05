# 홈어시스턴트 나이스 학교생활

[English](#english)

NEIS 교육정보 개방 포털의 공개 데이터를 Home Assistant에 연결하는 비공식 HACS 통합 구성요소입니다. 전국 초등학교, 중학교, 고등학교와 특수학교의 급식, 학사일정, 등교일과 반별 시간표를 제공합니다.

## 주요 기능

- 학교명 검색과 학교급 자동 판별
- 학년과 반 확인
- 선택한 조식·중식·석식의 오늘·내일 센서
- 메뉴, TTS, 열량, 영양성분, 알레르기, 원산지와 급식 인원
- 오늘과 내일의 등교일 binary sensor
- 오늘 일정, 다음 학교행사와 다음 등교일
- 오늘과 내일의 교시별 시간표
- 학년별로 필터링한 읽기 전용 Home Assistant 캘린더
- 한국어와 영어 UI

## 인증키와 제한 모드

인증키 없이도 학교정보와 하루 급식처럼 결과가 적은 기본 조회는 동작할 수 있습니다. 그러나 인증키가 없는 NEIS 요청은 첫 5건의 샘플만 반환하고 `pIndex`와 `pSize`도 무시할 수 있습니다.

실제 확인 사례는 다음과 같습니다.

| 조회 | 인증키 없음 | 인증키 있음 |
|---|---:|---:|
| 6학년 반정보 | 총 6건 중 5건 | 6건 |
| 6교시 시간표 | 1~5교시 | 1~6교시 |
| 한 달 학사일정 | 총 30건 중 5건 | 30건 |

통합 구성요소는 전체 건수보다 적은 행이 반환되면 해당 데이터를 `unavailable`로 처리하고 Home Assistant 수리 알림을 표시합니다. 월간 캘린더와 다음 일정 기능은 완전성을 보장하기 위해 인증키가 필요합니다.

인증키는 무료입니다.

1. [NEIS 인증키 신청](https://open.neis.go.kr/portal/guide/actKeyPage.do)에 접속합니다.
2. Google, 네이버 또는 다음 계정으로 로그인합니다.
3. 인증키를 신청합니다.
4. 마이페이지의 인증키 발급 내역에서 키를 확인합니다.

[NEIS 개발자 가이드](https://open.neis.go.kr/portal/guide/apiGuidePage.do)

## 설치

### HACS 사용자 저장소

1. HACS에서 사용자 지정 저장소를 엽니다.
2. `https://github.com/mahlernim/ha-neis-school`을 통합 구성요소 유형으로 추가합니다.
3. **홈어시스턴트 나이스 학교생활**을 설치합니다.
4. Home Assistant를 다시 시작합니다.
5. 설정 → 기기 및 서비스 → 통합 구성요소 추가에서 **NEIS School**을 선택합니다.

최소 지원 버전은 Home Assistant 2025.12.0입니다.

## 설정

1. 인증키를 입력하거나 제한 모드 안내를 확인합니다.
2. 시도교육청과 학교명을 입력합니다.
3. 검색 결과에서 학교를 선택합니다.
4. 학년과 반을 선택합니다.
5. 사용할 급식 유형을 선택합니다. 기본값은 중식입니다.

인증키, 학년, 반과 급식 유형은 통합 구성요소의 **구성** 메뉴에서 변경할 수 있습니다. 학교 하나는 한 번만 등록할 수 있으며 다른 학교는 통합 구성요소를 다시 추가하면 됩니다.

## 주요 엔티티

엔티티 ID는 Home Assistant 언어와 학교명에 따라 생성됩니다.

- `binary_sensor` 오늘 등교일, 내일 등교일
- `sensor` 식사별 오늘·내일 급식
- `sensor` 오늘 학사일정, 다음 학교행사, 다음 등교일
- `sensor` 오늘 시간표, 내일 시간표
- `calendar` 학사일정
- 기본 비활성 진단 센서 API 모드, 마지막 정상 갱신

급식과 시간표의 긴 내용은 센서 속성에서 확인할 수 있습니다. API 오류는 학교를 쉬는 날로 오인하지 않도록 `off` 대신 `unavailable`로 표시합니다.

## 개인정보와 보안

이 통합 구성요소는 공개 NEIS 데이터만 사용합니다. 학생 이름, 출결, 성적, 생활기록부, 담임교사, 숙제와 가정통신문에는 접근하지 않습니다.

API 키는 로그, 엔티티 속성, 진단 다운로드와 고유 ID에 포함하지 않습니다. 개발용 `env.txt`, `.env`와 `*.key` 파일은 Git에서 제외됩니다.

## 기존 HA 급식알리미와의 관계

이 프로젝트는 [HA 급식알리미](https://github.com/mahlernim/ha-geupshik-allimi)의 경험을 바탕으로 새 도메인과 데이터 모델로 다시 설계했습니다. 자동 마이그레이션은 제공하지 않으며 두 통합 구성요소를 병행 설치해 자동화를 하나씩 전환할 수 있습니다.

## English

NEIS School is an unofficial Home Assistant integration for Korea's public NEIS education data. It supports school search, breakfast/lunch/dinner, nutrition, schooldays, academic schedules, class timetables, and a read-only calendar for elementary, middle, high, and special schools.

An API key is optional for basic testing. Without a key, NEIS may return only the first five sample rows and ignore pagination. Incomplete responses are not exposed as valid automation data. Request a free key from the [NEIS key page](https://open.neis.go.kr/portal/guide/actKeyPage.do) for complete operation.

Install this repository as a HACS custom integration, restart Home Assistant, and add **NEIS School** from Settings → Devices & services. Home Assistant 2025.12.0 or newer is required.

This integration only accesses public school data and never accesses personal student records.

## License

MIT
