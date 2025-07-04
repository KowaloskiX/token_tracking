"""
Translation utilities for multilingual tender notifications.
Supports Polish (pl), English (en), and German (de) languages.
"""

from typing import Dict, Optional

# Translation dictionaries for each supported language
TENDER_NOTIFICATION_TRANSLATIONS = {
    "pl": {
        "tender_update_title": "Aktualizacja monitorowanego przetargu",
        "tender_outcome_title": "Przetarg zakończony - dostępne wyniki", 
        "update_prefix": "Aktualizacja",
        "outcome_prefix": "Wynik",
        "summary_changes": "Podsumowanie zmian:",
        "new_files": "Nowe pliki",
        "file_details": "Szczegóły zmian w plikach:",
        "tender_label": "Przetarg:",
        "organization_label": "Organizacja:",
        "tender_completed": "Przetarg został zakończony i dostępne są już wyniki oraz informacje o rozstrzygnięciu.",
        "view_tender_details": "Zobacz szczegóły przetargu",
        "view_update_details": "Zobacz szczegóły aktualizacji",
        "update_detected": "Wykryto aktualizację w monitorowanym przetargu.",
        "unknown_tender": "Nieznany przetarg",
        "unknown_organization": "Nieznana organizacja",
        "tender_updated": "Aktualizacja przetargu",
        "status_label": "Status",
        "winner_label": "Zwycięzca",
        "winner_location_label": "Lokalizacja zwycięzcy",
        "winning_price_label": "Cena zwycięska",
        "total_offers_label": "Liczba ofert",
        "lowest_price_label": "Najniższa cena",
        "highest_price_label": "Najwyższa cena",
        "contract_value_label": "Wartość umowy",
        "download_file": "Pobierz plik",
        "view_original_tender": "Zobacz oryginalny przetarg",
        "original_tender_link": "Link do oryginalnego przetargu",
        "not_available": "niedostępny",
        "contracting_authority": "Zamawiający"
    },
    "en": {
        "tender_update_title": "Tender monitoring update",
        "tender_outcome_title": "Tender completed - results available",
        "update_prefix": "Update",
        "outcome_prefix": "Result",
        "summary_changes": "Summary of changes:",
        "new_files": "New files",
        "file_details": "File change details:",
        "tender_label": "Tender:",
        "organization_label": "Organization:",
        "tender_completed": "The tender has been completed and results and award information are now available.",
        "view_tender_details": "View tender details",
        "view_update_details": "View update details",
        "update_detected": "Update detected in monitored tender.",
        "unknown_tender": "Unknown tender",
        "unknown_organization": "Unknown organization",
        "tender_updated": "Tender updated",
        "status_label": "Status",
        "winner_label": "Winner",
        "winner_location_label": "Winner Location",
        "winning_price_label": "Winning Price",
        "total_offers_label": "Total Offers",
        "lowest_price_label": "Lowest Price",
        "highest_price_label": "Highest Price",
        "contract_value_label": "Contract Value",
        "download_file": "Download file",
        "view_original_tender": "View original tender",
        "original_tender_link": "Original tender link",
        "not_available": "not available",
        "contracting_authority": "Contracting Authority"
    },
    "de": {
        "tender_update_title": "Ausschreibung Überwachungsupdate",
        "tender_outcome_title": "Ausschreibung abgeschlossen - Ergebnisse verfügbar",
        "update_prefix": "Aktualisierung",
        "outcome_prefix": "Ergebnis",
        "summary_changes": "Zusammenfassung der Änderungen:",
        "new_files": "Neue Dateien",
        "file_details": "Details zu Dateiänderungen:",
        "tender_label": "Ausschreibung:",
        "organization_label": "Organisation:",
        "tender_completed": "Die Ausschreibung wurde abgeschlossen und Ergebnisse sowie Vergabeinformationen sind jetzt verfügbar.",
        "view_tender_details": "Ausschreibungsdetails ansehen",
        "view_update_details": "Update-Details ansehen",
        "update_detected": "Update in überwachter Ausschreibung erkannt.",
        "unknown_tender": "Unbekannte Ausschreibung",
        "unknown_organization": "Unbekannte Organisation",
        "tender_updated": "Ausschreibung aktualisiert",
        "status_label": "Status",
        "winner_label": "Gewinner",
        "winner_location_label": "Gewinner Ort",
        "winning_price_label": "Gewinnpreis",
        "total_offers_label": "Gesamtzahl der Bieter",
        "lowest_price_label": "Niedrigste Preis",
        "highest_price_label": "Höchste Preis",
        "contract_value_label": "Vertragswert",
        "download_file": "Datei herunterladen",
        "view_original_tender": "Ursprüngliche Ausschreibung ansehen",
        "original_tender_link": "Link zur ursprünglichen Ausschreibung",
        "not_available": "nicht verfügbar",
        "contracting_authority": "Auftraggeber"
    }
}

def get_translation(language: Optional[str], key: str, fallback_language: str = "pl") -> str:
    """
    Get a translated message for the specified language.
    
    Args:
        language: Target language code (pl, en, de) or None
        key: Translation key to look up
        fallback_language: Language to use if translation not found (default: pl)
        
    Returns:
        Translated message string
    """
    # Default to Polish if language is None or not supported
    if not language or language not in TENDER_NOTIFICATION_TRANSLATIONS:
        language = fallback_language
    
    # Get the translation dictionary for the language
    translations = TENDER_NOTIFICATION_TRANSLATIONS.get(language, TENDER_NOTIFICATION_TRANSLATIONS[fallback_language])
    
    # Return the translation or fallback to the key itself if not found
    return translations.get(key, key)

def get_supported_languages() -> list[str]:
    """Get list of supported language codes."""
    return list(TENDER_NOTIFICATION_TRANSLATIONS.keys())

def is_language_supported(language: str) -> bool:
    """Check if a language is supported."""
    return language in TENDER_NOTIFICATION_TRANSLATIONS 