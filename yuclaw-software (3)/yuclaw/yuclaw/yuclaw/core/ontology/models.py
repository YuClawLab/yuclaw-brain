"""yuclaw/core/ontology/models.py — Financial object definitions."""
from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ValidationStatus(str, Enum):
    IDEA               = "Idea"
    EVIDENCE_EXTRACTED = "Evidence_Extracted"
    RED_TEAM_TESTED    = "Red_Team_Tested"
    REGIME_VALIDATED   = "Regime_Validated"
    POLICY_CLEARED     = "Policy_Cleared"
    APPROVED           = "Approved_for_Execution"
    SEALED             = "Version_Sealed"
    REJECTED           = "Red_Team_Rejected"


class FinancialObject(BaseModel):
    name: str
    aliases: list[str] = Field(default_factory=list)
    definition: str
    mathematical_formula: Optional[str] = None
    unit: Optional[str] = None
    data_sources: list[str] = Field(default_factory=list)
    related_objects: list[str] = Field(default_factory=list)
    failure_modes: list[str] = Field(default_factory=list)
    typical_range: Optional[str] = None


class EvidenceNode(BaseModel):
    claim: str
    source_doc_id: str
    page_number: int
    paragraph_hash: str
    extraction_timestamp: str
    model_version: str
    confidence: float
    ontology_tags: list[str] = Field(default_factory=list)


METRIC_REGISTRY: dict[str, FinancialObject] = {
    "revenue": FinancialObject(
        name="Revenue", aliases=["sales","top_line","net_revenue"],
        definition="Total income from business activities before expenses",
        unit="USD", data_sources=["10-K","10-Q","earnings_release"],
        related_objects=["gross_profit","ebitda"],
        failure_modes=["channel_stuffing","revenue_recognition_manipulation"],
    ),
    "ebitda": FinancialObject(
        name="EBITDA", aliases=["operating_earnings","core_earnings"],
        definition="Earnings Before Interest, Taxes, Depreciation, and Amortization",
        mathematical_formula="Net Income + Interest + Taxes + D&A",
        unit="USD", data_sources=["10-K","10-Q"],
        related_objects=["ebit","fcf","ev_ebitda"],
        typical_range="Margin 10-40% industrials; 50-80% software",
        failure_modes=["excludes capex — misleading for capital-intensive businesses"],
    ),
    "fcf": FinancialObject(
        name="Free Cash Flow", aliases=["free_cash_flow","levered_fcf"],
        definition="Cash generated after capital expenditures",
        mathematical_formula="Operating Cash Flow - Capex",
        unit="USD", data_sources=["cash_flow_statement","10-K"],
        related_objects=["ebitda","capex","working_capital"],
        failure_modes=["capex timing manipulation","working capital release masking decline"],
    ),
    "roic": FinancialObject(
        name="Return on Invested Capital", aliases=["roic","return_on_capital"],
        definition="After-tax operating profit as percentage of invested capital",
        mathematical_formula="NOPAT / (Total Equity + Total Debt - Cash)",
        unit="%", data_sources=["balance_sheet","income_statement"],
        related_objects=["wacc","ebit","invested_capital"],
        typical_range="ROIC > WACC = value creation",
        failure_modes=["goodwill distorts after acquisitions"],
    ),
    "gross_margin": FinancialObject(
        name="Gross Margin", aliases=["gross_profit_margin","gp_margin"],
        definition="Gross profit as percentage of revenue",
        mathematical_formula="(Revenue - COGS) / Revenue",
        unit="%", data_sources=["income_statement"],
        related_objects=["revenue","operating_margin","ebitda_margin"],
        typical_range="Software 70-85%; Hardware 35-55%; Retail 25-45%",
    ),
    "cet1": FinancialObject(
        name="CET1 Ratio", aliases=["cet1","tier1_capital"],
        definition="Common equity tier 1 as % of risk-weighted assets — bank capital measure",
        mathematical_formula="Common Equity Tier 1 / Risk-Weighted Assets",
        unit="%", data_sources=["bank_10-K","regulatory_filing"],
        related_objects=["nim","rwa","leverage_ratio"],
        typical_range="Regulatory minimum 4.5%; well-capitalized >10%",
    ),
    "nim": FinancialObject(
        name="Net Interest Margin", aliases=["net_interest_margin"],
        definition="Net interest income as % of earning assets — core bank profitability",
        mathematical_formula="(Interest Income - Interest Expense) / Avg Earning Assets",
        unit="%", data_sources=["bank_10-K","bank_10-Q"],
        related_objects=["cet1","deposit_cost","rate_sensitivity"],
    ),
    "ev_ebitda": FinancialObject(
        name="EV/EBITDA", aliases=["enterprise_value_to_ebitda"],
        definition="Enterprise value relative to EBITDA — primary valuation multiple",
        mathematical_formula="Enterprise Value / LTM EBITDA",
        unit="x", data_sources=["market_data","financial_statements"],
        related_objects=["ebitda","enterprise_value","pe_ratio"],
        typical_range="7-14x industrials; 15-25x technology; 4-8x utilities",
        failure_modes=["meaningless for negative EBITDA","distorted by recent M&A"],
    ),
    "operating_margin": FinancialObject(
        name="Operating Margin", aliases=["ebit_margin","op_margin"],
        definition="Operating income as percentage of revenue",
        mathematical_formula="EBIT / Revenue",
        unit="%", data_sources=["income_statement"],
        related_objects=["gross_margin","ebitda","revenue"],
    ),
    "pe_ratio": FinancialObject(
        name="P/E Ratio", aliases=["pe","price_to_earnings"],
        definition="Share price divided by earnings per share",
        mathematical_formula="Price / EPS",
        unit="x", data_sources=["market_data"],
        related_objects=["eps","ev_ebitda","peg_ratio"],
        failure_modes=["distorted by one-time items","useless for negative earnings"],
    ),
}
