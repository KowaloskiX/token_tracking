from datetime import datetime
import re

class DateStandardizer:
    POLISH_MONTHS = {
        'stycznia': '01', 'lutego': '02', 'marca': '03', 'kwietnia': '04',
        'maja': '05', 'czerwca': '06', 'lipca': '07', 'sierpnia': '08',
        'września': '09', 'października': '10', 'listopada': '11', 'grudnia': '12',
        'styczeń': '01', 'luty': '02', 'marzec': '03', 'kwiecień': '04',
        'maj': '05', 'czerwiec': '06', 'lipiec': '07', 'sierpień': '08',
        'wrzesień': '09', 'październik': '10', 'listopad': '11', 'grudzień': '12'
    }

    @staticmethod
    def standardize_deadline(deadline_str: str) -> str:
        if not deadline_str:
            return ""
            
        deadline_str = deadline_str.lower().strip()
        
        try:
            # Remove any extra whitespace and common prefixes
            deadline_str = re.sub(r'\s+', ' ', deadline_str)
            deadline_str = re.sub(r'godz\.?|godzina|time|hour', '', deadline_str, flags=re.IGNORECASE)
            
            # Try parsing ISO format first (YYYY-MM-DD HH:mm:ss)
            try:
                dt = datetime.fromisoformat(deadline_str)
                return dt.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                pass

            # Try parsing DD/MM/YYYY format
            try:
                if re.match(r'\d{2}/\d{2}/\d{4}', deadline_str):
                    dt = datetime.strptime(deadline_str, "%d/%m/%Y")
                    return dt.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                pass

            # Handle Polish format (e.g., "17 stycznia 2025, 09:00")
            for polish_month, month_num in DateStandardizer.POLISH_MONTHS.items():
                if polish_month in deadline_str:
                    # Extract components using regex
                    pattern = rf'(\d+)\s+{polish_month}\s+(\d{{4}})(?:[,\s]+(\d+[:]\d+))?'
                    match = re.search(pattern, deadline_str)
                    if match:
                        day, year, time = match.groups()
                        time = time if time else "00:00"
                        date_str = f"{year}-{month_num}-{day.zfill(2)} {time}"
                        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
                        return dt.strftime("%Y-%m-%d %H:%M")

            # If no format matches, try generic parsing as a last resort
            try:
                from dateutil import parser
                dt = parser.parse(deadline_str)
                return dt.strftime("%Y-%m-%d %H:%M")
            except:
                pass

            return deadline_str  # Return original if no parsing succeeded

        except Exception as e:
            print(f"Error standardizing date {deadline_str}: {str(e)}")
            return deadline_str

# Example usage:
if __name__ == "__main__":
    test_dates = [
        "11/02/2025",
        "17 stycznia 2025, godz 09:00",
        "2025-03-15 14:30:00",
        "15 marca 2025 roku, godzina 12:00",
        "2025-01-01",
        "Invalid date"
    ]
    
    for date in test_dates:
        print(f"Original: {date}")
        print(f"Standardized: {DateStandardizer.standardize_deadline(date)}\n")