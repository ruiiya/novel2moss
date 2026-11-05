# Novel2Moss Skill Pack — Ma trận nghiệm thu

## Các tình huống bắt buộc phải vượt qua

1. Nguồn chứa `nsfw`, `adult_explicit` hoặc nhãn khác phải được lưu nguyên qua Story → ShotSpec → sidecar. Việc nhận Story, điều kiện tạo prompt và phân loại lỗi backend phải tuân theo đúng scope/decision của `CONTENT_POLICY.md`; kiểm tra kèm `policy_version` và bằng chứng.
2. Hai nhân vật: A thực hiện hành động với B và B phản ứng. Phải giữ đúng danh tính, vị trí trái/phải, chiều actor/target và biểu cảm trong kế hoạch cũng như caption.
3. Một nhân vật: không tự tạo thêm người thực hiện, người nhận hoặc phản ứng từ nhân vật thứ hai.
4. Thay trang phục có chủ đích: trạng thái hiển thị chỉ đổi sau `delta` được ghi nhận. Màu được chỉ định ở cấp Shot được ưu tiên hơn mặc định.
5. Kế thừa trạng thái: dấu vết, tư thế, tình trạng trang phục hoặc vật đang giữ phải được duy trì cho đến khi có sự kiện/chuyển cảnh tường minh làm thay đổi.
6. Blind cast: ID vai trò ổn định; không đoán nhân vật/cốt truyện gốc. Khi gán nhân vật về sau, cập nhật toàn bộ tham chiếu theo revision.
7. Hình học layout: với ảnh 1024×1024, tọa độ `[128,64,512,960]` chuyển thành `[-448,-384,448,0]`; cần kiểm thử cả ảnh không vuông và tọa độ thập phân.
8. Layout không hợp lệ (thiếu văn bản, ngoài biên, trường trùng không được phép, sai hệ tọa độ) phải bị từ chối, không âm thầm cắt bbox.
9. `story_id`, `shot_id`, phân loại nội dung và tham số renderer phải nằm trong sidecar, không xuất hiện trong JSON gửi model.
10. Khi không có tool, trả `SKIP` kèm bằng chứng, không giả vờ đã render thành công.
11. Mâu thuẫn rõ ràng hoặc thiếu vai trò quan trọng phải trả `BLOCKED` với bằng chứng. Quyết định nội dung theo đúng `CONTENT_POLICY.md`; nguồn chuẩn không bị sửa.
12. Biên dịch lặp lại cùng một bản nháp phải cho JSON giống nhau đến từng byte; không ngẫu nhiên thay đổi hoặc tự sinh thêm sự kiện.
13. Cài đặt và kiểm thử trên một project rỗng không cần bất kỳ repository, database, đường dẫn đồng cấp, dịch vụ runtime hoặc bản sao hồ sơ từ dự án khác.
14. Mọi dữ liệu đầu vào bắt buộc và quyền sở hữu dữ liệu phải được khai báo trong Novel2Moss. Có thể ngắt renderer bên ngoài mà vẫn xuất được prompt offline.
15. V2 DB không có `render_jobs`/`render_assets`/QA `RENDER`; `export-bundle` tạo `layout.prompt.json`, `prompt.manifest.json`, `fidelity_report.json`, và renderer chạy chỉ với bundle khi DB đóng.

## Cấu trúc tối thiểu của phát hiện QA

```json
{
  "shot_id": "S01",
  "rule": "ACTOR_TARGET_MISMATCH",
  "status": "BLOCKED",
  "source_pointer": "/interaction/actor_id",
  "target_pointer": "/items/0/caption",
  "evidence": "Danh tính người thực hiện đã bị đổi",
  "suggestion": "Biên dịch lại từ dữ liệu nguồn mà không thay hành động",
  "autofix": false
}
```

Không được tuyên bố đúng ngữ nghĩa hay hình ảnh hoàn toàn chỉ từ các kiểm thử cú pháp. Phải có bước đối chiếu riêng bởi người kiểm tra hoặc hệ thống thị giác đối với ảnh thực tế.
