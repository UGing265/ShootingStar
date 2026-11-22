# Brainstorm: Gemini dự đoán xu hướng 6h + tái cấu trúc pipeline

Ngày: 2026-11-22 · Trạng thái: đã duyệt thiết kế, chưa lập plan

## Vấn đề
- Gemini 2.5 Flash luôn "trung lập" ở 30m → chiến thuật khóa.
  - Nguyên nhân gốc: schema cho phép `ABSTAIN`; prompt yêu cầu bằng chứng chặt + temp 0.1 → model né. Ở 30m BTC gần random walk nên né là hợp lý.
- Tầng research: mỗi job query Google grounding `"{pattern} definition criteria rules Steve Nison"` (`research_agent.py:28`) → tra lại kiến thức tĩnh, tốn tiền, không giá trị theo job.
- Context gửi Gemini nhiều nến thô → loãng.
- Code: `ExternalAnalysisService.run_pipeline` ~210 dòng ôm 5 stage; `gemini_adapter.py` 831 dòng trộn transport/prompt/mock.

## Quyết định đã chốt
| Chủ đề | Quyết định |
|---|---|
| Horizon | Cấu hình, mặc định 360 phút (6h); 30m vẫn chạy được |
| Output Gemini | Bắt `UP`/`DOWN` + `confidence` LOW/MED/HIGH (prompt có rubric từng mức). Bỏ % (cùng bản chất tự khai). Không LLM verifier (YAGNI) |
| Chống bịp tự tin | Python tính `agreement_score` = số chỉ số cùng chiều (số thật, hiện cạnh lời Gemini). Đủ mẫu → bảng đối chiếu: mỗi mức confidence thực tế đúng bao nhiêu % |
| Nhãn | close(t+6h) vs giá mua P; \|Δ\| < 1% = FLAT, không chấm (đo trước % mốc bị loại trên snapshot thật) |
| Khung nến | Đa khung, gộp từ nến 1m sẵn có: 1h × N ngày (khung chính) + 15m × 24h nhìn lại; không gửi 1m. N là tham số, mặc định 14 (thói quen, không bằng chứng), replay thử 7/14/30 |
| Horizon | Giữ 6h (360 phút), để tham số |
| Kiến thức | KHÔNG có thư viện kiến thức. Python tính chỉ báo bằng thư viện công thức (`pandas-ta`/`ta`/TA-Lib); Gemini đã biết định nghĩa RSI/MACD/mẫu nến |
| Replay | Mọi mốc; mốc trước knowledge cutoff model (~đầu 2025) gắn cờ `possible_memorization`, thống kê tách riêng |
| Baseline | "Luôn UP" + "theo đà 6h trước" (Python, độc lập, không tốn API) |
| Search | Bỏ Google grounding theo job (query đang hardcode `research_agent.py:28`); không thay bằng gì |
| Tin tức | Dự án riêng, brainstorm sau; chỉ chừa khối "bối cảnh" trong input stage phân tích (không code trước - YAGNI) |

## Phương án đã cân nhắc
1. Giữ 5 stage, chỉ đổi horizon → loại: vẫn ABSTAIN, vẫn tốn search, vẫn loãng.
2. **Chọn:** Python digest + KB tĩnh + 1 call Gemini + verifier + chấm vs baseline.
3. Gemini tự search tin/grounding → loại: không kiểm soát thời điểm bài viết (rò tương lai khi replay), đắt.

## Thiết kế
Pipeline (mỗi stage 1 file, <200 dòng; orchestrator mỏng):
1. `feed_stage` (Python): nến 1m đóng `<= t` → gộp 1h × 14 ngày + 15m × 24h → digest kỹ thuật có `feature_id`: trend EMA 1h/4h, RSI, MACD, ATR%, volume vs TB, vị trí giá trong range 24h/7d, swing high/low gần, mẫu nến (TA-Lib `CDL*`). Mục tiêu ~1–2k token.
2. `analyst_stage` (Gemini, 1 call): JSON `{direction, confidence, reasons[{feature_ids, text}]}`. Prompt: chỉ dùng số được cấp, cấm bịa số, rubric LOW/MED/HIGH.
3. `verify_stage` (Python): feature_id tồn tại, giá trị trích dẫn khớp; sai → cờ.
4. `report_stage` (Python): render VN UTC+7 qua `report_presentation.py`.

Chấm điểm: khi t+6h đóng → UP/DOWN/FLAT; bảng Gemini vs 2 baseline, chia theo confidence và cờ cutoff.

Tách adapter: transport (HTTP, key rotation, retry 503) / prompt builder / mock chuyển sang `tests/`. Xóa `research_agent.py` + grounding.

## Bằng chứng nghiên cứu (search 2026-11-22)
- Không nghiên cứu nào chỉ ra khung nến "tối ưu" cho dự báo 6h → chọn đa khung + A/B đo.
- BTC intraday momentum có, nhỏ: Shen, Urquhart & Wang 2022, Financial Review — https://onlinelibrary.wiley.com/doi/abs/10.1111/fire.12290
- TA crypto sau kiểm data-snooping đa số không có lời thật: Wei 2024 IJFE https://onlinelibrary.wiley.com/doi/full/10.1002/ijfe.2863 ; FRL reality check https://www.sciencedirect.com/science/article/abs/pii/S1544612320304414 ; ngược lại Annals of OR 2021 https://link.springer.com/content/pdf/10.1007/s10479-019-03357-1.pdf
- ML + chỉ báo trên BTC ~55–65% (trần lạc quan): https://arxiv.org/pdf/2410.06935
- LLM không chắc hơn bỏ LLM cho chuỗi thời gian: Tan et al., NeurIPS 2024 https://arxiv.org/abs/2406.16964 — LƯU Ý phạm vi: test kiến trúc forecaster gắn LLM, không phải prompt Gemini đọc chỉ số → cảnh báo, không phải bằng chứng trực tiếp.

## Kiểm chứng bổ sung (search 2026-11-22, lần 2)
- Knowledge cutoff gemini-2.5-flash = **01/2025** (Google AI docs https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash.md.txt ; Vertex https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/2-5-flash ; tech report https://arxiv.org/pdf/2507.06261) → cờ `possible_memorization` cho t < 2025-02-01.
- Prompt dặn "không dùng kiến thức sau mốc" KHÔNG ngăn được recall: Tang & Zhu https://arxiv.org/html/2504.14765v2 ; Gao et al. https://arxiv.org/pdf/2512.23847 ; LookaheadBench https://arxiv.org/pdf/2601.13770 → chỉ tách thống kê, không sửa bằng prompt.
- Verbalized confidence LLM overconfident; consistency-based (hỏi nhiều lần) tốt hơn: Xiong et al. ICLR 2024 https://arxiv.org/abs/2306.13063 → v1 dùng bảng đối chiếu; consistency để sau (tốn N× API).
- Baseline naive là chuẩn bắt buộc: Hewamalage et al. https://arxiv.org/pdf/2203.10716 ; Hyndman & Koehler 2006 https://www.doi.org/10.1016/J.IJFORECAST.2006.03.001
- Lookback: crypto momentum ngày/tuần (Liu & Tsyvinski RFS 2021 https://nber.org/papers/w24877 ; Liu, Tsyvinski & Wu, 1–4 tuần) → chỉ ủng hộ gián tiếp khoảng thử 7/14/30; 14 KHÔNG có bằng chứng riêng.

## Rủi ro
- Gemini có thể không vượt baseline → kết quả nghiên cứu hợp lệ, báo thật.
- Ngưỡng FLAT 1% có thể loại nhiều mốc 6h → đo tỷ lệ loại trên snapshot trước khi chốt.
- `confidence` tự khai → chỉ có giá trị khi bảng đối chiếu cho thấy HIGH đúng nhiều hơn LOW rõ rệt; ngược lại UI ghi "nhãn tự tin chưa có giá trị".
- Gemini biết định nghĩa chỉ báo: khả năng cao nhưng CHƯA kiểm; biết áp dụng/dự đoán: chưa biết → chỉ replay vs baseline trả lời được.
- Mẫu nhỏ: cần đủ mốc (≥ vài trăm, không chồng 6h) mới kết luận.
- Snapshot phải chứa ≥7 ngày trước t; thiếu → `INSUFFICIENT_HISTORY`.
- Contract/DB/FE đang dựa ABSTAIN + hypothesis/research → migration + sửa UI.

## Tiêu chí thành công
- 1 call Gemini/job, token input giảm rõ so hiện tại (đo thực tế).
- 0% ABSTAIN; mọi reason trỏ feature_id hợp lệ.
- Báo cáo accuracy Gemini vs baseline, theo confidence, tách cờ cutoff.
- Không file pipeline nào >200 dòng; pytest + FE typecheck pass.

## Câu hỏi mở
- Knowledge cutoff chính xác của gemini-2.5-flash (xác minh docs Google trước khi chốt mốc cờ).
- Snapshot hiện có đủ 7 ngày lookback cho các mốc replay chưa?
- Giữ lịch sử job cũ (30m/ABSTAIN) hay migrate/đánh dấu legacy?
