from app.services.serpapi_client import SerpAPIClient


def test_extract_currency_prefers_primary_price_symbol_over_alternative_currency() -> None:
    """
    Regression: SerpAPI may provide `alternative_price.currency` that does NOT match the
    primary `price`/`extracted_price`. We store the numeric amount from `extracted_price`,
    so currency must follow the primary `price` field (symbol) instead of alternative currency.
    """
    client = SerpAPIClient(api_key="test")
    item = {
        "title": "iPhone 17 Pro 24K Rose Gold Edition | Craft by Merlin 256 GB",
        "price": "€2,838.50",
        "extracted_price": 2838.5,
        "alternative_price": {"price": "AED 12,097", "extracted_price": 12097, "currency": "AED"},
    }
    assert client._extract_currency(item, gl="de") == "EUR"


def test_extract_currency_uses_alternative_currency_only_as_last_resort() -> None:
    client = SerpAPIClient(api_key="test")
    item = {
        "title": "Some product",
        "price": "12,097",  # no symbol
        "extracted_price": 12097,
        "alternative_price": {"price": "AED 12,097", "extracted_price": 12097, "currency": "AED"},
    }
    # No item.currency, no symbol in item.price; gl is unknown → fall back to alternative.
    assert client._extract_currency(item, gl="xx") == "AED"


def test_extract_currency_prefers_direct_currency_field() -> None:
    client = SerpAPIClient(api_key="test")
    item = {"title": "Some product", "price": "€1,229", "extracted_price": 1229, "currency": "USD"}
    assert client._extract_currency(item, gl="de") == "USD"

