from dataclasses import dataclass
from typing import Dict, List, Type, Optional
import logging

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
from minerva.tasks.sources.vergabe.extract_tender import DTVPLikeTenderExtractor
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
from minerva.tasks.sources.vergapeplatforms.extract_tender import VergabePlatformsTenderExtractor

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
        configs[TenderSourceType.DTVP_LIKE] = TenderSourceConfig(
            source_type=TenderSourceType.DTVP_LIKE,
            extractor_class=DTVPLikeTenderExtractor
        )
        configs[TenderSourceType.VERGABEPLATFORMS] = TenderSourceConfig(
            source_type=TenderSourceType.VERGABEPLATFORMS,
            extractor_class=VergabePlatformsTenderExtractor
        )
        configs[TenderSourceType.TED] = TenderSourceConfig(
                    source_type=TenderSourceType.TED,
                    extractor_class=TedTenderExtractor
        )
        configs[TenderSourceType.TED_GERMANY] = TenderSourceConfig(
            source_type=TenderSourceType.TED_GERMANY,
            extractor_class=GermanTedTenderExtractor
        )
        configs[TenderSourceType.TED_FRANCE] = TenderSourceConfig(
            source_type=TenderSourceType.TED_FRANCE,
            extractor_class=FrenchTedTenderExtractor
        )
        configs[TenderSourceType.TED_SPAIN] = TenderSourceConfig(
            source_type=TenderSourceType.TED_SPAIN,
            extractor_class=SpainTedTenderExtractor
        )
        configs[TenderSourceType.TED_ITALY] = TenderSourceConfig(
            source_type=TenderSourceType.TED_ITALY,
            extractor_class=ItalyTedTenderExtractor
        )
        configs[TenderSourceType.TED_BELGIUM] = TenderSourceConfig(
            source_type=TenderSourceType.TED_BELGIUM,
            extractor_class=BelgiumTedTenderExtractor
        )
        configs[TenderSourceType.TED_NETHERLANDS] = TenderSourceConfig(
            source_type=TenderSourceType.TED_NETHERLANDS,
            extractor_class=NetherlandsTedTenderExtractor
        )
        configs[TenderSourceType.TED_SWEDEN] = TenderSourceConfig(
            source_type=TenderSourceType.TED_SWEDEN,
            extractor_class=SwedenTedTenderExtractor
        )
        configs[TenderSourceType.TED_CZECHIA] = TenderSourceConfig(
            source_type=TenderSourceType.TED_CZECHIA,
            extractor_class=CzechiaTedTenderExtractor
        )
        configs[TenderSourceType.TED_AUSTRIA] = TenderSourceConfig(
            source_type=TenderSourceType.TED_AUSTRIA,
            extractor_class=AustriaTedTenderExtractor
        )
        configs[TenderSourceType.TED_PORTUGAL] = TenderSourceConfig(
            source_type=TenderSourceType.TED_PORTUGAL,
            extractor_class=PortugalTedTenderExtractor
        )
        configs[TenderSourceType.TED_DENMARK] = TenderSourceConfig(
            source_type=TenderSourceType.TED_DENMARK,
            extractor_class=DenmarkTedTenderExtractor
        )
        configs[TenderSourceType.TED_FINLAND] = TenderSourceConfig(
            source_type=TenderSourceType.TED_FINLAND,
            extractor_class=FinlandTedTenderExtractor
        )
        configs[TenderSourceType.TED_NORWAY] = TenderSourceConfig(
            source_type=TenderSourceType.TED_NORWAY,
            extractor_class=NorwayTedTenderExtractor
        )
        configs[TenderSourceType.TED_IRELAND] = TenderSourceConfig(
            source_type=TenderSourceType.TED_IRELAND,
            extractor_class=IrelandTedTenderExtractor
        )
        configs[TenderSourceType.TED_GREECE] = TenderSourceConfig(
            source_type=TenderSourceType.TED_GREECE,
            extractor_class=GreeceTedTenderExtractor
        )
        configs[TenderSourceType.TED_HUNGARY] = TenderSourceConfig(
            source_type=TenderSourceType.TED_HUNGARY,
            extractor_class=HungaryTedTenderExtractor
        )
        configs[TenderSourceType.TED_SLOVAKIA] = TenderSourceConfig(
            source_type=TenderSourceType.TED_SLOVAKIA,
            extractor_class=SlovakiaTedTenderExtractor
        )
        configs[TenderSourceType.TED_SLOVENIA] = TenderSourceConfig(
            source_type=TenderSourceType.TED_SLOVENIA,
            extractor_class=SloveniaTedTenderExtractor
        )
        configs[TenderSourceType.TED_CROATIA] = TenderSourceConfig(
            source_type=TenderSourceType.TED_CROATIA,
            extractor_class=CroatiaTedTenderExtractor
        )
        configs[TenderSourceType.TED_ROMANIA] = TenderSourceConfig(
            source_type=TenderSourceType.TED_ROMANIA,
            extractor_class=RomaniaTedTenderExtractor
        )
        configs[TenderSourceType.TED_BULGARIA] = TenderSourceConfig(
            source_type=TenderSourceType.TED_BULGARIA,
            extractor_class=BulgariaTedTenderExtractor
        )
        configs[TenderSourceType.TED_ESTONIA] = TenderSourceConfig(
            source_type=TenderSourceType.TED_ESTONIA,
            extractor_class=EstoniaTedTenderExtractor
        )
        configs[TenderSourceType.TED_LATVIA] = TenderSourceConfig(
            source_type=TenderSourceType.TED_LATVIA,
            extractor_class=LatviaTedTenderExtractor
        )
        configs[TenderSourceType.TED_LITHUANIA] = TenderSourceConfig(
            source_type=TenderSourceType.TED_LITHUANIA,
            extractor_class=LithuaniaTedTenderExtractor
        )
        configs[TenderSourceType.TED_LUXEMBOURG] = TenderSourceConfig(
            source_type=TenderSourceType.TED_LUXEMBOURG,
            extractor_class=LuxembourgTedTenderExtractor
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
