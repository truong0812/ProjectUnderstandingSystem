"""Logistics / Airport Cargo domain glossary plugin (Vietnamese).

Maps logistics/airport cargo domain terms to Vietnamese descriptions.
This plugin was extracted from the original hardcoded business_glossary.py
as part of the domain plugin architecture.
"""

from __future__ import annotations

import re

from project_understanding.ingest.domain_plugins.base import DomainGlossaryPlugin

# Domain keyword -> Vietnamese description
_LOGISTICS_GLOSSARY: dict[str, str] = {
    # Airport cargo operations
    "ramp": "Khu vực bãi đỗ hàng hóa tại sân bay (RAMP)",
    "uld": "Unit Load Device - Contain tiêu chuẩn vận chuyển hàng không",
    "inbound": "Hàng hóa nhập vào (Inbound) - Hàng đến từ chuyến bay",
    "outbound": "Hàng hóa xuất ra (Outbound) - Hàng chuẩn bị lên chuyến bay",
    "awb": "Air Waybill - Vận đơn hàng không",
    "mawb": "Master Air Waybill - Vận đơn chính",
    "hawb": "House Air Waybill - Vận đơn phụ",
    "flight": "Chuyến bay vận chuyển hàng hóa",
    "manifest": "Manifest - Danh sách hàng hóa trên chuyến bay",
    "cargo": "Hàng hóa vận chuyển qua đường hàng không",
    "ecargo": "Hệ thống quản lý hàng hóa điện tử (eCargo)",
    "freight": "Hàng hóa vận chuyển (freight/cargo)",
    "shipment": "Lô hàng vận chuyển",
    "consignment": "Lô hàng ủy thác vận chuyển",
    "booking": "Đặt chỗ vận chuyển hàng hóa",
    "warehouse": "Kho hàng tại sân bay",
    "terminal": "Nhà ga hàng hóa tại sân bay",
    " customs": "Hải quan - Xử lý thủ tục hải quan",
    "clearance": "Thông quan - Hoàn thành thủ tục hải quan",
    "inspection": "Kiểm tra hàng hóa (soi chiếu, kiểm đếm)",
    "weighing": "Cân trọng lượng hàng hóa",
    "dimension": "Kích thước hàng hóa (dài × rộng × cao)",
    "volumetric": "Trọng lượng thể tích - Quy đổi từ kích thước sang trọng lượng",
    "chargeable": "Trọng lượng tính cước - Lấy max(trọng lượng thực tế, trọng lượng thể tích)",
    "pallet": "Pallet - Bệ đỡ hàng hóa để xếp lên máy bay",
    "net": "Lưới buộc hàng trên pallet",
    "strapping": "Dây đai buộc hàng trên pallet/ULD",
    "barcode": "Mã vạch - Quét barcode để tracking hàng hóa",
    "qrcode": "Mã QR - Quét QR code để tracking",
    "scan": "Quét mã vạch/QR để xác nhận hàng hóa",
    "tracking": "Theo dõi trạng thái hàng hóa (tracking)",
    "status": "Trạng thái xử lý hàng hóa",
    "handheld": "Thiết bị handheld - Máy quét cầm tay cho nhân viên bãi",
    "signature": "Chữ ký điện tử xác nhận giao nhận hàng",
    "photo": "Chụp ảnh hàng hóa làm bằng chứng giao nhận",
    "damage": "Hàng hư hỏng - Ghi nhận tình trạng hư hỏng",
    "exception": "Ngoại lệ xử lý hàng (hư hỏng, thiếu, sai)",
    "seal": "Chì niêm phong contain/ULD",
    "departure": "Chuyến bay khởi hành (departure)",
    "arrival": "Chuyến bay đến (arrival)",
    "transit": "Hàng quá cảnh (transit)",
    "transfer": "Hàng chuyển tiếp (transfer) giữa các chuyến bay",
    "delivery": "Giao hàng cho người nhận",
    "pickup": "Nhận hàng từ người gửi",
    "agent": "Đại lý vận chuyển hàng hóa",
    "carrier": "Hãng hàng không vận chuyển",
    "shipper": "Người gửi hàng (shipper)",
    "consignee": "Người nhận hàng (consignee)",
    "notify": "Thông báo cho bên liên quan (người gửi/nhận)",
    "document": "Chứng từ hàng hóa (vận đơn, hóa đơn, packing list)",
    "invoice": "Hóa đơn thương mại",
    "packing": "Packing list - Danh sách đóng gói hàng hóa",
    "permit": "Giấy phép vận chuyển hàng đặc biệt",
    "dangerous": "Hàng nguy hiểm (DG - Dangerous Goods)",
    "dg": "Dangerous Goods - Hàng nguy hiểm",
    "lithium": "Pin lithium - Hàng nguy hiểm loại pin",
    "perishable": "Hàng dễ hỏng (thực phẩm, hoa tươi)",
    "live_animal": "Động vật sống - Hàng đặc biệt",
    "pharma": "Hàng dược phẩm - Cần kiểm soát nhiệt độ",
    "cool": "Hàng cần kiểm soát nhiệt độ (cool chain)",
    "temperature": "Nhiệt độ lưu trữ/vận chuyển hàng",
    "tally": "Kiểm đếm hàng hóa",
    "buildup": "Build-up - Xếp hàng vào ULD/pallet",
    "breakdown": "Break-down - Dỡ hàng từ ULD/pallet",
    "load": "Nạp hàng lên máy bay (loading)",
    "unload": "Dỡ hàng từ máy bay (unloading)",
    "irregularity": "Bất thường trong xử lý hàng",
    "claim": "Khiếu nại đền bù hàng hư hỏng/mất",
    "report": "Báo cáo thống kê hàng hóa",
}

# Pre-compiled regex patterns for fast matching
_LONG_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(rf"(?i)\b{re.escape(kw)}\b"), desc)
    for kw, desc in _LOGISTICS_GLOSSARY.items()
    if len(kw) >= 3
]

_SHORT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(rf"(?i)\b{re.escape(kw)}\b"), desc)
    for kw, desc in _LOGISTICS_GLOSSARY.items()
    if len(kw) < 3
]


class LogisticsViPlugin(DomainGlossaryPlugin):
    """Logistics / airport cargo domain glossary with Vietnamese descriptions."""

    @property
    def name(self) -> str:
        return "logistics_vi"

    @property
    def description(self) -> str:
        return "Logistics / Airport Cargo domain (Vietnamese descriptions)"

    def detect_context(
        self, code: str, max_terms: int = 5
    ) -> dict[str, str]:
        """Detect logistics/cargo terms in code and return Vietnamese context.

        Args:
            code: Source code or file content to analyze.
            max_terms: Maximum number of terms to include.

        Returns:
            Dictionary mapping keywords to their Vietnamese descriptions.
            Empty dict if no terms found.
        """
        found: dict[str, str] = {}

        # Check longer patterns first (more specific)
        for pattern, description in _LONG_PATTERNS:
            if pattern.search(code):
                key = description.split(" - ")[0] if " - " in description else description
                if key not in found:
                    found[key] = description
                if len(found) >= max_terms:
                    break

        # Check short patterns
        for pattern, description in _SHORT_PATTERNS:
            if pattern.search(code):
                key = description.split(" - ")[0] if " - " in description else description
                if key not in found:
                    found[key] = description
                if len(found) >= max_terms:
                    break

        return found