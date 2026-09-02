from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from generate_commit_activity import collect_commits

OUTPUT = Path("assets/streak-card.svg")
README = Path("README.md")
WEEKS = 52
BRAZIL_TZ = timezone(timedelta(hours=-3))


def format_day(value: date | None) -> str:
    if value is None:
        return "No active streak"
    return value.strftime("%b %d, %Y")


def streak_from_end(active_days: set[date], today: date) -> tuple[int, date | None, date | None]:
    if today in active_days:
        end = today
    elif today - timedelta(days=1) in active_days:
        end = today - timedelta(days=1)
    else:
        return 0, None, None

    start = end
    while start - timedelta(days=1) in active_days:
        start -= timedelta(days=1)

    return (end - start).days + 1, start, end


def longest_streak(active_days: set[date]) -> tuple[int, date | None, date | None]:
    if not active_days:
        return 0, None, None

    ordered = sorted(active_days)
    best_count = 1
    best_start = ordered[0]
    best_end = ordered[0]

    current_start = ordered[0]
    current_end = ordered[0]
    current_count = 1

    for value in ordered[1:]:
        if value == current_end + timedelta(days=1):
            current_end = value
            current_count += 1
        else:
            current_start = value
            current_end = value
            current_count = 1

        if current_count > best_count:
            best_count = current_count
            best_start = current_start
            best_end = current_end

    return best_count, best_start, best_end


def render_svg(total: int, current: tuple[int, date | None, date | None], longest: tuple[int, date | None, date | None]) -> str:
    current_count, current_start, current_end = current
    longest_count, longest_start, longest_end = longest

    current_range = (
        f"{format_day(current_start)} - {format_day(current_end)}"
        if current_count > 0
        else "No active streak"
    )
    longest_range = (
        f"{format_day(longest_start)} - {format_day(longest_end)}"
        if longest_count > 0
        else "No streak yet"
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="760" height="210" viewBox="0 0 760 210" role="img" aria-label="Public commit streak">
  <style>
    .big {{ font: 700 28px -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; fill: #ff3d8d; }}
    .big-current {{ font: 700 28px -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; fill: #f2cc60; }}
    .label {{ font: 500 14px -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; fill: #ff3d8d; }}
    .label-current {{ font: 600 14px -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; fill: #f2cc60; }}
    .date {{ font: 500 11px -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; fill: #79c0ff; }}
    .hint {{ font: 400 10px -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; fill: #8b949e; }}
  </style>

  <rect x="1" y="1" width="758" height="208" rx="12" fill="#13111f" stroke="#30363d" />
  <line x1="253" y1="30" x2="253" y2="178" stroke="#8b949e" stroke-width="1" opacity="0.65" />
  <line x1="507" y1="30" x2="507" y2="178" stroke="#8b949e" stroke-width="1" opacity="0.65" />

  <text x="126" y="79" text-anchor="middle" class="big">{total}</text>
  <text x="126" y="114" text-anchor="middle" class="label">Total Public Commits</text>
  <text x="126" y="145" text-anchor="middle" class="date">Last 52 weeks</text>

  <circle cx="380" cy="75" r="42" fill="none" stroke="#ff3d8d" stroke-width="5" />
  <path d="M380 24 C373 32 373 39 380 43 C387 39 387 32 380 24" fill="#ff3d8d" />
  <text x="380" y="84" text-anchor="middle" class="big-current">{current_count}</text>
  <text x="380" y="124" text-anchor="middle" class="label-current">Current Streak</text>
  <text x="380" y="148" text-anchor="middle" class="date">{current_range}</text>

  <text x="634" y="79" text-anchor="middle" class="big">{longest_count}</text>
  <text x="634" y="114" text-anchor="middle" class="label">Longest Streak</text>
  <text x="634" y="145" text-anchor="middle" class="date">{longest_range}</text>

  <text x="380" y="194" text-anchor="middle" class="hint">Calculated from commits authored by @IranRibeiro55 in public repositories owned by this account</text>
</svg>
'''


def patch_readme() -> bool:
    if not README.exists():
        return False

    original = README.read_text(encoding="utf-8")
    if "<!-- streak-card:start -->" in original:
        return False

    profile_src = 'src="./profile-summary-card-output/github_dark/0-profile-details.svg"'
    profile_pos = original.find(profile_src)
    if profile_pos == -1:
        raise RuntimeError("Profile details card was not found in README")

    paragraph_end = original.find("</p>", profile_pos)
    if paragraph_end == -1:
        raise RuntimeError("Could not find closing paragraph for profile details card")
    paragraph_end += len("</p>")

    block = '''

<!-- streak-card:start -->

<p align="center">
  <img
    src="./assets/streak-card.svg"
    width="72%"
    alt="Public Commit Streak"
  />
</p>

<!-- streak-card:end -->'''

    updated = original[:paragraph_end] + block + original[paragraph_end:]
    README.write_text(updated, encoding="utf-8")
    return True


def main() -> None:
    today = datetime.now(BRAZIL_TZ).date()
    since_day = today - timedelta(weeks=WEEKS)
    since = datetime.combine(since_day, datetime.min.time(), tzinfo=BRAZIL_TZ).astimezone(timezone.utc)

    commits = collect_commits(since)
    active_days = {timestamp.astimezone(BRAZIL_TZ).date() for timestamp in commits}

    current = streak_from_end(active_days, today)
    longest = longest_streak(active_days)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render_svg(len(commits), current, longest), encoding="utf-8")
    patch_readme()

    print(
        f"Generated {OUTPUT}: {len(commits)} public commits, "
        f"current streak {current[0]} day(s), longest streak {longest[0]} day(s)"
    )


if __name__ == "__main__":
    main()
