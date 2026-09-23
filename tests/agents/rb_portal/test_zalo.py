from app.agents.rb_portal.zalo import get_zalo_qr_status


def test_get_zalo_qr_status_reports_not_connected():
    status = get_zalo_qr_status()
    assert status["status"] == "NOT_CONNECTED"
    assert status["qr_url"] is None
    assert "Chưa kết nối" in status["message"]
