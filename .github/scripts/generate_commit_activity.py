from __future__ import annotations

import html
import json
import os
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

USERNAME = "IranRibeiro55"
API_URL = "https://api.github.com"
OUTPUT = Path("assets/commit-activity.svg")
README = Path("README.md")
WEEKS = 52


def github_get(path: str, params: dict[str, str | int] | None = None):
    url = f"{API_URL}{path}"
    if params:
        url = f"{url}?{urlencode(params)}"

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": f"{USERNAME}-profile-metrics",
    }

    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        # Empty repositories return 409 on the commits endpoint.
        if exc.code == 409:
            return []
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API request failed ({exc.code}) for {url}: {body}") from exc


def list_public_repositories() -> list[dict]:
    repositories: list[dict] = []
    page = 1

    while True:
        batch = github_get(
            f"/users/{USERNAME}/repos",
            {
                "type": "owner",
                "sort": "updated",
                "direction": "desc",
                "per_page": 100,
                "page": page,
            },
        )
        if not isinstance(batch, list):
            raise RuntimeError("Unexpected response while listing public repositories")

        repositories.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    return repositories


def collect_commits(since: datetime) -> list[datetime]:
    commit_dates: list[datetime] = []
    seen_shas: set[str] = set()
    since_iso = since.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    for repository in list_public_repositories():
        full_name = repository.get("full_name")
        if not full_name:
            continue

        page = 1
        while True:
            commits = github_get(
                f"/repos/{full_name}/commits",
                {
                    "author": USERNAME,
                    "since": since_iso,
                    "per_page": 100,
                    "page": page,
                },
            )
            if not isinstance(commits, list):
                raise RuntimeError(f"Unexpected commits response for {full_name}")

            for item in commits:
                sha = item.get("sha")
                if not sha or sha in seen_shas:
                    continue
                seen_shas.add(sha)

                commit = item.get("commit", {})
                author = commit.get("author") or {}
                committer = commit.get("committer") or {}
                raw_date = author.get("date") or committer.get("date")
                if not raw_date:
                    continue

                commit_dates.append(datetime.fromisoformat(raw_date.replace("Z", "+00:00")))

            if len(commits) < 100:
                break
            page += 1

    return commit_dates


def week_buckets(commit_dates: list[datetime], today: date) -> tuple[date, list[int], Counter[date]]:
    this_monday = today - timedelta(days=today.weekday())
    first_monday = this_monday - timedelta(weeks=WEEKS - 1)
    counts = [0] * WEEKS
    per_day: Counter[date] = Counter()

    for timestamp in commit_dates:
        commit_day = timestamp.date()
        per_day[commit_day] += 1
        index = (commit_day - first_monday).days // 7
        if 0 <= index < WEEKS:
            counts[index] += 1

    return first_monday, counts, per_day


def render_svg(first_monday: date, counts: list[int], per_day: Counter[date]) -> str:
    width = 900
    height = 220
    left = 42
    right = 24
    chart_top = 72
    chart_bottom = 154
    chart_width = width - left - right
    chart_height = chart_bottom - chart_top
    gap = 4
    bar_width = (chart_width - gap * (WEEKS - 1)) / WEEKS
    maximum = max(max(counts, default=0), 1)

    total = sum(counts)
    active_weeks = sum(1 for value in counts if value > 0)
    active_days = sum(1 for value in per_day.values() if value > 0)
    busiest_week = max(counts, default=0)

    bars: list[str] = []
    for index, value in enumerate(counts):
        x = left + index * (bar_width + gap)
        bar_height = 0 if value == 0 else max(3.0, (value / maximum) * chart_height)
        y = chart_bottom - bar_height
        opacity = 0.22 if value == 0 else 0.92
        bars.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_width:.2f}" height="{bar_height:.2f}" '
            f'rx="2" fill="#3fb950" opacity="{opacity}" />'
        )

    labels: list[str] = []
    for index in range(0, WEEKS, 8):
        week_date = first_monday + timedelta(weeks=index)
        x = left + index * (bar_width + gap)
        labels.append(
            f'<text x="{x:.2f}" y="176" class="axis">{html.escape(week_date.strftime("%b"))}</text>'
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Public commit activity for {USERNAME}">
  <style>
    .title {{ font: 600 22px -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; fill: #58a6ff; }}
    .subtitle {{ font: 400 12px -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; fill: #8b949e; }}
    .stat {{ font: 500 13px -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; fill: #c9d1d9; }}
    .axis {{ font: 400 10px -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; fill: #8b949e; }}
  </style>
  <rect x="1" y="1" width="898" height="218" rx="10" fill="#0d1117" stroke="#30363d" />
  <text x="42" y="38" class="title">Public Commit Activity</text>
  <text x="42" y="58" class="subtitle">Last 52 weeks · commits authored by @{USERNAME} in public repositories owned by this account</text>
  <line x1="42" y1="154" x2="876" y2="154" stroke="#30363d" stroke-width="1" />
  {''.join(bars)}
  {''.join(labels)}
  <text x="42" y="204" class="stat">{total} commits</text>
  <text x="190" y="204" class="stat">{active_weeks} active weeks</text>
  <text x="350" y="204" class="stat">{active_days} active days</text>
  <text x="500" y="204" class="stat">{busiest_week} commits in busiest week</text>
</svg>
'''


def patch_readme() -> bool:
    if not README.exists():
        return False

    original = README.read_text(encoding="utf-8")
    updated = original

    replacements = {
        'src="./profile-summary-card-output/github_dark/0-profile-details.svg"\n    width="100%"':
            'src="./profile-summary-card-output/github_dark/0-profile-details.svg"\n    width="82%"',
        'src="./profile-summary-card-output/github_dark/1-repos-per-language.svg"\n    width="49%"':
            'src="./profile-summary-card-output/github_dark/1-repos-per-language.svg"\n    width="40%"',
        'src="./profile-summary-card-output/github_dark/2-most-commit-language.svg"\n    width="49%"':
            'src="./profile-summary-card-output/github_dark/2-most-commit-language.svg"\n    width="40%"',
        'src="./profile-summary-card-output/github_dark/3-stats.svg"\n    width="49%"':
            'src="./profile-summary-card-output/github_dark/3-stats.svg"\n    width="40%"',
        'src="./profile-summary-card-output/github_dark/4-productive-time.svg"\n    width="49%"':
            'src="./profile-summary-card-output/github_dark/4-productive-time.svg"\n    width="40%"',
    }

    for old, new in replacements.items():
        updated = updated.replace(old, new)

    marker_start = "<!-- commit-activity:start -->"
    marker_end = "<!-- commit-activity:end -->"
    activity_block = f'''{marker_start}

### 📈 Public Commit Activity

<p align="center">
  <img
    src="./assets/commit-activity.svg"
    width="82%"
    alt="Public Commit Activity"
  />
</p>

{marker_end}'''

    if marker_start not in updated:
        anchor = "> GitHub metrics represent GitHub-visible activity. Corporate repositories, private production environments and confidential infrastructure are intentionally not exposed publicly."
        if anchor not in updated:
            raise RuntimeError("README metrics anchor was not found; refusing to patch an unexpected layout")
        updated = updated.replace(anchor, f"{activity_block}\n\n{anchor}")

    if updated == original:
        return False

    README.write_text(updated, encoding="utf-8")
    return True


def main() -> None:
    today = datetime.now(timezone.utc).date()
    this_monday = today - timedelta(days=today.weekday())
    since = datetime.combine(this_monday - timedelta(weeks=WEEKS - 1), datetime.min.time(), tzinfo=timezone.utc)

    commits = collect_commits(since)
    first_monday, counts, per_day = week_buckets(commits, today)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render_svg(first_monday, counts, per_day), encoding="utf-8")
    patch_readme()

    print(f"Generated {OUTPUT} from {sum(counts)} public commits across {WEEKS} weeks")


if __name__ == "__main__":
    main()
