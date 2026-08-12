# Changelog

## 0.1.2

### Changed

- Reduce routine NEIS traffic to three rolling requests twice per day instead
  of repeatedly requesting each today/tomorrow dataset.
- Persist date-indexed meals, timetables, and schedules so midnight rollover
  does not depend on an immediate network request.
- Retry temporary failures after increasing delays and retain complete cached
  datasets when only one NEIS endpoint fails.

### Fixed

- Keep valid no-data responses distinct from connection failures and expose
  cache use in downloadable diagnostics.

## 0.1.1

### Fixed

- Normalize school homepage addresses used in device metadata so integration
  setup remains reliable when upstream URL data omits a scheme.

## 0.1.0

First stable release of NEIS School for Home Assistant.

### Changed

- Count only valid timetable lessons in the sensor state so empty vacation-day
  rows report `0` consistently with their attributes and TTS text.
- Make the copy-ready TTS automations run only on schooldays and skip missing
  meals.
- Clarify limited-mode setup, sensor states, and browser-cache troubleshooting.
- Provide Korean-first GitHub issue forms.

## 0.1.0-beta.3

### Added

- Add reauthentication and proactive API-key reconfiguration.
- Add scheduled and manually dispatched compatibility validation.

### Changed

- Allow separate profiles for different grades or classes at the same school.
- Keep empty but complete timetable responses available with a status attribute.
- Cache calendar range requests and reuse the coordinator's schedule data.
- Store credentials in config entry data and keep student preferences in options.
- Use only the currently supported HACS manifest keys.

### Fixed

- Preserve existing entity and device registry customizations while migrating to
  entry-scoped identifiers.
- Mark entities unavailable when NEIS refreshes fail instead of silently reporting
  stale data as a successful update.
- Remove entry-scoped repair issues when the integration unloads.

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
