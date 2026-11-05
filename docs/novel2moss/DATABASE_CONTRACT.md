# Novel2Moss — Hợp đồng Database (DB CONTRACT) V2 · schema 006

## 1. Phạm vi và nguyên tắc

- Novel2Moss **độc lập hoàn toàn**: tự quản schema, migration, catalog, source, Story và render; không gọi DB/code của Novel2Anima.
- **SQLite là storage mặc định đã triển khai** trong `database/`. Tầng nghiệp vụ có thể đổi PostgreSQL nhưng phải giữ **hợp đồng dữ liệu** và test. Không bắt buộc ORM hoặc công cụ ETL cụ thể.
- DB là **system of record** cho dữ liệu được commit. JSON/Markdown xuất ra là artifact hoặc bản nháp; không thay thế revision/foreign key/provenance trong DB.
- Chỉ sử dụng câu lệnh tham số hóa hoặc phương thức DB adapter. Không viết SQL sinh từ dữ liệu người dùng một cách nối chuỗi; không ghi thay đổi bằng LLM tự do.
- Mọi thao tác ghi phải xác định rõ `story_id/role_id/shot_id/revision`; bảo đảm transaction, idempotency và không ghi đè dữ liệu đã duyệt.
- `docs/novel2moss/CONTENT_POLICY.md` là nguồn quy tắc nội dung riêng, không nằm trong migration/schema. Nhãn dữ liệu nguồn không được dùng để tự quyết định render.

## 2. Đường dẫn chuẩn

- `database/migrations/001_init.sql`, `002_integrity.sql`, `003_history_guards.sql`, `004_catalog_enrichment.sql`, `005_db_boundary.sql`, `006_qa_history_guards.sql`: migration có thứ tự.
- `database/src/n2m_db.py`: khởi tạo DB, seed catalog nhỏ, import file offline, tạo Story, gán role, compiler layout, `export-bundle`.
- `database/src/catalog_imports.py`: importer metadata-only cho tag CSV/JSON, pose (pilot), costume, CharaDB; không ảnh/portrait/render.
- `database/src/collect_sources.py` + `database/collect/source_manifest.json`: fetch metadata có consumer contract, SHA256/checkpoint/history.
- `database/src/catalog_report.py`: báo cáo catalog từ DB, không tải dữ liệu và không render.
- `database/src/n2m_workflow.py`: ghi Story Plan, Act, Beat, Event, Shot, Continuity, Layout, QA trước export; không render job.
- `database/data/novel2moss.db`: DB runtime tạo bằng CLI; **không đưa dữ liệu runtime vào Git**.
- `database/imports/`: raw snapshot metadata/CSV/Markdown; **không đưa file tải về hoặc ảnh vào Git**.
- `tools/novel2moss/compile_layout.py`: compiler JSON file độc lập; hai compiler phải cho kết quả ngữ nghĩa tương đương.

CLI mặc định đặt DB tại `database/data/novel2moss.db`. Có thể chọn đường dẫn khác bằng `--db` đứng **trước subcommand**. Mọi command `n2m_workflow.py` là thao tác DB cục bộ. DB workflow kết thúc tại `export-bundle`; renderer và image QA là downstream file-only, không có `queue-render`.

## 3. Bảng theo module

| Module | Bảng | Trách nhiệm |
|---|---|---|
| Provenance | `source_registry`, `import_runs`, `source_records`, `source_record_versions` | Nguồn gốc, quyền sử dụng, dữ liệu thô, hash, lịch sử import |
| Character Catalog | `universes`, `characters`, `character_aliases`, `character_traits`, `outfits`, `outfit_parts`, `catalog_tags`, `character_tags` | Identity khác outfit, có độ tin cậy, có nguồn |
| Catalog Enrichment | `catalog_assets`, `pose_reference_views`, `catalog_tag_relations`, `catalog_entity_links`, `catalog_captions`, `catalog_tag_taxonomy` | V2 dùng tag relations/captions/taxonomy; asset/pose view để trống trừ khi P1 pose được duyệt; không lưu ảnh |
| Concept Catalog | `vocabulary`, `vocabulary_relations`, `pose_references`, `layout_templates` | Pose/action/camera/spatial và template có thể tìm kiếm |
| Story | `stories`, `story_sources`, `story_revisions`, `story_roles`, `story_castings`, `acts`, `beats`, `story_events` | Story/Act/Beat, role tồn tại trước casting, plan revision |
| Shot | `shots`, `shot_participants`, `shot_interactions`, `continuity_snapshots` | ShotSpec đã commit, actor-target, trạng thái |
| Layout | `shot_layouts`, `shot_layout_items`, `layout_exports` | Draft `abs/xyxy`, MOSS JSON `abs_centralized/yxyx`; artifact bundle export |
| QA trước export | `qa_reports` | Chỉ `STORY/SHOT/LAYOUT`; không image/render QA, không render state |

## 4. Quy tắc đọc/ghi

**Nguồn:** `story_sources` là append-only. Giữ `raw_text`, `raw_labels_json`, SHA256; không ghi đè, kể cả khi sửa kế hoạch. Mỗi lần import lưu bản gốc vào `source_record_versions`. Không gán dữ liệu Danbooru/Core Tags thành outfit canon nếu chưa được xác minh.

**Catalog enrichment V2:** Tag CSV chỉ nhập namespace Danbooru, và chỉ các tag gắn với `character_tags` của character đã import (`--from-character-core-tags`); giữ `original_name`, category thô và post_count. Category label lưu ở `catalog_tag_taxonomy`. Alias/implication tag lưu ở `catalog_tag_relations`, không tự đưa vào `character_aliases`; CSV archive không có status từng alias nên dùng `archive_unspecified`. Không nhập e621/merged list. Pose gallery là P1, chỉ import khi caption tiếng Anh đã review; hiện để `enabled:false`, không có pose data trong DB V2. Costume/CharaDB chỉ tạo outfit `GENERIC`, `UNVERIFIED`, `character_id=NULL`; không tự tạo `ORIGINAL`. `catalog_assets`/portrait không được dùng để thu thập ảnh; V2 không lưu image reference. `catalog_entity_links` chỉ dùng khi có bằng chứng; không merge theo tên.

**Plan:** `stories.cast_mode` bắt buộc `BLIND|NON_BLIND`; `story_roles` luôn tồn tại trước event/shot. `story_revisions` lưu JSON được duyệt, có `revision`. Không dùng khóa vật lý của Story từ một Story khác. Với lần chạy lại cùng nội dung, trả ID/revision cũ; với nội dung khác, thêm revision mới.

**Casting:** `story_castings` gắn `story_role_id` với `character_id` và `outfit_id`; gắn Blind khi cần, Non-Blind trước khi lập Shot. Không sửa `story_events.actor_role_id` để đổi nhân vật. Một role chỉ có một casting hiện hành (unique partial index); `from_revision/until_revision` lưu lịch sử. Gán casting mới tăng `stories.current_revision` bằng transaction.

**Shot:** `shots` lưu `shot_spec_json` kèm `shot_key` và `revision`. Khi thay nội dung phải thêm hàng mới, đặt `supersedes_shot_id`, giữ bản cũ để tái hiện ảnh đã tạo. `shot_participants` và `shot_interactions` bắt buộc dùng role **cùng story** với shot, không dùng `character_id` làm actor/target chính. Trong một khung, giữ `actor_role_id -> action -> target_role_id`.

**Continuity:** trạng thái là chuỗi `before/delta/after` theo `shot_id + story_role_id`, và 1 trạng thái cảnh (role NULL). Không tự ghi đè một snapshot đã có; muốn thay đổi phải tạo Shot revision. Tránh nối state từ nhánh khác hoặc Story khác.

**Layout:** `shot_layouts + shot_layout_items` lưu vùng hình học `abs/xyxy` (pixel góc trên trái); `layout_exports` lưu MOSS JSON `abs_centralized/yxyx` (pixel tâm) + hash và compiler version. `role_key/story_role_id` chỉ là sidecar trong DB, **không xuất vào prompt**. Khi thay bbox/caption tạo layout revision mới. Kiểm tra `width/height`, bbox và số lượng nhân vật trước export.

**DB boundary / export:** `render_jobs` và `render_assets` không còn trong schema mục tiêu; migration `005_db_boundary` export chúng ra `database/data/backups/render-export-*.json` trước khi drop (nếu có dữ liệu). `export-bundle` ghi `layout.prompt.json`, `prompt.manifest.json`, `fidelity_report.json`; renderer chỉ đọc bundle, không kết nối SQLite. Không lưu seed, sampler, GPU, checkpoint, output ảnh hoặc trạng thái render trong DB.

**QA:** `qa_reports` append-only, subject chỉ `STORY/SHOT/LAYOUT`, phải tham chiếu đối tượng có thật. Lưu format, fidelity và policy trước export; `PASS` không được suy ra từ chưa chạy. Image/render QA là quy trình ngoài DB, không ghi `RENDER`. Quyết định policy lấy từ file trung tâm và ghi phiên bản ở `policy_ref` / JSON báo cáo; không lập policy mới trong DB skill.

## 5. Ranh giới transaction / đồng thời

- Luồng tạo Story: `stories + story_sources` trong một transaction.
- Luồng gán role: khóa revision logic và `story_castings` trong một transaction; kiểm tra stale revision trước khi ghi.
- Luồng tạo Shot: `shots + shot_participants + shot_interactions` trong một transaction. Nếu một bước thất bại, rollback toàn bộ.
- Luồng tạo Layout: `shot_layouts + shot_layout_items` trong một transaction; export sau khi draft hợp lệ.
- Với SQLite dùng `foreign_keys=ON`, `busy_timeout`, WAL khi ổn định trong local. Không chạy nhiều DB writer không điều phối. Nếu chuyển PostgreSQL phải xử lý optimistic lock có điều kiện hoặc row lock.
- Mọi schema change tạo migration tăng dần; không sửa migration đã áp dụng. Kiểm tra `PRAGMA integrity_check` và `PRAGMA foreign_key_check` sau mỗi thay đổi.

## 6. Sai lệch và phạm vi chưa triển khai

- CLI hiện đã làm được create-story/add-role/bind-role, save-plan/act/beat/event/shot/continuity/layout/QA, `export-layout`, `export-bundle`; collector/import DeepGHS, tag CSV/JSON, costume, CharaDB; `search-catalog` và báo cáo catalog.
- **Đã bỏ khỏi DB:** `queue-render`, `render_jobs`, `render_assets`, QA subject `RENDER`. Renderer/image QA là downstream file-only.
- **Chưa** có: adapter/renderer ngoài DB, đồng bộ tự động StoryPlan JSON vào đầy đủ Act/Beat/Event, catalog UI, vector search, chi tiết branch genealogy, PostgreSQL adapter, policy evaluator bằng máy, PoseScript/COCO/Grounded SAM/OpenPose importer, Wikidata entity linking.
- Danbooru API aliases/implications có thể bị Cloudflare chặn; chỉ import export thủ công có provenance, không bypass access control.
- Caption tiếng Anh tự nhiên cho pose/portrait, structured outfit palette/garment slots và consumer test vẫn là việc review, không tự sinh trong importer.
- `acts/beats/story_events` hiện là projection có cấu trúc; khi thay đổi nội dung đã lưu mà cần sửa projection, cần xây quy trình revision của projection riêng. CLI từ chối ghi đè khác nội dung, không tự xóa/sửa các sự kiện đã duyệt.
- Tránh báo hoàn thành một phần chưa có. Chỉ `init/seed` có nghĩa DB/catalog demo được khởi tạo, **không** có nghĩa import dữ liệu thật hoàn tất.

## 7. Tiêu chí nghiệm thu

1. Chạy migrations 2 lần không gây lỗi, không sinh bảng/record trùng.
2. Blind tạo Story/role/shot trước casting; sau gán casting, actor/target và Shot cũ vẫn bất biến.
3. Non-Blind gán trước; cả hai chế độ dùng cùng DB schema và Layout pipeline.
4. FK chặn role thuộc Story khác; lịch sử `story_sources`, `shots`, `layout_exports`, QA không bị sửa/xóa.
5. Import lặp không tạo bản ghi nhân vật/tag/outfit/caption trùng; source version giữ lịch sử thay đổi. Tag CSV chỉ nhập tag gắn với character core tags.
6. Core tags không thành outfit `ORIGINAL`; variant character không merge mù; generic outfit luôn `GENERIC/UNVERIFIED` và không có `character_id`.
7. Nếu bật pose P1: một identity + nhiều view, caption tiếng Anh đã review; V2 runtime mặc định không có pose/portrait/image asset.
8. Layout JSON không có metadata nội bộ, bbox chuyển đúng, hash xuất lại ổn định; template 1 người, 2 người và non-square compile được.
9. `export-bundle` tạo đủ `layout.prompt.json`, `prompt.manifest.json`, `fidelity_report.json`; manifest khớp hash; không có `render_jobs`/`render_assets`/QA `RENDER`. Báo cáo phân biệt metadata imported, consumer-tested và render tested (ngoài DB).
