# Novel2Moss — Chạy DB, thu thập, import và thao tác theo skill

Python 3.10+, SQLite có FTS5 + JSON1. Các command chạy từ thư mục gốc của project.

## Khởi tạo và kiểm tra

```powershell
python database/src/n2m_db.py init
python database/src/n2m_db.py seed
python database/src/n2m_db.py stats
python database/src/n2m_db.py stats --detailed
python -m unittest discover -s tests -v
```

Migration `005_db_boundary` bỏ `render_jobs`/`render_assets` và QA subject `RENDER`; `006_qa_history_guards` phục hồi trigger append-only cho `qa_reports`. Nếu DB cũ có render rows, `apply_migrations` tự ghi backup JSON vào `database/data/backups/render-export-*.json` trước khi drop; QA không-RENDER được giữ lại.

`seed` tạo từ vựng, template và source registry nhỏ do dự án định nghĩa; **không** tự tải dataset. Nếu dùng `--db` để thay DB, đặt trước subcommand:

```powershell
python database/src/n2m_db.py --db D:\data\novel2moss.db init
```

## Thu thập metadata (collector)

Manifest mặc định: `database/collect/source_manifest.json`. Collector chỉ tải các file metadata/Markdown/CSV được khai báo, từ chối đuôi ảnh, lưu SHA256 và sidecar `.meta.json`, archive bản cũ khi nội dung đổi, và ghi log `database/imports/collection_runs.jsonl`.

```powershell
python database/src/collect_sources.py list
python database/src/collect_sources.py fetch --source deepghs
python database/src/collect_sources.py fetch --source ai_pose_gallery
python database/src/collect_sources.py fetch --source dbr_e621_lists
python database/src/collect_sources.py fetch --dry-run
python database/src/collect_sources.py verify
```

Không thêm URL ảnh vào manifest. Không tự crawl, không vượt Cloudflare/rate limit. Nếu nguồn thay đổi, chạy lại `fetch` và kiểm tra `source_record_versions`/`import_runs.details_json`.

## Import dữ liệu nguồn (offline, có provenance)

### DeepGHS

```powershell
python database/src/n2m_db.py import-deepghs-md database/imports/deepghs/blue_archive.md
```

Import tên/series/core tags vào `universes`, `characters`, `character_tags` với `CORE_CANDIDATE`. Không suy tuổi, quan hệ, outfit gốc hoặc canon.

### Tag CSV (DraconicDragon archive)

```powershell
python database/src/n2m_db.py import-deepghs-md database/imports/deepghs/blue_archive.md
python database/src/n2m_db.py import-tags-csv `
  database/imports/dbr-e621-lists-archive/danbooru/danbooru_2026-10-01_pt20-ia-dd.csv `
  --namespace danbooru --from-character-core-tags `
  --source-revision "2026-10-01/pt20-ia-dd"
```

- CSV không có header: `name,category,post_count,aliases`.
- V2 chỉ nhập **Danbooru namespace** và chỉ các tag nằm trong `character_tags` của character đã import. Không nhập toàn bộ archive, không nhập e621/merged list.
- Alias trong CSV vào `catalog_tag_relations` dạng `ALIAS`, **không** vào `character_aliases`; status để `archive_unspecified` vì CSV không có status từng alias.
- `--limit N` để pilot; `--no-aliases` để chỉ nhập tag; `--dry-run` để đếm mà không ghi.
- Nếu chưa import character, `--from-character-core-tags` báo lỗi thay vì nhập toàn bộ.

### Alias/implication JSON thủ công

```powershell
python database/src/n2m_db.py import-tag-relations-json D:\data\danbooru_aliases.json --namespace danbooru --kind alias
python database/src/n2m_db.py import-tag-relations-json D:\data\danbooru_implications.json --namespace danbooru --kind implication
```

Chấp nhận list hoặc object có `tag_aliases`/`aliases` hoặc `tag_implications`/`implications`. Không tự suy implication từ alias.

### Costume / CharaDB (V2)

```powershell
python database/src/n2m_db.py import-costume-gallery-json database/imports/ai-pose-gallery/data/costume-zh.json --source-id ai_pose_gallery
python database/src/n2m_db.py import-costume-gallery-json database/imports/ai-pose-gallery/data/costume-anime-zh.json --source-id charadb
```

- Costume/CharaDB chỉ tạo outfit `GENERIC`, `UNVERIFIED`, `character_id=NULL`; không tạo `ORIGINAL`.
- `catalog_captions` giữ tên gốc và keywords; không tải/lưu image reference, không tạo `catalog_assets`.
- Outfit generic chỉ là candidate text; chưa có structured palette/garment slots đã review.
- **Pose gallery:** manifest để `enabled:false`; chỉ bật sau khi có caption tiếng Anh đã review và consumer test. `import-pose-gallery-json` vẫn tồn tại như công cụ P1, không phải dữ liệu runtime V2.
- **Portrait:** không thu thập/không import; đã bỏ khỏi manifest và CLI.

### Các importer cũ

```powershell
python database/src/n2m_db.py import-danbooru-json D:\data\tags.json
python database/src/n2m_db.py import-wikidata-json D:\data\wikidata_export.json
python database/src/n2m_db.py search-characters "blue_archive"
python database/src/n2m_db.py search-catalog tag "long_hair" --namespace danbooru
python database/src/n2m_db.py search-catalog action "head_pat"
python database/src/n2m_db.py search-catalog outfit "sailor"
```

`import-danbooru-json` nhận JSON tag list/object; `import-wikidata-json` nhận SPARQL `results.bindings`. Không dùng các lệnh này để giả lập CSV hoặc dump tùy ý.

## Báo cáo pilot

```powershell
python database/src/catalog_report.py
```

Mặc định ghi `reports/catalog_pilot_v2.md`. Báo cáo đọc DB, không tải dữ liệu và không render; phải phân biệt metadata imported / consumer-tested / render tested (ngoài DB).

## Blind Mode

```powershell
python database/src/n2m_db.py create-story --title "Demo Blind" --mode BLIND --text-file story.txt
python database/src/n2m_db.py add-role --story-id STORY_ID --key LEAD
python database/src/n2m_db.py add-role --story-id STORY_ID --key PARTNER_A
python database/src/n2m_workflow.py save-plan --story-id STORY_ID --file story_plan.json
python database/src/n2m_workflow.py add-act --story-id STORY_ID --order 1 --title "Act 1"
python database/src/n2m_workflow.py add-beat --act-id ACT_ID --order 1 --summary "Beat 1"
python database/src/n2m_workflow.py add-event --beat-id BEAT_ID --order 1 --file event.json
python database/src/n2m_workflow.py save-shot --beat-id BEAT_ID --shot-key SHOT_001 --file shot_spec_db.json
```

Khi chọn nhân vật:

```powershell
python database/src/n2m_db.py bind-role --story-id STORY_ID --key LEAD --character-id CHARACTER_ID
```

Lệnh casting tăng `stories.current_revision`; **không** tự thay `story_events.actor_role_id` hoặc prompt cũ.

## Non-Blind Mode

Tương tự Blind, nhưng tạo Story với `--mode NON_BLIND`, tạo role và **gán nhân vật trước khi lập Shot**. Story state và catalog không trộn lẫn.

## Continuity, Layout, QA và export bundle

```powershell
python database/src/n2m_workflow.py save-continuity --shot-id SHOT_ID --file continuity.json
python database/src/n2m_workflow.py save-layout --shot-id SHOT_ID --file layout_draft_db.json
python database/src/n2m_workflow.py save-qa --kind LAYOUT --subject-id LAYOUT_ID --verdict PASS --file qa.json
python database/src/n2m_db.py export-bundle --layout-id LAYOUT_ID --out-dir exports/STORY_ID/SHOT_KEY/REVISION
```

`export-bundle` ghi `layout.prompt.json`, `prompt.manifest.json`, `fidelity_report.json`. DB workflow **dừng tại đây**. Không có `queue-render`; renderer/image QA là downstream độc lập, chỉ đọc bundle và không kết nối SQLite.

`export-layout` vẫn tồn tại như lệnh tương thích chỉ ghi prompt; dùng `export-bundle` cho bàn giao V2.

## Mẫu JSON cho các subcommand

`event.json`:
```json
{"actor_role_key":"LEAD", "target_role_key":"PARTNER_A", "action":"head_pat", "reaction":"smiles", "raw_labels":[], "spec":{}}
```

`shot_spec_db.json`:
```json
{"shot_id":"logical-shot-1", "participants":[{"role_key":"LEAD","spec":{"pose":"standing"}},{"role_key":"PARTNER_A","spec":{"pose":"sitting"}}], "interactions":[{"actor_role_key":"LEAD","target_role_key":"PARTNER_A","action_text":"gently pats the head"}]}
```

`continuity.json`:
```json
{"snapshots":[{"role_key":"LEAD","before":{"pose":"standing"},"delta":{"action":"head_pat"},"after":{"pose":"standing"}}]}
```

`layout_draft_db.json`:
```json
{"width":1024,"height":1024,"bbox_coord_space":"abs","bbox_format":"xyxy", "summary":{"meta":["anime illustration"],"canvas":"single","caption":"Two adults in a sunlit room, the left person pats the right person's head."}, "items":[{"label":"character","role_key":"LEAD","caption":"A person standing on the left, reaching to pat the other person's head.","bbox":[70,100,550,955]},{"label":"character","role_key":"PARTNER_A","caption":"A seated person on the right receiving the gesture.","bbox":[480,210,970,960]}]}
```

## Bất biến

- ID và revision trả từ mỗi command phải được dùng lại; không tự dựng ID dựa trên tên/nhãn.
- Ghi lặp với **cùng nội dung** chỉ trả lại dữ liệu có sẵn. Ghi cùng key nhưng khác nội dung khi không có revision thích hợp phải báo xung đột.
- Mỗi giai đoạn đọc policy trung tâm theo phạm vi trước khi derive prompt hoặc dispatch; dữ liệu nguồn vẫn lưu nguyên.
- Trong V2 chưa có transaction điều phối đa-command; mỗi command là một transaction độc lập. Nếu cần atomic ở mức toàn Story, phải bổ sung service/transaction coordinator.
- Không import ảnh, không đóng gói lại dữ liệu chưa rõ quyền, không báo `COMPLETE`/`PASS` nếu chưa có bằng chứng thực tế.
