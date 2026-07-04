"""
Parser module for the Document Ingestion Pipeline.

Extracts clean text and structured metadata from raw Groww mutual-fund
HTML pages. Strips navigation, footer, ads, scripts and styles, while
preserving key financial data as structured key-value text suitable for
downstream chunking and embedding.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_PROCESSED_DIR = _PROJECT_ROOT / "data" / "processed"


# ---------------------------------------------------------------------------
# CSS-class prefixes used by Groww's React build to identify page sections.
# These are the stable *prefix* part before the hash suffix.
# ---------------------------------------------------------------------------

_SECTION_CLASSES = {
    "fund_details": "fundDetails_fundDetailsContainer",
    "fund_details_item": "fundDetails_gap4",
    "investment_objective": "investmentObjective_container",
    "benchmark_row": "investmentObjective_benchmarkRow",
    "exit_load_section": "exitLoadStampDutyTax_section__",
    "exit_load_row": "exitLoadStampDutyTax_exitLoadRow",
    "min_investments": "minInvestments_table__",
    "fund_house": "fundHouse_container",
    "fund_house_info_item": "fundHouse_infoItem",
    "fund_management_card": "fundManagement_card__",
    "compare_funds": "compareSimilarFunds_container",
}


# ---------------------------------------------------------------------------
# Helper: find elements by partial CSS class name
# ---------------------------------------------------------------------------

def _find(soup: BeautifulSoup, class_key: str,
          find_all: bool = False) -> Any:
    """Find element(s) by partial CSS class match using _SECTION_CLASSES."""
    prefix = _SECTION_CLASSES.get(class_key, class_key)
    selector = lambda c: c and prefix in str(c)  # noqa: E731
    if find_all:
        return soup.find_all(True, class_=selector)
    return soup.find(True, class_=selector)


# ---------------------------------------------------------------------------
# Metadata extraction helpers
# ---------------------------------------------------------------------------

def _extract_scheme_name(soup: BeautifulSoup) -> str:
    """Extract scheme name from the <h1> tag."""
    h1 = soup.find("h1")
    return h1.get_text(strip=True) if h1 else ""


def _extract_category_and_risk(soup: BeautifulSoup) -> Dict[str, str]:
    """Extract asset type, sub-category and risk level from the header area.

    The Groww header renders as:
        <h1>HDFC Large Cap Fund Direct Growth</h1>
        Equity          ← asset type
        Large Cap       ← sub-category
        Very High Risk  ← risk level
    """
    result = {"asset_type": "", "sub_category": "", "risk_level": ""}

    h1 = soup.find("h1")
    if not h1:
        return result

    # Walk up to the containing div
    parent = h1.parent
    for _ in range(3):
        if parent and parent.parent:
            parent = parent.parent

    if not parent:
        return result

    lines = parent.get_text(separator="\n", strip=True).split("\n")
    # Lines after the H1 text are: asset_type, sub_category, risk_level
    h1_text = h1.get_text(strip=True)
    found_h1 = False
    metadata_lines: List[str] = []
    for line in lines:
        if found_h1 and len(metadata_lines) < 3:
            metadata_lines.append(line.strip())
        if line.strip() == h1_text:
            found_h1 = True

    if len(metadata_lines) >= 1:
        result["asset_type"] = metadata_lines[0]
    if len(metadata_lines) >= 2:
        result["sub_category"] = metadata_lines[1]
    if len(metadata_lines) >= 3:
        result["risk_level"] = metadata_lines[2]

    return result


def _extract_fund_details(soup: BeautifulSoup) -> Dict[str, str]:
    """Extract the key stats strip: NAV, Min SIP, AUM, Expense Ratio, Rating.

    The fundDetails container has direct children (fundDetails_gap4 divs),
    each containing a label → value pair:
        NAV: 03 Jul '26  →  ₹1,234.16
        Min. for SIP     →  ₹100
        Fund size (AUM)  →  ₹37,808.31 Cr
        Expense ratio    →  1.04%
        Rating           →  4
    """
    result: Dict[str, str] = {}

    # Find the container and iterate its direct children only
    container = _find(soup, "fund_details")
    if not container:
        return result

    for item in container.find_all(True, recursive=False):
        # Each item has two sub-children: label div and value div
        sub_children = item.find_all(True, recursive=False)
        if len(sub_children) >= 2:
            label = sub_children[0].get_text(strip=True)
            value = sub_children[1].get_text(strip=True)

            if "NAV" in label:
                result["nav_date"] = label      # e.g. "NAV: 03 Jul '26"
                result["nav_value"] = value     # e.g. "₹1,234.16"
            elif "SIP" in label:
                result["min_sip"] = value
            elif "AUM" in label or "Fund size" in label:
                result["aum"] = value
            elif "expense" in label.lower():
                result["expense_ratio"] = value
            elif "Rating" in label:
                result["rating"] = value

    return result


def _extract_benchmark(soup: BeautifulSoup) -> str:
    """Extract the fund benchmark name."""
    row = _find(soup, "benchmark_row")
    if row:
        text = row.get_text(separator="|", strip=True)
        parts = [p.strip() for p in text.split("|") if p.strip()]
        # Format: "Fund benchmark | NIFTY 100 Total Return Index"
        for i, part in enumerate(parts):
            if "benchmark" in part.lower() and i + 1 < len(parts):
                return parts[i + 1]
    return ""


def _extract_investment_objective(soup: BeautifulSoup) -> str:
    """Extract the About section and investment objective text."""
    container = _find(soup, "investment_objective")
    if not container:
        return ""

    text = container.get_text(separator="\n", strip=True)
    lines = text.split("\n")

    # Skip the heading lines ("About", scheme name) and collect content
    scheme_name = _extract_scheme_name(soup)
    content_lines: List[str] = []
    skip_labels = {"About", "Fund benchmark", "Scheme Information Document(SID)"}

    for line in lines:
        line = line.strip()
        if not line or line in skip_labels:
            continue
        # Skip the scheme name line (same as h1)
        if line == scheme_name:
            continue
        # Skip stray punctuation lines
        if line in {";", ",", ".", ":"}:
            continue
        # Stop before benchmark/SID links
        if "Fund benchmark" in line or "Scheme Information" in line:
            break
        content_lines.append(line)

    return "\n".join(content_lines)


def _extract_exit_load(soup: BeautifulSoup) -> List[str]:
    """Extract exit load information."""
    rows = _find(soup, "exit_load_row", find_all=True)
    exit_loads: List[str] = []
    for row in rows:
        text = row.get_text(separator=" | ", strip=True)
        exit_loads.append(text)
    return exit_loads


def _extract_stamp_duty(soup: BeautifulSoup) -> str:
    """Extract stamp duty information."""
    sections = _find(soup, "exit_load_section", find_all=True)
    for section in sections:
        text = section.get_text(separator="\n", strip=True)
        if "stamp duty" in text.lower() or "Stamp duty" in text:
            # Find the stamp duty value line
            lines = text.split("\n")
            for line in lines:
                if "%" in line and "stamp" not in line.lower():
                    return line.strip()
    return ""


def _extract_min_investments(soup: BeautifulSoup) -> Dict[str, str]:
    """Extract minimum investment amounts."""
    table = _find(soup, "min_investments")
    if not table:
        return {}

    result: Dict[str, str] = {}
    text = table.get_text(separator="\n", strip=True)
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # Lines alternate: label, value
    for i in range(0, len(lines) - 1, 2):
        label = lines[i]
        value = lines[i + 1]
        if "1st" in label:
            result["min_first_investment"] = value
        elif "2nd" in label:
            result["min_subsequent_investment"] = value
        elif "SIP" in label:
            result["min_sip"] = value

    return result


def _extract_fund_house_info(soup: BeautifulSoup) -> Dict[str, str]:
    """Extract fund house details: name, launch date, total AUM, etc."""
    container = _find(soup, "fund_house")
    if not container:
        return {}

    result: Dict[str, str] = {}
    text = container.get_text(separator="\n", strip=True)
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # Key-value pairs follow a pattern: label on one line, value on next
    kv_labels = {
        "Fund house": "fund_house",
        "Rank (total assets)": "fund_house_rank",
        "Total AUM": "total_aum",
        "Date of Incorporation": "incorporation_date",
        "Launch Date": "launch_date",
        "Phone": "phone",
        "Custodian": "custodian",
    }

    for i, line in enumerate(lines):
        for label, key in kv_labels.items():
            if line == label and i + 1 < len(lines):
                result[key] = lines[i + 1]
                break

    return result


def _extract_fund_managers(soup: BeautifulSoup) -> List[str]:
    """Extract fund manager names and tenures."""
    cards = _find(soup, "fund_management_card", find_all=True)
    managers: List[str] = []
    for card in cards:
        text = card.get_text(separator=" | ", strip=True)
        # Format: "RB | Rahul Baijal | Jul 2022 | - Present | View details"
        parts = [p.strip() for p in text.split("|")]
        if len(parts) >= 4:
            name = parts[1].strip()
            tenure_start = parts[2].strip()
            tenure_end = parts[3].strip().lstrip("- ").strip()
            managers.append(f"{name} ({tenure_start} - {tenure_end})")
        elif len(parts) >= 2:
            managers.append(parts[1].strip())
    return managers


def _extract_faq(soup: BeautifulSoup) -> List[Dict[str, str]]:
    """Extract FAQ data from JSON-LD structured data."""
    faqs: List[Dict[str, str]] = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.get_text())
            if data.get("@type") == "FAQPage":
                for item in data.get("mainEntity", []):
                    question = item.get("name", "")
                    answer_html = item.get("acceptedAnswer", {}).get("text", "")
                    # Strip HTML from answer
                    answer_soup = BeautifulSoup(answer_html, "html.parser")
                    answer = answer_soup.get_text(separator=" ", strip=True)
                    if question and answer:
                        faqs.append({"question": question, "answer": answer})
        except (json.JSONDecodeError, AttributeError):
            continue
    return faqs


# ---------------------------------------------------------------------------
# Clean text extraction (strips nav, footer, ads, scripts, styles)
# ---------------------------------------------------------------------------

def _clean_html_to_text(soup: BeautifulSoup, scheme_name: str) -> str:
    """Convert HTML to clean, structured plain text for RAG.

    Strips: scripts, styles, nav, footer, ads, compare-funds widget.
    Preserves: headings, key-value data, paragraphs.
    """
    # Deep copy to avoid mutating the original
    soup_copy = BeautifulSoup(str(soup), "html.parser")

    # Remove unwanted tags
    for tag in soup_copy(["script", "style", "noscript", "link", "meta",
                          "iframe", "svg", "img", "picture", "video"]):
        tag.decompose()

    # Remove navigation, footer, ads
    for tag in soup_copy.find_all(["nav", "footer", "header"]):
        tag.decompose()

    # Remove compare-funds widget (noise for RAG)
    for tag in _find(soup_copy, "compare_funds", find_all=True) or []:
        tag.decompose()

    # Get the main content wrapper
    main = soup_copy.find(
        True, class_=lambda c: c and "pw14ContentWrapper" in str(c)
    )
    if not main:
        main = soup_copy.find("body") or soup_copy

    text = main.get_text(separator="\n", strip=True)

    # Clean up
    lines = text.split("\n")
    cleaned: List[str] = []
    seen: set = set()

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Skip very short noise lines (single chars, icons)
        if len(line) <= 2 and not line.replace(".", "").replace(",", "").isdigit():
            continue
        # Skip duplicate consecutive lines
        if line in seen:
            continue
        seen.add(line)
        cleaned.append(line)

    return "\n".join(cleaned)


# ---------------------------------------------------------------------------
# Structured text builder — assembles metadata into RAG-friendly text
# ---------------------------------------------------------------------------

def _build_structured_text(
    scheme_name: str,
    category_info: Dict[str, str],
    fund_details: Dict[str, str],
    benchmark: str,
    objective_text: str,
    exit_loads: List[str],
    stamp_duty: str,
    min_investments: Dict[str, str],
    fund_house_info: Dict[str, str],
    fund_managers: List[str],
    faqs: List[Dict[str, str]],
    clean_text: str,
) -> str:
    """Build a structured plain-text document optimized for chunking.

    Organizes data into clearly labeled sections so the chunker and
    retriever can find relevant information efficiently.
    """
    sections: List[str] = []

    # --- Scheme Overview ---
    sections.append(f"# {scheme_name}")
    sections.append("")
    overview_parts = []
    if category_info.get("asset_type"):
        overview_parts.append(
            f"Asset Type: {category_info['asset_type']}"
        )
    if category_info.get("sub_category"):
        overview_parts.append(
            f"Category: {category_info['sub_category']}"
        )
    if category_info.get("risk_level"):
        overview_parts.append(
            f"Risk Level: {category_info['risk_level']}"
        )
    if overview_parts:
        sections.append("\n".join(overview_parts))
        sections.append("")

    # --- Key Stats ---
    sections.append("## Key Fund Details")
    if fund_details.get("nav_date"):
        sections.append(
            f"{fund_details['nav_date']}: {fund_details.get('nav_value', 'N/A')}"
        )
    if fund_details.get("min_sip"):
        sections.append(f"Minimum SIP Amount: {fund_details['min_sip']}")
    if fund_details.get("aum"):
        sections.append(f"Fund Size (AUM): {fund_details['aum']}")
    if fund_details.get("expense_ratio"):
        sections.append(f"Expense Ratio: {fund_details['expense_ratio']}")
    if fund_details.get("rating"):
        sections.append(f"Rating: {fund_details['rating']} out of 5")
    if benchmark:
        sections.append(f"Benchmark: {benchmark}")
    sections.append("")

    # --- Minimum Investments ---
    if min_investments:
        sections.append("## Minimum Investments")
        if min_investments.get("min_first_investment"):
            sections.append(
                f"Minimum 1st Investment: {min_investments['min_first_investment']}"
            )
        if min_investments.get("min_subsequent_investment"):
            sections.append(
                f"Minimum Subsequent Investment: {min_investments['min_subsequent_investment']}"
            )
        if min_investments.get("min_sip"):
            sections.append(
                f"Minimum SIP: {min_investments['min_sip']}"
            )
        sections.append("")

    # --- Exit Load ---
    if exit_loads:
        sections.append("## Exit Load")
        # Use only the most recent exit load entry
        sections.append(exit_loads[0])
        sections.append("")

    # --- Stamp Duty ---
    if stamp_duty:
        sections.append("## Stamp Duty")
        sections.append(f"Stamp Duty on Investment: {stamp_duty}")
        sections.append("")

    # --- Fund Managers ---
    if fund_managers:
        sections.append("## Fund Managers")
        for manager in fund_managers:
            sections.append(f"- {manager}")
        sections.append("")

    # --- Investment Objective / About ---
    if objective_text:
        sections.append("## About This Fund")
        sections.append(objective_text)
        sections.append("")

    # --- Fund House ---
    if fund_house_info:
        sections.append("## Fund House Information")
        if fund_house_info.get("fund_house"):
            sections.append(
                f"Fund House: {fund_house_info['fund_house']}"
            )
        if fund_house_info.get("fund_house_rank"):
            sections.append(
                f"Rank: {fund_house_info['fund_house_rank']}"
            )
        if fund_house_info.get("total_aum"):
            sections.append(
                f"Total AUM: {fund_house_info['total_aum']}"
            )
        if fund_house_info.get("launch_date"):
            sections.append(
                f"Launch Date: {fund_house_info['launch_date']}"
            )
        if fund_house_info.get("custodian"):
            sections.append(
                f"Custodian: {fund_house_info['custodian']}"
            )
        sections.append("")

    # --- FAQs ---
    if faqs:
        sections.append("## Frequently Asked Questions")
        for faq in faqs:
            sections.append(f"Q: {faq['question']}")
            sections.append(f"A: {faq['answer']}")
            sections.append("")

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_html(html: str, source_url: str) -> Dict[str, Any]:
    """Extract structured text and metadata from raw Groww HTML.

    Args:
        html: Raw HTML content from a Groww mutual fund page.
        source_url: The original URL the HTML was scraped from.

    Returns:
        Dictionary containing:
        - text (str): Clean, structured text content for chunking
        - scheme_name (str): Fund scheme name from <h1>
        - category (str): Sub-category e.g. 'Large Cap'
        - asset_type (str): Top-level type e.g. 'Equity', 'Commodities'
        - risk_level (str): Risk classification e.g. 'Very High Risk'
        - nav_value (str): Current NAV value e.g. '₹1,234.16'
        - nav_date (str): NAV date string e.g. "NAV: 03 Jul '26"
        - expense_ratio (str): Expense ratio e.g. '1.04%'
        - aum (str): Assets under management e.g. '₹37,808.31 Cr'
        - min_sip (str): Minimum SIP amount e.g. '₹100'
        - benchmark (str): Fund benchmark e.g. 'NIFTY 100 Total Return Index'
        - exit_load (str): Current exit load policy
        - fund_managers (list[str]): Fund manager names with tenures
        - launch_date (str): Fund launch date
        - fund_house (str): AMC name
        - source_url (str): Original URL
        - scrape_date (str): ISO date of parsing
    """
    soup = BeautifulSoup(html, "html.parser")
    scrape_date = date.today().isoformat()

    # --- Extract all metadata ---
    scheme_name = _extract_scheme_name(soup)
    category_info = _extract_category_and_risk(soup)
    fund_details = _extract_fund_details(soup)
    benchmark = _extract_benchmark(soup)
    objective_text = _extract_investment_objective(soup)
    exit_loads = _extract_exit_load(soup)
    stamp_duty = _extract_stamp_duty(soup)
    min_investments = _extract_min_investments(soup)
    fund_house_info = _extract_fund_house_info(soup)
    fund_managers = _extract_fund_managers(soup)
    faqs = _extract_faq(soup)
    clean_text = _clean_html_to_text(soup, scheme_name)

    # --- Build structured text ---
    structured_text = _build_structured_text(
        scheme_name=scheme_name,
        category_info=category_info,
        fund_details=fund_details,
        benchmark=benchmark,
        objective_text=objective_text,
        exit_loads=exit_loads,
        stamp_duty=stamp_duty,
        min_investments=min_investments,
        fund_house_info=fund_house_info,
        fund_managers=fund_managers,
        faqs=faqs,
        clean_text=clean_text,
    )

    # --- Assemble result ---
    result: Dict[str, Any] = {
        "text": structured_text,
        "scheme_name": scheme_name,
        "category": category_info.get("sub_category", ""),
        "asset_type": category_info.get("asset_type", ""),
        "risk_level": category_info.get("risk_level", ""),
        "nav_value": fund_details.get("nav_value", ""),
        "nav_date": fund_details.get("nav_date", ""),
        "expense_ratio": fund_details.get("expense_ratio", ""),
        "aum": fund_details.get("aum", ""),
        "min_sip": fund_details.get("min_sip", ""),
        "benchmark": benchmark,
        "exit_load": exit_loads[0] if exit_loads else "",
        "fund_managers": fund_managers,
        "launch_date": fund_house_info.get("launch_date", ""),
        "fund_house": fund_house_info.get("fund_house", ""),
        "source_url": source_url,
        "scrape_date": scrape_date,
    }

    logger.info(
        "Parsed %s: %d chars of structured text, "
        "expense_ratio=%s, aum=%s, risk=%s",
        scheme_name, len(structured_text),
        result["expense_ratio"], result["aum"], result["risk_level"],
    )

    return result


def parse_all(html_map: Dict[str, str]) -> List[Dict[str, Any]]:
    """Parse all scraped HTML pages.

    Args:
        html_map: Dict mapping URL -> raw HTML content
                  (as returned by scraper.scrape_all).

    Returns:
        List of parsed document dicts.
    """
    documents: List[Dict[str, Any]] = []

    for url, html in html_map.items():
        logger.info("Parsing %s...", url)
        try:
            doc = parse_html(html, url)
            documents.append(doc)
        except Exception as e:
            logger.error("Failed to parse %s: %s", url, e)

    logger.info(
        "Parsing complete: %d/%d documents parsed.",
        len(documents), len(html_map),
    )

    return documents


def save_parsed(documents: List[Dict[str, Any]]) -> None:
    """Save parsed documents to data/processed/ as JSON files.

    Each document is saved as <scheme_slug>.json for inspection
    and debugging.
    """
    _PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    for doc in documents:
        scheme_name = doc.get("scheme_name", "unknown")
        slug = re.sub(r"[^a-z0-9]+", "-", scheme_name.lower()).strip("-")
        filepath = _PROCESSED_DIR / f"{slug}.json"

        # Convert to serializable format
        save_data = {k: v for k, v in doc.items()}

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)

        logger.info("Saved parsed data to %s", filepath)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    from src.ingestion.scraper import scrape_all

    logger.info("Step 1: Scraping all corpus URLs...")
    html_map = scrape_all()

    logger.info("Step 2: Parsing all HTML pages...")
    documents = parse_all(html_map)

    logger.info("Step 3: Saving parsed documents...")
    save_parsed(documents)

    # Summary
    print("\n" + "=" * 60)
    print("PARSING SUMMARY")
    print("=" * 60)
    for doc in documents:
        print(f"\n  Scheme: {doc['scheme_name']}")
        print(f"  Category: {doc['asset_type']} / {doc['category']}")
        print(f"  Risk: {doc['risk_level']}")
        print(f"  NAV: {doc['nav_value']} ({doc['nav_date']})")
        print(f"  Expense Ratio: {doc['expense_ratio']}")
        print(f"  AUM: {doc['aum']}")
        print(f"  Min SIP: {doc['min_sip']}")
        print(f"  Benchmark: {doc['benchmark']}")
        print(f"  Exit Load: {doc['exit_load']}")
        print(f"  Fund Managers: {', '.join(doc['fund_managers'])}")
        print(f"  Launch Date: {doc['launch_date']}")
        print(f"  Text length: {len(doc['text'])} chars")
