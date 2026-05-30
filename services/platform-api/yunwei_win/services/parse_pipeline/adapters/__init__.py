"""Source-type adapters — Excel / contract / screenshot → CandidateJSON."""

from yunwei_win.services.parse_pipeline.adapters.contract import parse_contract
from yunwei_win.services.parse_pipeline.adapters.excel import parse_excel
from yunwei_win.services.parse_pipeline.adapters.screenshot import parse_screenshot

__all__ = ["parse_contract", "parse_excel", "parse_screenshot"]
