# M-Insight 360 — Thiết kế kiến trúc (MSB x GreenNode AI Hackathon 2026)

Ngày: 2026-09-21 · Hạn nộp bài: trưa 2026-09-22

## 1. Mục tiêu & phạm vi

RM khối EB/RB của MSB mất 4-8h đọc/thẩm định 1 bộ hồ sơ tín dụng, sau đó tự soạn tờ trình thủ công. M-Insight 360 là trợ lý AI giúp RM: nhận hồ sơ khách hàng upload (docx/pdf/xlsx/csv, kể cả ảnh/scan), tự OCR + trích xuất + đối chiếu dữ liệu, **tính toán tài chính bằng code xác định (không để LLM tự đoán số)**, phát hiện rủi ro/red-flag có bằng chứng, đối chiếu chính sách demo, và soạn dự thảo tờ trình tín dụng. **Agent chỉ chuẩn bị & kiến nghị — con người luôn là người quyết định cuối cùng.**

MVP (theo quyết định của chủ đầu tư) gồm **cả 3 agent**: Agent RB, Agent EB, và Agent Cross-sell (skill 8 — được ưu tiên vì ban lãnh đạo quan tâm). Zalo bot và tính năng "Lịch sử thẩm định" **ngoài phạm vi MVP** (đã được xác nhận không bắt buộc). Ưu tiên cao nhất: pipeline chạy được từ lúc nhập liệu tới lúc ra kết quả, cho cả 3 agent.

## 2. Kiến trúc tổng thể (đã chốt với người dùng)

- **Một repo, một Docker image**: backend FastAPI phục vụ cả REST API lẫn frontend Next.js đã build (static). Thoả đúng yêu cầu bắt buộc duy nhất của GreenNode AgentBase Runtime: lắng nghe port 8080, có `GET /health` trả 200. Không tách frontend ra host riêng.
- **CI/CD qua GitHub Actions — KHÔNG cài Docker local**: workflow `.github/workflows/deploy.yml` (đã viết & **đã kiểm chứng chạy thành công thật** — xem mục 10) build image → push Container Registry GreenNode → tạo/update Agent Runtime → health check.
- **Skill AgentBase đã vendor** vào `.claude/skills/agentbase*` (theo đúng yêu cầu BTC "Bước 1 bắt buộc: Import AgentBase Skills").
- **Kiến trúc 3 lớp cho mọi agent** (nguyên tắc xuyên suốt cả 3 agent, lấy từ system prompt RB & Cross-sell):
  1. **Lớp trích xuất (facts)** — OCR/parse tài liệu, mỗi giá trị lưu kèm: số gốc, số chuẩn hoá, file nguồn, trang/ô, phương pháp trích xuất, độ tin cậy.
  2. **Lớp tính toán (rule engine, code Python thuần, KHÔNG qua LLM)** — mọi công thức tài chính, mọi red-flag, mọi rule chính sách chạy bằng code xác định. Thiếu input bắt buộc → trả `"NEED_MORE_DATA"`/`"CALCULATION_REQUIRED"`, không suy đoán.
  3. **Lớp AI diễn giải (LLM)** — chỉ nhận JSON đã tính toán xong ở lớp 2, viết nhận xét/tường thuật có dẫn chứng (phần "WHY", tóm tắt cho RM, dự thảo tờ trình). Không tự tính số, không ghi đè giá trị.

### Cấu trúc thư mục

```
/app
  /extraction        # Lớp 1 — dùng chung cho cả 3 agent
    /parsers          # docx, pdf (text-layer), xlsx/csv
    /ocr               # vision LLM (ảnh/PDF scan) + fallback thư viện
  /engine
    /core              # framework lớp 2 dùng chung (Evidence, Metric, RuleResult...)
    /rb                # công thức/ngưỡng/red-flag RB (mục 5)
    /eb                # công thức/ngưỡng/red-flag EB (mục 6)
    /crosssell         # 6 rule + QĐ.EB.039 (mục 7)
  /agents              # Lớp 3 — prompt & sinh nhận xét riêng từng agent
  /api                 # FastAPI: /api/rb/assess, /api/eb/assess, /api/crosssell/assess
  /storage             # SQLite + repository (mục 9)
  /web                 # Next.js, build ra static, FastAPI serve (mục 8)
Dockerfile
.github/workflows/deploy.yml
```

Agent nào xử lý request do **tab/nút bấm trên UI quyết định** (không để LLM tự chọn luồng) — giữ đúng tinh thần "AI chuẩn bị, không tự quyết định", dễ test trong thời gian ngắn.

## 3. Document Intake & Extraction (Lớp 1)

Input cho phép: **docx, pdf, xlsx, csv** (theo yêu cầu), ảnh (jpg) khi đính kèm trong PDF scan.

- **Văn bản có lớp chữ** (PDF digital, docx, xlsx, csv) → parse bằng thư viện: `pdfplumber`/`PyMuPDF` (PDF), `python-docx` (Word), `openpyxl`/`pandas` (Excel/CSV).
- **PDF scan/ảnh (không có lớp chữ)** → gửi cho LLM vision qua GreenNode MaaS. **Đã verify thật (test 21/09/2026)**: `qwen/qwen3.6-flash` và `google/gemma-4-31b-it` đọc ảnh chính xác (trả lời đúng màu ảnh test, có `image_tokens`/`multimodal_tokens` trong response). `z-ai/glm-5.2-hackathon` **từ chối thẳng** nội dung `image_url` (API error) — **không dùng GLM cho OCR ảnh**. Có test case thật cần OCR: 24 file PDF trong bộ hồ sơ EB Alpha Group đã bị raster hoá hoàn toàn (0 ký tự text layer) — đây là phép thử OCR thực tế.
- Fallback nếu vision-model lỗi/không khả dụng: OCR thư viện (Tesseract/PaddleOCR). Chỉ ghi "đã OCR" khi pipeline OCR **thực sự chạy** — không đoán số theo tên file.
- Mỗi trường trích xuất lưu: `raw_value`, `normalized_value`, `source_file`, `location` (trang/ô), `extraction_method`, `confidence`. Mâu thuẫn giữa 2 chứng từ → `CROSS_DOCUMENT_CONFLICT`, không tự chọn 1 giá trị.

## 4. Model LLM assignment (đã chốt với người dùng)

| Việc | Model | Lý do |
|---|---|---|
| OCR ảnh/PDF scan | `qwen/qwen3.6-flash` hoặc `google/gemma-4-31b-it` | Đã verify xử lý ảnh chính xác |
| Lớp 3 — viết nhận xét/tờ trình (text-only) | `z-ai/glm-5.2-hackathon` | Theo yêu cầu người dùng ("thông minh"); không nhận ảnh nên chỉ dùng cho việc thuần văn bản |

API endpoint: `https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1/chat/completions` (OpenAI-compatible), key lưu trong secret `LLM_API_KEY`.

## 5. Agent RB (Retail/Cá nhân/Hộ kinh doanh)

Nguồn: sheet "02. Agent RB" trong `M Insight 360.xlsx` — system prompt đầy đủ 24 phần, dùng **nguyên văn làm system prompt lớp 3**. Tóm tắt các điểm implement bắt buộc ở lớp 2 (engine):

- **Hồ sơ đầu vào bắt buộc theo luồng** (nhóm A pháp lý / B nguồn thu / C khoản vay), thiếu (*) → `status="ADDITIONAL_DOCUMENTS_REQUIRED"`, không thẩm định.
- **Phân loại chứng từ**: `LEGAL_IDENTITY, BUSINESS_REGISTRATION, TAX_DOCUMENT, BANK_STATEMENT, INCOME_DOCUMENT, ECOMMERCE_REVENUE, CIC_REPORT, LOAN_REQUEST, PURCHASE_CONTRACT, SUPPLIER_INVOICE, COLLATERAL_DOCUMENT, FINANCIAL_STATEMENT, BUSINESS_CONTRACT, OTHER`. Tin cậy thấp → `UNCLASSIFIED` + `MANUAL_REVIEW_REQUIRED`.
- **Credit Engine (lớp 2, bắt buộc code xác định)**: `eligible_income, monthly_debt_obligation, proposed_monthly_payment, DTI, DSR, FOIR, LTV, remaining_disposable_income`. Mỗi metric trả `{metric, value, formula, input_values, input_sources}`. Thiếu input → `metric_status="NEED_MORE_DATA"`.
- **Risk flags**: `IDENTITY_CONFLICT, TAX_ID_MISMATCH, INCOME_UNVERIFIED, HIGH_EXISTING_DEBT, HIGH_DTI, HIGH_DSR, ABNORMAL_STATEMENT, NEGATIVE_CASHFLOW, REVENUE_VOLATILITY, DOCUMENT_INCONSISTENCY, POLICY_GAP, MISSING_CIC, MISSING_MANDATORY_DOCUMENT, LOW_OCR_CONFIDENCE, SUSPICIOUS_DOCUMENT, TRANSACTION_RISK_SIGNAL`. Mỗi flag có `severity(LOW/MEDIUM/HIGH), evidence, impact, recommended_action`.
- **Credit Readiness** (KHÔNG phải điểm tín dụng): `READY, READY_WITH_CONDITIONS, NOT_READY, MANUAL_REVIEW_REQUIRED`.
- **Khuyến nghị cuối** — CHỈ 4 giá trị được phép: `PROCEED_FOR_HUMAN_REVIEW, PROCEED_WITH_CONDITIONS, ADDITIONAL_DOCUMENTS_REQUIRED, REQUIRES_CREDIT_OFFICER_REVIEW`. **TUYỆT ĐỐI không** dùng APPROVE/REJECT/APPROVED/DECLINED.
- **Output JSON schema chuẩn** (đúng theo prompt gốc phần 18):
```json
{"case_id":"","customer_profile":{},"document_status":{"legal":[],"income":[],"loan_request":[]},
 "mandatory_document_check":{},"document_authenticity":{"status":"","signals":[],"action":""},
 "income_assessment":{},"statement_analysis":{},"existing_obligations":{},"credit_engine":{},
 "policy_eligibility":[],"risk_flags":[],"missing_data":[],"credit_readiness":"","recommendation":"",
 "why":[],"next_best_actions":[],"credit_memo":"","evidence":[]}
```
- **Test cases đã có ground truth** (dùng để verify pipeline, KHÔNG copy số vào code — chỉ dùng để so khớp kết quả):
  `Example data input-output/Data example RB/M_CREDIT360_3_STANDARD_TEST_CASES/` — CASE_01 TikTok Shop (DTI=0.2262, kỳ vọng CONDITIONAL/HUMAN REVIEW), CASE_02 Vietcons (OCF âm, phải thu cao, kỳ vọng REVIEW), CASE_03 An Nhiên Beauty (TAX_ID lệch 1 số giữa profile và eTax → kỳ vọng `TAX_ID_MISMATCH` + `SUSPICIOUS` + `MANUAL_VERIFICATION_REQUIRED`, KHÔNG được kết luận "FAKE_DOCUMENT").

## 6. Agent EB (Doanh nghiệp SME)

Nguồn: sheet "01. Agent EB". **Lưu ý: tài liệu gốc bị cắt giữa chừng** ở "Bước 8 — Đề xuất cấu trúc hạn mức..." — phần sau (nếu có) không có trong dữ liệu cung cấp; implement tới hết Bước 8 + 5 red-flag, các bước sau nếu thiếu để `NEED_MORE_DATA`.

- 8 bước xử lý: (1) Kiểm kê & định danh hồ sơ, (2) Trích xuất có chứng cứ, (3) Đối soát BCTC, (4) Tính toán định lượng (NWC, vòng quay, đòn bẩy, DSCR, ICR...), (5) Phân tích tín dụng, (6) Cảnh báo rủi ro, (7) Đối chiếu chính sách (chỉ áp policy đã nạp có version; thiếu → `CHƯA_CÓ_CĂN_CỨ_CHÍNH_SÁCH`), (8) Đề xuất cấu trúc hạn mức.
- **5 Red-flag bắt buộc** (mã, công thức, ngưỡng demo — phải gắn nhãn "quy tắc demo"):
  - `RF01` Mất cân đối vốn: VCSH ≤ 0 hoặc NWC = TSNH − NNH < 0. Mức: cao.
  - `RF02` CFO < 0 trong kỳ đánh giá. Mức: cao.
  - `RF03` Dư nợ vay ngắn hạn / tổng nợ phải trả > **50%** (ngưỡng demo). Mức: trung bình.
  - `RF04` Sai lệch Digisale/DSP vs BCTC: `|BCTC − DSP|/|BCTC|` > **5%** (ngưỡng demo); không có DSP → `CHƯA ĐÁNH GIÁ` (không phải "đạt"). Mức: cao.
  - `RF05` DSCR < **1.0** hoặc ICR < **1.5** (ngưỡng demo). Thiếu CFO/CFADS/gốc/lãi → `KHÔNG ĐỦ DỮ LIỆU`, không gán 0. Mức: nghiêm trọng.
- Mỗi red-flag trả: mã, trạng thái (`KÍCH HOẠT/KHÔNG KÍCH HOẠT/CHƯA ĐÁNH GIÁ`), mức độ, giá trị quan sát, ngưỡng + phiên bản chính sách, công thức, evidence, câu hỏi xác minh, đề xuất kiểm soát.
- **Output web bắt buộc** (theo `Output Agent EB/OUTPUT TREN WEB AGENT EB.docx`): các vùng hiển thị Doanh nghiệp / Kỳ dữ liệu / Hồ sơ / B02 (BCTC) với nguồn dữ liệu rõ ràng; hệ số thanh toán hiện hành = TSNH/NNH (chỉ tính khi mẫu số > 0); cảnh báo rủi ro; cơ hội bán chéo/tài trợ đầu ra (liên kết Cross-sell); backend trả payload có cấu trúc cho mỗi trường số.
- **Mẫu tờ trình xuất ("Xuất tờ trình MB02")**: tài liệu gốc yêu cầu file "MB02c" nhưng **file này KHÔNG có trong bộ dữ liệu cung cấp** — chỉ có `Form Tờ trình/2a. MB02a.QT.RR.037 To trinh TD cua HO (SME, MC)_Sua doi.docx` (rất dài, nhiều trường ký duyệt nội bộ không thể agent tự điền). **Quyết định implement**: dùng MB02a làm template xuất, agent chỉ tự điền các trường có bằng chứng (tổng quan KH, nhu cầu tín dụng, đánh giá nguồn thu, nghĩa vụ hiện hữu, chỉ số Credit Engine, red-flags, hồ sơ thiếu, khuyến nghị) — các trường ký duyệt/nội bộ để trống cho RM/CBTĐ điền tay. Nếu MB02c thật xuất hiện trước hạn nộp bài, ưu tiên đổi sang MB02c.

## 7. Agent Cross-sell (skill 8 — EB & RB)

Nguồn: sheet "03. Agent Cross sale EB, RB". Input chính: sao kê ngân hàng (pdf/xlsx/csv), input phụ tùy chọn: bảng công nợ 131 (phải thu)/331 (phải trả).

**Chưa có sẵn**: tài liệu tham chiếu tới 2 script `pipeline.py`/`analyze_statement.py` và `xls_biff8.py` như đã tồn tại & kiểm chứng (PASS 1.295/1.295 GD, 924 GD Alpha Group) nhưng **các file này không có trong bộ dữ liệu cung cấp** — phải tự xây trong dự án này (thuộc lớp 1+2). Cột chuẩn theo README mẫu (HEADER_MAP): `Ngày | Số bút toán | Ghi nợ | Ghi có | Diễn giải | Đối tác | Tài khoản đối tác | Ngân hàng đối tác | Loại tiền | Nguồn`. Hỗ trợ sao kê MSB/MB/TPBank (MSB xếp ngày tăng dần; MB/TPBank giảm dần).

### Bước 0 — Pre-check chứng từ (BẮT BUỘC chạy trước mọi phân tích)
Kiểm toán: `Số dư đầu kỳ + Thu − Chi = Số dư cuối kỳ` (toàn kỳ) và từng dòng. Verdict `BLOCK` (dừng, báo khách hàng bổ sung — dùng đúng câu mẫu, **cấm dùng từ "lỗi/sai sót/RM gửi thiếu"**) / `WARN` (vẫn phân tích, hạ trần Confidence xuống M) / `PASS`. Không có cột số dư → không đối chiếu được, phải nêu rõ (xem case Alpha Group thật: 924 GD nhưng thiếu cột số dư → WARN).

### Bước 0B — Kiểm tra chất lượng bóc tên
WARN nếu: >20% tên đối tác rỗng, >10% tên <8 ký tự, >10% tên không khoảng trắng, tên cụt đầu (`PANY`, `ONG TY`...). Lọc rác tên: toàn số, `DON VI/NGUOI THU HUONG`, `TONG/CONG/SO DU/BALANCE/TOTAL`, <4 ký tự — **không loại tên bắt đầu bằng `TK`** (có thể là "Thiết Kế").

### Phạm vi dữ liệu
Chỉ sao kê **pháp nhân**. Phát hiện sao kê cá nhân → DỪNG. Lưu tối đa 12 tháng rồi xoá.

### Phân loại dòng tiền — bắt buộc dùng `operating_in`
`direct` (doanh thu thật) / `cash` (nộp tiền mặt) / `interbank` (điều chuyển nội bộ KH). Mọi tính toán deal size/doanh thu PHẢI dùng `operating_in = flow_classification.direct.inflow`, **không dùng `total_in`**. `operating_in_pct < 60%` → cảnh báo cơ hội kéo dòng tiền về MSB. Thị phần theo bank = `direct_inflow[bank] / operating_in` (không dùng tổng thu, tránh đếm 2 lần tiền tự chuyển). Nhận diện tự chuyển bằng regex có cấu trúc + loại trừ "LIÊN DANH".

### Bộ 6 rule bán chéo
1. **Rule 1 (RB — lương)**: diễn giải chứa "Lương/Salary/Payroll/CT LUONG" ≥1 GD/năm → Payroll + thẻ tín dụng CBNV. Thiếu dữ liệu ghi nợ → "chưa đủ dữ liệu", không kết luận "không có lương".
2. **Rule 2 (EB — SCF/thanh toán)**: top 3 đối tác In/Out theo tần suất+giá trị; tần suất ≥3 lần/tháng **và** ≥500tr/đối tác (ngưỡng vào danh sách) → SCF hoặc bảo thanh toán L/C.
3. **Rule 3 (nguồn vốn nhàn rỗi → CCTG/FD)**: số dư cuối ngày > **5 tỷ**, xuất hiện ≥**10 ngày** → CCTG (nền cao ổn định) hoặc FD ngắn hạn (biến động). Deal size = **số dư thấp nhất kỳ** (không phải trung bình). Tính riêng từng bank, không cộng gộp. **Bẫy đã biết**: không dùng số dư luỹ kế suy ra từ Thu−Chi bắt đầu từ 0 khi không có cột số dư thật — phải đối chiếu BCTC nếu có.
4. **Rule 4 (FX)**: ≥1 GD ngoại tệ → hạn mức FX + Trade Finance; phải xác minh cột Loại tiền thực tế, không chỉ bắt từ khoá. Không có tín hiệu ≠ không có nhu cầu.
5. **Rule 5 (công nợ 131/331)**: chỉ chạy khi có bảng công nợ (không ghép tên với sao kê — bảng 131/331 chỉ có tên, không MST). 5A: deal size tài trợ phải thu = 80% dư nợ 131 trong hạn (90% nếu qua L/C/BLTT, 98% nếu BCT hoàn hảo theo L/C). 5B: hạn mức SCF/bảo lãnh dựa dư có 331. 5C: DSO = Dư nợ 131/Doanh thu×số ngày kỳ; DPO = Dư có 331/Giá vốn×số ngày kỳ. 5D: tỷ lệ về MSB = operating_in(MSB)/Tổng phát sinh Có 131; <50% → tín hiệu mạnh, kèm cảnh báo bắt buộc (không chỉ đích danh mức độ rò rỉ).
6. **Rule 6 (vay ở bank khác)**: quét "KHE UOC/GIAI NGAN/THU GOC/THU LAI/TRA NO VAY" + mã `LD+số` → đề xuất chia sẻ hạn mức/tái tài trợ. Không suy ra dư nợ hiện tại (cần RM lấy CIC). Loại các GD vay/trả nợ khỏi danh sách đối tác tiềm năng.

### QĐ.EB.039 — Tài trợ đầu ra KHDN
Deal size = tỷ lệ(phương thức) × giá trị phương án (annualized). Bảng tỷ lệ: BCT hoàn hảo theo L/C 98%, theo L/C/BLTT đầu ra 90%, BCT xuất khẩu (D/A,D/P,T/T,CAD) 90%, theo HĐDR/thông báo trúng thầu 80%, phải thu trong nước 80%.

### Output
Dashboard dòng tiền (theo tháng, top đối tác đã loại GD vay/tiền mặt, thị phần theo bank) + bảng cơ hội bán chéo (Priority + Confidence, Confidence bị hạ trần theo Pre-check verdict) + kịch bản tiếp cận. Có ví dụ thật đầy đủ tại `Data example EB/Output Agent cross sell/OUTPUT_KY_VONG_ALPHA_GROUP (1).md` — dùng làm tài liệu tham chiếu định dạng khi implement, không copy số liệu.

## 8. Web app (theo sheet "Web", đã bỏ mục Lịch sử thẩm định khỏi MVP)

- Design tokens lấy từ msb.com.vn thật (đã fetch 2026-09-21): primary `#091E42` (navy), accent `#F4600C` (cam), nền `#DEE5EF`/`#FFFFFF`, font **Inter**.
- 2 tab **RB / EB** (Cross-sell hiển thị như một khối kết quả bổ sung trong trang kết quả, không có tab riêng — spec Web gốc không yêu cầu tab cross-sell).
- Trang mặc định "Thẩm định AI", 3 khối:
  1. Banner giới thiệu Agent + tính năng.
  2. Form thẩm định: Tên KH* (bắt buộc), MST* (bắt buộc), Upload file* (bắt buộc, nhận docx/pdf/xlsx/csv), nút "Chạy thẩm định AI" (validate đủ trường trước khi chạy), hiển thị tiến trình theo bước (OCR → Tính toán → Đối chiếu chính sách → Soạn nhận xét → Hoàn tất).
  3. Kết quả thẩm định gần nhất hiện ngay dưới form, kèm nút "Xuất tờ trình MB02".

## 9. Lưu trữ dữ liệu

**Quyết định (đã chốt với người dùng)**: SQLite cục bộ trong container. Chấp nhận mất dữ liệu mỗi lần redeploy (vì tính năng Lịch sử thẩm định không bắt buộc trong MVP) — không cần DB ngoài.

## 10. CI/CD & Deploy — ĐÃ XÂY DỰNG VÀ KIỂM CHỨNG THÀNH CÔNG (2026-09-21)

- `.github/workflows/deploy.yml`: build Docker image trên GitHub Actions runner (không cần Docker local) → đăng nhập Container Registry GreenNode thật (`vcr.vngcloud.vn/111480-abp114553`) → push → tạo/update Agent Runtime (`runtime.sh`, flavor `runtime-s2-general-2x4`) → poll endpoint URL (có retry, tránh race condition) → health check `/health`.
- **Kết quả thực tế đã chạy xanh**: runtime `m-insight-360` ACTIVE, endpoint `https://endpoint-21af0bfd-8ddd-44c6-a5dc-60a08bf4770c.agentbase-runtime.aiplatform.vngcloud.vn` trả `{"status":"ok"}`. App hiện tại chỉ là FastAPI placeholder (`app/main.py`) — sẽ được thay bằng app thật khi implement.
- **Lưu ý kỹ thuật đã phát hiện, cần nhớ khi implement tiếp**:
  - `cr.sh` (script CR trong bộ skill AgentBase) trả `PROVISIONING_FAILED` (HTTP 500) cho service account `GREENNODE_CLIENT_ID`/`GREENNODE_CLIENT_SECRET` hiện tại — nghi ngờ thiếu policy `vcrFullAccess`. **Workaround đang dùng**: đăng nhập CR trực tiếp bằng username/secret lấy từ console (secret `GREENNODE_CR_USERNAME`/`GREENNODE_CR_PASSWORD`), không qua `cr.sh`. Nếu BTC gắn quyền cho service account, có thể chuyển lại dùng `cr.sh --from-cr` cho gọn (không bắt buộc).
  - Flavor hợp lệ thực tế cho tài khoản: `runtime-s2-general-2x4` (2 CPU/4GB), `runtime-s2-general-4x8` — KHÔNG phải `1x1-general` như trong ví dụ tài liệu skill.
  - Endpoint URL cần retry sau khi tạo/update runtime (API không trả `url` ngay lập tức).
- **Secrets đã cấu hình trên GitHub** (Settings → Secrets → Actions): `GREENNODE_CLIENT_ID`, `GREENNODE_CLIENT_SECRET`, `LLM_API_KEY`, `GREENNODE_CR_USERNAME`, `GREENNODE_CR_PASSWORD`.

## 11. Ngoài phạm vi MVP / Rủi ro đã biết

- **Ngoài phạm vi**: Zalo bot, tính năng "Lịch sử thẩm định" (đã xác nhận với người dùng).
- **Rủi ro/giả định cần theo dõi**:
  - Mẫu tờ trình MB02c không có sẵn → dùng MB02a (mục 6).
  - EB brief bị cắt cụt ở Bước 8 → chỉ implement tới đó, các phần sau để `NEED_MORE_DATA` nếu cần mở rộng.
  - Script `pipeline.py`/`analyze_statement.py`/`xls_biff8.py` cho Cross-sell không có sẵn, phải tự viết (mục 7).
  - SQLite mất dữ liệu mỗi lần redeploy — chấp nhận được cho demo hackathon.
  - Ngưỡng DSCR/ICR/RF03/RF04/Rule 2/Rule 3... đều là **ngưỡng demo**, phải hiển thị rõ "quy tắc demo"/`policy_mode=DEMO_UAT`, không được trình bày như chuẩn MSB chính thức.

## 12. Bước tiếp theo

Chuyển sang lập kế hoạch triển khai chi tiết (writing-plans) cho: (A) Foundation (mục 2-4, 8-10 — đã xong phần hạ tầng CI/CD, còn lại extraction pipeline + web skeleton + credit-engine framework), (B) Agent RB, (C) Agent EB, (D) Agent Cross-sell. B/C/D có thể triển khai song song sau khi Foundation xong vì cùng dùng chung framework lớp 2 nhưng rule set độc lập.
