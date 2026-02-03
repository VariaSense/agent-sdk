"""Tests for Cost Tracking."""
import pytest
from agent_sdk.observability.cost_tracker import (
    ModelPricing, CostUnit,
)


class TestModelPricing:
    def test_pricing_creation(self):
        pricing = ModelPricing(
            model_id="gpt-4",
            input_price_per_1k=0.03,
            output_price_per_1k=0.06,
        )
        assert pricing.model_id == "gpt-4"

    def test_input_cost_calculation(self):
        pricing = ModelPricing(
            model_id="gpt-4",
            input_price_per_1k=0.03,
            output_price_per_1k=0.06,
        )
        cost = pricing.calculate_input_cost(1000)
        assert cost == 0.03

    def test_output_cost_calculation(self):
        pricing = ModelPricing(
            model_id="gpt-4",
            input_price_per_1k=0.03,
            output_price_per_1k=0.06,
        )
        cost = pricing.calculate_output_cost(1000)
        assert cost == 0.06

    def test_total_cost_calculation(self):
        pricing = ModelPricing(
            model_id="gpt-4",
            input_price_per_1k=0.03,
            output_price_per_1k=0.06,
        )
        cost = pricing.calculate_total_cost(1000, 1000)
        assert cost == 0.09


class TestCostUnit:
    def test_cost_units(self):
        assert CostUnit.TOKENS.value == "tokens"
        assert CostUnit.CHARACTERS.value == "characters"

