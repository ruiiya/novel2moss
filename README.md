# Novel2Moss Skills V2 — Bản tiếng Việt · Độc lập · Database-First · Chỉ dùng MOSS Layout

Bộ **11 skill dạng `SKILL.md`** và **SQLite Database-First** cho dự án **Novel2Moss độc lập hoàn toàn**. Pipeline: `Story → Act → Beat → ShotSpec → MOSS-Image Layout Prompts (Experimental)`.

Toàn bộ hợp đồng dữ liệu, migration, catalog, công cụ và tài liệu được quản lý trong Novel2Moss; không cần lấy source, database, schema, skill hay runtime từ bất kỳ dự án khác.

## Cài đặt

Giải nén, chạy trong thư mục vừa giải nén (Python 3.10 trở lên):

```powershell
python install.py --target D:\NGV\novel2moss --mode claude
```

Cấu trúc được cài vào dự án:

```text
novel2moss/
  .claude/skills/novel2moss-*/SKILL.md  # Tự phát hiện skill trong Claude Code
  docs/novel2moss/                      # Policy, contract, hướng dẫn vận hành
  tools/novel2moss/                     # Compiler + kiểm tra cấu trúc (Python stdlib)
  examples/novel2moss/                  # Các JSON ví dụ
  database/
    collect/source_manifest.json        # Manifest nguồn metadata-only
    migrations/                         # 001..006, không sửa migration đã áp dụng
    src/                                # DB CLI, collector, importer, report
    data/                               # DB runtime (không đưa vào Git)
    imports/                            # Raw snapshot tải về (không đưa vào Git)
```

Báo cáo pilot nằm trong bundle nguồn tại `reports/catalog_pilot_v2.md` (không copy khi cài).

Chọn `--mode portable` để cài vào `skills/` hoặc `--mode both` để cài cả hai nơi. Dùng `--dry-run` để xem trước. Bộ cài **không ghi đè** thư mục đích đang tồn tại; `--upgrade` sẽ backup từng file và bảo toàn `CONTENT_POLICY.md` hiện có. Installer **không copy** `database/imports/` hoặc DB runtime.

## Danh sách 11 skill

| Skill | Trách nhiệm |
|---|---|
| `novel2moss-orchestrator` | Điều phối các bước và các cổng kiểm tra |
| `novel2moss-story-planner` | Lập Story, Act, Beat, sự kiện và nhánh |
| `novel2moss-shot-spec` | Định nghĩa ShotSpec chuẩn và vai trò actor/action/target |
| `novel2moss-continuity` | Theo dõi `before/delta/after` và tính liên tục |
| `novel2moss-character-profile` | Định danh nhân vật, trang phục, màu sắc, bằng chứng |
| `novel2moss-layout-planner` | Lập bố cục và sinh MOSS Layout JSON |
| `novel2moss-fidelity-qa` | Đối chiếu nguồn→Shot→Layout trước export; không quản lý image/render QA trong DB |
| `novel2moss-render-adapter` | Render từ artifact file độc lập; không kết nối/ghi SQLite |
| `novel2moss-blind-cast` | Lập truyện trước, gán nhân vật sau |
| `novel2moss-database` | Khởi tạo, migration, transaction, kiểm tra toàn vẹn SQLite |
| `novel2moss-catalog-ingest` | Thu thập/import catalog metadata, provenance, license, idempotency |

## Database-First V2

### Khởi tạo và kiểm tra

```powershell
python database/src/n2m_db.py init
python database/src/n2m_db.py seed
python database/src/n2m_db.py stats --detailed
python -m unittest discover -s tests -v
```

`seed` chỉ tạo vocabulary, template và source registry nhỏ do dự án định nghĩa; **không** tự tải dataset. Dùng `--db` trước subcommand để chọn DB khác.

### Thu thập metadata và import

Collector chỉ tải file metadata/Markdown/CSV khai báo trong manifest, từ chối đuôi ảnh, lưu SHA256, sidecar `.meta.json`, lịch sử khi nội dung đổi và log `database/imports/collection_runs.jsonl`.

```powershell
python database/src/collect_sources.py list
python database/src/collect_sources.py fetch --source deepghs
python database/src/collect_sources.py fetch --source ai_pose_gallery
python database/src/collect_sources.py fetch --source dbr_e621_lists
python database/src/collect_sources.py verify

python database/src/n2m_db.py import-deepghs-md database/imports/deepghs/blue_archive.md
python database/src/n2m_db.py import-tags-csv database/imports/dbr-e621-lists-archive/danbooru/danbooru_2026-10-01_pt20-ia-dd.csv --namespace danbooru --from-character-core-tags
python database/src/n2m_db.py import-costume-gallery-json database/imports/ai-pose-gallery/data/costume-zh.json --source-id ai_pose_gallery
python database/src/n2m_db.py import-costume-gallery-json database/imports/ai-pose-gallery/data/costume-anime-zh.json --source-id charadb
```

V2 **không** nhập toàn bộ tag archive, e621, portrait, pose chưa review, skeleton, COCO/OpenPose/Grounded SAM. Tag CSV chỉ nhập tag gắn với core tags của character đã import. Import metadata không có nghĩa đã xác minh trang phục/canon, tuổi, quan hệ hoặc quyền dùng ảnh. Generic outfit luôn `GENERIC/UNVERIFIED`, không gán nhân vật, không lưu image reference.

Các lệnh import file JSON thủ công vẫn có:

```powershell
python database/src/n2m_db.py import-danbooru-json D:\data\tags.json
python database/src/n2m_db.py import-tag-relations-json D:\data\aliases.json --namespace danbooru --kind alias
python database/src/n2m_db.py import-wikidata-json D:\data\wikidata_export.json
python database/src/n2m_db.py search-characters "blue_archive"
python database/src/n2m_db.py search-catalog character "asuna"
python database/src/n2m_db.py search-catalog action "head_pat"
python database/src/n2m_db.py search-catalog outfit "sailor"
```

### Báo cáo pilot

```powershell
python database/src/catalog_report.py
```

Báo cáo hiện tại: `reports/catalog_pilot_v2.md`. Báo cáo phân biệt rõ **metadata imported**, **consumer-tested** và **render tested** (ngoài DB); ba giai đoạn này không đồng nghĩa.

### Export bundle và ranh giới renderer

```powershell
python database/src/n2m_db.py export-bundle `
  --layout-id LAYOUT_ID `
  --out-dir exports/STORY_ID/SHOT_KEY/REVISION
```

Bundle gồm `layout.prompt.json`, `prompt.manifest.json`, `fidelity_report.json`. DB workflow **dừng tại đây**; adapter render chỉ đọc bundle, không kết nối SQLite. `render_jobs`, `render_assets`, QA `RENDER` và `queue-render` đã bị loại khỏi schema/CLI V2.

## Các nguyên tắc bắt buộc

**Chính sách nội dung tập trung:** `docs/novel2moss/CONTENT_POLICY.md` là nơi duy nhất quyết định điều kiện `SOURCE_INGEST`, `STORY_ANALYSIS`, `PROMPT_DERIVATION`, `RENDER_DISPATCH` và `QA`. Mọi skill phải đọc và tham chiếu policy này; không tự đặt danh sách nội dung bị chặn ở từng skill. Blind Mode nhận và lưu mọi Story mà không tự viết lại nhãn; điều kiện tạo prompt được đánh giá riêng.

**Renderer local:** Không tự giả định bộ lọc cloud/provider. Lỗi backend phải có bằng chứng thực tế; trạng thái kết quả phải phân biệt lỗi kỹ thuật và quyết định policy.

**Ranh giới DB:** Novel2Moss DB chỉ giữ catalog và Story workspace đến export bundle. Không lưu render job, seed, checkpoint, output ảnh, trạng thái GPU hoặc image QA. Renderer có thể chạy khi DB đóng hoặc không tồn tại.

**Công cụ linh hoạt:** Có thể thay Python/SQLite/CLI/LLM/dịch vụ render bằng công cụ tương đương nếu giữ nguyên hợp đồng dữ liệu và đạt kiểm thử. Không mặc định có ComfyUI, GPU hay kho dữ liệu nhân vật. Không báo đã render khi chưa thực hiện.

**Định dạng prompt cố định:** Đầu ra gửi model **chỉ** là MOSS Layout JSON (`summary`, `items`, `bbox_coord_space="abs_centralized"`, `bbox_format="yxyx"`). Các trường width/height, ID, nhãn nội dung, revision và thiết lập render nằm trong tệp metadata đi kèm (sidecar). Bản nháp dùng tọa độ pixel `abs/xyxy` tính từ góc trên trái; compiler đổi sang hệ tọa độ tâm. Không sử dụng caption-only, tag-only hoặc hybrid làm prompt đầu ra trong V2.

**Ngôn ngữ:** Phần hướng dẫn skill là tiếng Việt. Giữ nguyên tên skill, mã trạng thái, tên trường JSON, lệnh và giao thức. Mô tả hình ảnh gửi MOSS có thể viết **bằng tiếng Anh** theo cấu hình để phù hợp model; dịch tài liệu không đồng nghĩa phải dịch nội dung prompt ảnh.

## Chạy ví dụ và kiểm thử

```bash
python tools/novel2moss/compile_layout.py examples/layout_draft.example.json \
  --output my_prompt.layout.json --manifest my_prompt.manifest.json

python tools/novel2moss/audit_shot.py \
  --story examples/story_plan.example.json \
  --shot examples/shot_spec.example.json

python -m unittest discover -s tests -v
```

Các script hoạt động offline, không gọi API hoặc tạo ảnh. Policy là hợp đồng hướng dẫn cho agent; các script demo chưa thực thi bộ đánh giá ngữ nghĩa policy tự động. `audit_shot.py` chỉ đối chiếu được một số trường có cấu trúc xác định, **không chứng minh đầy đủ việc bảo toàn ngữ nghĩa**. `compile_layout.py` kiểm tra schema và tọa độ; vẫn cần QA về nhân vật, hành động, bố cục và ảnh thực tế.

## Nguồn tài liệu kỹ thuật

- Hướng dẫn MOSS-Image: https://github.com/OpenMOSS/MOSS-Image/blob/main/USERGUIDE.md#layout-prompts-experimental
- Skill Prompt Enhancer chính thức: https://github.com/OpenMOSS/MOSS-Image/blob/main/skills/moss-image-prompt-enhancer/SKILL.md

Bản V2 là bộ skill + SQLite starter độc lập có thể kiểm thử offline; **chưa phải toàn bộ ứng dụng Novel2Moss**, và chất lượng ảnh sinh ra chưa được kiểm chứng thực tế bằng MOSS-Image.
