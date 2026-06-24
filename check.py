#!/usr/bin/env python3
"""
IYHA Hostel Availability Checker
Checks all ANA hostels for availability in July-August 2026
for 2 adults + 4 children, outputs results to CSV and terminal.
"""

import requests
import json
import csv
import sys
from datetime import datetime, date
from collections import defaultdict

HOTELS = [
    {"name": "אנ\"א תל-חי",           "OptID": "10224", "Wing": "1", "CloudID": "323"},
    {"name": "אנ\"א פקיעין",           "OptID": "10220", "Wing": "1", "CloudID": "325"},
    {"name": "אנ\"א שלומי",            "OptID": "10223", "Wing": "1", "CloudID": "324"},
    {"name": "אנ\"א עכו",              "OptID": "10215", "Wing": "1", "CloudID": "326"},
    {"name": "אנ\"א חיפה",             "OptID": "10217", "Wing": "1", "CloudID": "329"},
    {"name": "אנ\"א כרי דשא - כנרת",  "OptID": "10218", "Wing": "1", "CloudID": "327"},
    {"name": "אנ\"א פוריה - כנרת",    "OptID": "10221", "Wing": "1", "CloudID": "328"},
    {"name": "אנ\"א בית שאן",          "OptID": "10216", "Wing": "1", "CloudID": "331"},
    {"name": "אנ\"א מעיין חרוד",       "OptID": "10219", "Wing": "1", "CloudID": "330"},
    {"name": "אנ\"א תל אביב",          "OptID": "10212", "Wing": "1", "CloudID": "332"},
    {"name": "אנ\"א רבין - ירושלים",   "OptID": "10214", "Wing": "1", "CloudID": "335"},
    {"name": "אנ\"א אגרון - ירושלים",  "OptID": "10211", "Wing": "1", "CloudID": "334"},
    {"name": "אנ\"א עין גדי",          "OptID": "10208", "Wing": "1", "CloudID": "336"},
    {"name": "אנ\"א מצדה",             "OptID": "10209", "Wing": "1", "CloudID": "337"},
    {"name": "אנ\"א מצפה רמון",        "OptID": "10210", "Wing": "1", "CloudID": "339"},
    {"name": "אנ\"א אילת",             "OptID": "10207", "Wing": "1", "CloudID": "340"},
]

BASE_URL = "https://www.iyha.org.il/be"
HOTEL_PARAM = ",".join(f"{h['OptID']}_{h['Wing']}" for h in HOTELS)

JUL1  = date(2026, 7, 1)
AUG31 = date(2026, 8, 31)


def get_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"https://www.iyha.org.il/be/be/pro/results?lang=heb&chainid=186&hotel={HOTEL_PARAM}&in=2026-07-01&out=2026-07-02&rooms=1&ad1=2&ch1=4&inf1=0",
    })
    print("[1/3] Getting session cookies...")
    s.get(
        f"{BASE_URL}/be/pro/results",
        params={
            "lang": "heb", "chainid": "186", "hotel": HOTEL_PARAM,
            "in": "2026-07-01", "out": "2026-07-02",
            "rooms": "1", "ad1": "2", "ch1": "4", "inf1": "0",
            "reffrom": "google_ads_max_ISRAEL",
        }
    )
    xsrf = s.cookies.get("XSRF-COOKIE", "")
    s.headers["RequestVerificationToken"] = xsrf
    return s


def init_engine(session):
    print("[2/3] Initializing booking engine...")
    resp = session.post(
        f"{BASE_URL}/BE_EngineService/InitEngine",
        json={"query": {
            "lang": "heb", "chainid": "186", "hotel": HOTEL_PARAM,
            "in": "2026-07-01", "out": "2026-07-02",
            "rooms": "1", "ad1": "2", "ch1": "4", "inf1": "0",
        }},
    )
    data = resp.json()
    if not data.get("Success"):
        print("ERROR: InitEngine failed:", data.get("Error"))
        sys.exit(1)

    # Update hotel names from API (Hebrew names)
    for s in data["Obj"]["SearchEngine"].get("Settings", []):
        if s.get("Lang") == "heb":
            for resort in s.get("AllResorts", []):
                cloud_id = str(resort["HotelsCloudID"])
                for h in HOTELS:
                    if h["CloudID"] == cloud_id:
                        h["name"] = resort["ResortName"]


def get_calendar(session, hotel):
    resp = session.post(
        f"{BASE_URL}/BE_EngineService/getAllData",
        json={"gap": {
            "hotelID": hotel["OptID"],
            "wing": True,
            "dsn": "",
            "lang": "heb",
            "days": 365,
            "chainId": 186,
            "HotelsCloudID": hotel["CloudID"],
            "fromdate": None,
            "enddate": None,
            "priceCodeCategoryIDList": None,
        }},
    )
    return resp.json().get("CalendarItems", [])


def parse_date(s):
    return datetime.strptime(s[:10], "%Y-%m-%d").date()


def main():
    session = get_session()
    init_engine(session)

    print(f"[3/3] Checking availability for all {len(HOTELS)} hostels in Jul-Aug 2026...")
    print()

    all_rows = []
    summary = {}

    for i, hotel in enumerate(HOTELS, 1):
        name = hotel["name"]
        print(f"  [{i:02d}/{len(HOTELS)}] {name}...", end=" ", flush=True)
        try:
            calendar = get_calendar(session, hotel)
        except Exception as e:
            print(f"ERROR: {e}")
            summary[name] = []
            continue

        available = []
        for item in calendar:
            d = parse_date(item["Date"])
            if d < JUL1 or d > AUG31:
                continue
            if item["Closed"] or item["ClosedForArrival"]:
                continue
            if item["RoomsAvailableForSale"] <= 0:
                continue
            available.append({
                "hostel": name,
                "date": d.isoformat(),
                "day": d.strftime("%A"),
                "rooms_available": item["RoomsAvailableForSale"],
                "price_ils": item["LocalPrice"],
                "min_nights": item["MinLOS"],
            })
            all_rows.append(available[-1])

        summary[name] = available
        count = len(available)
        if count:
            prices = [r["price_ils"] for r in available if r["price_ils"] > 0]
            min_p = f"₪{min(prices):.0f}" if prices else "n/a"
            print(f"{count} dates open, from {min_p}")
        else:
            print("FULLY BOOKED / no availability")

    # Save CSV
    csv_path = "/root/iyha-checker/availability.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["hostel", "date", "day", "rooms_available", "price_ils", "min_nights"])
        writer.writeheader()
        writer.writerows(sorted(all_rows, key=lambda r: (r["date"], r["hostel"])))

    # Print summary table
    print()
    print("=" * 70)
    print("  IYHA ANA HOSTELS — Available dates, July–August 2026")
    print("  Configuration: 2 Adults + 4 Children, 1 Room")
    print("=" * 70)
    for name, dates in sorted(summary.items(), key=lambda x: -len(x[1])):
        if not dates:
            print(f"  {name}: —")
            continue
        prices = [d["price_ils"] for d in dates if d["price_ils"] > 0]
        price_str = f"₪{min(prices):.0f}–₪{max(prices):.0f}" if prices else ""
        date_range = f"{dates[0]['date']} to {dates[-1]['date']}"
        print(f"  {name}: {len(dates)} dates  {price_str}")
        # Show date ranges compactly
        blocks = []
        cur_start = cur_end = None
        for row in sorted(dates, key=lambda r: r["date"]):
            d = date.fromisoformat(row["date"])
            if cur_start is None:
                cur_start = cur_end = d
            elif (d - cur_end).days == 1:
                cur_end = d
            else:
                blocks.append((cur_start, cur_end))
                cur_start = cur_end = d
        if cur_start:
            blocks.append((cur_start, cur_end))
        for start, end in blocks:
            if start == end:
                print(f"    • {start}")
            else:
                print(f"    • {start} – {end}")

    print()
    print(f"  Full results saved to: {csv_path}")
    print(f"  Total available hotel-nights: {len(all_rows)}")


if __name__ == "__main__":
    main()
