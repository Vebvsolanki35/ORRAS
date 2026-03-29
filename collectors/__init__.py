"""
collectors — package of individual data-source collector modules.

Exports all collector classes and the orchestrator for convenient import.
"""

from collectors.cloudflare import CloudflareRadarCollector
from collectors.gdelt import GDELTCollector
from collectors.nasa_firms import NASAFIRMSCollector
from collectors.newsapi import NewsAPICollector
from collectors.opensky import OpenSkyCollector
from collectors.orchestrator import DataCollectionOrchestrator

__all__ = [
    "NewsAPICollector",
    "GDELTCollector",
    "OpenSkyCollector",
    "NASAFIRMSCollector",
    "CloudflareRadarCollector",
    "DataCollectionOrchestrator",
]
