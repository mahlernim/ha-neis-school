# Changelog

## 0.1.0-beta.2

### Added

- Add complete Korean and English setup, options, entity, and error text.
- Add TTS-ready text for today's academic schedule.
- Add privacy-safe downloadable diagnostics with NEIS response and refresh
  details for troubleshooting.

### Changed

- Present grades as a dropdown with the correct range for each school type.
- Keep the read-only academic calendar available but disabled by default.
- Improve meal and timetable announcements, including natural no-meal text and
  cleaner handling of incomplete timetable rows.
- Require confirmation before switching to limited mode and require at least
  one meal type.

### Fixed

- Detect incomplete or inconsistent NEIS responses instead of treating partial
  data as complete.
- Use the Home Assistant local date when determining the Korean academic year.
- Add the repository metadata and brand assets required for HACS distribution.

## 0.1.0-beta.1

- Initial beta release.
- Add user-friendly school search, grade and class validation.
- Add optional API key and safe limited-mode handling.
- Add meal, nutrition, schoolday, schedule, timetable, calendar, and diagnostics entities.
- Add Korean and English translations.
