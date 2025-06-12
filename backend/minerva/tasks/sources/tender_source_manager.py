from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Type, Optional
import logging

from minerva.core.services.vectorstore.pinecone.upsert import EmbeddingConfig
from minerva.tasks.services.tender_insert_service import TenderInsertConfig, TenderInsertService, GenericTenderAdapter
from minerva.tasks.sources.bazakonkurencyjnosci.extract_tenders import BazaKonkurencyjnosciTenderExtractor
from minerva.tasks.sources.eb2b.extract_tenders import Eb2bTenderExtractor
from minerva.tasks.sources.egospodarka.extract_tenders import EGospodarkaTenderExtractor
from minerva.tasks.sources.epropuplico_ogloszenia.extract_tenders import EproPublicoMainTenderExtractor
from minerva.tasks.sources.ezamawiajacy.extract_tenders import EzamawiajacyTenderExtractor
from minerva.tasks.sources.ezamowienia.extract_tenders import TenderExtractor
from minerva.tasks.sources.logintrade.extract_tenders import LoginTradeExtractor
from minerva.tasks.sources.orlenconnect.extract_tenders import OrlenConnectTenderExtractor
from minerva.tasks.sources.pge.extract_tenders import PGETenderExtractor
from minerva.tasks.sources.platformazakupowa.extract_tenders import PlatformaZakupowaTenderExtractor
from minerva.tasks.sources.smartpzp.extract_tenders import SmartPZPTenderExtractor
from minerva.tasks.sources.source_types import TenderSourceType
from minerva.tasks.sources.tedeuropa.extract_tenders import TedTenderExtractor
from minerva.tasks.sources.tedgermany.extract_tenders import GermanTedTenderExtractor

logger = logging.getLogger(__name__)

@dataclass
class TenderSourceConfig:
    source_type: TenderSourceType
    extractor_class: Type
    organization_config: Optional[dict] = None


class TenderSourceManager:
    """Manages the configuration and initialization of tender sources."""
    
    def __init__(self, config: TenderInsertConfig):
        self.config = config
        self.source_configs = self._initialize_source_configs()

    def _initialize_source_configs(self) -> Dict[TenderSourceType, TenderSourceConfig]:
        """Define all available tender sources and their configurations."""
        configs = {}

        # Add basic sources
        configs[TenderSourceType.EZAMOWIENIA] = TenderSourceConfig(
            source_type=TenderSourceType.EZAMOWIENIA,
            extractor_class=TenderExtractor
        )
        configs[TenderSourceType.EB2B] = TenderSourceConfig(
            source_type=TenderSourceType.EB2B,
            extractor_class=Eb2bTenderExtractor
        )
        configs[TenderSourceType.TED] = TenderSourceConfig(
            source_type=TenderSourceType.TED,
            extractor_class=TedTenderExtractor
        )
        configs[TenderSourceType.TED_GERMANY] = TenderSourceConfig(
            source_type=TenderSourceType.TED_GERMANY,
            extractor_class=GermanTedTenderExtractor
        )
        configs[TenderSourceType.PLATFORMAZAKUPOWA] = TenderSourceConfig(
            source_type=TenderSourceType.PLATFORMAZAKUPOWA,
            extractor_class=PlatformaZakupowaTenderExtractor
        )
        configs[TenderSourceType.EGOSPODARKA] = TenderSourceConfig(
            source_type=TenderSourceType.EGOSPODARKA,
            extractor_class=EGospodarkaTenderExtractor
        )
        configs[TenderSourceType.SMARTPZP] = TenderSourceConfig(
            source_type=TenderSourceType.SMARTPZP,
            extractor_class=SmartPZPTenderExtractor,
        )
        configs[TenderSourceType.EPROPUBLICO_MAIN] = TenderSourceConfig(
            source_type=TenderSourceType.EPROPUBLICO_MAIN,
            extractor_class=EproPublicoMainTenderExtractor
        )
        configs[TenderSourceType.EZAMAWIAJACY] = TenderSourceConfig(
            source_type=TenderSourceType.EZAMAWIAJACY,
            extractor_class=EzamawiajacyTenderExtractor
        )
        configs[TenderSourceType.LOGINTRADE] = TenderSourceConfig(
            source_type=TenderSourceType.LOGINTRADE,
            extractor_class=LoginTradeExtractor
        )
        configs[TenderSourceType.BAZAKONKURENCYJNOSCI] = TenderSourceConfig(
            source_type=TenderSourceType.BAZAKONKURENCYJNOSCI,
            extractor_class=BazaKonkurencyjnosciTenderExtractor
        )
        configs[TenderSourceType.ORLENCONNECT] = TenderSourceConfig(
            source_type=TenderSourceType.ORLENCONNECT,
            extractor_class=OrlenConnectTenderExtractor
        )
        configs[TenderSourceType.PGE] = TenderSourceConfig(
            source_type=TenderSourceType.PGE,
            extractor_class=PGETenderExtractor
        )
        # Add all ezamawiajacy organizations
        # for source_type in EzamawiajacyConfig.ORGANIZATIONS.keys():
        #     configs[source_type] = TenderSourceConfig(
        #         source_type=source_type,
        #         extractor_class=EzamawiajacyTenderExtractor,
        #         organization_config=EzamawiajacyConfig.get_config(source_type)
        #     )

        # Add all epropublico organizations
        # for source_type in EproPublicoConfig.ORGANIZATIONS.keys():
        #     configs[source_type] = TenderSourceConfig(
        #         source_type=source_type,
        #         extractor_class=EproPublicoTenderExtractor,
        #         organization_config=EproPublicoConfig.get_config(source_type)
        #     )

        return configs

    def create_tender_insert_service(self, source_type: TenderSourceType) -> TenderInsertService:
        """Create a TenderInsertService for storing tender data in both Pinecone and Elasticsearch."""
        config = self.source_configs[source_type]
        
        if config.organization_config:
            extractor = config.extractor_class(**config.organization_config)
        else:
            extractor = config.extractor_class()

        return TenderInsertService(
            config=self.config,
            tender_source=extractor,
            tender_adapter=GenericTenderAdapter()
        )

    def create_embedding_service(self, source_type: TenderSourceType) -> TenderInsertService:
        """Legacy method for backward compatibility. Use create_tender_insert_service instead."""
        logger.warning("create_embedding_service is deprecated, use create_tender_insert_service instead")
        return self.create_tender_insert_service(source_type)

    def get_active_sources(self) -> List[TenderSourceType]:
        """Get list of currently active source types."""
        return list(self.source_configs.keys())