"""Asset universe definitions.

Metadata (name, class, country, sector, currency, liquidity) is static and
versioned here. Prices are *never* stored in this file -- they come from a
MarketDataProvider.

The demo generator parameters (annualised drift / volatility and factor
loading shares) describe how the synthetic series behave in DEMO mode. They are
calibration inputs, not claims about any real security.
"""
from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["AssetMeta", "UNIVERSE", "by_symbol", "symbols_for", "ASSET_CLASSES", "SECTORS"]


@dataclass(frozen=True)
class AssetMeta:
    symbol: str
    name: str
    assetClass: str
    country: str
    sector: str
    currency: str
    liquidity: float                 # 0..1, relative tradability
    dataSource: str
    demoDrift: float = 0.08          # annualised arithmetic mean, demo mode only
    demoVol: float = 0.15            # annualised volatility, demo mode only
    demoLoadings: dict = field(default_factory=dict)   # factor -> share of variance
    notes: str = ""


ASSET_CLASSES = {
    "equity": "Equity",
    "bond": "Fixed Income",
    "gold": "Gold",
    "silver": "Silver",
    "commodity": "Commodity",
    "international_equity": "International Equity",
    "reit": "REIT / InvIT",
    "cash": "Cash / Liquid",
}

SECTORS = [
    "Broad Market", "Banking", "Information Technology", "Pharma", "FMCG",
    "Auto", "Infrastructure", "Government", "Corporate Credit", "Precious Metals",
    "Energy", "Base Metals", "Global", "Real Assets", "Cash",
]

IN = "IN"
US = "US"
GLOBAL = "GLOBAL"

_DEMO = "DemoMarketDataProvider (synthetic)"

UNIVERSE: list[AssetMeta] = [
    # ---------------------------------------------------------------- equity
    AssetMeta("NIFTY50", "Nifty 50", "equity", IN, "Broad Market", "INR", 0.97, _DEMO,
              0.115, 0.16, {"in_equity": 0.82, "global_equity": 0.05}),
    AssetMeta("NIFTYNEXT50", "Nifty Next 50", "equity", IN, "Broad Market", "INR", 0.9, _DEMO,
              0.125, 0.19, {"in_equity": 0.74, "in_sizemid": 0.08, "global_equity": 0.04}),
    AssetMeta("NIFTYMIDCAP150", "Nifty Midcap 150", "equity", IN, "Broad Market", "INR", 0.8, _DEMO,
              0.135, 0.22, {"in_equity": 0.64, "in_sizemid": 0.16}),
    AssetMeta("NIFTYSMALLCAP250", "Nifty Smallcap 250", "equity", IN, "Broad Market", "INR", 0.6, _DEMO,
              0.145, 0.28, {"in_equity": 0.54, "in_sizesmall": 0.24}),
    AssetMeta("NIFTYBANK", "Nifty Bank", "equity", IN, "Banking", "INR", 0.95, _DEMO,
              0.125, 0.21, {"in_equity": 0.60, "sector_bank": 0.26}),
    AssetMeta("NIFTYIT", "Nifty IT", "equity", IN, "Information Technology", "INR", 0.94, _DEMO,
              0.13, 0.20, {"in_equity": 0.44, "sector_it": 0.30, "usdinr": 0.12}),
    AssetMeta("NIFTYPHARMA", "Nifty Pharma", "equity", IN, "Pharma", "INR", 0.9, _DEMO,
              0.115, 0.18, {"in_equity": 0.46, "sector_pharma": 0.28}),
    AssetMeta("NIFTYFMCG", "Nifty FMCG", "equity", IN, "FMCG", "INR", 0.9, _DEMO,
              0.105, 0.14, {"in_equity": 0.52, "sector_fmcg": 0.26}),
    AssetMeta("NIFTYAUTO", "Nifty Auto", "equity", IN, "Auto", "INR", 0.9, _DEMO,
              0.125, 0.21, {"in_equity": 0.54, "sector_auto": 0.26}),
    AssetMeta("NIFTYINFRA", "Nifty Infrastructure", "equity", IN, "Infrastructure", "INR", 0.85, _DEMO,
              0.115, 0.22, {"in_equity": 0.58, "sector_infra": 0.24}),
    # ------------------------------------------------------------ fixed income
    AssetMeta("GSEC10Y", "Indian 10Y Government Bond", "bond", IN, "Government", "INR", 0.85, _DEMO,
              0.072, 0.07, {"rates": 0.80, "credit": 0.02}),
    AssetMeta("GSEC5Y", "Indian 5Y Government Bond", "bond", IN, "Government", "INR", 0.82, _DEMO,
              0.068, 0.045, {"rates": 0.72, "credit": 0.01}),
    AssetMeta("CORPBOND", "Indian Corporate Bond Index", "bond", IN, "Corporate Credit", "INR", 0.55, _DEMO,
              0.079, 0.055, {"rates": 0.54, "credit": 0.30}),
    AssetMeta("LIQUIDFUND", "Liquid / Money Market Fund", "bond", IN, "Cash", "INR", 0.9, _DEMO,
              0.062, 0.006, {"rates": 0.10}),
    # ------------------------------------------------------------------- cash
    AssetMeta("CASH", "Cash (overnight / T-bill proxy)", "cash", IN, "Cash", "INR", 1.0, _DEMO,
              0.055, 0.002, {}),
    # -------------------------------------------------------- precious metals
    AssetMeta("GOLD", "Gold (MCX / Gold ETF, INR)", "gold", IN, "Precious Metals", "INR", 0.92, _DEMO,
              0.095, 0.14, {"gold": 0.72, "usdinr": 0.16}),
    AssetMeta("SILVER", "Silver (MCX / Silver ETF, INR)", "silver", IN, "Precious Metals", "INR", 0.8, _DEMO,
              0.1, 0.23, {"silver": 0.52, "gold": 0.18, "commodity": 0.12}),
    # ------------------------------------------------------------ commodities
    AssetMeta("CRUDE", "Crude Oil (MCX, INR)", "commodity", IN, "Energy", "INR", 0.75, _DEMO,
              0.05, 0.32, {"commodity": 0.42, "crude": 0.30}),
    AssetMeta("COPPER", "Copper (MCX, INR)", "commodity", IN, "Base Metals", "INR", 0.6, _DEMO,
              0.06, 0.24, {"commodity": 0.44, "copper": 0.24}),
    AssetMeta("NATGAS", "Natural Gas (MCX, INR)", "commodity", IN, "Energy", "INR", 0.55, _DEMO,
              0.03, 0.36, {"commodity": 0.28, "natgas": 0.36}),
    # ----------------------------------------------------- international equity
    AssetMeta("US_EQUITY", "S&P 500 (INR converted)", "international_equity", US, "Global", "INR", 0.9, _DEMO,
              0.115, 0.17, {"global_equity": 0.60, "us_tech": 0.10, "usdinr": 0.18}),
    AssetMeta("US_TECH", "Nasdaq 100 (INR converted)", "international_equity", US, "Global", "INR", 0.85, _DEMO,
              0.145, 0.23, {"global_equity": 0.38, "us_tech": 0.34, "usdinr": 0.16}),
    AssetMeta("GLOBAL_ETF", "MSCI World ex-India (INR)", "international_equity", GLOBAL, "Global", "INR", 0.85, _DEMO,
              0.095, 0.16, {"global_equity": 0.68, "usdinr": 0.17}),
    AssetMeta("EM_EQUITY", "MSCI Emerging Markets (INR)", "international_equity", GLOBAL, "Global", "INR", 0.75, _DEMO,
              0.085, 0.20, {"global_equity": 0.44, "em_equity": 0.30, "usdinr": 0.12}),
    # ------------------------------------------------------------ alternatives
    AssetMeta("IND_REIT", "Indian REITs (composite)", "reit", IN, "Real Assets", "INR", 0.5, _DEMO,
              0.095, 0.17, {"in_equity": 0.28, "reit": 0.40, "rates": 0.12}),
    AssetMeta("INVIT", "Indian InvITs (composite)", "reit", IN, "Real Assets", "INR", 0.4, _DEMO,
              0.09, 0.13, {"in_equity": 0.20, "reit": 0.30, "rates": 0.26}),
]

_BY_SYMBOL: dict[str, AssetMeta] = {a.symbol: a for a in UNIVERSE}


def by_symbol(symbol: str) -> AssetMeta:
    return _BY_SYMBOL[symbol]


def symbols_for(asset_class: str | None = None, country: str | None = None) -> list[str]:
    out = UNIVERSE
    if asset_class:
        out = [a for a in out if a.assetClass == asset_class]
    if country:
        out = [a for a in out if a.country == country]
    return [a.symbol for a in out]


def class_map() -> dict[str, str]:
    return {a.symbol: a.assetClass for a in UNIVERSE}


def sector_map() -> dict[str, str]:
    return {a.symbol: a.sector for a in UNIVERSE}


def liquidity_map() -> dict[str, float]:
    return {a.symbol: a.liquidity for a in UNIVERSE}
