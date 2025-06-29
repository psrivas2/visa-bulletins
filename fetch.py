import os
import sys
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import webbrowser
from dateutil.relativedelta import relativedelta
import matplotlib.pyplot as plt
from typing import Optional, Tuple, List, Dict, Any

# Constants
BASE_URL = "https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin"
SAVE_DIR = "/Users/prakalps/repos/visa/.bulletins"
MONTHS = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december"
]


def fetch_bulletin_html(fiscal_year: int, year: int, month: str) -> Optional[str]:
    """
    Fetch the visa bulletin HTML content from the official website.

    Args:
        fiscal_year (int): The fiscal year for the bulletin.
        year (int): The calendar year for the bulletin.
        month (str): The month name (lowercase).

    Returns:
        Optional[str]: HTML content if successful, else None.
    """
    url = f"{BASE_URL}/{fiscal_year}/visa-bulletin-for-{month}-{year}.html"
    response = requests.get(url)
    if response.status_code == 200:
        return response.text
    return None


def save_bulletin_html(content: str, year: int, month: str) -> None:
    """
    Save the bulletin HTML content to a local file.

    Args:
        content (str): HTML content to save.
        year (int): Year of the bulletin.
        month (str): Month name.
    """
    year_dir = os.path.join(SAVE_DIR, str(year))
    os.makedirs(year_dir, exist_ok=True)
    file_path = os.path.join(year_dir, f"{month}.html")
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(content)


def is_bulletin_saved(year: int, month: str) -> bool:
    """
    Check if the bulletin HTML file already exists locally.

    Args:
        year (int): Year of the bulletin.
        month (str): Month name.

    Returns:
        bool: True if file exists, False otherwise.
    """
    file_path = os.path.join(SAVE_DIR, str(year), f"{month}.html")
    return os.path.exists(file_path)


def download_bulletin_if_needed(year: int, month: str, current_year: int, current_month: int) -> None:
    """
    Download and save a bulletin if it does not exist locally.

    Args:
        year (int): Year of the bulletin.
        month (str): Month name.
        current_year (int): Current year.
        current_month (int): Current month (1-based).
    """
    fiscal_year = year if month not in ["october", "november", "december"] else year + 1
    if year == current_year and MONTHS.index(month) > current_month - 1:
        return

    print(f"Processing bulletin for {month.capitalize()} {year}")
    if not is_bulletin_saved(year, month):
        content = fetch_bulletin_html(fiscal_year, year, month)
        if content:
            save_bulletin_html(content, year, month)
            print(f"Saved bulletin for {month.capitalize()} {year}")
        else:
            print(f"Failed to fetch bulletin for {month.capitalize()} {year}")


def fetch_and_save_bulletins_for_years(past_years: int) -> None:
    """
    Fetch and save all bulletins for the specified number of past years.

    Args:
        past_years (int): Number of past years to fetch.
    """
    now = datetime.now()
    current_year = now.year
    current_month = now.month + 1
    if current_month > 12:
        current_month -= 12
        current_year += 1

    print(
        f"Fetching bulletins for the past {past_years} year(s)... "
        f"starting from {MONTHS[current_month - 1].capitalize()} {current_year}"
    )
    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(download_bulletin_if_needed, year, month, current_year, current_month)
            for year in range(current_year - past_years, current_year + 1)
            for month in MONTHS
        ]
        for future in futures:
            future.result()


def extract_eb1_dates_from_table(table, bulletin_date: datetime) -> List[Optional[datetime]]:
    """
    Extract EB1 dates for India from a single HTML table.

    Args:
        table: BeautifulSoup table element.
        bulletin_date (datetime): The bulletin's date.

    Returns:
        List[Optional[datetime]]: List with one date (or None).
    """
    header_row = table.find("tr")
    headers = header_row.find_all("td")
    india_column_index = next(
        (i for i, header in enumerate(headers) if "INDIA" in header.get_text(strip=True).upper()),
        None
    )
    if india_column_index is None:
        return []

    for row in table.find_all("tr")[1:]:
        cells = row.find_all("td")
        if cells and cells[0].get_text(strip=True).lower() == "1st":
            if len(cells) > india_column_index:
                india_date = cells[india_column_index].get_text(strip=True)
                if india_date == "C":
                    return [bulletin_date]
                elif india_date == "U":
                    return [None]
                else:
                    try:
                        return [datetime.strptime(india_date, "%d%b%y")]
                    except ValueError:
                        return [None]
    return []


def extract_eb1_final_action_and_filing_dates_from_html(content: str, bulletin_date: datetime) -> List[Optional[datetime]]:
    """
    Extract EB1 final action and filing dates from bulletin HTML content.

    Args:
        content (str): Bulletin HTML content.
        bulletin_date (datetime): The bulletin's date.

    Returns:
        List[Optional[datetime]]: [final_action_date, filing_date]
    """
    soup = BeautifulSoup(content, "html.parser")
    tables = soup.find_all("table")
    dates = []
    for table in tables:
        extracted = extract_eb1_dates_from_table(table, bulletin_date)
        if extracted:
            dates.append(extracted[0])
        if len(dates) == 2:
            break
    while len(dates) < 2:
        dates.append(None)
    return dates


def collect_and_plot_eb1_dates(past_years: int) -> None:
    """
    Collect EB1 dates from all saved bulletins and plot their progression.

    Args:
        past_years (int): Number of past years to process.
    """
    bulletins = []
    for root, _, files in os.walk(SAVE_DIR):
        year = os.path.basename(root)
        if not year.isdigit() or int(year) < datetime.now().year - past_years:
            continue
        for file in files:
            if file.endswith(".html") and file.replace(".html", "") in MONTHS:
                month = file.replace(".html", "")
                month_index = MONTHS.index(month) + 1
                bulletin_date = datetime(int(year), month_index, 1)
                file_path = os.path.join(root, file)
                bulletins.append((bulletin_date, file_path))

    bulletins.sort()
    eb1_dates: Dict[datetime.date, Dict[str, Any]] = {}

    for bulletin_date, file_path in bulletins:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            dates = extract_eb1_final_action_and_filing_dates_from_html(content, bulletin_date)
            if dates:
                eb1_dates[bulletin_date.date()] = {
                    "final_action_date": dates[0].date() if dates[0] else "N/A",
                    "filing_date": dates[1].date() if dates[1] else "N/A",
                }

    plot_eb1_progression(eb1_dates)


def days_to_years_months_days(days: int) -> Tuple[int, int, int]:
    """
    Convert a number of days to years, months, and days.

    Args:
        days (int): Number of days.

    Returns:
        Tuple[int, int, int]: (years, months, days)
    """
    years = days // 365
    remaining_days = days % 365
    months = remaining_days // 30
    days = remaining_days % 30
    return years, months, days


def plot_eb1_progression(eb1_dates: Dict[datetime.date, Dict[str, Any]]) -> None:
    """
    Plot the progression of EB1 India final action and filing dates.

    Args:
        eb1_dates (Dict[datetime.date, Dict[str, Any]]): Mapping of bulletin dates to EB1 dates.
    """
    bulletin_dates = list(eb1_dates.keys())
    final_action_dates = [eb1_dates[date]["final_action_date"] for date in bulletin_dates]
    filing_dates = [eb1_dates[date]["filing_date"] for date in bulletin_dates]

    filtered_data = [
        (bd, fad, fd)
        for bd, fad, fd in zip(bulletin_dates, final_action_dates, filing_dates)
        if fad != "N/A" and fd != "N/A"
    ]
    if not filtered_data:
        print("No valid EB1 data to plot.")
        return

    filtered_bulletin_dates, filtered_final_action_dates, filtered_filing_dates = zip(*filtered_data)

    plt.style.use("seaborn-v0_8")
    fig, ax = plt.subplots(figsize=(12, 7))

    filing_line = ax.plot(
        filtered_bulletin_dates,
        filtered_filing_dates,
        marker="o",
        linestyle="-",
        linewidth=2,
        markersize=6,
        color="#2ecc71",
        label="Date of Filing",
        picker=5,
    )[0]
    final_action_line = ax.plot(
        filtered_bulletin_dates,
        filtered_final_action_dates,
        marker="s",
        linestyle="-",
        linewidth=2,
        markersize=6,
        color="#3498db",
        label="Final Action Date",
        picker=5,
    )[0]
    ax.plot(
        filtered_bulletin_dates,
        filtered_bulletin_dates,
        color="#e74c3c",
        linestyle="--",
        linewidth=1.5,
        label="Current Date",
    )

    may_2023_date = datetime(2023, 5, 1).date()
    last_filing_date = filtered_filing_dates[-1]
    dy, dm, dd = days_to_years_months_days((may_2023_date - last_filing_date).days)

    ax.set_xlabel("Bulletin Date", fontsize=12, fontweight="bold")
    ax.axhline(y=may_2023_date, color='#f39c12', linestyle='-.', linewidth=1.5, label='May 2023 Priority Date')
    ax.plot(
        [filtered_bulletin_dates[-1], filtered_bulletin_dates[-1]],
        [last_filing_date, may_2023_date],
        color="#f39c12",
        linestyle=":",
        linewidth=1.5,
    )
    ax.text(
        x=filtered_bulletin_dates[-1],
        y=last_filing_date + (may_2023_date - last_filing_date) / 2,
        s=f"{dy} years, {dm} months, {dd} days",
        verticalalignment="center",
        horizontalalignment="left",
        color="#f39c12",
        fontsize=10,
        bbox=dict(facecolor="white", alpha=0.5),
    )
    ax.set_ylabel("Date", fontsize=12, fontweight="bold")
    ax.set_title(
        "EB1 India: Final Action and Filing Dates Progression",
        fontsize=14,
        fontweight="bold",
        pad=20,
    )

    ax.grid(True, linestyle="--", alpha=0.7)
    plt.xticks(rotation=45)
    ax.tick_params(axis="both", which="major", labelsize=10)
    ax.legend(loc="upper left", frameon=True, fancybox=True, shadow=True, fontsize=10)

    def on_pick(event):
        ind = event.ind[0]
        date = filtered_bulletin_dates[ind]
        fiscal_year = date.year if date.month not in [10, 11, 12] else date.year + 1
        month = MONTHS[date.month - 1]
        url = f"{BASE_URL}/{fiscal_year}/visa-bulletin-for-{month}-{date.year}.html"
        webbrowser.open(url)

    fig.canvas.mpl_connect("pick_event", on_pick)
    plt.tight_layout()
    plt.show()


def main():
    """
    Main entry point for the script.
    Downloads bulletins and plots EB1 India progression.
    """
    past_years = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    fetch_and_save_bulletins_for_years(past_years)
    collect_and_plot_eb1_dates(past_years)


if __name__ == "__main__":
    main()
