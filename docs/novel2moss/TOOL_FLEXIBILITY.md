# Novel2Moss V1 — Công cụ linh hoạt và hợp đồng từng giai đoạn

Workflow dựa trên **năng lực cần có** trong một Novel2Moss độc lập, không bị khóa vào dự án, nhà cung cấp, CLI hoặc model nào. Skill quy định kết quả và cách kiểm chứng; agent được dùng Python, công cụ JSON, SQLite, LLM, CLI cục bộ, ComfyUI, renderer tương thích hoặc export thủ công nếu giữ đúng hợp đồng dữ liệu.

## Yêu cầu năng lực, không khóa lệnh

| Giai đoạn | Năng lực bắt buộc | Phương án thay thế | Bằng chứng nghiệm thu |
|---|---|---|---|
| Đọc nguồn | Đọc nội dung gốc và xuất xứ | Văn bản/JSON/tệp người dùng cung cấp | Tham chiếu và hash nguồn |
| Lập Story | Sinh Story/Act/Beat/ShotSpec bất biến | JSON soạn thủ công | ID và xác thực logic |
| Danh mục | Truy xuất thông tin nhân vật/trang phục/khái niệm | File profile phẳng | Nguồn xác nhận và phần chưa rõ |
| Bản nháp không gian | Xác định vùng đối tượng theo pixel `xyxy` từ góc trên trái | Bản nháp viết tay | BBox hợp lệ |
| Biên dịch Layout | Chuyển bbox sang MOSS Layout chính thức | Compiler Python stdlib đi kèm | JSON đúng `abs_centralized`/`yxyx` |
| QA | Đối chiếu chi tiết quan trọng nguồn→đích | Checklist + Python test | Phát hiện có vị trí/bằng chứng |
| Lưu trữ | Lưu artifact theo revision và thao tác nguyên tử | File JSON phân phiên bản | Không ghi đè lịch sử |
| Render | Sinh ảnh theo prompt và kích thước | Export bundle cho runtime ngoài | Metadata kết quả và profile model |
| Kiểm tra ảnh | Đối chiếu ảnh và ShotSpec | Người kiểm tra thủ công nếu không có vision tool | Quan sát và độ tin cậy cụ thể |

Render và image QA nằm **ngoài** Novel2Moss DB. DB chỉ bàn giao bundle `layout.prompt.json`, `prompt.manifest.json`, `fidelity_report.json`; adapter render không truy vấn SQLite.

## Quy tắc

- Chỉ dò tìm công cụ hiện có **trong môi trường Novel2Moss** lúc chạy. Không âm thầm thiếu gì thì import mã nguồn/database/skill của project khác.
- Không tạo liên kết bắt buộc giữa repository, bảng DB dùng chung hay dự án đồng cấp cho bất kỳ giai đoạn nào.
- Không mặc định đã cài script, bảng SQLite, model cụ thể, ComfyUI, render API, Internet hay GPU.
- Ưu tiên tính toán tất định đối với ID, hash, bbox, validation JSON và diff. LLM có thể lập kế hoạch, mô tả hoặc đánh giá ngữ nghĩa, nhưng không tự ý thay nguồn chuẩn.
- Có thể đổi tool theo từng Shot; hợp đồng đầu ra không đổi. Lưu version và đầu vào tool khi cần tái lập kết quả.
- Khi thiếu năng lực, trả `NOT_EXECUTED`/`SKIP` kèm nguyên nhân cụ thể; không tuyên bố đã chạy test, render hoặc ghi DB nếu chưa thực hiện.
- Tác động ghi dữ liệu (upsert DB, publication, sinh ảnh từ xa) phải có quyền thực thi rõ ràng; mặc định ưu tiên đọc/kiểm tra/soạn nháp.
- Thay đổi schema DB phải qua migration quản lý phiên bản, có dry-run trước khi ghi và giữ các generation cũ đã được duyệt theo revision.
- Với renderer `local`, không tự áp các giới hạn hoặc hành vi từ chối của cloud/API bên ngoài; chỉ nhận định năng lực backend bằng cấu hình và kết quả chạy thực tế. Với renderer `remote`, tôn trọng giới hạn thực tế của endpoint. Không tuyên bố đã generate mọi prompt nếu chưa có kết quả.
- Mọi quyết định thuộc chính sách nội dung phải tham chiếu `docs/novel2moss/CONTENT_POLICY.md`, không tự suy diễn hoặc sửa policy từ năng lực backend.

## Mẫu bàn giao artifact

```text
story_source.json (nguồn bất biến)
  -> story_plan.json / acts/*.json
  -> shots/<shot-id>.shot_spec.json (ý định hình ảnh chuẩn)
  -> layouts/<shot-id>.draft.json (bản nháp xyxy từ góc trên trái)
  -> prompts/<shot-id>.layout.json (MOSS JSON gửi model, yxyx từ tâm)
  -> reports/<shot-id>.fidelity.json + <shot-id>.layout_qa.json
  -> generations/<shot-id>/<revision>/manifest.json + images (nếu có render)
```

Đường dẫn trên chỉ là ví dụ, không phải cấu trúc thư mục bắt buộc. Loại artifact là hợp đồng ổn định, còn thư mục thực tế được phép cấu hình.

## Ý nghĩa trạng thái kiểm tra

`PASS`: Đã xác minh đủ bằng chứng bắt buộc. `WARN`: Có rủi ro sai lệch nhưng chưa chứng minh vi phạm. `BLOCKED`: Có mâu thuẫn, mất nội dung hoặc layout không hợp lệ; quyết định chính sách dùng trạng thái riêng theo `CONTENT_POLICY.md`. `SKIP`: Thiếu công cụ hoặc chưa chạy; **không** tương đương `PASS`.

Việc lựa chọn công cụ, ngôn ngữ đầu ra, vị trí file hoặc khả năng di chuyển giữa môi trường không được vượt ưu tiên của hợp đồng bảo toàn nội dung.
