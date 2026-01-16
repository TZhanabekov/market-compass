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

    def test_iphone_17_series(self):
        """Test iPhone 17 series (2025)."""
        assert extract_model("Apple iPhone 17 Pro Max 512GB") == "iphone-17-pro-max"
        assert extract_model("iPhone 17 Pro 256GB Deep Blue") == "iphone-17-pro"
        assert extract_model("iPhone 17 Air 256GB Silver") == "iphone-17-air"
        assert extract_model("iPhone 17 256GB") == "iphone-17"

    def test_iphone_16e(self):
        """Test iPhone 16e budget model."""
        assert extract_model("iPhone 16e 128GB White") == "iphone-16e"
        assert extract_model("iPhone 16 e 256GB Black") == "iphone-16e"

    def test_iphone_15_series(self):
        assert extract_model("Apple iPhone 15 Pro Max 1TB") == "iphone-15-pro-max"
        assert extract_model("iPhone 15 Pro 256GB") == "iphone-15-pro"
        assert extract_model("iPhone 15 Plus") == "iphone-15-plus"
        assert extract_model("iPhone 15 128GB") == "iphone-15"

    def test_iphone_13_series(self):
        """Test iPhone 13 series."""
        assert extract_model("iPhone 13 Pro Max 256GB") == "iphone-13-pro-max"
        assert extract_model("iPhone 13 Pro 128GB") == "iphone-13-pro"
        assert extract_model("iPhone 13 mini 128GB") == "iphone-13-mini"
        assert extract_model("iPhone 13 128GB") == "iphone-13"

    def test_iphone_se_series(self):
        """Test iPhone SE series."""
        assert extract_model("iPhone SE 3rd Gen 64GB") == "iphone-se-3"
        assert extract_model("iPhone SE 2nd Generation") == "iphone-se-2"
        assert extract_model("iPhone SE 2022 128GB") == "iphone-se-3"
        assert extract_model("iPhone SE 64GB") == "iphone-se"

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

    def test_all_valid_storages(self):
        assert extract_storage("iPhone SE 64GB") == "64gb"
        assert extract_storage("iPhone 17 Pro Max 2TB") == "2tb"

    def test_invalid_storages_ignored(self):
        # 32GB is not a valid modern iPhone storage
        assert extract_storage("Some device 32GB") is None
        # 4TB is not a valid iPhone storage
        assert extract_storage("Some device 4TB") is None

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

    def test_iphone_17_colors(self):
        """Test iPhone 17 Pro colors (2025)."""
        assert extract_color("iPhone 17 Pro Deep Blue") == "deep-blue"
        assert extract_color("iPhone 17 Pro Max Cosmic Orange") == "cosmic-orange"

    def test_iphone_16_colors(self):
        """Test iPhone 16 specific colors."""
        assert extract_color("iPhone 16 Ultramarine") == "ultramarine"
        assert extract_color("iPhone 16 Teal") == "teal"

    def test_midnight_starlight_colors(self):
        """Test Midnight/Starlight colors (iPhone 13/14/SE)."""
        assert extract_color("iPhone 14 Midnight") == "midnight"
        assert extract_color("iPhone 14 Starlight") == "starlight"

    def test_product_red(self):
        """Test Product RED color."""
        assert extract_color("iPhone 14 (PRODUCT)RED") == "red"
        assert extract_color("iPhone 14 Product Red") == "red"

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
