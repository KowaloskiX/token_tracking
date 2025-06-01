
from dataclasses import dataclass
from typing import Dict, Type

from minerva.tasks.services.tender_monitoring_service import TenderMonitoringService
from minerva.tasks.sources.bazakonkurencyjnosci.extract_tenders import BazaKonkurencyjnosciTenderExtractor
from minerva.tasks.sources.eb2b.extract_tenders import Eb2bTenderExtractor
from minerva.tasks.sources.epropuplico_ogloszenia.extract_tenders import EproPublicoMainTenderExtractor
from minerva.tasks.sources.ezamawiajacy.extract_tenders import EzamawiajacyTenderExtractor
from minerva.tasks.sources.ezamowienia.extract_tenders import TenderExtractor
from minerva.tasks.sources.logintrade.extract_tenders import LoginTradeExtractor
from minerva.tasks.sources.platformazakupowa.extract_tenders import PlatformaZakupowaTenderExtractor
from minerva.tasks.sources.smartpzp.extract_tenders import SmartPZPTenderExtractor
from minerva.tasks.sources.source_types import TenderSourceType
from minerva.tasks.sources.ted.tender_countries import (
    TedTenderExtractor,
    GermanTedTenderExtractor,
    FrenchTedTenderExtractor,
    SpainTedTenderExtractor,
    ItalyTedTenderExtractor,
    BelgiumTedTenderExtractor,
    NetherlandsTedTenderExtractor,
    SwedenTedTenderExtractor,
    CzechiaTedTenderExtractor,
    AustriaTedTenderExtractor,
    PortugalTedTenderExtractor,
    DenmarkTedTenderExtractor,
    FinlandTedTenderExtractor,
    NorwayTedTenderExtractor,
    IrelandTedTenderExtractor,
    GreeceTedTenderExtractor,
    HungaryTedTenderExtractor,
    SlovakiaTedTenderExtractor,
    SloveniaTedTenderExtractor,
    CroatiaTedTenderExtractor,
    RomaniaTedTenderExtractor,
    BulgariaTedTenderExtractor,
    EstoniaTedTenderExtractor,
    LatviaTedTenderExtractor,
    LithuaniaTedTenderExtractor,
    LuxembourgTedTenderExtractor,
)

@dataclass
class TenderMonitoringConfig:
    source_type: TenderSourceType
    extractor_class: Type
    is_date_str: bool = False

class TenderMonitoringManager:

    def __init__(self):
        self.monitoring_config = self._initialize_monitoring_configs()

    def _initialize_monitoring_configs(self) -> Dict[TenderSourceType, TenderMonitoringConfig]:
        """Define all available tender monitorings and their configurations."""
        configs = {}

        # Add basic sources
        configs[TenderSourceType.EZAMOWIENIA] = TenderMonitoringConfig(
            source_type=TenderSourceType.EZAMOWIENIA,
            extractor_class=TenderExtractor,
            is_date_str=True
        )
        configs[TenderSourceType.EB2B] = TenderMonitoringConfig(
            source_type=TenderSourceType.EB2B,
            extractor_class=Eb2bTenderExtractor
        )
        configs[TenderSourceType.TED] = TenderMonitoringConfig(
                    source_type=TenderSourceType.TED,
                    extractor_class=TedTenderExtractor
                )
        configs[TenderSourceType.TED_GERMANY] = TenderMonitoringConfig(
            source_type=TenderSourceType.TED_GERMANY,
            extractor_class=GermanTedTenderExtractor
        )
        configs[TenderSourceType.TED_FRANCE] = TenderMonitoringConfig(
            source_type=TenderSourceType.TED_FRANCE,
            extractor_class=FrenchTedTenderExtractor
        )
        configs[TenderSourceType.TED_SPAIN] = TenderMonitoringConfig(
            source_type=TenderSourceType.TED_SPAIN,
            extractor_class=SpainTedTenderExtractor
        )
        configs[TenderSourceType.TED_ITALY] = TenderMonitoringConfig(
            source_type=TenderSourceType.TED_ITALY,
            extractor_class=ItalyTedTenderExtractor
        )
        configs[TenderSourceType.TED_BELGIUM] = TenderMonitoringConfig(
            source_type=TenderSourceType.TED_BELGIUM,
            extractor_class=BelgiumTedTenderExtractor
        )
        configs[TenderSourceType.TED_NETHERLANDS] = TenderMonitoringConfig(
            source_type=TenderSourceType.TED_NETHERLANDS,
            extractor_class=NetherlandsTedTenderExtractor
        )
        configs[TenderSourceType.TED_SWEDEN] = TenderMonitoringConfig(
            source_type=TenderSourceType.TED_SWEDEN,
            extractor_class=SwedenTedTenderExtractor
        )
        configs[TenderSourceType.TED_CZECHIA] = TenderMonitoringConfig(
            source_type=TenderSourceType.TED_CZECHIA,
            extractor_class=CzechiaTedTenderExtractor
        )
        configs[TenderSourceType.TED_AUSTRIA] = TenderMonitoringConfig(
            source_type=TenderSourceType.TED_AUSTRIA,
            extractor_class=AustriaTedTenderExtractor
        )
        configs[TenderSourceType.TED_PORTUGAL] = TenderMonitoringConfig(
            source_type=TenderSourceType.TED_PORTUGAL,
            extractor_class=PortugalTedTenderExtractor
        )
        configs[TenderSourceType.TED_DENMARK] = TenderMonitoringConfig(
            source_type=TenderSourceType.TED_DENMARK,
            extractor_class=DenmarkTedTenderExtractor
        )
        configs[TenderSourceType.TED_FINLAND] = TenderMonitoringConfig(
            source_type=TenderSourceType.TED_FINLAND,
            extractor_class=FinlandTedTenderExtractor
        )
        configs[TenderSourceType.TED_NORWAY] = TenderMonitoringConfig(
            source_type=TenderSourceType.TED_NORWAY,
            extractor_class=NorwayTedTenderExtractor
        )
        configs[TenderSourceType.TED_IRELAND] = TenderMonitoringConfig(
            source_type=TenderSourceType.TED_IRELAND,
            extractor_class=IrelandTedTenderExtractor
        )
        configs[TenderSourceType.TED_GREECE] = TenderMonitoringConfig(
            source_type=TenderSourceType.TED_GREECE,
            extractor_class=GreeceTedTenderExtractor
        )
        configs[TenderSourceType.TED_HUNGARY] = TenderMonitoringConfig(
            source_type=TenderSourceType.TED_HUNGARY,
            extractor_class=HungaryTedTenderExtractor
        )
        configs[TenderSourceType.TED_SLOVAKIA] = TenderMonitoringConfig(
            source_type=TenderSourceType.TED_SLOVAKIA,
            extractor_class=SlovakiaTedTenderExtractor
        )
        configs[TenderSourceType.TED_SLOVENIA] = TenderMonitoringConfig(
            source_type=TenderSourceType.TED_SLOVENIA,
            extractor_class=SloveniaTedTenderExtractor
        )
        configs[TenderSourceType.TED_CROATIA] = TenderMonitoringConfig(
            source_type=TenderSourceType.TED_CROATIA,
            extractor_class=CroatiaTedTenderExtractor
        )
        configs[TenderSourceType.TED_ROMANIA] = TenderMonitoringConfig(
            source_type=TenderSourceType.TED_ROMANIA,
            extractor_class=RomaniaTedTenderExtractor
        )
        configs[TenderSourceType.TED_BULGARIA] = TenderMonitoringConfig(
            source_type=TenderSourceType.TED_BULGARIA,
            extractor_class=BulgariaTedTenderExtractor
        )
        configs[TenderSourceType.TED_ESTONIA] = TenderMonitoringConfig(
            source_type=TenderSourceType.TED_ESTONIA,
            extractor_class=EstoniaTedTenderExtractor
        )
        configs[TenderSourceType.TED_LATVIA] = TenderMonitoringConfig(
            source_type=TenderSourceType.TED_LATVIA,
            extractor_class=LatviaTedTenderExtractor
        )
        configs[TenderSourceType.TED_LITHUANIA] = TenderMonitoringConfig(
            source_type=TenderSourceType.TED_LITHUANIA,
            extractor_class=LithuaniaTedTenderExtractor
        )
        configs[TenderSourceType.TED_LUXEMBOURG] = TenderMonitoringConfig(
            source_type=TenderSourceType.TED_LUXEMBOURG,
            extractor_class=LuxembourgTedTenderExtractor
        )
        configs[TenderSourceType.PLATFORMAZAKUPOWA] = TenderMonitoringConfig(
            source_type=TenderSourceType.PLATFORMAZAKUPOWA,
            extractor_class=PlatformaZakupowaTenderExtractor
        )
        configs[TenderSourceType.EPROPUBLICO_MAIN] = TenderMonitoringConfig(
            source_type=TenderSourceType.EPROPUBLICO_MAIN,
            extractor_class=EproPublicoMainTenderExtractor
        )
        configs[TenderSourceType.BAZAKONKURENCYJNOSCI] = TenderMonitoringConfig(
            source_type=TenderSourceType.BAZAKONKURENCYJNOSCI,
            extractor_class=BazaKonkurencyjnosciTenderExtractor
        )
        configs[TenderSourceType.SMARTPZP] = TenderMonitoringConfig(
            source_type=TenderSourceType.SMARTPZP,
            extractor_class=SmartPZPTenderExtractor,
        )
        configs[TenderSourceType.EZAMAWIAJACY] = TenderMonitoringConfig(
            source_type=TenderSourceType.EZAMAWIAJACY,
            extractor_class=EzamawiajacyTenderExtractor
        )
        configs[TenderSourceType.LOGINTRADE] = TenderMonitoringConfig(
            source_type=TenderSourceType.LOGINTRADE,
            extractor_class=LoginTradeExtractor
        )
        return configs
    
    def create_monitoring_service(self, source_type: TenderSourceType) -> TenderMonitoringService:
        config = self.monitoring_config[source_type]
        extractor = config.extractor_class()
        return TenderMonitoringService(
            tender_source=extractor,
            tender_source_type=source_type,
            is_date_str=config.is_date_str
        )
    
    def get_active_monitoring_sources(self) -> list[TenderSourceType]:
        """Get list of currently active monitoring types."""
        return list(self.monitoring_config.keys())