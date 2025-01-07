import os
import sys
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import matplotlib.pyplot as plt

# Constants
BASE_URL = "https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin"
SAVE_DIR = "/Users/prakalps/repos/visa/bulletins"
MONTHS = ["january", "february", "march", "april", "may", "june", 
          "july", "august", "september", "october", "november", "december"]

# Fetching and saving bulletins
def fetch_bulletin(fiscal_year, year, month):
    """Fetch visa bulletin from the website."""
    url = f"{BASE_URL}/{fiscal_year}/visa-bulletin-for-{month}-{year}.html"
    response = requests.get(url)
    return response.text if response.status_code == 200 else None

def save_bulletin(content, year, month):
    """Save bulletin content to a file."""
    year_dir = os.path.join(SAVE_DIR, str(year))
    os.makedirs(year_dir, exist_ok=True)
    file_path = os.path.join(year_dir, f"{month}.html")
    with open(file_path, 'w') as file:
        file.write(content)

def bulletin_exists(year, month):
    """Check if bulletin already exists locally."""
    file_path = os.path.join(SAVE_DIR, str(year), f"{month}.html")
    return os.path.exists(file_path)

def process_bulletin(year, month, current_year, current_month):
    """Process single bulletin download."""
    fiscal_year = year if month not in ["october", "november", "december"] else year + 1
    if year == current_year and MONTHS.index(month) > current_month - 1:
        return
    
    if not bulletin_exists(year, month):
        content = fetch_bulletin(fiscal_year, year, month)
        if content:
            save_bulletin(content, year, month)
            print(f"Saved bulletin for {month} {year}")
        else:
            print(f"Failed to fetch bulletin for {month} {year}")

def fetch_and_save_bulletins(past_years):
    """Fetch and save all bulletins for the specified years."""
    current_year = datetime.now().year
    current_month = datetime.now().month

    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(process_bulletin, year, month, current_year, current_month)
            for year in range(current_year - past_years, current_year)
            for month in MONTHS
        ]
        for future in futures:
            future.result()

# Data extraction and processing
def extract_eb1_final_action_and_filing_dates(content, bulletin_date):
    """Extract EB1 dates from bulletin content."""
    soup = BeautifulSoup(content, 'html.parser')
    tables = soup.find_all('table')
    dates = []

    for table in tables:
        header_row = table.find('tr')
        headers = header_row.find_all('td')
        india_column_index = next((index for index, header in enumerate(headers) 
                                 if "INDIA" in header.get_text(strip=True).upper()), None)

        if india_column_index is None:
            continue

        for row in table.find_all('tr')[1:]:
            cells = row.find_all('td')
            if cells[0].get_text(strip=True).lower() == "1st":
                if len(cells) > india_column_index:
                    india_date = cells[india_column_index].get_text(strip=True)
                    india_date = (bulletin_date if india_date == "C" 
                                else None if india_date == "U"
                                else datetime.strptime(india_date, "%d%b%y"))
                    dates.append(india_date)
                    break

        if len(dates) == 2:
            break

    while len(dates) < 2:
        dates.append(None)

    return dates

def extract_eb1_final_action_and_filing_dates_from_all_bulletins(past_years):
    """Process all bulletins and extract dates."""
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
    eb1_dates = {}

    for bulletin_date, file_path in bulletins:
        with open(file_path, 'r') as f:
            content = f.read()
            dates = extract_eb1_final_action_and_filing_dates(content, bulletin_date)
            if dates:
                eb1_dates[bulletin_date.date()] = {
                    "final_action_date": dates[0].date() if dates[0] else 'N/A',
                    "filing_date": dates[1].date() if dates[1] else 'N/A'
                }

    plot_eb1_dates(eb1_dates)

# Visualization
def plot_eb1_dates(eb1_dates):
    """Plot the extracted dates with enhanced styling."""
    # Prepare data
    bulletin_dates = list(eb1_dates.keys())
    final_action_dates = [eb1_dates[date]["final_action_date"] for date in bulletin_dates]
    filing_dates = [eb1_dates[date]["filing_date"] for date in bulletin_dates]

    filtered_data = [(bd, fad, fd) for bd, fad, fd in zip(bulletin_dates, final_action_dates, filing_dates)
                    if fad != 'N/A' and fd != 'N/A']
    filtered_bulletin_dates, filtered_final_action_dates, filtered_filing_dates = zip(*filtered_data)

    # Set style
    plt.style.use('seaborn-v0_8')  # or use 'ggplot' if seaborn is not installed
    fig, ax = plt.subplots(figsize=(12, 7))

    # Plot lines with enhanced styling
    ax.plot(filtered_bulletin_dates, filtered_filing_dates, 
            marker='o', linestyle='-', linewidth=2, markersize=6,
            color='#2ecc71', label='Date of Filing')
    ax.plot(filtered_bulletin_dates, filtered_final_action_dates, 
            marker='s', linestyle='-', linewidth=2, markersize=6,
            color='#3498db', label='Final Action Date')
    ax.plot(filtered_bulletin_dates, filtered_bulletin_dates, 
            color='#e74c3c', linestyle='--', linewidth=1.5,
            label='Current Date')

    # Customize appearance
    ax.set_xlabel('Bulletin Date', fontsize=12, fontweight='bold')
    ax.set_ylabel('Date', fontsize=12, fontweight='bold')
    ax.set_title('EB1 India: Final Action and Filing Dates Progression', 
                fontsize=14, fontweight='bold', pad=20)
    
    # Customize grid
    ax.grid(True, linestyle='--', alpha=0.7)
    
    # Customize ticks
    plt.xticks(rotation=45)
    ax.tick_params(axis='both', which='major', labelsize=10)
    
    # Enhance legend
    ax.legend(loc='upper left', frameon=True, fancybox=True, 
             shadow=True, fontsize=10)

    # Adjust layout
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    past_years = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    fetch_and_save_bulletins(past_years)
    extract_eb1_final_action_and_filing_dates_from_all_bulletins(past_years)
