<p align="center">
  <img src="custom_components/neis_school/brand/icon@2x.png" alt="홈어시스턴트 나이스 학교생활" width="168">
</p>

<h1 align="center">홈어시스턴트 나이스 학교생활</h1>

<p align="center">
  우리 학교의 급식, 시간표, 학사일정과 등교 정보를 Home Assistant에서 확인하고 자동화하세요.
</p>

<p align="center">
  <a href="https://github.com/mahlernim/ha-neis-school/releases"><img alt="최신 릴리스" src="https://img.shields.io/github/v/release/mahlernim/ha-neis-school"></a>
  <a href="https://github.com/mahlernim/ha-neis-school/actions/workflows/validate.yml"><img alt="검증 상태" src="https://github.com/mahlernim/ha-neis-school/actions/workflows/validate.yml/badge.svg"></a>
  <img alt="Home Assistant 2025.12 이상" src="https://img.shields.io/badge/Home%20Assistant-2025.12%2B-18BCF2?logo=home-assistant&logoColor=white">
  <img alt="HACS 통합 구성요소" src="https://img.shields.io/badge/HACS-Integration-41BDF5?logo=home-assistant-community-store&logoColor=white">
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

<p align="center"><a href="#english">English summary</a></p>

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
- NEIS 서비스에 연결할 수 있는 인터넷 환경
- 완전한 데이터 조회를 위한 무료 NEIS 인증키 사용 권장

## 설치

### HACS

1. 위의 **HACS에서 저장소 열기** 버튼을 선택합니다.
2. 아직 기본 저장소에 표시되지 않는 경우 HACS 사용자 지정 저장소로 추가합니다.
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

1. NEIS 인증키를 입력합니다.
2. 시도교육청을 선택하고 학교 이름을 검색합니다.
3. 검색 결과에서 학교를 선택합니다.
4. 학년과 반을 선택합니다.
5. 사용할 급식 유형을 선택합니다. 기본값은 중식입니다.

설정이 끝나면 선택한 학교·학년·반이 하나의 기기로 추가되고 관련 엔티티가
자동으로 생성됩니다. 같은 학교에 다니는 자녀도 학년이나 반이 다르면 각각
추가할 수 있습니다. 학년, 반과 급식 유형은 **구성**에서 변경하고, 인증키는
통합 구성요소의 **재구성**에서 교체하거나 제한 모드로 전환할 수 있습니다.

## NEIS 인증키

인증키 없이 제한 모드로 설정할 수도 있지만, NEIS가 일부 요청에서 전체 결과
대신 제한된 샘플만 반환할 수 있습니다. 이 경우 통합 구성요소는 불완전한 값을
자동화에 사용하지 않도록 관련 엔티티를 `unavailable`로 표시합니다.

안정적인 시간표, 학사일정과 캘린더 사용을 위해 무료 인증키를 권장합니다.

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
- 문제가 계속되면 **설정 → 기기 및 서비스 → 홈어시스턴트 나이스 학교생활
  → 점 3개 메뉴 → 진단 정보 다운로드**에서 진단 파일을 저장합니다.
- [GitHub Issues](https://github.com/mahlernim/ha-neis-school/issues)에 Home
  Assistant 버전, 통합 구성요소 버전, 증상과 진단 파일을 첨부합니다.

진단 정보에서는 인증키, 학교 코드·이름, 홈페이지와 주소를 자동으로 가립니다.

## 개인정보 보호

이 통합 구성요소는 공개 NEIS 데이터만 사용합니다. 학생 이름, 출결, 성적,
생활기록부, 담임교사, 숙제와 가정통신문에는 접근하지 않습니다. NEIS 인증키는
엔티티 상태, 로그와 다운로드 진단 정보에 노출하지 않습니다.

## English

NEIS School is an unofficial Home Assistant integration for Korea's public
education data. It provides school search, meals, schooldays, academic events,
class timetables, TTS-ready text, and an optional read-only calendar.

Install it with HACS, restart Home Assistant, and add **NEIS School** from
**Settings → Devices & services**. A free NEIS API key is recommended because
unauthenticated requests may return incomplete sample data. Home Assistant
2025.12.0 or newer is required.

## 라이선스

[MIT License](LICENSE)
