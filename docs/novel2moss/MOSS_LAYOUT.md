# Novel2Moss V1 — Hợp đồng MOSS-Image Layout

> Phạm vi tệp: hợp đồng kỹ thuật/dữ liệu, không định nghĩa chính sách nội dung. Mọi quyết định nội dung thuộc `docs/novel2moss/CONTENT_POLICY.md`.


Nguồn chính thức: https://github.com/OpenMOSS/MOSS-Image/blob/main/USERGUIDE.md#layout-prompts-experimental
Skill cải thiện prompt chính thức: https://github.com/OpenMOSS/MOSS-Image/blob/main/skills/moss-image-prompt-enhancer/SKILL.md

MOSS-Image-Base đánh dấu **Layout Prompts là experimental**. Một prompt JSON hợp lệ chứa `summary`, danh sách `items` phẳng, `bbox_coord_space: "abs_centralized"` và `bbox_format: "yxyx"`. Layout chỉ định hướng bố cục; không cam kết model tuân thủ tuyệt đối không gian hoặc giải phẫu.

## Schema đầu ra (chỉ phần gửi model)

```json
{
  "summary": { "meta": ["anime illustration"], "canvas": "single", "caption": "Whole visible scene, style, setting, lighting, action relationship." },
  "items": [
    { "label": "character", "caption": "Visible character identity, clothing, expression, pose and action.", "bbox": [-400, -420, 448, 40] },
    { "label": "object", "caption": "Visible object.", "bbox": [40, 80, 300, 300] }
  ],
  "bbox_coord_space": "abs_centralized",
  "bbox_format": "yxyx"
}
```

Không đưa StorySpec ID, độ tuổi, cờ phân loại nội dung, hash, revision, width/height, negative prompt, thông số render hay metadata kiểm tra điều kiện vào JSON gửi model; những thông tin này nằm trong sidecar. Caption tổng quan và caption của item chỉ chứa đặc điểm trực quan có nguồn đối chiếu, không chứa toàn bộ dữ liệu truyện.

## Định dạng bản nháp có thể chỉnh sửa (dành cho ứng dụng)

Trước khi biên dịch, sử dụng đối tượng có `width`, `height`, `bbox_coord_space:"abs"`, `bbox_format:"xyxy"`, `summary`, `items`. Mỗi bbox bản nháp là `[left, top, right, bottom]`, tính bằng pixel từ góc trên trái ảnh. Không dùng phần trăm, hệ tọa độ cục bộ lồng nhau hoặc tự tính tọa độ tâm thủ công.

Với chiều rộng W, chiều cao H, chuyển bbox theo công thức:

`[top - H/2, left - W/2, bottom - H/2, right - W/2]`.

Nếu tọa độ là số thập phân, làm tròn xuống left/top và làm tròn lên right/bottom **trước khi** trừ W/2 hoặc H/2. Tất cả tọa độ phải nằm trong canvas. Width/height phải là bội số dương của 16. Đầu ra là số nguyên theo thứ tự `[y_min,x_min,y_max,x_max]`.

Ví dụ ảnh 1024×1024:

- Draft `[128,64,512,960]` → tâm `[-448,-384,448,0]`.
- Draft `[544,64,960,960]` → tâm `[-448,32,448,448]`.

Bản nháp và prompt cuối phải sử dụng **cùng kích thước render**. Không âm thầm scale hoặc crop.

## Lập kế hoạch bố cục theo ngữ nghĩa

- Mỗi người có thể phân biệt về mặt hình ảnh nên có một item `character` riêng. Dùng tên/đặc điểm nhận diện khác nhau theo nguồn và vị trí trái/phải/trước/sau; không vô tình gộp nhân vật.
- `summary.caption` diễn tả một cảnh, phong cách chung, bố cục, tương tác quan trọng của sự kiện và ánh sáng.
- `items[].caption` diễn tả chính đối tượng nhìn thấy: điểm nhận diện, trang phục và màu chính xác, biểu cảm, tư thế, động tác, hướng nhìn, chiều thực hiện/nhận hành động.
- Item `object` dành cho vật dụng quan trọng hoặc đạo cụ tương tác. Item `text` cần trường `text` chính xác và caption mô tả phong cách chữ; giữ nguyên nội dung hiển thị.
- BBox có thể chồng lấn khi cần chạm, che khuất hoặc tương tác. Không máy móc từ chối mọi vùng chồng lấn. Phải xem vùng actor và target có cho phép tương tác được mô tả hay không.
- BBox chỉ là chỉ dẫn vị trí, **không** phải khung hình chữ nhật cần vẽ lên ảnh.
- Không bịa tag, đặc điểm nhân vật hoặc sự kiện truyện.
- Mặc định caption mô tả bằng tiếng Anh nếu người dùng không yêu cầu khác; giữ nguyên chính tả/ngôn ngữ của chữ cần xuất hiện trong ảnh.
- Bản nháp và JSON cuối là hai artifact khác nhau. Không gửi bản nháp cho renderer như prompt chính thức.

## Yêu cầu kiểm tra

1. JSON đúng cú pháp, không chứa trường lạ; `summary` có caption không rỗng và có thể thêm `meta`/`canvas`.
2. `items` không rỗng; mỗi item có label `character`, `object` hoặc `text`, caption không rỗng và bbox gồm bốn số hữu hạn, diện tích dương; item `text` phải có đúng trường `text`.
3. Tọa độ nằm trong canvas; đầu ra là `abs_centralized/yxyx`, kích thước khớp manifest.
4. Kiểm tra riêng ánh xạ actor/target, số nhân vật, màu trang phục, trạng thái hiển thị, đạo cụ chính và các điều kiện loại trừ. JSON hợp lệ chưa chắc đã đúng ngữ nghĩa.
5. Sai lệch bố cục của model experimental không tự động có nghĩa prompt JSON sai.

Công cụ offline kèm theo: `tools/novel2moss/compile_layout.py`. Có thể thay bằng công cụ tất định tương đương sau khi vượt kiểm thử đối chiếu.
