from minerva.tasks.sources.ted.extract_tenders import BaseTedCountryExtractor

# Poland (Original TED extractor)
class TedTenderExtractor(BaseTedCountryExtractor):
    def __init__(self):
        super().__init__(
            country_code="POL",
            priority_languages=["PL", "EN"],
            source_type_name="ted"
        )

# Germany 
class GermanTedTenderExtractor(BaseTedCountryExtractor):
    def __init__(self):
        super().__init__(
            country_code="DEU",
            priority_languages=["DE", "EN"],
            source_type_name="ted_germany"
        )

# France
class FrenchTedTenderExtractor(BaseTedCountryExtractor):
    def __init__(self):
        super().__init__(
            country_code="FRA",
            priority_languages=["FR", "EN"],
            source_type_name="ted_france"
        )

# Spain
class SpainTedTenderExtractor(BaseTedCountryExtractor):
    def __init__(self):
        super().__init__(
            country_code="ESP",
            priority_languages=["ES", "EN"],
            source_type_name="ted_spain"
        )

# Italy
class ItalyTedTenderExtractor(BaseTedCountryExtractor):
    def __init__(self):
        super().__init__(
            country_code="ITA",
            priority_languages=["IT", "EN"],
            source_type_name="ted_italy"
        )

# Belgium
class BelgiumTedTenderExtractor(BaseTedCountryExtractor):
    def __init__(self):
        super().__init__(
            country_code="BEL",
            priority_languages=["FR", "NL", "EN"],  # Belgium has multiple official languages
            source_type_name="ted_belgium"
        )

# Netherlands
class NetherlandsTedTenderExtractor(BaseTedCountryExtractor):
    def __init__(self):
        super().__init__(
            country_code="NLD",
            priority_languages=["NL", "EN"],
            source_type_name="ted_netherlands"
        )

# Sweden
class SwedenTedTenderExtractor(BaseTedCountryExtractor):
    def __init__(self):
        super().__init__(
            country_code="SWE",
            priority_languages=["SV", "EN"],  # SV is the ISO code for Swedish
            source_type_name="ted_sweden"
        )

# Czechia
class CzechiaTedTenderExtractor(BaseTedCountryExtractor):
    def __init__(self):
        super().__init__(
            country_code="CZE",
            priority_languages=["CS", "EN"],  # CS is the ISO code for Czech
            source_type_name="ted_czechia"
        )

# Austria
class AustriaTedTenderExtractor(BaseTedCountryExtractor):
    def __init__(self):
        super().__init__(
            country_code="AUT",
            priority_languages=["DE", "EN"],
            source_type_name="ted_austria"
        )

        # Portugal
class PortugalTedTenderExtractor(BaseTedCountryExtractor):
    def __init__(self):
        super().__init__(
            country_code="PRT",
            priority_languages=["PT", "EN"],
            source_type_name="ted_portugal"
        )

# Denmark
class DenmarkTedTenderExtractor(BaseTedCountryExtractor):
    def __init__(self):
        super().__init__(
            country_code="DNK",
            priority_languages=["DA", "EN"],  # DA is the ISO code for Danish
            source_type_name="ted_denmark"
        )

# Finland
class FinlandTedTenderExtractor(BaseTedCountryExtractor):
    def __init__(self):
        super().__init__(
            country_code="FIN",
            priority_languages=["FI", "SV", "EN"],  # Finland has Finnish and Swedish as official languages
            source_type_name="ted_finland"
        )

# Norway
class NorwayTedTenderExtractor(BaseTedCountryExtractor):
    def __init__(self):
        super().__init__(
            country_code="NOR",
            priority_languages=["NO", "EN"],  # NO is the ISO code for Norwegian
            source_type_name="ted_norway"
        )

# Ireland
class IrelandTedTenderExtractor(BaseTedCountryExtractor):
    def __init__(self):
        super().__init__(
            country_code="IRL",
            priority_languages=["EN", "GA"],  # English and Irish Gaelic
            source_type_name="ted_ireland"
        )

# Greece
class GreeceTedTenderExtractor(BaseTedCountryExtractor):
    def __init__(self):
        super().__init__(
            country_code="GRC",
            priority_languages=["EL", "EN"],  # EL is the ISO code for Greek
            source_type_name="ted_greece"
        )

# Hungary
class HungaryTedTenderExtractor(BaseTedCountryExtractor):
    def __init__(self):
        super().__init__(
            country_code="HUN",
            priority_languages=["HU", "EN"],
            source_type_name="ted_hungary"
        )

# Slovakia
class SlovakiaTedTenderExtractor(BaseTedCountryExtractor):
    def __init__(self):
        super().__init__(
            country_code="SVK",
            priority_languages=["SK", "EN"],
            source_type_name="ted_slovakia"
        )

# Slovenia
class SloveniaTedTenderExtractor(BaseTedCountryExtractor):
    def __init__(self):
        super().__init__(
            country_code="SVN",
            priority_languages=["SL", "EN"],  # SL is the ISO code for Slovenian
            source_type_name="ted_slovenia"
        )

# Croatia
class CroatiaTedTenderExtractor(BaseTedCountryExtractor):
    def __init__(self):
        super().__init__(
            country_code="HRV",
            priority_languages=["HR", "EN"],
            source_type_name="ted_croatia"
        )

# Romania
class RomaniaTedTenderExtractor(BaseTedCountryExtractor):
    def __init__(self):
        super().__init__(
            country_code="ROU",
            priority_languages=["RO", "EN"],
            source_type_name="ted_romania"
        )

# Bulgaria
class BulgariaTedTenderExtractor(BaseTedCountryExtractor):
    def __init__(self):
        super().__init__(
            country_code="BGR",
            priority_languages=["BG", "EN"],
            source_type_name="ted_bulgaria"
        )

# Estonia
class EstoniaTedTenderExtractor(BaseTedCountryExtractor):
    def __init__(self):
        super().__init__(
            country_code="EST",
            priority_languages=["ET", "EN"],
            source_type_name="ted_estonia"
        )

# Latvia
class LatviaTedTenderExtractor(BaseTedCountryExtractor):
    def __init__(self):
        super().__init__(
            country_code="LVA",
            priority_languages=["LV", "EN"],
            source_type_name="ted_latvia"
        )

# Lithuania
class LithuaniaTedTenderExtractor(BaseTedCountryExtractor):
    def __init__(self):
        super().__init__(
            country_code="LTU",
            priority_languages=["LT", "EN"],
            source_type_name="ted_lithuania"
        )

# Luxembourg
class LuxembourgTedTenderExtractor(BaseTedCountryExtractor):
    def __init__(self):
        super().__init__(
            country_code="LUX",
            priority_languages=["FR", "DE", "LB", "EN"],  # Luxembourg has multiple official languages
            source_type_name="ted_luxembourg"
        )