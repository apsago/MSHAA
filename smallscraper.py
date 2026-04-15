from playwright.sync_api import sync_playwright
import csv
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs
from datetime import datetime
import re 

BASE_URL = "https://www.mshsaa.org"
SCHOOL_PAGE = "https://www.mshsaa.org/MySchool/Schedule.aspx?s={school_id}"

USER_AGENT = "HighSchoolSportsResearchBot/1.0 (contact: apsago@mail.missouri.edu)"

schools = [
    {"school_name": "Columbia Independent", "school_id": 566},
    {"school_name": "Christian Fellowship", "school_id": 1099},
    {"school_name": "Father Tolton", "school_id": 917},
]

REQUEST_DELAY = 2

#04152026: updated to save file name differently - DO NOT add to main scraper
OUTPUT_DIR = Path("testing")
OUTPUT_DIR.mkdir(exist_ok=True)

today_str = datetime.now().strftime("%m%d%Y_%H%M%S")
OUTPUT_FILE = OUTPUT_DIR / f"output_{today_str}.csv"

activity_record = {
    "school_id": None,
    "school_name": None,
    "activity_name": None,
    "alg": None,
    "activity_url": None,
    "season": None,
    "level": None
}
event_records = []
activity_records = []

#04152026: added to create levels_of_play column
LEVEL_MAP = {
    "1": "Varsity",
    "2": "Junior Varsity",
    "4": "Freshman",
}

def visit_school(page, school):
    school_id = school["school_id"]
    school_name = school["school_name"]
    url = SCHOOL_PAGE.format(school_id=school_id)

    print(f"\nVisiting {school_name} ({school_id}): {url}")

    page.goto(url, wait_until="domcontentloaded",timeout=15000)

    print(f"Final URL: {page.url}")

    title = page.title()
    h1_text = page.locator("h1").first.inner_text().strip()

    print(f"Page title: {title}")
    print(f"School heading: {h1_text}")

def safe_attr(row, selector, attr_name):
    element = row.locator(selector)

    if element.count() == 0:
        return None

    try:
        value = element.first.get_attribute(attr_name)
        return value if value else None
    except Exception:
        return None

#04152026: separating times and scores 
def split_time_and_score(raw_value):
    if not raw_value:
        return None, None

    value = " ".join(raw_value.split()).strip()
    lower_value = value.lower()

    # Future event times
    if "am" in lower_value or "pm" in lower_value:
        return value, None

    # Placeholder
    if lower_value == "tbd":
        return value, None

    # Scores like 4 - 8 or 4 - 7 (8) or 0-2
    if re.search(r"\d+\s*-\s*\d+", value):
        return None, value

    return None, None

#04152026: added to get correct level of play
def get_current_level_of_play(page):
    try:
        current_tab = page.locator("#LevelsOfPlay li.level.current").first
        text = " ".join(current_tab.inner_text().split()).strip()
        return text if text else None
    except Exception:
        return None

def collect_activity_links(page, school):
    school_id = school["school_id"]
    school_name = school["school_name"]

    school_url = SCHOOL_PAGE.format(school_id=school_id)
    page.goto(school_url, wait_until="domcontentloaded",timeout=15000)

    anchors = page.locator("#Activities a").all()

    activities = []

    for anchor in anchors:
        href = anchor.get_attribute("href")
        if not href:
            continue

        full_url = urljoin(BASE_URL, href)

        # extract alg value from URL
        parsed = urlparse(full_url)
        alg = parse_qs(parsed.query).get("alg", [None])[0]

        season = anchor.get_attribute("data-season")
        level = anchor.get_attribute("data-level")

        activity_name = " ".join(anchor.inner_text().split())
        if not activity_name:
            activity_name = f"Unknown Activity {alg}"

        record = {
            "school_id": school_id,
            "school_name": school_name,
            "activity_name": activity_name,
            "alg": alg,
            "activity_url": full_url,
            "season": season,
            "level": level
        }

        activities.append(record)

    return activities

def safe_rendered_text(row, selector):
    cell = row.locator(selector)

    if cell.count() == 0:
        return None

    try:
        text = " ".join(cell.first.inner_text().split())
        return text if text else None
    except Exception:
        return None

def collect_events_from_activity(page, activity):
    page.goto(activity["activity_url"], wait_until="domcontentloaded", timeout=15000)

    #04152026: added to correctly find level of play
    current_level_of_play = get_current_level_of_play(page)


    rows = page.locator("table.schedule tbody tr").all()
    print(f"Found {len(rows)} rows")

    events = []

    for i, row in enumerate(rows, start=1):
        date = safe_rendered_text(row, "td.gamedate")
        event_name = safe_rendered_text(row, "td[id$='tdOpponent'] a")
        #04152026: updated event_name to capture tournament names
        if not event_name:
            event_name = safe_rendered_text(row, "td[id$='tdOpponent']")
        #04152026: updated to separate score/event time
        raw_time_or_score = safe_rendered_text(row, "td[id*='dScoreTime']")
        event_time, score = split_time_and_score(raw_time_or_score)
        location = None
        matchup_link = safe_attr(row, "td[id$='tdMatchup'] a", "href")
        if matchup_link:
            matchup_link = urljoin(BASE_URL, matchup_link)
        row_class = row.get_attribute("class") or ""
        if "tournament" in row_class:
            location = "tournament"
        elif "home" in row_class:
            location = "home"
        elif "away" in row_class:
            location = "away"
        else:
            location = None

        # skip rows that are basically empty / structural
        if not any([date, event_name, event_time, location]):
            continue

        event = {
            "school_id": activity["school_id"],
            "school_name": activity["school_name"],
            "activity_name": activity["activity_name"],
            "alg": activity["alg"],
            #04152026: updated to add level_of_play
            "level_of_play": current_level_of_play or LEVEL_MAP.get(str(activity["level"]), f"Unknown ({activity['level']})"),
            "event_date": date,
            "event_time": event_time,
            #04152026: updated to add score to data, change event_name column header
            "score": score,
            "event_name_or_opponent": event_name,
            "location": location,
            "source_activity_url": activity["activity_url"],
            "matchup_link": matchup_link,            
        }

        events.append(event)

    return events

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            user_agent=USER_AGENT
        )

        page = context.new_page()

        for school in schools:
            try: 
                activities = collect_activity_links(page, school)

                print(f"\n{school['school_name']} activities:")

                for activity in activities:
                    print(f"Found {len(activities)} activities for {school['school_name']}")

                activity_records.extend(activities)

                for activity in activities:
                    try:
                        print(f"\nScraping events for {activity['school_name']} - {activity['activity_name']}")

                        events = collect_events_from_activity(page, activity)

                        for event in events:
                            print(f"Collected {len(events)} events for {activity['activity_name']}")

                        event_records.extend(events)


                    except Exception as e:
                        print(
                            f"Error on activity {activity['activity_name']} "
                            f"for {activity['school_name']} ({activity['school_id']}): {e}"
                        )

                time.sleep(REQUEST_DELAY)

            except Exception as e:
                print(f"Error on school {school['school_name']} ({school['school_id']}): {e}")
        
        print(f"\nWriting {len(event_records)} events to CSV...")

        if event_records:
            with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=event_records[0].keys()
                )
                writer.writeheader()
                writer.writerows(event_records)

            print(f"CSV saved to {OUTPUT_FILE}")
        else:
            print("No events found; CSV not written.")

        browser.close()


if __name__ == "__main__":
    main()