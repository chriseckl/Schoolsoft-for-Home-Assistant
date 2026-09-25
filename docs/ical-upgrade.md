# iCalendar upgrade design

## Goal

Use SchoolSoft's private iCalendar subscription as the authoritative timetable while retaining the authenticated guardian page for attendance notices.

## Data flow

```text
private iCalendar URL  -> lesson events -> Home Assistant calendar and lesson sensors
guardian SchoolSoft UI -> attendance links -> lesson-ID match -> [ABSENT] / [LATE] labels
```

SchoolSoft's iCalendar lesson UIDs have the form `lesson-<id>-…`. The guardian attendance links include the same `<id>` as the `lesson` query parameter. Matching those IDs avoids relying only on subject, date, and time when lessons overlap or schedules change.

## Scope

- Import timed lesson events from the iCalendar feed.
- Exclude lunch, planning, and assignment events in this first version.
- Keep the existing guardian credentials and polling cadence for attendance.
- Fall back to the legacy weekly-page timetable when the optional feed URL is empty.

## Migration and rollback

Enter the private URL through the integration's **Configure** dialog, then reload the integration. Clearing the URL returns to the weekly-page timetable. Never store a private feed URL in YAML, source control, screenshots, or support requests.

## Acceptance checks

1. The calendar includes upcoming lessons from the feed, including concurrent events.
2. Current and next lesson sensors reflect the feed.
3. A guardian attendance notice produces the label on the matching lesson ID.
4. Clearing the option restores the weekly-page fallback.
