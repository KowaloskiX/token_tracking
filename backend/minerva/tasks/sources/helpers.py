import re
from typing import List
import unicodedata
import urllib.parse
from bs4 import BeautifulSoup
from minerva.core.models.extensions.tenders.tender_analysis import TenderAnalysisResult
from pymongo import UpdateOne
from minerva.core.models.utils import PyObjectId
from minerva.core.database.database import db
from minerva.core.models.user import User

def normalize_id(s):
    if not s:
        return ""
    s = ''.join(c for c in s if c.isalnum())
    s = unicodedata.normalize('NFKC', s)
    return s.lower()



def extract_bzp_plan_fields(text: str) -> tuple[str|None, str|None]:
    plan_num = None
    plan_id = None

    # Normalize line endings
    lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    
    for i, line in enumerate(lines):

        if "2.9" in line and "Numer planu postępow" in line:
            # Try to extract from same line - improved regex to handle various Polish characters
            m = re.search(r"2\.9\.\)?\s*Numer planu postępow[aąeę]*[nń]*\s*w\s*BZP:\s*(.+)", line, re.IGNORECASE)
            if m and m.group(1).strip():
                plan_num = m.group(1).strip()
            # Or from next line
            elif i+1 < len(lines):
                next_line = lines[i+1].strip()
                if next_line and not next_line.startswith("2.10"):
                    plan_num = next_line
                    
        if "2.10" in line and "Identyfikator pozycji planu postępow" in line:
            # Try extraction from the same line first
            m = re.search(r"2\.10\.\)?\s*Identyfikator pozycji planu postępow[aąeę]*[nń]*:\s*(.+)", line, re.IGNORECASE)
            if m and m.group(1).strip():
                plan_id = m.group(1).strip()
            else:
                # Walk forward until we hit a non-empty line (skip possible blank line directly after 2.10)
                look_ahead_idx = i + 1
                while look_ahead_idx < len(lines):
                    candidate_line = lines[look_ahead_idx].strip()
                    # Skip empty lines
                    if not candidate_line:
                        look_ahead_idx += 1
                        continue
                    # Stop scanning if we already moved into next numbered section header (e.g. 2.11.) or a SEKCJA header
                    if re.match(r"^2\.11\)|^SEKCJA", candidate_line, re.IGNORECASE):
                        break
                    # At this point we consider candidate_line as the one that should hold the identifier
                    id_match = re.match(r"^(\d+(?:\.\d+)*)", candidate_line)
                    if id_match:
                        plan_id = id_match.group(1)
                    else:
                        # Fallback: take full candidate line
                        plan_id = candidate_line
                    break  # We processed a non-empty candidate line; exit loop
                    
    return plan_num, plan_id


async def scrape_bzp_budget_row(context, plan_num: str, plan_pos_id: str) -> tuple[str, str] | None:
    """
    Given a plan number and position id, scrape the BZP plan page and return the full row as a nicely described string.
    Returns (row_string, url) or None if not found.
    """
    url = f"https://ezamowienia.gov.pl/mo-client-board/bzp/tender-details/{urllib.parse.quote(plan_num, safe='')}"
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=40000)
        await page.wait_for_selector("table.table-positions td", timeout=20000)
        html = await page.content()
        soup = BeautifulSoup(html, "lxml")
        tables = soup.find_all("table", class_="table-positions")
        print(f"Found {len(tables)} table-positions tables")
        if not tables:
            print("No table-positions tables found in BZP plan page!")
            return None
        norm_id = normalize_id(plan_pos_id)
        for tbl in tables:
            for tr in tbl.find_all("tr"):
                tds = tr.find_all("td")
                if not tds:
                    continue
                first_col_raw = tds[0].get_text()
                first_col = normalize_id(first_col_raw)
                if first_col == norm_id or norm_id in first_col:
                    # Prepare labels
                    labels = [
                        "Pozycja Planu",
                        "Przedmiot zamówienia",
                        "Przewidywany tryb albo procedura udzielenia zamówienia",
                        "Budżet/Orientacyjna wartość zamówienia",
                        "Przewidywany termin wszczęcia postępowania",
                        "Informacje dodatkowe",
                        # "Informacja na temat aktualizacji"  # Uncomment if you want this too
                    ]
                    # Extract values, prettify <br> in "Informacje dodatkowe"
                    values = []
                    for idx, td in enumerate(tds[:len(labels)]):
                        # For "Informacje dodatkowe", replace <br> with newlines
                        if idx == 5:
                            # Get text with <br> as '\n'
                            value = ""
                            for elem in td.contents:
                                if getattr(elem, 'name', None) == 'br':
                                    value += "\n"
                                elif isinstance(elem, str):
                                    value += elem.strip()
                                else:
                                    value += elem.get_text(strip=True)
                            values.append(value.strip())
                        else:
                            values.append(td.get_text(strip=True))
                    row_str = "\n".join(f"{label}: {value}" for label, value in zip(labels, values))
                    return row_str, url
    finally:
        await page.close()
    return None


async def assign_order_numbers(analysis_id: PyObjectId, current_user: User) -> List[TenderAnalysisResult]:
    """
    Assigns unique order numbers to tender analysis results that don't have them yet.
    Returns all results for the analysis with updated order numbers.
    """
    # Check if there are any results without order numbers (either not exists or null)
    count_without_order = await db.tender_analysis_results.count_documents({
        "tender_analysis_id": analysis_id,
        "$or": [
            {"order_number": {"$exists": False}},
            {"order_number": None}
        ]
    })
    
    # Quick return if no updates needed
    if count_without_order == 0:
        # Get all results for response
        results = await db.tender_analysis_results.find({
            "tender_analysis_id": analysis_id
        }).sort("created_at", 1).to_list(None)
        return [TenderAnalysisResult(**result) for result in results]
    
    # Find the highest existing order number
    highest_order = await db.tender_analysis_results.find({
        "tender_analysis_id": analysis_id,
        "order_number": {"$exists": True, "$ne": None}
    }).sort("order_number", -1).limit(1).to_list(1)
    
    next_order = highest_order[0].get("order_number", 0) + 1 if highest_order else 1
    
    # Get all results that need updating
    results_to_update = await db.tender_analysis_results.find({
        "tender_analysis_id": analysis_id,
        "$or": [
            {"order_number": {"$exists": False}},
            {"order_number": None}
        ]
    }).sort("created_at", 1).to_list(None)  # Ascending order by creation date
    
    # Prepare updates
    updates = []
    for result in results_to_update:
        result["order_number"] = next_order  # Update in memory for response
        updates.append(UpdateOne(
            {"_id": result["_id"]},
            {"$set": {"order_number": next_order}}
        ))
        next_order += 1
    
    # Execute bulk updates
    if updates:
        await db.tender_analysis_results.bulk_write(updates)
    
    # Get all results for response (including the newly updated ones)
    all_results = await db.tender_analysis_results.find({
        "tender_analysis_id": analysis_id
    }).sort("created_at", 1).to_list(None)
    
    return [TenderAnalysisResult(**result) for result in all_results]