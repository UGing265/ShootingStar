---
title: "Hoàn thiện Next.js và hợp đồng đọc ShootingStar"
description: "Khôi phục Phase 8/9 theo plan gốc: FastAPI read contracts, Next.js năm trang, hướng dẫn chạy riêng và script chạy cả hai."
status: pending
priority: P1
tags: [frontend, backend, api, docs]
blockedBy: []
blocks: []
created: 2026-10-09
---
# ShootingStar Next.js Implementation Plan

> **Cho người thực hiện:** chỉ đánh dấu hoàn tất sau khi thấy kết quả chạy thực tế. Đây là **kế hoạch**, không phải báo cáo đã triển khai. Thứ tự A0 đối soát chất lượng dữ liệu/model/signal → Backend read contracts → Frontend → Docs & launcher → browser smoke. Không commit/push nếu chưa được yêu cầu.

**Goal:** Hoàn thiện Next.js App Router/TypeScript năm trang theo Phase 8, dùng dữ liệu thật từ FastAPI; hướng dẫn sử dụng riêng backend/frontend và một script PowerShell chạy cả hai local.

**Architecture:** Python/FastAPI là nguồn duy nhất tính toán và đọc PostgreSQL/Parquet; Next.js chỉ đọc qua server-side fetch (`SHOOTINGSTAR_API_URL`, mặc định `http://127.0.0.1:8000`). **Tổ chức frontend theo feature-based gọn**, không FSD đầy đủ: `app/` chỉ điều hướng/ghép trang; `features/{data,research,patterns,signals}` giữ UI, truy vấn và types riêng cho từng mảng; `shared/` chỉ chứa HTTP client, navigation, format UTC và UI primitives thật sự dùng ở nhiều feature. Overview (`app/page.tsx`) và landing (`app/about/page.tsx`) ở route cho đến khi đủ phức tạp cần tách feature. Không đưa mật khẩu, raw payload, thuật toán thống kê hay P&L chưa duyệt vào browser; không chuyển công thức model sang frontend.

**Cập nhật phạm vi UI (2026-10-09):** Frontend đã nằm ở `frontend/` và có các trang làm việc; các mô tả `web/` scaffold/đường dẫn và layout `app/page.tsx` trong kế hoạch lịch sử bên dưới không còn là chỉ dẫn triển khai hiện hành. Landing `/`, Overview `/dashboard` và sidebar năm mục theo [`../261009-shootingstar-cinematic-landing-sidebar/plan.md`](../261009-shootingstar-cinematic-landing-sidebar/plan.md). A0, API contracts và gate dữ liệu của kế hoạch này giữ nguyên, không đánh dấu đã nghiệm thu.

**Tech stack:** Python/FastAPI/SQLAlchemy/PostgreSQL/pytest; Next.js App Router + TypeScript + React; PowerShell cho máy Windows hiện tại. Dùng `web/package-lock.json` đã tạo, kiểm tra khả năng cài đặt của lockfile trước khi nâng phiên bản; không khẳng định Next 14 cũ an toàn nếu chưa kiểm tra advisory.

## Thực trạng bắt buộc ghi đúng

- `plans/261009-shootingstar-research-platform/plan.md` §Phase 8 yêu cầu cả read API và **Next.js năm trang**, §Phase 9 yêu cầu landing scrollytelling. Phần đầu plan cũ vẫn ghi “chưa triển khai”; các tuyên bố chat trước đó rằng đã xong 10 phase là sai.
- `web/` là scaffold **chưa chạy được**: hiện chỉ có `package.json`, `package-lock.json`, `tsconfig.json` (untracked); **không có** `app/`, Next pages, `next.config`, `next-env.d.ts`, test hay script chạy chung. Không gọi đây là frontend đã xong.
- FastAPI đã có `GET /health`, `/snapshots`, `/experiments`, `/experiments/{id}`, `/patterns`, `/signals`, `/narrative`; `/` hiện là HTML hardcode, không phải Next.js. Chưa đủ read contracts Phase 8: quality/gap/candle drilldown; report + calibration có schema nhưng API chưa hoàn chỉnh; pattern hits/rules được lưu trong DB chưa đọc qua API; reviews/audit chưa trả về; `/patterns` còn tính từ Parquet mỗi request thay vì đọc kết quả đã lưu.
- `docs/DESIGN.md` là visual system (light/parchment, blue tương tác); dashboard FastAPI hiện dark và hardcode số liệu. Không copy hardcode đó sang Next. Các con số chỉ đọc từ report có provenance, hiển thị trạng thái blocked cho cost-adjusted metrics.
- Phase 7 local signal command theo plan vẫn cần kiểm chứng độc lập; nếu DB chưa có signal thì Signals hiển thị trạng thái chưa có dữ liệu, không dựng signal giả.

## Phân chia sở hữu và tài liệu

| Mục | Source/kiểm thử | Tài liệu cần viết khi triển khai |
|---|---|---|
| Backend | `src/shootingstar/api/`, `src/shootingstar/adapters/db/`, `tests/test_api_and_ui.py` | `docs/backend/README.md` (DB, Alembic, API, smoke, cấu hình) |
| Frontend | `web/src/app/`, `web/src/features/`, `web/src/shared/`, `web/package.json`, `web/tsconfig.json` | `docs/frontend/README.md` (Node, env, cấu trúc feature, năm trang, build, dev) |
| Docs & launcher | `README.md`, `docs/`, `scripts/run-local.ps1`, `.gitignore`, `web/.env.example` | `docs/README.md` làm mục lục; `docs/local-run.md` chạy riêng/tất cả |

**Ranh giới import:** `app → features → shared`; `features` không import nhau theo đường tắt, khi nhiều feature thực sự dùng chung thì chuyển phần trung lập vào `shared` (không chuyển nghiệp vụ nghiên cứu thành helper chung). `shared` không import `features`/`app`. Trong mỗi feature, đặt file cạnh nhau lúc ít code; chỉ tách `components/`, `api/`, `types/` khi phần đó lớn thật. Không dựng sẵn tầng `entities/widgets/pages` của FSD.

Giữ `docs/DESIGN.md`, `docs/external-apis.md`, `docs/binance-spot-fees.md` nguyên vị trí; liên kết từ index, không di chuyển tài liệu lịch sử. `web/.env.local` phải git-ignored; `web/.env.example` chỉ chứa `SHOOTINGSTAR_API_URL` công khai; `.env.example` gốc đã có template cho DB và phải được kiểm tra key `SHOOTINGSTAR_DATABASE_URL` trước khi viết guide. Tránh tạo `frontend/` cạnh `web/`: Next code nằm duy nhất trong `web/`.
## Phụ thuộc plan

Plan này hoàn tất phạm vi Phase 8/9 của `plans/261009-shootingstar-research-platform/plan.md`, nhưng phụ thuộc vào **gate dữ liệu/đánh giá/producer Phase 2–7 còn thiếu** được liệt kê ở A0. Không đợi Phase 10 hay fee/slippage để dựng UI, nhưng các trường đó vẫn gated. Plan gốc đã liên kết plan này và đánh dấu Phase 8/9 chưa đạt gate; không tạo vòng `blockedBy` giữa hai plan. `blockedBy: []`, `blocks: []` là quan hệ cấp plan; A0 → Backend → Frontend → Docs là quan hệ công việc.

## Chiến lược, lựa chọn

- **Chọn Next server-side fetch FastAPI:** browser chỉ gọi Next (port 3000); ít CORS, URL backend chỉ ở server, xử lý lỗi một nơi. Client component chỉ cho tương tác cần thiết (filter, drilldown); thay đổi filter dùng URL search params hoặc link. `cache: 'no-store'` trên dữ liệu trạng thái; dữ liệu immutable chỉ cache khi có ID/checksum tường minh.
- Không chọn SPA gọi FastAPI thẳng từ browser: phải cấu hình CORS và để lộ topology, nhân đôi xử lý lỗi. Không chọn Next route-proxy cho mỗi API: thêm tầng forwarding không cần thiết cho dashboard chỉ đọc.
- Dùng DB read endpoints với response typed và phân trang; không tính metric bằng JS, không đọc `data/reports/*.json` từ Next trực tiếp, không trả filesystem path/raw preview/reviewer private notes lên danh sách public.

## A0. Rà soát chức năng độc lập trước khi mở UI

Một agent chỉ đọc đã đối chiếu plan gốc §§1–10 với source/test hiện tại. **Đây là audit tĩnh, không chạy DB, test, Binance hay browser; “có code” không đồng nghĩa gate đã qua.** Các dòng sau là việc **phải làm khi triển khai kế hoạch**, không phải sửa code trong lần lập plan này:

| Phase gốc | Tình trạng theo audit tĩnh | Chặn nghiệm thu/giao diện nào |
|---|---|---|
| 1 Data contracts | Có domain/CLI, gate CLI và boundary chưa được agent chạy lại | Kiểm chứng smoke domain/CLI offline trước khi báo hoàn tất |
| 2 Pilot | Có adapter/raw/Parquet; `application/ingestion.py:153-175` đo coverage từ nến đầu→cuối trả về và ghi chính danh sách đó | Data: đo cả requested window, xử lý duplicate/reject có lý do; kiểm chứng snapshot/replay và 1m/5m thực tế |
| 3 DB/provenance | Có models/repositories và migration tests; pipeline chưa chứng minh ghi đủ canonical/reject/artifact/audit | Không suy ra “có bảng” = “có bản ghi”; test linkage, migration up/down trên DB test, retrieval sau pilot |
| 4 Labels/features | Có directional-only; cost-adjusted 3 lớp còn gated | Đóng băng latency lịch sử, thời điểm availability, entry thực thi sau khi data có; gap/boundary fixtures trước khi dùng Research |
| 5 Model/evaluation | Có LR, split/report; `splits.py:38` hardcode 6 mẫu (chỉ 30m trên 5m); `evaluation.py:222-224` fit Majority bằng `y_test`; `experiment.py:118,178-180` ghi hash suffix và nuốt lỗi DB | Research: sửa leakage/1m purge/full checksum, validation selection, save/load/replay; không công bố report hiện có như kết luận chuẩn |
| 6 Pattern Lab | Có 4 detector và scan; `patterns.py:235-267` bỏ hits chưa đủ tương lai; `cli/main.py:223-251` chỉ in aggregate | Pattern: version rule + lưu **tất cả** hits kể cả failure/pending; kiểm tra overlap/gap và reject luật nhìn tương lai |
| 7 Signals | Có service + list/mature CLI, **không có lệnh model-driven tạo signal** (`cli/main.py:34-63`); `signals.py:113-149` đánh giá target theo open time mà không kiểm tra close/availability | Signals: tạo prediction có provenance thực, maturity chỉ sau nến đóng/có sẵn + quality; smoke model→pending→mature→review; không dùng test synthetic làm bằng chứng signal thật |
| 8 Web | FastAPI một phần; `web/` chưa có route | B1/F1–F4 + browser smoke trên migrated DB; sửa `/health` và DTO không leak secrets |
| 9 Landing | Có narrative markdown + FastAPI `/` hardcode, chưa có Next landing | Gate cả **bề mặt cũ** `/` và `/narrative`: ẩn số pilot chưa được duyệt, chỉ công bố report có checksum/provenance được phê duyệt, hoặc “chưa có kết quả kiểm chứng” |
| 10 Deferred | Chỉ có docs liệt kê gate | Giữ paper/news/deploy gated; không lấy làm dependency bắt buộc của UI đọc |

**Thứ tự chặn dữ liệu:** A0 chất lượng/availability → A0 split/report → A0 pattern persistence & signal producer/maturity → B1 read contracts → F1–F4 → D1/D2 & browser smoke. Khi sửa upstream phải cập nhật report/snapshot bị ảnh hưởng hoặc đánh dấu report pilot cũ “chưa xác minh”; không hồi tố coi 51.05% là edge.

- [ ] Phase 2/4: test requested-window edge gaps, duplicate/reject isolation và availability ở thời điểm dự đoán; chưa đạt thì Data chỉ được hiển thị metadata có caveat, không công bố coverage 100% như đã kiểm chứng.
- [ ] Phase 5: purge theo timeframe/horizon (30 mẫu 1m, 6 mẫu 5m nếu nhãn mỗi nến), fit majority trên train, dùng validation cho chọn model/threshold rồi test độc lập; lưu hash **đầy đủ**, báo lỗi persist thay vì nuốt; test replay report/model khi nạp lại.
- [ ] Phase 6: persistence rule/version + mọi hit, cả hit cuối window PENDING và outcome thất bại; không biến count của on-demand scan thành số liệu lịch sử đã lưu.
- [ ] Phase 7: local producer từ model/artifact đã duyệt, đóng băng decision policy trước dự đoán, validate probability/domain; maturation dùng close_time **và** availability/quality, không dùng `now_ms` suy từ snapshot làm bằng chứng receipt; test boundary và late arrival.
- [ ] Phase 9: rà `docs/landing-page-narrative.md`, FastAPI `/` và `/narrative` trước khi public Next landing; bỏ/gate số hardcode và tham chiếu artifact checksum không khớp. Không ghi report là kết quả xác nhận nếu nguồn hiện tại chưa đủ.

## Backend — triển khai trước Frontend

### B1. Khóa hợp đồng response, provenance và trang đầu

**Files:** sửa `src/shootingstar/api/app.py` (tách route/schema sang `src/shootingstar/api/schemas.py`, `src/shootingstar/api/read_routes.py` nếu app tiếp tục phình to); bổ sung `tests/test_api_and_ui.py` bằng test DB Alembic hiện có.

- [ ] Viết ma trận JSON: `GET /health`; `GET /ingestion-runs?limit&cursor`; `GET /snapshots?limit&cursor`, `GET /snapshots/{id}/quality`; `GET /snapshots/{id}/candles?start_ms&end_ms&limit` (trích Parquet đã đăng ký và xác minh checksum, không raw JSON); `GET /experiments?limit&cursor`; `GET /experiments/{id}` (ordered splits, **all** reports + calibration bins + baselines, experiment/snapshot/artifact checksum); `GET /pattern-rules?limit&cursor`, `GET /pattern-rules/{id}/hits?limit&cursor`; `GET /signals?limit&cursor`, `GET /signals/{id}` (prediction, separate decision/outcome/reviews/audit đã lọc), `GET /narrative`. Nếu cần tổng hợp pattern từ snapshot trên demand thì chỉ là endpoint tính toán riêng, không gán nó thành persisted hit.
- [ ] Đặt `limit` trong `[1,100]` (hoặc giới hạn nhất quán đã chốt), stable ordering có tie-break ID và cursor theo `(time,id)`; filter UTC milliseconds và symbol/timeframe với bounds. `404` ID không có; `422` query sai; `503` DB không sẵn; kết quả rỗng hợp lệ là danh sách rỗng, không fabricate. Khi có nhiều report, không lấy `reports[0]` không order.
- [ ] `GET /health` không đưa exception/connection URL/password ra response; chỉ `status`/`database_status`, 503 nếu DB bắt buộc mà offline. API response không trả `file_path`, raw payload preview, audit details nhạy cảm; chỉ checksum/ID an toàn.
- [ ] Kiểm tra ánh xạ dữ liệu thực sự đã persist: `ingestion_runs` có counts/coverage nhưng **không lưu danh sách missing timestamps**; nếu chưa có gap timeline chi tiết, thể hiện rõ `unavailable`, không tự suy ra từ `coverage_ratio`. `metric_reports.calibration_json`, `pattern_hits`, `review_overrides` có schema nhưng phải chứng minh được ghi khi pipeline chạy; nếu không, trả trạng thái “chưa lưu” thay vì tạo số liệu. Không thêm migration trừ khi một hợp đồng thực sự cần lưu dữ liệu; nếu cần thì viết migration + test PostgreSQL.
- [ ] Contract tests: empty DB, seeded snapshot + report + 1 failure hit + signal PENDING/EVALUATED/UNSCORABLE và review, multi-report ordering, pagination tie, invalid query, missing file/hash mismatch, DB offline, tuyệt đối không rò secret. Chạy test theo file rồi full suite.

**Gate B1:** curl/TestClient trả đủ DTO thật từ DB đã migration, không crash/misleading/secret; state thiếu là `unavailable` có lý do. Kết quả B1 quyết định field UI, không đoán tên trường.

## Frontend — Next.js năm trang

### F1. Nền Next có thể build và API client thống nhất

**Files:** hoàn thiện `web/package.json`, `web/package-lock.json`, `web/tsconfig.json`, tạo `web/next.config.mjs` khi cần, `web/src/app/layout.tsx`, `web/src/app/globals.css`, `web/src/shared/api-client.ts`, `web/src/shared/ui/`; tạo `web/src/features/{data,research,patterns,signals}/` khi có code feature.

- [ ] Kiểm tra phiên bản Next hiện trong scaffold và advisory; giữ một major được hỗ trợ và cập nhật lockfile đồng bộ, script `dev`, `build`, `start`, `typecheck` (`tsc --noEmit`); thay `next lint` cũ nếu không còn hỗ trợ ở phiên bản chọn. Thiết lập ignore `web/.next`, `web/node_modules`, `web/.env.local`; `npm ci` phải tái lập.
- [ ] `shared/api-client.ts`: server-side `fetch` tới `process.env.SHOOTINGSTAR_API_URL ?? 'http://127.0.0.1:8000'`; timeout có thời hạn, encode query, phân biệt 404/422/503/network, không nuốt lỗi. DTO riêng một feature đặt trong feature đó; chỉ type nhiều feature dùng chung mới đặt trong `shared`. Không để `NEXT_PUBLIC_` cho URL nếu browser không gọi FastAPI trực tiếp.
- [ ] Layout chung: navigation Overview/Data/Research/Pattern Lab/Signals; liên kết tới báo cáo và narrative; CSS theo `docs/DESIGN.md`, số cột căn phải, ngày/giờ UTC có nhãn, focus visible, không dùng màu để ám chỉ lợi nhuận. Mỗi route có `loading.tsx`, `error.tsx` nếu cần client boundary, empty state có lý do.
- [ ] Smoke build + typecheck + trực tiếp truy cập `/` với API healthy/offline; không cho build qua nếu import/route sai.

### F2. Trang Overview và Data

**Files:** `web/src/app/page.tsx`, `web/src/app/data/page.tsx`, `web/src/features/data/quality-view.tsx`, `web/src/features/data/candle-table.tsx`, `web/src/features/data/load-data.ts`. Overview ghép health/links trong `app/page.tsx`, không tạo feature Overview rỗng.

- [ ] Overview hiển thị health và **số bản ghi chỉ khi API trả total có provenance**; nếu API chỉ trả một trang, ghi “bản ghi gần đây” thay vì giả làm tổng số; nếu thiếu dữ liệu hiển thị “Chưa có dữ liệu”. Banner rõ nghiên cứu chưa có cost-adjusted result. Link tới Data/Research/Signals.
- [ ] Data: UTC coverage window, expected/valid/missing/duplicate và quality state từ ingestion run; snapshot SHA; drilldown nến trang nhỏ (có giới hạn thời gian + row limit). Với gap timestamp chưa được lưu, hiển thị “chưa có danh sách gap” và total nếu có. Thử một run pristine và một run có gap từ seeded DB, kể cả case không có Parquet.

### F3. Research và Pattern Lab

**Files:** `web/src/app/research/page.tsx`, `web/src/app/research/[id]/page.tsx`, `web/src/features/research/`; `web/src/app/patterns/page.tsx`, `web/src/app/patterns/[id]/page.tsx`, `web/src/features/patterns/`. Mỗi feature sở hữu UI, query và types của riêng mình.

- [ ] Research list chọn experiment; detail hiển thị snapshot/config hash, train/calibration/test chronological splits, report theo split, baseline so khớp **cùng test window**, calibration bins kèm sample_count; không gọi 51% là edge. Trường cost-adjusted đánh dấu `UNAVAILABLE_PENDING_SLIPPAGE_METHOD` và không vẽ P&L.
- [ ] Pattern Lab hiển thị rule ID/version/definition, tất cả hits có outcomes kể cả failure và chưa mature; thumbnail candle lấy OHLC đúng theo hit nếu endpoint có dữ liệu; nếu thiếu OHLC hiển thị “không có candle minh họa”, không bịa cây nến đẹp. Dùng tên “tỷ lệ đúng hướng” (không “win rate giao dịch”), nhắc mẫu trùng lặp và giới hạn độ tin cậy. Chỉ dùng persisted rule/hit cho trang, không giả tạo rules từ on-demand aggregate.

### F4. Signals và landing riêng

**Files:** `web/src/app/signals/page.tsx`, `web/src/app/signals/[id]/page.tsx`, `web/src/features/signals/`, `web/src/app/about/page.tsx` (landing narrative riêng; chỉ tạo `features/landing/` nếu có logic/UI đủ lớn).

- [ ] Signals tách `predicted_class`/probability khỏi `decision` và lý do; `PENDING` nếu chưa có outcome, `EVALUATED`/`UNSCORABLE` có thời gian/lý do; review và audit lọc theo signal. Không hiển thị DOWN Spot như short profit. Rỗng = “chưa ghi signal”; không có nút Train/Trade giả.
- [ ] Landing Phase 9: `/about` kể **vì sao ShootingStar ra đời, là gì, mục tiêu nghiên cứu**, rồi trình bày kết quả báo cáo/giới hạn đã được duyệt; **không kể tuần tự quy trình xử lý dữ liệu**. Copy tiếng Việt; chỉ hiện report nếu có nguồn đã xác minh và được phép công khai, nếu không “chưa có kết quả kiểm chứng”. Minh họa sao băng SVG/canvas tiết chế theo `docs/DESIGN.md`; desktop có **một** đoạn sticky/pinned chuyển cảnh bằng native scroll (không scroll hijack), chuyển động cơ bản. Mobile xếp cảnh theo chiều dọc, `prefers-reduced-motion` hiển thị khung tĩnh đọc được; trang công việc không thêm scrollytelling. Không hứa 90% accuracy hay lợi nhuận.
- [ ] Browser smoke thật từ migrated **test** DB: Data gap → Research calibration → Pattern failure → Signal PENDING được tạo bằng **model-driven local command** rồi sau nến thực sự đóng/mature thành EVALUATED; chụp desktop/mobile, kiểm tra network failure, keyboard, reduced motion. Seed fixtures được phép cho boundary Data/Research/Pattern nhưng không thay thế smoke producer Signal thật; không sửa production DB và không chèn fixture vào giao diện người dùng.

## Docs & chạy local hai dịch vụ

### D1. Hướng dẫn tách riêng

**Files:** `docs/backend/README.md`, `docs/frontend/README.md`, `docs/README.md`, `docs/local-run.md`, cập nhật `README.md`, tạo `web/.env.example`, kiểm tra `.env.example` ở root và `.gitignore`.

- [ ] Trước khi đưa lệnh copy vào hướng dẫn, kiểm tra `.env.example` ở root vẫn có `SHOOTINGSTAR_DATABASE_URL` placeholder; **tạo** `web/.env.example` với đúng `SHOOTINGSTAR_API_URL=http://127.0.0.1:8000` (không DB secret); ignore `web/.env.local` và không ghi đè `.env`/`.env.local` hiện có.
- [ ] Backend doc: prerequisites Python 3.11+ (kiểm tra thực tế env 3.14), PostgreSQL role/DB riêng; tạo `.env` từ `.env.example` **chỉ nếu file chưa tồn tại**, người vận hành tự điền biến **không in mật khẩu ra console**; `.venv\Scripts\python.exe -m pip install -e '.[dev]'`; `.venv\Scripts\alembic.exe upgrade head`; `.venv\Scripts\shootingstar.exe serve --host 127.0.0.1 --port 8000`; thử `http://127.0.0.1:8000/health` và `/docs`.
- [ ] Frontend doc: Node tương thích phiên bản Next được chọn; `cd web; npm ci`; tạo `.env.local` từ `.env.example` **chỉ nếu file chưa tồn tại** (chỉ `SHOOTINGSTAR_API_URL=http://127.0.0.1:8000`); `npm run dev`; mở `http://127.0.0.1:3000`; `npm run build` + `npm run typecheck`. Nhấn mạnh Next **chưa chạy được** cho đến khi F1–F4 xong.
- [ ] `docs/local-run.md`: Windows PowerShell mở 2 terminal; backend trước frontend; cần PostgreSQL và DB migrations; thiếu DB → backend health báo lỗi, frontend báo không kết nối; `Ctrl+C` dừng từng terminal. Chỉ ra `shootingstar serve` là FastAPI, không phải Next; không phải chạy lại Binance fetch/model để giao diện khởi động, nhưng trang sẽ rỗng nếu DB chưa có dữ liệu.
- [ ] README root: ba nhóm link **Frontend**, **Backend**, **Docs**; local quickstart và trạng thái phase trung thực. Không thay đổi lịch sử docs hoặc hứa kết quả chưa xác minh.

### D2. Script PowerShell chạy cả hai (sẽ được viết khi thực thi plan)

**Files:** tạo `scripts/run-local.ps1`, kiểm tra thủ công script trên Windows; không tạo shell script cho OS chưa được yêu cầu.

- [ ] Script nhận `-ApiPort 8000`, `-WebPort 3000`, `-ApiUrl` tùy chọn; `Resolve-Path` từ `$PSScriptRoot/..` nên chạy được ở mọi cwd; kiểm tra `.venv/Scripts/shootingstar.exe`, `web/node_modules/.bin/next.cmd`, `web/package.json`, cấu hình DB; chỉ kiểm tra **sự hiện diện** `.env`, không đọc/in URL bí mật. Kiểm tra port trước khi spawn, fail rõ ràng nếu port bận, không giết PID khác.
- [ ] Chạy backend và frontend như child processes, đặt cwd tương ứng (root, `web`), truyền `SHOOTINGSTAR_API_URL` cho child frontend (local backend port); đợi backend `/health` báo connected (timeout hữu hạn), sau đó đợi Next `/` trả response. Không tự `npm install`, migrate hay ingest lúc khởi động; báo rõ lệnh xử lý tiền điều kiện.
- [ ] Cả hai ghi log ra terminal hoặc temp log rõ vị trí **không chứa DB URL**; khi Ctrl+C hay một process thoát bất thường: dừng **chỉ** hai child do script tạo và exit non-zero cho lỗi. Không dùng `Start-Process` tách rời mà mất khả năng cleanup; chọn .NET `System.Diagnostics.Process` với `WorkingDirectory`, `ArgumentList`, `UseShellExecute=false`/`Environment`, quản lý PID thực và `Kill(entireProcessTree)` chỉ cho PID sở hữu.
- [ ] Smoke lần 1 từ root, lần 2 từ cwd khác, thử port-bận/backend-missing/stop; xác minh hai process kết thúc và cổng giải phóng. Sau đó tài liệu một lệnh `powershell -NoProfile -File .\scripts\run-local.ps1`; nếu PowerShell policy chặn thì chạy `pwsh -NoProfile -File ...` khi có pwsh, **không** khuyên tắt ExecutionPolicy toàn máy.

## Kiểm chứng & gate toàn dự án

1. `pytest -v` trên DB test Alembic: API DTO, pagination, dữ liệu rỗng/lỗi, provenance và không leak secrets. Không tuyên bố N tests mới trước khi chạy.
2. `npm ci`, `npm run typecheck`, `npm run build` từ `web/`; Next dev server phục vụ năm trang và landing; API down/empty và seeded paths đều xem được.
3. Browser smoke thực tế tại `localhost:3000`: dữ liệu gap/report/pattern qua migrated test DB, signal pending→mature qua producer đã duyệt; screenshot desktop/mobile, keyboard & reduced motion. Mock/TestClient hoặc trực tiếp insert prediction synthetic không thay thế gate này.
4. `scripts/run-local.ps1` khởi/dừng đúng hai process, không in secrets; kiểm tra dùng hai terminal riêng cũng hoạt động.
5. Chỉ sau 1–4 sửa bảng trạng thái Phase 8/9 trong plan gốc; Phase 10 tiếp tục gated; không tự tạo trading P&L, ngưỡng cost-adjusted hay số mẫu.

## Không nằm trong kế hoạch

Docker Compose/deploy, live Binance order/trading, realtime WebSocket, news/Gemini, thuật toán fee/slippage chưa duyệt, chatbot, auto-training, công bố lợi nhuận. Tất cả đều có gate riêng của plan gốc.
