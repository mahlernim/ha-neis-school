# NEIS School 자동화 예제

이 문서의 YAML은 Home Assistant 자동화 편집기에서 바로 붙여 넣을 수 있습니다.

1. **설정 → 자동화 및 장면 → 자동화 만들기 → 새 자동화 만들기**를 엽니다.
2. 오른쪽 위 점 3개 메뉴에서 **YAML로 편집**을 선택합니다.
3. 원하는 예제를 붙여 넣습니다.
4. 아래 예제의 세 엔티티 ID를 자신의 환경에 맞게 바꿉니다.
   - `sensor.my_school_lunch_today` 같은 NEIS School 센서
   - `tts.home_assistant_cloud` 같은 TTS 엔진
   - `media_player.living_room` 같은 스피커

실제 NEIS School 엔티티 ID는 **개발자 도구 → 상태**에서 확인할 수 있습니다.
먼저 스피커 볼륨을 낮게 설정하고 수동 실행으로 문장을 확인하는 것을 권장합니다.

## 급식 메뉴 안내

매일 오전 7시에 오늘 중식이 있으면 정리된 `menu_tts` 문장을 읽습니다.

```yaml
alias: 학교 중식 안내
description: 오늘 중식 메뉴를 매일 아침 스피커로 안내합니다.
triggers:
  - trigger: time
    at: "07:00:00"
conditions:
  - condition: template
    value_template: >-
      {{ state_attr('sensor.my_school_lunch_today', 'menu_tts')
         | default('', true) | trim != '' }}
actions:
  - action: tts.speak
    target:
      entity_id: tts.home_assistant_cloud
    data:
      media_player_entity_id: media_player.living_room
      message: >-
        {{ state_attr('sensor.my_school_lunch_today', 'menu_tts') }}
      cache: true
mode: single
```

## 오늘 시간표 안내

평일 오전 7시 5분에 유효한 시간표가 있을 때만 `timetable_tts`를 읽습니다.
과목이나 교시 정보가 불완전한 항목은 안내에서 제외됩니다.

```yaml
alias: 오늘 시간표 안내
description: 평일 아침 오늘 시간표를 스피커로 안내합니다.
triggers:
  - trigger: time
    at: "07:05:00"
conditions:
  - condition: time
    weekday:
      - mon
      - tue
      - wed
      - thu
      - fri
  - condition: template
    value_template: >-
      {{ state_attr('sensor.my_school_timetable_today', 'timetable_tts')
         | default('', true) | trim != '' }}
actions:
  - action: tts.speak
    target:
      entity_id: tts.home_assistant_cloud
    data:
      media_player_entity_id: media_player.living_room
      message: >-
        {{ state_attr('sensor.my_school_timetable_today', 'timetable_tts') }}
      cache: true
mode: single
```

## 아침 학교생활 브리핑

급식, 학사일정과 시간표 중 실제 문장이 있는 항목만 이어 붙여 한 번에 읽습니다.
센서 값이 없거나 `unavailable`인 항목은 자연스럽게 건너뜁니다.

```yaml
alias: 아침 학교생활 브리핑
description: 오늘 급식, 학사일정과 시간표를 한 번에 안내합니다.
triggers:
  - trigger: time
    at: "07:00:00"
conditions:
  - condition: template
    value_template: >-
      {% set values = [
        state_attr('sensor.my_school_lunch_today', 'menu_tts'),
        state_attr('sensor.my_school_schedule_today', 'schedule_tts'),
        state_attr('sensor.my_school_timetable_today', 'timetable_tts')
      ] %}
      {{ values | select('string') | map('trim') | reject('equalto', '')
         | list | count > 0 }}
actions:
  - variables:
      briefing: >-
        {% set values = [
          state_attr('sensor.my_school_lunch_today', 'menu_tts'),
          state_attr('sensor.my_school_schedule_today', 'schedule_tts'),
          state_attr('sensor.my_school_timetable_today', 'timetable_tts')
        ] %}
        {{ values | select('string') | map('trim') | reject('equalto', '')
           | join(' ') }}
  - action: tts.speak
    target:
      entity_id: tts.home_assistant_cloud
    data:
      media_player_entity_id: media_player.living_room
      message: "{{ briefing }}"
      cache: true
mode: single
```

## 다른 TTS 서비스를 사용할 때

위 예제는 현재 Home Assistant의 `tts.speak` 액션 형식을 사용합니다. 사용 중인
TTS 통합 구성요소가 별도의 액션 형식을 제공한다면 `actions` 부분만 해당 서비스의
개발자 도구 예제로 바꾸고 `message` 템플릿은 그대로 사용할 수 있습니다.
