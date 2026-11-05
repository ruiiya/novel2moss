---
name: novel2moss-database
description: "Khởi tạo, migration, kiểm tra toàn vẹn và quản lý transaction/revision cho SQLite Novel2Moss, dùng database làm nguồn dữ liệu chuẩn."
---
# Novel2Moss — Database Manager

> Đọc `docs/novel2moss/DATABASE_CONTRACT.md`, `DATABASE_SKILL_MAPPING.md`, `DATABASE_OPERATIONS.md` và `docs/novel2moss/CONTENT_POLICY.md` trước khi tác động dữ liệu.

## Khi nào kích hoạt

- Khởi tạo repository/database mới, nâng schema, lỗi FK/SQLite, kiểm tra integrity, quản lý revision, backup hoặc quyết định chiến lược persistence.
- Trước khi orchestrator bắt đầu Story trong repository chưa có DB. Không bắt buộc gọi lại khi schema đã kiểm tra trong cùng phiên.

## Quy trình bắt buộc

1. Kiểm tra repository hiện tại; tuyệt đối không kết nối database từ dự án khác. Xác nhận đường dẫn SQLite, quyền truy cập và migration version. Không suy ra DB tồn tại chỉ từ tên file.
2. Chạy `python database/src/n2m_db.py init`. Migration chỉ chạy nếu chưa có phiên bản trong `schema_migrations`; không chỉnh sửa migration cũ sau khi đã áp dụng.
3. Kiểm tra `PRAGMA foreign_keys`, `PRAGMA integrity_check`, `PRAGMA foreign_key_check`, danh sách migration. Nếu có lỗi, báo chứng cứ; không tự phá/reset database để sửa.
4. Gắn phiên bản schema và ID dữ liệu vào ngữ cảnh các skill còn lại. Mọi update phải dùng prepared statements, transaction và expected revision ở thao tác có thể chạy song song.
5. Tách schema/catalog dữ liệu chung khỏi Story/Shot; đừng dùng outfit/tag của dự án khác nếu không có bước import có provenance.
6. Hỗ trợ backup DB bằng API SQLite/`VACUUM INTO` theo điều kiện runtime; khi bảo trì phải đảm bảo không mất thay đổi WAL. Không dùng copy file DB đang ghi để coi là backup nhất quán.
7. Nếu schema chưa đủ cho workflow, tạo migration mới + test, không phát minh cột trong câu SQL hoặc nhồi dữ liệu không cùng ý nghĩa vào trường cũ.

## Công cụ

- Mặc định Python 3.10+ stdlib SQLite, file `database/src/n2m_db.py`, `n2m_workflow.py`, `catalog_imports.py`, `collect_sources.py`, `catalog_report.py`. Có thể thay ORM, backend hoặc shell nếu giữ nguyên schema mapping, foreign key, history và test.
- Migration hiện hành: `001_init` → `002_integrity` → `003_history_guards` → `004_catalog_enrichment` → `005_db_boundary` → `006_qa_history_guards`. Không sửa migration đã áp dụng; dùng migration mới.
- CLI cung cấp `init`, `seed`, `stats --detailed`, collector metadata, import DeepGHS/tag CSV/JSON/costume, tạo Story/role/casting, Plan/Act/Beat/Event/Shot/Continuity/Layout/QA, `export-layout` và `export-bundle`.
- **DB boundary V2:** không có `render_jobs`, `render_assets`; `qa_reports` chỉ nhận `STORY/SHOT/LAYOUT`. `export-bundle` ghi `layout.prompt.json`, `prompt.manifest.json`, `fidelity_report.json`; renderer là downstream file-only.
- Migration `005_db_boundary` tự export render rows cũ ra `database/data/backups/render-export-*.json` trước khi drop, và giữ lại QA không-RENDER. Không tự xóa dữ liệu render mà không có backup.

## Trả kết quả

`db_path`, migration versions, integrity status, số record có bằng chứng, thao tác đã commit, ID/revision, lỗi và bước còn chưa triển khai. Không lấy dữ liệu từ một DB giả định hoặc tự sửa policy.
