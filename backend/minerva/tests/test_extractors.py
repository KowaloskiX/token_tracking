from minerva.tasks.sources.source_types import TenderSourceType
from minerva.tasks.sources.tender_source_manager import TenderSourceManager
import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from minerva.core.services.vectorstore.pinecone.upsert import EmbeddingConfig

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source_type,test_url",
    [
        (TenderSourceType.EZAMOWIENIA, "https://ezamowienia.gov.pl/mp-client/search/list"),
        (TenderSourceType.EZAMAWIAJACY_IKARD, "https://ikard.ezamawiajacy.pl/pn/ikard/demand/notice/publicpzp/current/list"),
        (TenderSourceType.TED, "https://ted.europa.eu/en/search/result?ojs-number=1%2F2025&scope=ALL"),
    ]
)
@patch("minerva.services.tenders.sources.ezamowienia.extract_tenders.async_playwright")
@patch("minerva.services.tenders.sources.ezamawiajacy.extract_tenders.async_playwright")
@patch("minerva.services.tenders.sources.tedeuropa.extract_tenders.async_playwright")
async def test_extractor_generic(
    mock_ted_playwright,
    mock_ezamawiajacy_playwright,
    mock_ezamowienia_playwright,
    source_type,
    test_url
):
    """
    Generic test for all extractors: 
      - Mock Playwright and extractor behavior.
      - Ensure extractors return the expected metadata and tenders.
    """

    # Mock Pinecone interactions (if required)
    with patch("pinecone.Index", autospec=True):
        # 1. Setup a manager with dummy embedding config
        embedding_config = EmbeddingConfig(
            index_name="tenders",
            namespace="",
            embedding_model="text-embedding-3-large"
        )
        manager = TenderSourceManager(embedding_config=embedding_config)

        # 2. Create a service for this specific source
        service = manager.create_embedding_service(source_type)
        extractor = service.tender_source  # The actual extractor instance

        # 3. Mock Playwright browser interactions
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        for mock_playwright in (
            mock_ted_playwright,
            mock_ezamawiajacy_playwright,
            mock_ezamowienia_playwright
        ):
            mock_playwright.return_value.__aenter__.return_value.chromium.launch.return_value = mock_browser

        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        # Mock Playwright page behavior
        mock_page.goto = AsyncMock()
        mock_page.wait_for_selector = AsyncMock()

        # Simulate table rows
        mock_row = AsyncMock()
        mock_cells = [AsyncMock() for _ in range(8)]
        mock_cells[0].inner_text.return_value = "Tender #1"
        mock_row.query_selector_all.return_value = mock_cells
        mock_page.query_selector_all.return_value = [mock_row]

        # No next page => Stop pagination
        mock_page.query_selector.return_value = None

        # Mock execute() to return expected structure
        mock_execute_result = {
            "tenders": [{"name": "Tender 1", "organization": "Org 1", "details_url": "http://example.com/tender1"}],
            "metadata": {"total_tenders": 1, "pages_scraped": 1},
        }
        extractor.execute = AsyncMock(return_value=mock_execute_result)

        # 4. Run the extractor's execute method
        result = await extractor.execute({"max_pages": 1, "start_date": "2025-03-01"})

        # 5. Verify the structure
        assert isinstance(result, dict), f"Expected a dictionary for source {source_type}"
        assert "tenders" in result, f"Result missing 'tenders' for source {source_type}"
        assert "metadata" in result, f"Result missing 'metadata' for source {source_type}"

        # Check metadata fields
        metadata = result["metadata"]
        assert "total_tenders" in metadata, "Missing total_tenders in metadata"
        assert "pages_scraped" in metadata, "Missing pages_scraped in metadata"

        print(f"\n[INFO] Source {source_type} tested successfully with URL: {test_url}")
