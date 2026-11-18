# MyFAP API CLI

**English** | [Tiếng Việt](./README.vi.md)

## Introduction

An unofficial CLI that talks to the internal APIs of the myFAP mobile app to check class schedules, exam dates, grades (the family disappointment edition), and student profile info.

## Disclaimer

- **Unofficial tool:** This is an independent project built for personal and educational use. It is not affiliated with, authorized, maintained, or endorsed by FPT University (FPTU) or the official myFAP development team.
- **Use at your own risk:** This software is provided "as is", without warranty of any kind. The author is not responsible for any account issues, inaccurate data, service disruptions, or other damages resulting from using this CLI. Always double-check important academic records such as exam schedules, final grades, and tuition fees on the official FAP portal or the official myFAP app.
- **Warnings on internal APIs and session security:**
  - **Reverse-engineered internal APIs:** This tool relies on undocumented internal endpoints extracted from the myFAP Android client. Upstream changes can break functionality, alter responses, or block requests at any time without notice.
  - **Plaintext local session:** After logging in, your OAuth tokens and `authen_key` are stored in plaintext JSON at `~/.myfap-api-cli/session.json` (or the path passed to `--config`). Never share this file or commit exported `.json`/`.ics` student data to public repositories. Run `myfap logout` when finished on shared machines.
  - **Responsible usage:** Avoid automated high-frequency polling or scraping that puts unnecessary load on upstream servers.

## Key Features
- Cross-platform support (Windows, macOS, Linux)
- Log in via FEID or Google OAuth
- View class schedules (weekly or full semester)
- View grades (per subject or full semester)
- Check attendance (per subject or full semester)
- Check submitted student applications
- Read campus news and announcements
- View student profile and Student Services (DVSV) info
- Export semester class schedules and exam schedules to **ICS** for Google Calendar or other calendar apps
- And more...

## Usage

- Install the CLI:

  ```sh
  pip install myfap
  ```

- List available campuses:

  ```sh
  myfap campuses
  ```

- Log in to the myFAP API via FEID:

  ```sh
  myfap login --campus HN
  ```

  After logging in, your session is saved at `~/.myfap-api-cli/session.json`.

- Log in for the Xavalo (HCM) campus:

  ```sh
  myfap login -c HCM
  ```

- Fetch your class schedule *(automatically picks the latest semester)*:

  ```sh
  myfap schedule
  ```

## Command Reference

| Command | Description |
|:--|:--|
| `version` | Show the CLI version |
| `doctor` | Check local configuration; add `--online` to test the v2 bootstrap connection |
| `login` | Log in or reuse an existing session; add `--force` to force re-authentication |
| `logout` | Delete the local session |
| `refresh` | Refresh tokens and session state |
| `campuses` | List campuses for the selected API version |
| `semesters` | List available semesters |
| `schedule` | View semester class schedule; use `--ics` to export an **ICS** calendar |
| `week-timetable` | View weekly or daily class timetable |
| `exams` | View exam schedule; use `--ics` to export an **ICS** file, add `--full` for extra fields |
| `courses` | List courses for a semester |
| `marks` | View semester grades, per-course details, or summary with `--summary` |
| `transcript` | View full academic transcript; `--pretty` parses the HTML table into JSON |
| `attendance` | Check attendance by semester or filter by subject and class |
| `applications` | List submitted student applications |
| `news` | Read or search campus news |
| `info student` | View student profile information |
| `info photo` | Fetch student photo data as JSON |
| `info campus` | View Student Services (DVSV) contact details |
| `other training` | View training points by semester |
| `other survey` | Check pending surveys |
| `other feedback` | Check open feedbacks |
| `other feedbacks` | List student feedbacks; v2 only |
| `other profile` | Check profile update requests |
| `other notification` | View student notifications |
| `other fee` | View tuition fees and payment status |
| `other balance` | View account balance |
| `other subjects` | List subjects; optionally filter by semester |
| `other rating list` | View rating list; v1 only |

## Environment Variables
Two environment variables are supported by default:
- `MYFAP_TIMEOUT`: override the default request timeout in seconds (default: `10`s; subject listing uses `30`s)
- `MYFAP_API_VER`: override the API version (default: `v2`)

## Notes
When `--semester` is omitted, the CLI picks the current semester from recent `startDate` values (at least one past semester needs a valid `startDate` for auto-selection to work, which holds true unless you are a freshman whose first semester has not started yet). For `week-timetable`, `--date` determines the year if `--year` is omitted.

## Options
Examples:
```sh
myfap --api-version v2 --campus HN schedule --ics
myfap schedule --ics --api-version v2 --campus HN
myfap info student --timeout 20 --stdout
```

If the same option is passed at multiple command levels, the subcommand value takes precedence. If repeated at the same level, the last value wins.

| Option | Description |
|:--|:--|
| `--help` | Show commands and options help |
| `--config <path>` | Path to a custom session config file (default: `~/.myfap-api-cli/session.json`) |
| `--timeout <seconds>` | Server request timeout in seconds; can also be set via `MYFAP_TIMEOUT` |
| `--api-version <v1 or v2>` | Select API version. Precedence: CLI option, `MYFAP_API_VER`, session version, then default `v2`. Legacy sessions without a version still default to `v1` |
| `-c, --campus <campus>` | Campus code. Precedence: CLI option then session. `APHL` is the default only for `v1`; `v2` requires choosing a campus if no compatible code is stored in the session |
| `-s, --semester <semester>` | Semester name (e.g., `Fall2026`) |
| `-cid, --courseid <id>` | Internal numeric course ID, only available on `marks` (e.g., `82934` from the semester grade table, not subject codes like `PRO192` or `SWE201c`) |
| `-w, --week <week>` | Week number, only available on `week-timetable` |
| `-y, --year <year>` | Academic year, only available on `week-timetable` |
| `-d, --date <YYYY-MM-DD>` | Specific date, only available on `week-timetable` |
| `-sc, --subjectcode <code>` | Subject code, only available on `attendance` |
| `-cn, --classname <class>` | Class name, only available on `attendance` |
| `--ics` | Export to **ICS** for easy import into Google Calendar or other calendar apps; supported on `schedule` (classes) and `exams` (exam schedule) |
| `--full` | Include all extra fields when exporting ICS on `exams` (default exports key fields: subject, exam room, and result announcement date) |
| `-p, --pretty` | Parse the raw HTML grade tables into JSON; supported on `marks` and `transcript` |
| `--output, -o <dir>` | Output directory instead of the current working directory |
| `--stdout` | Print output to stdout instead of saving a file |
| `-f, --force` | Force re-login and ignore `session.json`; only available on `login` |

## Further Documentation
*(Note: detailed documentation under `docs/` is currently written in Vietnamese.)*

- [Choosing API v1 or v2](./docs/cli/api-versions.md): `v2` is the default when no session exists; precedence rules and using `v1`
- [Usage Examples](./docs/cli/Example.md)
- [Setting up a dev environment with uv](./docs/cli/development.md)
- [CI and Artifact Checks](./docs/cli/development.md#ci-và-kiểm-tra-artifact)

## Credits
- Internal APIs reverse engineered from [myFAP Android](https://play.google.com/store/apps/details?id=com.fuct): version *2.0.6*, versionCode *31*
- [JADX](https://github.com/skylot/jadx): decompiling and unpacking the Android APK
- [Hermes decomp](https://github.com/SymbioticSec/hermes-decomp): decompiling `index.android.bundle` into readable JavaScript
- [Burp Suite Community Edition](https://portswigger.net/burp): intercepting packets and dynamic analysis of myFAP
- [Playwright](https://playwright.dev/): handles the browser OAuth login flow
- [Typer](https://typer.tiangolo.com/) & [Rich](https://rich.readthedocs.io/): CLI framework and terminal UI
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/): HTML parsing and extraction
- [ics.py](https://icspy.readthedocs.io/): generating and normalizing iCalendar files for calendar imports

## License

This project is licensed under the MIT License. See the [LICENSE](./LICENSE) file for details.
