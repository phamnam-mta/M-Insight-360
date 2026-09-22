"""Sinh kịch bản tiếp cận — điền khung mẫu có sẵn, không gọi LLM.

Spec §D6 / §TƯỜNG LỬA DỮ LIỆU: kịch bản loại A (nhờ KH nguồn giới thiệu) được
dùng đầy đủ số liệu vì nói chuyện với chính chủ dữ liệu; loại B (tiếp cận
trực tiếp đối tác) TUYỆT ĐỐI không được chứa tên KH nguồn hay bất kỳ con số
nào từ sao kê. Dùng khung có sẵn (§D6 Khung A/B) điền từ dữ liệu đã tính sẵn
— không phải văn xuôi tự do — loại bỏ hoàn toàn rủi ro bịa số hoặc lộ tên
khách hàng của hồ sơ khác mà một lời gọi LLM tự do sẽ phải tự canh giữ.
"""

from .card_types import Opportunity, Scenario

PRODUCT_BENEFIT = {
    "RULE1_PAYROLL": "miễn phí chuyển lương, nhân viên có thêm quyền lợi từ thẻ tín dụng ưu đãi",
    "RULE2_SCF": "rút ngắn thời gian thu tiền mà không cần thêm tài sản bảo đảm",
    "RULE3_IDLE": "lãi suất cố định cao hơn tiền gửi thường, chuyển nhượng và cầm cố vay lại được",
    "RULE4_FX": "tối ưu chi phí chuyển đổi ngoại tệ và phòng ngừa rủi ro tỷ giá",
    "RULE5A_AR": "rút ngắn vòng quay tiền từ khoản phải thu",
    "RULE5B_AP": "chủ động nguồn vốn thanh toán nhà cung cấp",
    "RULE6_LOAN": "thêm một đầu mối ngân hàng dự phòng và tăng vị thế đàm phán lãi suất",
}


def _scenario_a(rule_id: str, san_pham: str, signal_1dong: str) -> Scenario:
    benefit = PRODUCT_BENEFIT.get(rule_id, "tối ưu dòng tiền và chi phí vốn")
    content = (
        f"Chào anh/chị, qua rà soát dòng tiền kỳ này, em thấy {signal_1dong.rstrip('.').lower()} "
        f"MSB có gói {san_pham.split('—')[0].strip().lower()} giúp công ty {benefit}. "
        f"Anh/chị cho em xin thêm ít thông tin để bên em tư vấn phương án cụ thể, phù hợp với tình "
        f"hình hoạt động hiện tại của công ty, và có thể trao đổi thêm về điều kiện, mức phí cũng như "
        f"thời gian xử lý hồ sơ dự kiến ạ."
    )
    return Scenario(loai="A", doi_tuong="Khách hàng nguồn", noi_dung=content)


def _scenario_b(san_pham: str, industry: str) -> Scenario:
    benefit = "tối ưu dòng tiền, giảm chi phí vốn lưu động và rút ngắn thời gian xử lý hồ sơ"
    content = (
        f"Chào anh/chị, MSB đang đẩy mạnh {san_pham.split('—')[0].strip().lower()} cho nhóm doanh "
        f"nghiệp ngành {industry.lower()}. Bên em có gói sản phẩm giúp doanh nghiệp {benefit} mà "
        f"không cần bổ sung nhiều tài sản bảo đảm, hồ sơ xử lý trong vài ngày làm việc. Em xin phép "
        f"gửi brochure để anh/chị tham khảo, nếu thấy phù hợp mình hẹn một buổi trao đổi ngắn để em "
        f"trình bày kỹ hơn về điều kiện và mức phí ạ."
    )
    return Scenario(loai="B", doi_tuong="Đối tác", noi_dung=content)


def generate_scenarios(opportunity: Opportunity, industry_guess: str = "thương mại và dịch vụ") -> list[Scenario]:
    if opportunity.priority == "P-NA":
        return []
    scenarios = [_scenario_a(opportunity.rule_id, opportunity.san_pham, opportunity.signal_1dong)]
    if opportunity.priority in ("P1", "P2"):
        scenarios.append(_scenario_b(opportunity.san_pham, industry_guess))
    return scenarios


def generate_partner_scenarios(partner_name: str, direction: str, industry_guess: str) -> list[Scenario]:
    """§D6: đủ 2 kịch bản cho Top 3 đối tác — độc lập với cơ hội, gắn theo tên đối tác."""
    del partner_name  # loại B không được nhắc tên đối tác/khách hàng nguồn
    san_pham = "tài trợ chuỗi cung ứng" if direction != "Dau vao (NCC)" else "chiết khấu hoá đơn và tài trợ khoản phải thu"
    return [_scenario_b(san_pham, industry_guess)]
