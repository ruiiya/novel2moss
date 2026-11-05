# Novel2Moss — Mapping skill ↔ database

Đọc cùng `DATABASE_CONTRACT.md`. Danh sách này là **bảng đã có thật trong migrations**, không phải yêu cầu tự phát minh schema mới.

| Skill | Đọc | Ghi / hành vi | Điều kiện |
|---|---|---|---|
| `novel2moss-orchestrator` | schema_migrations, stories, story_revisions, qa_reports | điều phối transaction, CLI; không cập nhật DB ngầm | Khởi tạo DB/migration trước workflow |
| `novel2moss-database` | schema_migrations, sqlite_master, PRAGMA | chạy migration, kiểm tra integrity, xác định DB version | Dừng nếu schema thiếu/không tương thích |
| `novel2moss-catalog-ingest` | source_registry, source_records, catalog_tags, catalog_tag_relations, catalog_captions | import_runs, source_record_versions, characters, selected tags, generic outfits/captions | Consumer contract + provenance/license rõ; không ngụy tạo outfit canon |
| `novel2moss-character-profile` | characters, traits, outfits, outfit_parts, aliases, catalog_captions | bản ghi đã xác minh với nguồn; không sửa dữ liệu canon không chứng cứ | Catalog độc lập mọi Story |
| `novel2moss-story-planner` | stories, story_sources, story_revisions, story_roles | create-story, save-plan, add-act, add-beat, add-event | Mọi event tham chiếu role trong story |
| `novel2moss-blind-cast` | stories, story_roles, story_castings, characters | add-role, bind-role | Gán trễ, revision mới, không đổi role event |
| `novel2moss-shot-spec` | beats, story_events, roles, castings, vocabulary, outfits | save-shot → shots/shot_participants/shot_interactions | Actor-target theo role, append-only |
| `novel2moss-continuity` | shots, continuity_snapshots, story_roles | save-continuity → before/delta/after | Role state không xuyên Story/nhánh |
| `novel2moss-layout-planner` | shot_spec_json, shot participants, layout_templates | save-layout, `export-bundle` | Draft abs/xyxy, export abs_centralized/yxyx |
| `novel2moss-fidelity-qa` | toàn bộ chuỗi nguồn→shot→layout, policy version | save-qa → qa_reports | Chỉ trước export; subject STORY/SHOT/LAYOUT; report append-only |
| `novel2moss-render-adapter` | **không đọc DB** | chỉ đọc `layout.prompt.json` + manifest + fidelity report | File-only; không render state trong DB |

## Catalog enrichment / V2 boundary

- `catalog_tags`: chỉ Danbooru tag gắn với character core tags; giữ category thô và `original_name`; `catalog_tag_taxonomy` giải thích category.
- `catalog_tag_relations`: alias/implication tag, không phải `character_aliases`.
- `catalog_assets`: không dùng để thu thập ảnh/portrait/pose trong V2; bảng có thể rỗng.
- `pose_references` + `pose_reference_views`: P1, chỉ bật khi caption tiếng Anh đã review; V2 runtime mặc định 0.
- `outfits` generic: `outfit_kind='GENERIC'`, `verification='UNVERIFIED'`, `character_id=NULL`; không tự thành `ORIGINAL`.
- `catalog_entity_links`: chỉ dùng khi có evidence; không merge theo tên.
- `catalog_captions`: giữ bản gốc, `lang`, `origin`, `review`; bản dịch tiếng Anh phải được review riêng.
- `qa_reports`: chỉ `STORY/SHOT/LAYOUT`; migration `005_db_boundary` bỏ RENDER/render tables, `006_qa_history_guards` phục hồi trigger append-only.

## Đối chiếu JSON ↔ cột

- `story_plan.json` → `story_revisions.plan_json`; `story_sources.raw_text` là bản gốc không sửa.
- `story_plan.acts[].beats[].events[]` → tương ứng `acts`, `beats`, `story_events`; CLI chưa tự đồng bộ nested plan, phải gọi các thao tác add riêng.
- `shot_spec.json` → `shots.shot_spec_json`; các role/hành động truy vấn nhanh nằm ở `shot_participants`, `shot_interactions`.
- `continuity_state.json` → `continuity_snapshots.{before_json,delta_json,after_json}`.
- `layout.draft.json` → `shot_layouts` + `shot_layout_items`; các item có `role_key` bên bản nháp sẽ được đổi thành `story_role_id` trong DB.
- `export-bundle` → thư mục `exports/<story>/<shot>/<revision>/`: `layout.prompt.json` từ `layout_exports.prompt_json`, `prompt.manifest.json` (story/shot/revision/size/hash/compiler), `fidelity_report.json` từ QA trước export.
- `layout.prompt.json` **không** chứa `story_id`, `role_key`, `shot_id`, `policy_ref`, width/height hoặc provenance.
- `fidelity_report.json` ← `qa_reports.report_json`; subject chỉ `STORY/SHOT/LAYOUT`; render/image QA không ghi vào DB.

## Đọc lại trước khi tạo artifact

- Tìm story/shot/layout hiện hành bằng ID và `revision` lớn nhất tương ứng, không dùng `ORDER BY created_at` khi có revision.
- Khi cần render lịch sử, dùng đúng bundle `layout.prompt.json`/`prompt_sha256` đã export, **không** tái biên dịch từ Shot mới và không đọc render job từ DB.
- Khi sửa Story, dùng `source_sha256` để nhận biết đầu vào; không tự thay đổi nguồn đã lưu.
- Khi chọn nhân vật, chỉ dùng `character_traits.is_locked`/`confidence`, `outfits.verification`, `source_record_id` để quyết định mức độ xác minh; nhãn catalog không chứng minh trang phục gốc.
