from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class FieldSelector:
    selectors: List[str]
    attribute: str = "text"
    regex: Optional[str] = None
    required: bool = False
    join_with: str = " "


@dataclass
class SiteConfig:
    key: str
    engine: str = "auto"
    domains: List[str] = field(default_factory=list)
    wait_for: Optional[str] = None
    timeout_sec: int = 25
    playwright_timeout_sec: int = 25
    headers: Dict[str, str] = field(default_factory=dict)
    selectors: Dict[str, FieldSelector] = field(default_factory=dict)
    in_stock_patterns: List[str] = field(default_factory=list)
    out_of_stock_patterns: List[str] = field(default_factory=list)


@dataclass
class ProductConfig:
    key: str
    label: str
    url: str
    my_price: Optional[int] = None
    site: Optional[str] = None


@dataclass
class CsvOutputConfig:
    enabled: bool = True
    report_path: str = "data/current_report.csv"
    history_path: Optional[str] = "data/history.csv"


@dataclass
class GoogleSheetsConfig:
    enabled: bool = False
    spreadsheet_id: str = ""
    worksheet_name: str = "Competitor Prices"
    comparison_worksheet_name: str = "Сравнение цен"
    catalog_worksheet_name: str = "Список моделей"
    credentials_path: str = ""


@dataclass
class OutputConfig:
    snapshot_path: str = "data/latest_snapshot.json"
    csv: CsvOutputConfig = field(default_factory=CsvOutputConfig)
    google_sheets: GoogleSheetsConfig = field(default_factory=GoogleSheetsConfig)


@dataclass
class DefaultsConfig:
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    timeout_sec: int = 25
    use_playwright_on_incomplete: bool = True


@dataclass
class LoggingConfig:
    level: str = "INFO"
    file_path: str = "logs/price_monitor.log"


@dataclass
class AppConfig:
    defaults: DefaultsConfig
    logging: LoggingConfig
    output: OutputConfig
    sites: Dict[str, SiteConfig]
    products: List[ProductConfig]


@dataclass
class ExtractionResult:
    title: Optional[str] = None
    price: Optional[int] = None
    original_price: Optional[int] = None
    availability_text: Optional[str] = None
    availability_status: str = "unknown"
    missing_required_fields: List[str] = field(default_factory=list)

    def is_complete(self) -> bool:
        return not self.missing_required_fields


@dataclass
class ProductRecord:
    product_key: str
    product_label: str
    site_key: str
    url: str
    checked_at: str
    scraped_name: Optional[str] = None
    competitor_price: Optional[int] = None
    competitor_old_price: Optional[int] = None
    previous_competitor_price: Optional[int] = None
    price_changed: bool = False
    my_price: Optional[int] = None
    price_diff_rub: Optional[int] = None
    cheaper_side: str = "unknown"
    competitor_cheaper: bool = False
    availability_status: str = "unknown"
    availability_text: Optional[str] = None
    renderer_used: Optional[str] = None
    status: str = "ok"
    error: Optional[str] = None


@dataclass
class SnapshotRecord:
    competitor_price: Optional[int] = None
    checked_at: Optional[str] = None
