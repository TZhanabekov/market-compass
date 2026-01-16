"""Tests for attribute extraction from product titles."""

import pytest

from app.services.attribute_extractor import (
    ExtractionConfidence,
    extract_attributes,
    extract_color,
    extract_condition,
    extract_model,
    extract_storage,
    filter_non_iphone_products,
    is_iphone_product,
)


class TestExtractModel:
    """Tests for model extraction."""

    def test_iphone_16_pro_max(self):
        assert extract_model("Apple iPhone 16 Pro Max 256GB Black") == "iphone-16-pro-max"
        assert extract_model("iPhone 16 Pro Max") == "iphone-16-pro-max"
        assert extract_model("IPHONE16PROMAX 512GB") == "iphone-16-pro-max"

    def test_iphone_16_pro(self):
        assert extract_model("Apple iPhone 16 Pro 256GB") == "iphone-16-pro"
        assert extract_model("iPhone 16Pro Black Titanium") == "iphone-16-pro"

    def test_iphone_16_plus(self):
        assert extract_model("Apple iPhone 16 Plus 128GB Pink") == "iphone-16-plus"

    def test_iphone_16(self):
        assert extract_model("Apple iPhone 16 128GB Blue") == "iphone-16"

    def test_iphone_15_series(self):
        assert extract_model("Apple iPhone 15 Pro Max 1TB") == "iphone-15-pro-max"
        assert extract_model("iPhone 15 Pro 256GB") == "iphone-15-pro"
        assert extract_model("iPhone 15 Plus") == "iphone-15-plus"
        assert extract_model("iPhone 15 128GB") == "iphone-15"

    def test_no_model(self):
        assert extract_model("Samsung Galaxy S24 Ultra") is None
        assert extract_model("iPhone Case Cover") is None


class TestExtractStorage:
    """Tests for storage extraction."""

    def test_valid_storages(self):
        assert extract_storage("iPhone 16 Pro 128GB") == "128gb"
        assert extract_storage("iPhone 16 Pro 256 GB Black") == "256gb"
        assert extract_storage("iPhone 16 Pro Max 512GB") == "512gb"
        assert extract_storage("iPhone 16 Pro 1TB Titanium") == "1tb"

    def test_invalid_storages_ignored(self):
        # 64GB is not a valid iPhone 16 storage
        assert extract_storage("Some device 64GB") is None
        # 2TB is not a valid iPhone storage
        assert extract_storage("Some device 2TB") is None

    def test_no_storage(self):
        assert extract_storage("iPhone 16 Pro Black") is None


class TestExtractColor:
    """Tests for color extraction."""

    def test_titanium_colors(self):
        assert extract_color("iPhone 16 Pro Natural Titanium") == "natural"
        assert extract_color("iPhone 16 Pro White Titanium") == "white"
        assert extract_color("iPhone 16 Pro Black Titanium") == "black"
        assert extract_color("iPhone 16 Pro Blue Titanium") == "blue"
        assert extract_color("iPhone 16 Pro Desert Titanium") == "desert"

    def test_space_colors(self):
        assert extract_color("iPhone 15 Space Black") == "black"
        assert extract_color("iPhone 14 Space Gray") == "gray"
        assert extract_color("iPhone 14 Space Grey") == "gray"

    def test_basic_colors(self):
        assert extract_color("iPhone 16 Black") == "black"
        assert extract_color("iPhone 16 White") == "white"
        assert extract_color("iPhone 16 Blue") == "blue"
        assert extract_color("iPhone 16 Pink") == "pink"

    def test_french_colors(self):
        assert extract_color("iPhone 16 Noir") == "black"
        assert extract_color("iPhone 16 Blanc") == "white"

    def test_no_color(self):
        assert extract_color("iPhone 16 Pro 256GB") is None


class TestExtractCondition:
    """Tests for condition extraction."""

    def test_new_conditions(self):
        assert extract_condition("iPhone 16 Pro New") == "new"
        assert extract_condition("iPhone 16 Pro Brand New Sealed") == "new"
        assert extract_condition("iPhone 16 Pro BNIB") == "new"

    def test_refurbished_conditions(self):
        assert extract_condition("iPhone 16 Pro Refurbished") == "refurbished"
        assert extract_condition("iPhone 16 Pro Renewed") == "refurbished"
        assert extract_condition("iPhone 16 Pro Certified Pre-Owned") == "refurbished"

    def test_used_conditions(self):
        assert extract_condition("iPhone 16 Pro Used") == "used"
        assert extract_condition("iPhone 16 Pro Pre-Owned") == "used"
        assert extract_condition("iPhone 16 Pro Second Hand") == "used"

    def test_default_to_new(self):
        # If no condition specified, default to "new"
        assert extract_condition("iPhone 16 Pro 256GB Black") == "new"


class TestExtractAttributes:
    """Tests for full attribute extraction."""

    def test_high_confidence(self):
        result = extract_attributes("Apple iPhone 16 Pro Max 256GB Black Titanium New")
        assert result.confidence == ExtractionConfidence.HIGH
        assert result.attributes["model"] == "iphone-16-pro-max"
        assert result.attributes["storage"] == "256gb"
        assert result.attributes["color"] == "black"
        assert result.attributes["condition"] == "new"

    def test_medium_confidence_missing_color(self):
        result = extract_attributes("Apple iPhone 16 Pro 512GB Sealed")
        assert result.confidence == ExtractionConfidence.MEDIUM
        assert result.attributes["model"] == "iphone-16-pro"
        assert result.attributes["storage"] == "512gb"
        assert "color" not in result.attributes or result.attributes.get("color") is None

    def test_medium_confidence_missing_storage(self):
        result = extract_attributes("Apple iPhone 16 Pro Black")
        assert result.confidence == ExtractionConfidence.MEDIUM
        assert result.attributes["model"] == "iphone-16-pro"
        assert result.attributes["color"] == "black"

    def test_low_confidence_no_model(self):
        result = extract_attributes("256GB Black Phone Case")
        assert result.confidence == ExtractionConfidence.LOW

    def test_preserves_raw_title(self):
        title = "Apple iPhone 16 Pro Max 256GB Desert Titanium"
        result = extract_attributes(title)
        assert result.raw_title == title


class TestIsIphoneProduct:
    """Tests for iPhone detection."""

    def test_is_iphone(self):
        assert is_iphone_product("Apple iPhone 16 Pro") is True
        assert is_iphone_product("IPHONE 16") is True
        assert is_iphone_product("New iPhone 15 Pro Max") is True

    def test_not_iphone(self):
        assert is_iphone_product("Samsung Galaxy S24") is False
        assert is_iphone_product("iPad Pro 2024") is False


class TestFilterNonIphoneProducts:
    """Tests for filtering accessories and non-iPhone products."""

    def test_filters_cases(self):
        assert filter_non_iphone_products("iPhone 16 Pro Case Cover") is True
        assert filter_non_iphone_products("Leather case for iPhone") is True

    def test_filters_screen_protectors(self):
        assert filter_non_iphone_products("iPhone 16 Screen Protector") is True
        assert filter_non_iphone_products("Tempered Glass for iPhone") is True

    def test_filters_accessories(self):
        assert filter_non_iphone_products("iPhone Charger Cable") is True
        assert filter_non_iphone_products("MagSafe Battery Pack") is True
        assert filter_non_iphone_products("AirPods Pro 2") is True

    def test_allows_actual_iphones(self):
        assert filter_non_iphone_products("Apple iPhone 16 Pro Max 256GB") is False
        assert filter_non_iphone_products("iPhone 16 Pro Black Titanium") is False
