"""
Collectors package - Scraping dati COT
"""

from .cot_scraper import COTScraper
from .data_processor import COTDataProcessor

__all__ = ['COTScraper', 'COTDataProcessor']