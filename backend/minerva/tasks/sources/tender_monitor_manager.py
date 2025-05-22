
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
from minerva.tasks.sources.tedeuropa.extract_tenders import TedTenderExtractor
from minerva.tasks.sources.tedgermany.extract_tenders import GermanTedTenderExtractor


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