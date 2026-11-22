Vai: REVIEWER (theo docs/orchestration-rules.md §1, §6). Khong sua code. Chi doc diff, tu chay lai lenh, ra verdict.

Goal: kiem chung doc lap phan command-code vua lam (phase P4 cua docs/plans/261121-remove-self-learning/plan.md): go dau vet tu hoc khoi frontend va docs, giu nguyen luong bao cao.

Pham vi duoc phep sua cua implementer: frontend/**, README.md, docs/** TRU docs/plans/**, docs/systemmd/**, docs/database-schema.dbml. Moi file ngoai pham vi do bi doi = vi pham.
Ban KHONG review phan backend/** cua chinh ban (ban khong duoc tu duyet phan minh viet); Lead se doc diff phan do.

Invariants (AGENTS.md muc 1-4): khong mock data; khong lo file_path/artifact_path; UI UTC+7; khong UUID tho tren UI; chart giu zoom/pan/click; khong commit/push.

Kiem chung (chay that, dan output nguyen van):
1. git status + git diff cho frontend/** README.md docs/** (tru plans, systemmd, dbml). Liet ke file doi, danh dau file nao nam ngoai pham vi.
2. Doc diff: co chi doi comment/format, stub, TODO, mock khong? Co thay doi hanh vi /report, /replay, /data, /dashboard, /about khong (khong duoc)?
3. Grep trong frontend/src README.md docs (tru plans, systemmd, docs/journals, docs/reseaching, docs/materials) tim: lesson|Pattern Lab|scan-patterns|research-pattern|self-trained|/lessons|/patterns|/signals|/research . Con sot thi ghi file:line. Luu y: PatternDiagnostic, Google grounding, nhan RESEARCHING/RESEARCH_INCOMPLETE la GIU, khong phai tu hoc.
4. cd frontend && npm run typecheck (exit code). npm run build (exit code, dan dong loi bao mat Next 16.4.0 neu co).
5. Quet chinh ta phan text moi them/sua (tieng Viet co dau, tieng Anh, ten bien). UI copy khong dung gach ngang em/en dash.
6. Dung giu cac thay doi ngoai README/docs/frontend; neu thay file ngoai pham vi bi doi, liet ke.

Cam: sua file, commit, push, doi status plan.

Dinh dang tra loi bat buoc:
VERDICT: PASS | FAIL
Da chay: <lenh> -> <ket qua that>
Vi pham: <file:line - van de>   (neu FAIL)
Yeu cau lam lai: <viec cu the, do duoc>
Chua kiem chung: <nhung gi khong chay duoc>
