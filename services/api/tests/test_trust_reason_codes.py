from app.services.trust import MerchantTier, TrustFactors, calculate_trust_score_with_reasons


def test_trust_reason_codes_include_tier_and_adjustments() -> None:
    score, reasons = calculate_trust_score_with_reasons(
        TrustFactors(
            merchant_tier=MerchantTier.UNKNOWN,
            has_shipping_info=False,
            has_warranty_info=False,
            has_return_policy=False,
            price_within_expected_range=False,
            verified_stock=True,
            has_physical_address=True,
        )
    )
    assert isinstance(score, int)
    assert "TIER_UNKNOWN" in reasons
    assert "MISSING_SHIPPING" in reasons
    assert "MISSING_WARRANTY" in reasons
    assert "MISSING_RETURN_POLICY" in reasons
    assert "PRICE_ANOMALY" in reasons
    assert "VERIFIED_STOCK" in reasons
    assert "HAS_PHYSICAL_ADDRESS" in reasons

