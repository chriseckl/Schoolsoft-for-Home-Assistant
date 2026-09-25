# SchoolSoft for Home Assistant

An unofficial Home Assistant custom integration for a child's SchoolSoft timetable and guardian attendance notices.

It signs in as a **guardian** (`usertype=2`) and reads the authenticated weekly timetable page. This is important because SchoolSoft's calendar REST endpoint may reject guardian sessions.

> This project is independent of SchoolSoft and Home Assistant. It has been tested with the Robertsfors SchoolSoft site; different schools may render their timetable differently.

## What it provides

- A calendar entity, for example `calendar.student_school`
- Current and next lesson sensors
- A `current_lesson_attendance` sensor with `absent`, `late`, or `none`
- Today's school start and end time sensors
- Attendance sensors: absence, late arrival, left/out early, and other school activity
- Per-lesson labels in the calendar:
  - `[ABSENT]` for absence
  - `[LATE]` for late arrival
- Automatic refresh every 30 minutes and automatic guardian re-login when a session expires
- Overlapping lessons are retained in the calendar

The text labels deliberately avoid coloured emoji, which are not rendered consistently in Home Assistant on older Android/Fire tablet WebViews.

## Current scope: one child

Each integration entry currently represents one child. This keeps the timetable, current/next lesson sensors, and attendance labels unambiguous on a dashboard.

Support for multiple siblings can be added in a future release by creating separate child selections and separate calendar/sensor entities for each sibling. The current integration does not yet provide that selection flow, so parents with several children should add this as a feature request rather than expecting one entry to merge their schedules.

## Installation

### HACS

1. In HACS, open **Integrations**.
2. Open the three-dot menu and choose **Custom repositories**.
3. Add `https://github.com/chriseckl/Schoolsoft-for-Home-Assistant` as an **Integration** repository.
4. Search for **SchoolSoft**, install it, then restart Home Assistant.

### Manual installation

1. Copy the `custom_components/schoolsoft` directory from this repository into your Home Assistant configuration directory:

   ```text
   /config/custom_components/schoolsoft
   ```

2. Restart Home Assistant.

## Configuration

1. In Home Assistant, open **Settings** → **Devices & services** → **Add integration**.
2. Search for **SchoolSoft**.
3. Enter:
   - Your child's name, used to name the calendar
   - Your SchoolSoft URL, for example `https://sms.schoolsoft.se/robertsfors`
   - Your guardian username and password
4. Submit the form. The integration verifies the guardian login before creating the entry.

Home Assistant stores the configuration entry, including credentials, in its normal local configuration storage. Do not commit your Home Assistant configuration, backups, browser cookies, or `.storage` directory to a public repository.

## Add the timetable to a dashboard

Add a **Calendar** card and select the SchoolSoft calendar. For a day view, use this YAML:

```yaml
type: calendar
initial_view: day
entities:
  - calendar.student_school
```

The actual entity ID is based on the student name entered during setup.

You can also add the current and next lesson sensors to an Entities card:

```yaml
type: entities
entities:
  - sensor.current_lesson
  - sensor.next_lesson
  - sensor.school_start
  - sensor.school_end
```

## Telegram alert for the current lesson

Set up the official **Telegram bot** integration in Home Assistant first. A send-only **Broadcast** bot is sufficient and does not require exposing Home Assistant to the internet. Follow Home Assistant's [Telegram bot setup guide](https://www.home-assistant.io/integrations/telegram_bot/), create a bot with `@BotFather`, start a chat with it, and add your Telegram chat ID to the integration's allowed chat IDs.

Then create an automation in **Settings** → **Automations & scenes**. In YAML mode, use the following and replace `notify.telegram_bot_your_chat` with the notify entity created for your allowed chat ID:

```yaml
alias: SchoolSoft – current lesson attendance
description: Notify once when the current SchoolSoft lesson is marked absent or late.
triggers:
  - trigger: state
    entity_id: sensor.current_lesson_attendance
conditions:
  - condition: template
    value_template: "{{ trigger.to_state.state in ['absent', 'late'] }}"
actions:
  - action: notify.send_message
    data:
      entity_id: notify.telegram_bot_your_chat
      message: >-
        SchoolSoft: {{ states('sensor.current_lesson') }} is marked
        {{ trigger.to_state.state }}.
mode: single
```

SchoolSoft reports attendance asynchronously and this integration refreshes every 30 minutes, so an alert can arrive up to one refresh interval after a teacher records it.

## Privacy and security

- This integration uses your guardian account only to retrieve your child's timetable and attendance notices.
- It does not read or import browser cookies or saved SchoolSoft sessions.
- It never sends SchoolSoft data to any service other than your configured SchoolSoft site.
- Treat Home Assistant backups and `.storage` as sensitive: they can contain integration credentials.

## Troubleshooting

**The integration says it cannot connect**

Confirm the SchoolSoft URL includes your school's path, such as `/robertsfors`, and that Home Assistant has internet access.

**The calendar is empty or lesson titles look wrong**

SchoolSoft installations can use different timetable HTML. Please open an issue with the school URL (do not share credentials, cookies, pupil names, or timetable screenshots containing personal data).

**Attendance labels do not appear**

SchoolSoft only displays labels when it has an individual attendance notice linked to a lesson. The integration recognizes `Absent`/`Frånvaro` and `Sen ankomst` (late arrival).

## Development

The component intentionally uses Home Assistant's built-in `aiohttp` client and Python's standard HTML parser, with no additional runtime dependencies.
