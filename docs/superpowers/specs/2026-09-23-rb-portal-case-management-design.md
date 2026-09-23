# RB Portal — Case-Management Rebuild Design

## Bối cảnh

Nguồn yêu cầu: brief "M-INSIGHT360 RB | IT IMPLEMENTATION BRIEF — Phiên bản 3"
do người dùng cung cấp, kèm ảnh tham chiếu layout tab Tổng hợp và file
template gốc `docs/templates/MB01A_QT.RR.038_lan_3.docx` (Giấy đề nghị cấp
tín dụng, mẫu MB01A/QT.RR.038 lần 3).

Tab RB hiện tại (`app/agents/rb/router.py`, `web/components/AssessmentForm.tsx`
+ `ResultPanel.tsx`) là luồng một-lượt: RM upload file → AI trích xuất tự
động (regex trên text đã OCR/parse) → trả kết quả ngay, không lưu case,
không cho sửa dữ liệu, không có trạng thái hồ sơ theo thời gian.

Brief yêu cầu đổi hẳn mô hình tương tác sang **case-management**: RM tạo hồ
sơ, tự nhập dữ liệu theo từng nhóm nghiệp vụ (không phụ thuộc AI trích xuất
đúng), tải chứng từ đi kèm để lưu vết/checklist, và có thể chạy thẩm định sơ
bộ bất cứ lúc nào dữ liệu đã đủ tối thiểu.

## Quyết định phạm vi đã thống nhất với người dùng

Các câu hỏi đã hỏi và chốt trong phiên brainstorm:

1. **Thay thế hoàn toàn tab RB cũ** — không chạy song song. `app/agents/rb/router.py`
   hiện tại (endpoint `/api/rb/assess`) và luồng frontend cũ
   (`AssessmentForm` dùng cho tab RB + `ResultPanel.tsx`) bị gỡ khỏi UI.
   Các module tính toán thuần (không phụ thuộc luồng upload một-lượt) —
   `credit_engine.py`, `risk_flags.py`, `readiness.py`, `profile_checks.py`
   — được **giữ lại và tái sử dụng** bởi router case-based mới; chỉ đổi nguồn
   dữ liệu đầu vào. `document_classifier.py` và `extract_document` pipeline
   cũng được giữ lại, dùng để gợi ý category/trạng thái file khi upload
   (hỗ trợ, không phải nguồn sự thật).
2. **Không làm đăng nhập/SSO.** Không có bảng user, không có route
   protection theo người dùng thật, không có JWT/session. Hệ quả trực tiếp:
   - Không có tab "Tổng quan" kiểu "dashboard công việc của RM" theo đúng
     nghĩa cá nhân hoá — thay bằng dashboard toàn cục (danh sách case gần
     đây, không lọc theo người tạo).
   - `audit_log` vẫn ghi lại hành động (tạo case, cập nhật section, upload,
     chạy thẩm định, export) nhưng trường "actor" là hằng số `"RM"` thay vì
     user_id thật — đây là khoảng cách CÓ CHỦ ĐÍCH so với "audit log cho
     login" trong brief, cần nêu rõ khi bàn giao.
   - Endpoint `/api/auth/login`, `/api/auth/logout` trong brief: **không
     triển khai**.
3. **Có file template gốc** (`docs/templates/MB01A_QT.RR.038_lan_3.docx`) —
   xuất Word dùng đúng file này, không dựng lại form.
4. **Zalo Bot: chưa có OA/bot thật** — làm modal hoàn chỉnh với QR/link là
   placeholder rõ ràng ("Chưa kết nối — liên hệ IT để lấy mã QR chính
   thức"), không bịa QR giả.

## Nguyên tắc nghiệp vụ (giữ nguyên từ brief, khớp với toàn bộ codebase hiện tại)

- AI hỗ trợ hiểu/chuẩn bị hồ sơ; Credit Engine tính toán deterministic;
  rule/policy phải truy vết được (evidence, formula); con người quyết định
  cuối cùng.
- Không dùng APPROVE/REJECT — dùng `PRELIMINARY_READY`,
  `PRELIMINARY_READY_WITH_CONDITIONS`, `INSUFFICIENT_DATA`,
  `MANUAL_REVIEW_REQUIRED` (khớp với `credit_readiness`/`recommendation`
  pattern đã dùng ở EB/RB hiện tại — tái dùng nguyên xi, không đặt tên mới).
- Thiếu input cho một metric → trả `null`/`NEED_MORE_DATA`, UI hiển thị
  "Chưa có dữ liệu". Không bao giờ hiển thị 0 giả.
- AI Insight là optional — timeout/unavailable không được làm sập trang
  Tổng hợp (đã có sẵn `narrative_budget_exceeded` pattern dùng lại được).
- Không để nút giả — chức năng chưa làm (Zalo thật, SSO) phải ghi rõ
  "chưa kết nối"/để placeholder tường minh, không giả vờ hoạt động.

## Kiến trúc tổng thể

```
Frontend (Next.js static export)
  web/app/page.tsx           — tab selector: EB | RB | Cross-sell
    → khi chọn "RB": render <RbPortal /> thay cho AssessmentForm+ResultPanel cũ
  web/components/rb-portal/
    RbPortal.tsx              — layout: sidebar 10 mục + case selector/tạo mới
    tabs/OverviewTab.tsx       — "Tổng quan": danh sách case gần đây, quick action
    tabs/CustomerTab.tsx       — "Hồ sơ khách hàng"
    tabs/LegalTab.tsx          — "Pháp lý"
    tabs/IncomeTab.tsx         — "Nguồn thu" (có cờ bắt buộc tờ khai thuế)
    tabs/LoanTab.tsx           — "Khoản vay"
    tabs/CollateralTab.tsx     — "Tài sản bảo đảm"
    tabs/OtherDocsTab.tsx      — "Hồ sơ khác"
    tabs/DocumentsTab.tsx      — "Tải lên chứng từ" (danh sách file theo category)
    tabs/AssessmentTab.tsx     — "Thẩm định" (nút chạy sơ bộ/đầy đủ)
    tabs/SummaryTab.tsx        — "Tổng hợp" (layout bắt buộc theo ảnh tham chiếu)
    tabs/HistoryTab.tsx        — "Lịch sử" (version list)
    ZaloBotModal.tsx           — modal QR placeholder

Backend (FastAPI)
  app/agents/rb_portal/         — module MỚI, độc lập với app/agents/rb/ cũ
    router.py                   — toàn bộ endpoint case-based (§API Contract)
    models.py                   — dataclass cho từng section (Customer/Legal/
                                   Income/Loan/Collateral/Other)
    mandatory_check.py          — checklist bắt buộc theo nhóm + cờ tờ khai thuế
    assessment.py                — cầu nối: build RbLoanInputs từ case đã lưu,
                                   gọi lại app/agents/rb/credit_engine.py +
                                   risk_flags.py + readiness.py nguyên xi
    mb01a_export.py             — xuất Word từ template thật
    zalo.py                     — GET /api/rb/zalo-bot/qr (trả placeholder)

  app/storage/db.py             — thêm 4 bảng mới (xem Mô hình dữ liệu)
  app/storage/rb_case_repository.py — CRUD case, documents, assessments, audit
```

## Mô hình dữ liệu

SQLite, tận dụng `app/storage/db.py`'s `SCHEMA` string hiện có (giữ nguyên
convention `CREATE TABLE IF NOT EXISTS` + `init_db` chạy `ALTER TABLE` cho
cột mới nếu cần, như đã làm với `case_id` trên bảng `assessments`).

```sql
CREATE TABLE IF NOT EXISTS rb_cases (
    case_id TEXT PRIMARY KEY,            -- "RB-{tax_id}-{8 hex}", giống format EB
    status TEXT NOT NULL DEFAULT 'RECEIVED',  -- RECEIVED|DOCS_ANALYZED|PRELIM_DONE|FULL_DONE
    customer_json TEXT,                  -- null cho tới khi PATCH .../customer lần đầu
    legal_json TEXT,
    income_json TEXT,
    loan_json TEXT,
    collateral_json TEXT,
    other_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rb_case_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    file_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    category TEXT NOT NULL,              -- LEGAL|INCOME|LOAN|COLLATERAL|OTHER
    document_type TEXT,                  -- kết quả classify_document (gợi ý, RM sửa được)
    status TEXT NOT NULL DEFAULT 'UPLOADED',  -- UPLOADED|PROCESSING|EXTRACTED|FAILED|NEED_OCR_VLM
    content_type TEXT,
    size_bytes INTEGER NOT NULL,
    storage_path TEXT NOT NULL,
    uploaded_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rb_case_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    version INTEGER NOT NULL,            -- tăng dần theo case_id, tính ở application layer
    kind TEXT NOT NULL,                  -- PRELIMINARY|FULL
    computed_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rb_case_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'RM',    -- hằng số, xem "Quyết định phạm vi" #2
    action TEXT NOT NULL,                -- CASE_CREATED|SECTION_UPDATED:income|DOCUMENT_UPLOADED|...
    detail TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

Mỗi `*_json` là một dict tuỳ ý theo dataclass tương ứng trong `models.py`
(giống pattern `EbFinancialInputs`/`asdict()` đã dùng cho EB) — cho phép
field mới thêm sau không cần migration schema.

## API Contract

Bỏ 2 endpoint auth so với brief (theo Quyết định phạm vi #2). Còn lại giữ
đúng method/path brief đã liệt kê, dưới prefix `/api/rb-portal` (không dùng
lại `/api/rb` để tránh đụng route cũ đang bị deprecate, và để CI/tests cũ
của `app/agents/rb/` không bị ảnh hưởng trong lúc chuyển đổi):

| Method | Endpoint | Ghi chú |
|---|---|---|
| POST | `/api/rb-portal/cases` | Tạo case rỗng, trả `case_id` |
| GET | `/api/rb-portal/cases` | Danh sách case gần đây (cho tab Tổng quan) |
| GET | `/api/rb-portal/cases/{case_id}` | Toàn bộ case (mọi section) |
| PATCH | `/api/rb-portal/cases/{case_id}/customer` | |
| PATCH | `/api/rb-portal/cases/{case_id}/legal` | |
| PATCH | `/api/rb-portal/cases/{case_id}/income` | field `tax_declaration_present: bool` |
| PATCH | `/api/rb-portal/cases/{case_id}/loan` | |
| PATCH | `/api/rb-portal/cases/{case_id}/collateral` | |
| PATCH | `/api/rb-portal/cases/{case_id}/other` | |
| POST | `/api/rb-portal/cases/{case_id}/documents` | multipart upload + category |
| GET | `/api/rb-portal/cases/{case_id}/documents` | |
| POST | `/api/rb-portal/cases/{case_id}/preliminary-assessment` | |
| POST | `/api/rb-portal/cases/{case_id}/full-assessment` | gating: đủ mandatory_check mới cho chạy |
| GET | `/api/rb-portal/cases/{case_id}/summary` | dữ liệu tab Tổng hợp — contract §6 brief |
| POST | `/api/rb-portal/cases/{case_id}/export/mb01a` | trả file .docx |
| GET | `/api/rb-portal/cases/{case_id}/history` | list `rb_case_assessments` |
| GET | `/api/rb-portal/zalo-bot/qr` | placeholder metadata |

## Logic thẩm định — tái sử dụng có kiểm soát

`app/agents/rb_portal/assessment.py` build `RbLoanInputs` (dataclass **đã
có sẵn** trong `app/agents/rb/loan_inputs.py`) trực tiếp từ
`income_json`/`loan_json`/`collateral_json` đã lưu — KHÔNG gọi
`extract_loan_inputs()` (hàm đó chỉ dùng regex trên text tài liệu, thuộc về
luồng cũ). Sau khi build xong `RbLoanInputs`, gọi nguyên xi:

```python
from app.agents.rb.credit_engine import run_credit_engine
from app.agents.rb.risk_flags import compute_risk_flags
from app.agents.rb.readiness import determine_readiness
```

`mandatory_check` cho case-based flow là **module mới**
(`rb_portal/mandatory_check.py`), khác với `app/agents/rb/mandatory_check.py`
cũ (cái cũ kiểm tra document TYPE đã phân loại; cái mới kiểm tra theo
nhóm §3 của brief + cờ tờ khai thuế):

```python
def check_mandatory(customer, legal, income, loan, documents) -> dict:
    """
    Trả về {"legal": [...], "income": [...], "loan": [...], "other": [...],
             "tax_declaration_required": bool, "tax_declaration_present": bool}
    tax_declaration_required = True khi income.source_type thuộc
    {"business", "self_employed", "household_business"} (đúng rule §3.2/§6
    "Quy tắc bắt buộc" của brief).
    """
```

## Frontend — cấu trúc RB Portal

Sidebar 10 mục (bỏ "Zalo Chat Bot" ra khỏi sidebar chính — brief nói đó là
menu "sau login"; không có login nên đặt thành nút riêng trong header của
`RbPortal.tsx`, mở modal, không chiếm 1 slot điều hướng case):

Tổng quan · Hồ sơ khách hàng · Pháp lý · Nguồn thu · Khoản vay ·
Tài sản bảo đảm · Hồ sơ khác · Tải lên chứng từ · Thẩm định · Tổng hợp ·
Lịch sử

Mỗi tab (trừ Tổng quan/Tổng hợp/Lịch sử) là một form PATCH-on-save đơn
giản: load section hiện tại từ `GET .../cases/{id}`, sửa, bấm Lưu → PATCH.
Không auto-save theo từng keystroke (tránh spam request; giữ nút Lưu tường
minh, khớp tinh thần "không nút giả" — nút Lưu phải thật sự gọi API và có
trạng thái loading/error, không silent fail, giống `AssessmentForm.tsx`
hiện tại đã làm đúng).

### Tab "Tổng hợp" — layout bắt buộc (từ ảnh tham chiếu + brief §4)

Header breadcrumb + badge trạng thái, rồi lưới card:
Thông tin khách hàng | Thông tin khoản vay đề nghị (mỗi card có nút "Chỉnh
sửa" điều hướng sang tab tương ứng) → Chỉ tiêu tài chính sơ bộ (6 số liệu,
tái dùng `MetricCard`/`MetricValue` type đã có ở `shared/MetricCard.tsx`) →
Đánh giá & Khuyến nghị → Điểm cần lưu ý (risk flags, tái dùng
`RiskFlagsSection.tsx` đã có) → Trạng thái hồ sơ (timeline 4 mốc) → Hồ sơ
còn thiếu → Hồ sơ đã tải lên (file + category + status badge) → AI Insight
(tái dùng `AiInsightSection.tsx`).

**Tái dùng tối đa components `web/components/shared/*` đã có** thay vì viết
mới — đây là lý do chính các phần "Chỉ tiêu tài chính", "Điểm cần lưu ý",
"AI Insight" trong bảng trên đã ghi rõ component nguồn.

## Xuất Word MB01A QT.RR.038 (lần 3)

**Cơ chế đã xác minh trên file thật** (không phải giả định):
- File có 1 bảng lớn (134 dòng × tối đa 69 cột, nhiều merged cell).
- Checkbox là **legacy `FORMCHECKBOX` field** (`<w:ffData><w:checkBox>
  <w:default w:val="0|1"/></w:checkBox></w:ffData>`, bookmark tên kiểu
  `Check9`) — **tên bookmark KHÔNG duy nhất** trong toàn file (đã xác nhận
  2 checkbox Nam/Nữ cùng dùng tên `Check9`), nên phải định vị checkbox theo
  **(row_index, cell_index, thứ tự xuất hiện trong cell)**, không theo tên.
  Set giá trị bằng cách đổi `w:default/@w:val` từ `"0"` sang `"1"`.

**Cách làm** (`app/agents/rb_portal/mb01a_export.py`, theo pattern
`io.BytesIO()` + `document.save()` đã dùng ở `mb02_export.py`, nhưng
**load từ template thật** thay vì `docx.Document()` rỗng):

```python
def build_mb01a_docx(case: RbCase) -> bytes:
    document = docx.Document("docs/templates/MB01A_QT.RR.038_lan_3.docx")
    table = document.tables[0]
    _set_cell_text(table, row=3, cell=0, value=case.customer.full_name)  # "Họ tên:"
    _check_box(table, row=4, cell=0, occurrence=0 if case.customer.gender == "male" else 1)
    ...  # bảng mapping đầy đủ là 1 task riêng trong plan, xem "Phạm vi field"
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()
```

**Phạm vi field** (đã thống nhất trong "Quyết định phạm vi" #3): điền đầy
đủ các phần khớp với 6 tab RB Portal đã định — thông tin cá nhân (dòng
2–19), hoạt động kinh doanh (20–31) hoặc nghề nghiệp (32–41) tuỳ
`income.source_type`, thông tin tài chính thu/chi (65–81), khoản vay đề
nghị (82–89), TSBĐ (122–126), quan hệ tín dụng (127–132). **Để trống**
(không bịa): vợ/chồng (49–56), người bảo lãnh (57–64), thẻ tín dụng chính/
phụ (99–121), hạn mức khung (90–98) — RB Portal chưa có tab thu thập các
mục này.

**Rủi ro kỹ thuật cần proof-of-concept sớm trong plan** (task đầu tiên của
phần export, trước khi làm toàn bộ bảng mapping): ghi thử 1 checkbox + 1 ô
text, mở lại bằng `python-docx` để đọc `w:default` xác nhận đổi đúng giá
trị, **và** convert thử sang PDF bằng `libreoffice --headless --convert-to
pdf` (đã có LibreOffice khả dụng trong nhiều môi trường CI tương tự — cần
kiểm tra) để xác nhận checkbox **hiển thị đã tick** khi mở bằng phần mềm
đọc thật, không chỉ đúng ở tầng XML. Nếu môi trường không có LibreOffice để
verify hình ảnh, ghi rõ giới hạn này khi bàn giao thay vì khẳng định suông.

## Zalo Chat Bot — placeholder

`GET /api/rb-portal/zalo-bot/qr` trả:
```json
{"status": "NOT_CONNECTED", "qr_url": null,
 "message": "Chưa kết nối Zalo OA — liên hệ IT để cấu hình bot chính thức."}
```
`ZaloBotModal.tsx` render placeholder rõ ràng (icon + message trên), không
có ảnh QR giả. Khi có OA thật, chỉ cần đổi response của endpoint này —
frontend không đổi.

## Rà soát so với Acceptance Criteria gốc của brief

| # | Tiêu chí gốc | Trạng thái trong spec này |
|---|---|---|
| Login hoạt động + route protection | **Không làm** (Quyết định #2) |
| Tạo case và persist dữ liệu | Có |
| Nhập Pháp lý/Nguồn thu/Khoản vay/TSBĐ/Hồ sơ khác | Có |
| Nguồn thu kinh doanh + kiểm tra Tờ khai thuế | Có |
| Upload file gắn case_id + category | Có |
| Tab Tổng hợp giống ảnh tham chiếu | Có |
| Thẩm định sơ bộ chạy được, không silent fail | Có |
| Metric null-safe | Có (tái dùng `Metric.need_more_data` pattern) |
| Risk + missing + next action hiển thị đúng | Có |
| Xuất MB01A QT.RR.038 (lần 3).docx | Có, phạm vi field như trên |
| QR Zalo mở được sau login | **Đổi**: mở được, không cần login, QR là placeholder |
| AI lỗi không sập core flow | Có |
| Refresh không mất dữ liệu | Có (case persist ở backend, không phụ thuộc localStorage) |
| Build/deploy pass | Có, verify trước khi báo hoàn tất |
| Audit log cho login, case create/update... | **Một phần**: audit case-level có, không có "login" (vì không login) và actor là hằng số |

## Ngoài phạm vi plan này (đã nêu ở "Quyết định phạm vi")

- Đăng nhập/SSO/RBAC thật.
- Zalo OA/bot thật (chỉ làm placeholder).
- Các phần form MB01A không có tab thu thập tương ứng (vợ/chồng, người bảo
  lãnh, thẻ tín dụng, hạn mức khung) — để trống trên file xuất.
