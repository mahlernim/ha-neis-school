"""Constants for the NEIS School integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "neis_school"

CONF_API_KEY: Final = "api_key"
CONF_OFFICE_CODE: Final = "office_code"
CONF_SCHOOL_CODE: Final = "school_code"
CONF_SCHOOL_NAME: Final = "school_name"
CONF_SCHOOL_KIND: Final = "school_kind"
CONF_SCHOOL_HOMEPAGE: Final = "school_homepage"
CONF_GRADE: Final = "grade"
CONF_CLASS_NAME: Final = "class_name"
CONF_MEAL_TYPES: Final = "meal_types"
CONF_LIMITED_ACK: Final = "limited_ack"

MEAL_BREAKFAST: Final = "1"
MEAL_LUNCH: Final = "2"
MEAL_DINNER: Final = "3"
MEAL_TYPES: Final = (MEAL_BREAKFAST, MEAL_LUNCH, MEAL_DINNER)
DEFAULT_MEAL_TYPES: Final = [MEAL_LUNCH]

UPDATE_INTERVAL: Final = timedelta(hours=3)
SCHEDULE_LOOKAHEAD_DAYS: Final = 90
REQUEST_TIMEOUT_SECONDS: Final = 10
PAGE_SIZE: Final = 1000
MAX_PAGES: Final = 100

ISSUE_INCOMPLETE_DATA: Final = "incomplete_data"

SCHOOL_KIND_ENDPOINTS: Final = {
    "초등학교": "elsTimetable",
    "중학교": "misTimetable",
    "고등학교": "hisTimetable",
    "특수학교": "spsTimetable",
}

OFFICES: Final = {
    "B10": "서울특별시교육청",
    "C10": "부산광역시교육청",
    "D10": "대구광역시교육청",
    "E10": "인천광역시교육청",
    "F10": "광주광역시교육청",
    "G10": "대전광역시교육청",
    "H10": "울산광역시교육청",
    "I10": "세종특별자치시교육청",
    "J10": "경기도교육청",
    "K10": "강원특별자치도교육청",
    "M10": "충청북도교육청",
    "N10": "충청남도교육청",
    "P10": "전북특별자치도교육청",
    "Q10": "전라남도교육청",
    "R10": "경상북도교육청",
    "S10": "경상남도교육청",
    "T10": "제주특별자치도교육청",
}

GRADE_EVENT_FIELDS: Final = {
    1: "ONE_GRADE_EVENT_YN",
    2: "TW_GRADE_EVENT_YN",
    3: "THREE_GRADE_EVENT_YN",
    4: "FR_GRADE_EVENT_YN",
    5: "FIV_GRADE_EVENT_YN",
    6: "SIX_GRADE_EVENT_YN",
}
