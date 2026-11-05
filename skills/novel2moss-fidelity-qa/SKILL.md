---
name: novel2moss-fidelity-qa
description: "Kiểm tra bảo toàn nội dung trước export từ nguồn đến Story, Shot và MOSS Layout; giữ nhãn NSFW, đúng chiều vai trò, bbox. Không quản lý image/render QA trong DB."
---
# Novel2Moss — Kiểm tra bảo toàn nội dung và chất lượng (Fidelity QA)

> **Policy nội dung bắt buộc:** Đọc `docs/novel2moss/CONTENT_POLICY.md` trước khi xử lý. Mọi quyết định nội dung tuân theo scope và phiên bản tại đó; skill này không tự đặt chính sách khác.

## Vai trò

Xác minh dựa trên bằng chứng, **không phá hủy dữ liệu**. Đọc `docs/novel2moss/CONTENT_FIDELITY.md`, `docs/novel2moss/MOSS_LAYOUT.md` và `docs/novel2moss/ACCEPTANCE.md`.

## Các cổng QA trước export

1. **Nguồn và mạch truyện:** Nhãn nguồn còn nguyên văn; actor → action → target; số người tham gia; diễn biến sự kiện; ràng buộc, điều kiện cấm, phản ứng có ý nghĩa; `before/delta/after` và tính liên tục trang phục/đạo cụ.
2. **Biểu diễn trực quan và định dạng:** So sánh ShotSpec với bản nháp và MOSS Layout đã biên dịch; xác minh số item, định danh, màu outfit, trái/phải, camera, chiều hành động, đạo cụ quan trọng, chữ trong ảnh, chuyển bbox và khớp kích thước. Nếu có `render.prompt.json`: kiểm tra `scene_type`, `gen_brief`, `elements`, panel nền, bbox chồng lấn, không grid, mặt không bị che. Metadata chỉ thuộc ứng dụng phải nằm ở sidecar.
3. **Policy trước dispatch:** Xác minh `policy_id`, `policy_version`, `scope=PROMPT_DERIVATION`, quyết định và bằng chứng. Không tự tạo điều kiện chặn mới.

QA ảnh/render là quy trình **bên ngoài DB**, không ghi `qa_reports` subject `RENDER`.

## Kiểm tra chính sách nội dung

QA bảo toàn mọi nhãn nguồn và provenance. QA **không tự động phát sinh** quyết định chặn **chỉ từ nhãn NSFW/explicit**. Thay vào đó, QA xác minh `policy_id`, `policy_version`, `scope`, `decision`, bằng chứng và liên kết tới Shot theo `docs/novel2moss/CONTENT_POLICY.md`.

Phân biệt rõ kết quả kiểm tra định dạng, kết quả fidelity, quyết định policy và lỗi backend thật. Không quy lỗi render thành lỗi nội dung khi không có bằng chứng.

## Schema phát hiện

Mỗi phát hiện gồm `{shot_id, rule, status, source_pointer, target_pointer, evidence, suggestion, autofix:false}`. Tránh đánh giá chất lượng chung chung mà không có bằng chứng. Mức trạng thái: `PASS`, `WARN`, `BLOCKED`, `SKIP`. Tách riêng lỗi hình học, độ chưa chắc chắn về ảnh và lỗi điều kiện nội dung.

## Ví dụ các phát hiện QA

`ACTOR_TARGET_MISMATCH`, `PARTICIPANT_LOSS`, `SOURCE_LABEL_LOSS`, `WARDROBE_COLOR_CHANGED`, `STATE_RESET_UNEXPLAINED`, `NEGATED_CONSTRAINT_VIOLATION`, `LAYOUT_INVALID`, `LAYOUT_GRID_COLLAPSE`, `BBOX_NO_OVERLAP`.

Chỉ sử dụng trạng thái `REVIEW_REQUIRED` hoặc `POLICY_BLOCKED` từ quyết định chính sách ở scope `PROMPT_DERIVATION`; không tự định nghĩa thêm điều kiện chặn.

## Quy tắc

- Ưu tiên so sánh trường có cấu trúc, kiểm tra schema để có bằng chứng tất định; chỉ dùng LLM/vision khi cần phán đoán ngữ nghĩa.
- Không tự sửa bằng cách viết lại nguồn, đảo actor/target, đổi thể loại/cường độ, bỏ nhãn NSFW hoặc bịa tuổi trưởng thành. Chỉ đề xuất sửa nhỏ nhất trên **artifact dẫn xuất**, có lưu xuất xứ.
- Không đưa image/render QA vào `qa_reports`; QA ảnh nếu có là quy trình ngoài DB, không được ghi `subject_kind='RENDER'`.
- Giữ các generation/artifact đã được duyệt; phát hiện mới được thêm theo revision/review ID, không ghi đè record lịch sử.

## Nghiệm thu

Chuỗi nguồn → ShotSpec → Layout không có `LOSS` chưa giải thích; cổng định dạng đạt; prompt đa bbox không bị grid, có overlap và mặt không bị che; điều kiện nội dung (nếu áp dụng) đã được đánh giá độc lập; QA trước export được gán `PASS/WARN/BLOCKED/SKIP` trung thực theo bằng chứng. Không tuyên bố QA ảnh/render nếu chưa chạy ngoài DB.

## Bằng chứng QA từ Database

- Đối chiếu `story_sources`/hash → `story_revisions` → `story_events` → `shots` → `continuity_snapshots` → `layout_exports`; kiểm tra FK cùng Story và revision cụ thể, không so sánh những bản mới nhất không cùng generation.
- Lưu báo cáo bằng `n2m_workflow.py save-qa` vào `qa_reports(subject_kind,subject_id,verdict,policy_ref,report_json)`. QA report append-only; không tự UPDATE Shot/Source/Layout khi phát hiện lỗi.
- `qa_reports` có thể chứa thông tin `policy_id`, `policy_version`, `scope`, `decision` đã được xác minh từ file policy; đây là ghi nhận, không phải nơi định nghĩa policy mới. `PASS` phải có bằng chứng; subject chỉ là `STORY/SHOT/LAYOUT`.
- Kiểm tra `PRAGMA foreign_key_check`, layout bounds và hash để phân biệt lỗi toàn vẹn DB với lỗi fidelity ngữ nghĩa. Không có QA ảnh trong DB.
