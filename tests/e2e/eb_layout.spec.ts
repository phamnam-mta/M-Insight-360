import { test, expect, Page } from "@playwright/test";

// Seeds a full EB assessment result straight into localStorage (the same
// place HistoryPanel reads from — see web/lib/api.ts's
// loadHistoryItemsLocally/startHistoryPlaceholder/finishHistoryPlaceholder)
// and selects it via the history list. This drives the REAL
// EbResultPanel.tsx render tree end-to-end without needing a live BCTC
// upload or an LLM call — T22-T28 are layout concerns the computation
// layer (already covered by the Phần A/B pytest suites) doesn't touch.
async function seedEbHistory(page: Page, result: Record<string, unknown>) {
  const item = {
    id: Date.now(),
    agent_type: "eb",
    customer_name: "CÔNG TY CỔ PHẦN ĐẦU TƯ ALPHA GROUP",
    tax_id: "0000000000",
    result,
    created_at: new Date().toISOString(),
    run_status: "success",
  };
  await page.addInitScript((serialized) => {
    window.localStorage.setItem("msb_assessment_history_eb", serialized);
  }, JSON.stringify([item]));
}

async function openEbResult(page: Page) {
  await page.goto("/");
  const ebTab = page.getByRole("button", { name: "EB" });
  if (await ebTab.isVisible()) await ebTab.click();
  await page.getByText("CÔNG TY CỔ PHẦN ĐẦU TƯ ALPHA GROUP").first().click();
}

const FULL_RESULT = {
  case_id: "EB-TEST-001",
  assessed_at: new Date().toISOString(),
  customer_profile: { customer_name: "CÔNG TY CỔ PHẦN ĐẦU TƯ ALPHA GROUP", tax_id: "0000000000" },
  credit_engine: {
    nwc: { value: 128_061_897_765, status: "OK", formula: "x", input_values: {}, input_sources: {} },
    liquidity_balance: { value: 1.4212, status: "OK", formula: "x", input_values: {}, input_sources: {} },
    dscr: { value: null, status: "NEED_MORE_DATA", formula: "x", input_values: {}, input_sources: {} },
    icr: { value: 1.0, status: "OK", formula: "x", input_values: {}, input_sources: {} },
  },
  risk_flags: [
    { rule_id: "RF09", rule_name: "Khả năng trả nợ yếu (ICR)", status: "KÍCH HOẠT", severity: "CRITICAL", observed_value: 1.0 },
    { rule_id: "RF05", rule_name: "Khả năng trả nợ yếu (DSCR)", status: "CHƯA ĐÁNH GIÁ" },
  ],
  missing_data: [],
  credit_readiness: "MANUAL_REVIEW_REQUIRED",
  recommendation: "REQUIRES_CREDIT_OFFICER_REVIEW",
  overview: [],
  overview_summary: { checked: 0, total: 0, passed: 0, failed: 0, pending: 0 },
  overall_conclusion: "Cần thẩm định thêm",
  documents: [],
  why: ["Doanh thu tăng trưởng ổn định.", "Đòn bẩy ở mức an toàn."],
  credit_memo: "Tóm tắt hồ sơ.",
  export_available: true,
  ho_so_period: { selected: "2025", available: ["2025"] },
  capital_balance_check: { trai: 128_061_897_765, phai: 128_061_897_765, trang_thai: "Cân bằng", nhan_xet: "x" },
  financial_inputs: {
    net_revenue_vnd: 90_105_893_754, pbt_vnd: 29_084_707, pat_vnd: 23_267_766,
    interest_expense_vnd: 12_131_595_580, depreciation_vnd: 1, current_assets_vnd: 293_369_838_619,
    current_liabilities_vnd: 165_307_940_854, equity_vnd: 580_965_107_518, receivables_vnd: 1_030_523_666,
  },
  export_gate: { verdict: "XUAT_KEM_CANH_BAO", block_type: null, signal_count: 1, signals: [], data_warnings: [], reasons: [] },
  sanity_check: { suspect_fields: {}, balance_mismatch: false, balance_mismatch_detail: null },
};

const LOW_COVERAGE_RESULT = {
  ...FULL_RESULT,
  case_id: "EB-TEST-002",
  financial_inputs: { equity_vnd: 580_965_107_518 },
  export_gate: { verdict: "XUAT", block_type: null, signal_count: 0, signals: [], data_warnings: [], reasons: [] },
  risk_flags: [],
  why: [],
};

const SUSPECT_VALUE_RESULT = {
  ...FULL_RESULT,
  case_id: "EB-TEST-003",
  financial_inputs: { ...FULL_RESULT.financial_inputs, net_revenue_vnd: 2025 },
  sanity_check: {
    suspect_fields: { net_revenue_vnd: "Giá trị đọc được nghi ngờ sai dòng (2025 trùng số năm báo cáo 2025), đề nghị kiểm tra lại hồ sơ nguồn." },
    balance_mismatch: false, balance_mismatch_detail: null,
  },
};

test.describe("EB result panel — v2.3 layout (Phần C, T22-T28)", () => {
  test("T23: KPI card order is NWC, Liquidity Balance, DSCR, ICR", async ({ page }) => {
    await seedEbHistory(page, FULL_RESULT);
    await openEbResult(page);
    const labels = await page.locator('[data-testid="eb-kpi-card"] h3').allTextContents();
    expect(labels.slice(0, 4)).toEqual(["Vốn lưu động ròng", "Cân đối thanh khoản", "DSCR", "ICR"]);
  });

  test("T25: action buttons are inside the AI insight panel, not floating siblings", async ({ page }) => {
    await seedEbHistory(page, FULL_RESULT);
    await openEbResult(page);
    const panel = page.locator('[data-testid="eb-r1-panel"]');
    await expect(panel.getByRole("button", { name: /Stress Test/ })).toBeVisible();
    await expect(panel.getByRole("button", { name: /Soạn tờ trình MB02a/ })).toBeVisible();
  });

  test("T26: empty AI narrative never shows the banned technical phrase", async ({ page }) => {
    await seedEbHistory(page, LOW_COVERAGE_RESULT);
    await openEbResult(page);
    await expect(page.getByText(/vượt ngân sách thời gian xử lý/)).toHaveCount(0);
    await expect(page.getByText("Đang tổng hợp nhận định")).toBeVisible();
  });

  test("T28: no cross-sell block under any heading", async ({ page }) => {
    await seedEbHistory(page, FULL_RESULT);
    await openEbResult(page);
    await expect(page.getByText(/Cơ hội bán chéo|Gợi ý sản phẩm|Khuyến nghị bán thêm/)).toHaveCount(0);
  });

  test("T22: <30% coverage triggers compact KPI mode with M2 as the focus", async ({ page }) => {
    await seedEbHistory(page, LOW_COVERAGE_RESULT);
    await openEbResult(page);
    await expect(page.getByText("Cần bổ sung để chạy thẩm định")).toBeVisible();
    const compactCards = page.locator('[data-testid="eb-kpi-card"]');
    await expect(compactCards.first()).toHaveCSS("max-height", "72px");
    // No card renders "Chưa có dữ liệu" text at all (H8: that phrase never
    // appears verbatim — unknown cards show "—" plus a collapsed link).
    await expect(page.getByText("Chưa có dữ liệu")).toHaveCount(0);
  });

  test("T24: all middle-column slots render (banner, KPIs, capital balance, QĐ039, both red-flag groups)", async ({ page }) => {
    await seedEbHistory(page, FULL_RESULT);
    await openEbResult(page);
    await expect(page.getByText("Kết luận thẩm định")).toBeVisible();
    await expect(page.locator('[data-testid="eb-kpi-card"]')).toHaveCount(4);
    await expect(page.getByText("Cân bằng hai vế · kỳ hạn nguồn vốn")).toBeVisible();
    await expect(page.getByText("Tài trợ chuỗi — QĐ.EB.039 (chỉ tiêu thẩm định)")).toBeVisible();
    await expect(page.getByText("Tín hiệu tín dụng cần thẩm định thêm")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Cảnh báo dữ liệu" })).toBeVisible();
  });

  test("T27: a year-collision suspect value renders as unknown, not as the real number", async ({ page }) => {
    await seedEbHistory(page, SUSPECT_VALUE_RESULT);
    await openEbResult(page);
    await expect(page.getByText(/nghi ngờ sai dòng/).first()).toBeVisible();
    await expect(page.getByText("2.025", { exact: false })).toHaveCount(0);
  });
});
