---
name: novel2moss-layout-planner
description: "Tạo MOSS-Image Layout Prompts (Experimental) và render prompt đa bbox một cảnh đúng ShotSpec, từ bản nháp xyxy dễ sửa sang yxyx theo tâm bằng compiler tất định."
---
# Novel2Moss — Lập bố cục và prompt MOSS Layout

> **Policy nội dung bắt buộc:** Đọc `docs/novel2moss/CONTENT_POLICY.md` trước khi xử lý. Mọi quyết định nội dung tuân theo scope và phiên bản tại đó; skill này không tự đặt chính sách khác.

## Đích đến

**Canonical: MOSS-Image Layout Prompts (Experimental)**. Không dùng caption-only, tag-only hoặc hybrid làm prompt cuối. Trước khi xuất, đọc `docs/novel2moss/MOSS_LAYOUT.md` và `docs/novel2moss/CONTENT_FIDELITY.md`.

Có thể xuất thêm **`render.prompt.json` đa bbox** cho renderer nhận `scene_type / gen_brief / elements`. Đây là artifact export-side đi kèm, không thay `layout.prompt.json`, không đổi schema DB và không đổi nội dung truyện.

## Nguồn chính thức

- Repo: `https://github.com/OpenMOSS/MOSS-Image`
- Skill: `skills/moss-image-prompt-enhancer/SKILL.md`
- Layout công khai: `summary` + `items`; draft `width/height` bội số 16, `bbox_coord_space="abs"`, `bbox_format="xyxy"`; compiler đổi sang `abs_centralized` / `yxyx`, bỏ width/height khỏi prompt.
- Compiler từ chối field lạ, gồm `scene-schema elements`, `children`, `parent`, `id`. Vì vậy **không trộn** `elements` vào `layout.prompt.json`.
- Gallery có ví dụ `scene_type/gen_brief/elements`; đó là scene schema tương thích gallery, không phải schema compiler chính thức. Chỉ dùng ở `render.prompt.json` khi renderer nhận.
- Skill chính thức mặc định **caption** cho cảnh thường; Layout dùng khi cần kiểm soát vị trí/text/panel. Novel2Moss vẫn dùng Layout vì cần kiểm soát bố cục.

## Quy trình

1. Đọc ShotSpec đã duyệt, tham chiếu nguồn, width/height và quyết định `PROMPT_DERIVATION` từ policy trung tâm. Chỉ xuất prompt cho quyết định `PASS`; các trạng thái khác được ghi nhận đúng scope, không sửa ý nghĩa truyện.
2. Lập **sơ đồ cảnh**: số người xuất hiện, đặc điểm nhận diện, actor → action → target → reaction, tư thế, hướng nhìn, cử chỉ, trang phục/màu sắc, đạo cụ, camera, ánh sáng và ràng buộc nhìn thấy.
3. Viết `summary.caption` mô tả toàn cảnh trực quan và tương tác chính **đúng sự kiện**. Caption mỗi item tập trung vào đặc điểm người/vật và hành động cụ thể; tránh đại từ mơ hồ, nhất là cảnh nhiều nhân vật.
4. Tạo một item phẳng cho mỗi nhân vật quan trọng xuất hiện (thêm vật/chữ chỉ khi cần). Các nhân vật có ý nghĩa định danh phải giữ tên hoặc điểm nhận diện khác biệt đã có trong nguồn.
5. Phác vùng đối tượng bằng bbox pixel góc trên-trái `[x_min,y_min,x_max,y_max]` với kích thước render rõ ràng. BBox có thể chồng lấn khi có chạm/che khuất; kiểm tra quan hệ không gian actor/target có khả thi.
6. Lưu `layout.draft.json` với `bbox_coord_space:"abs"`, `bbox_format:"xyxy"`. **Không** để LLM tự tính tọa độ tâm cuối cùng.
7. Dùng compiler chính thức nếu có hoặc `tools/novel2moss/compile_layout.py`; có thể thay bằng công cụ tất định tương đương đã kiểm thử. Đảm bảo JSON cuối có `abs_centralized`, `yxyx`, tọa độ nguyên và **không** chứa trường nội bộ ứng dụng.
8. Sinh sidecar ánh xạ từng chi tiết ShotSpec quan trọng tới `summary.caption`, `items[n].caption`, bbox hoặc `NON_VISUAL_SIDECAR`. Nếu mất ý nghĩa hoặc mâu thuẫn thì chặn phát hành.
9. Nếu renderer nhận `elements`, xuất thêm `render.prompt.json` đa bbox theo mục dưới; giữ nguyên `layout.prompt.json` canonical.

## Bảo toàn nội dung

Không tự thêm sự kiện, đảo actor và người nhận, đổi trang phục/màu sắc, bỏ nhân vật bắt buộc hoặc đổi nhãn nguồn. Nhãn nội dung ở sidecar; cổng xuất prompt dựa vào quyết định policy tương ứng, không được tự làm nhẹ hoặc viết lại nguồn để đổi kết quả.

## Render prompt đa bbox (một cảnh)

Dùng khi renderer nhận scene schema `scene_type / gen_brief / elements / bbox_coord_space`. Đây là bản export-side, không thay `layout.prompt.json` canonical và **không phải** schema compiler chính thức của MOSS-Image.

Nếu render MOSS-Image-Base/SFT: dùng `layout.prompt.json` (`summary/items`), không đưa `elements` vào compiler.

```json
{
  "scene_type": "explicit anime group sex, ...",
  "gen_brief": "Single continuous anime illustration, one scene, not a grid or rows. ...",
  "elements": [
    {"type": "panel", "salience": "background", "identity": "Continuous setting, no panels or dividers.", "bbox": [-512, -512, 512, 512]},
    {"type": "obj", "salience": "primary", "identity": "Name, adult, appearance, outfit, pose, expression, interaction.", "bbox": [-480, -260, 480, 420]},
    {"type": "obj", "salience": "secondary", "identity": "...", "bbox": [-500, -420, 300, 200]}
  ],
  "bbox_coord_space": "abs_centralized"
}
```

- Nhiều bbox được phép; **không bắt buộc 1 bbox full-canvas**. Chỉ dùng 1 item full-canvas cho cảnh solo.
- Mỗi nhân vật một `obj`; nền một `panel` full canvas.
- Bbox **chồng lấn** theo quan hệ cơ thể; không xếp 2×2/3×2/ô chân dung, không chia đều 4 góc.
- Một anchor rõ (thường target/người nhận) ở tiền cảnh; actor và người khác thành cung lệch, cao thấp so le.
- `gen_brief` phải ghi rõ: `single continuous scene`, `not a grid or rows`, `no panels/split screen/comic grid`, `overlap shoulders and lower torsos, never faces`, `faces unobstructed`, `heads/torsos fill boxes`, `no extra limbs/duplicates/spectators`.
- Ghi pose/action cụ thể trong `gen_brief` và `elements[].identity`; không để renderer tự suy ra.
- Bbox centered `yxyx`; nếu renderer yêu cầu, thêm `bbox_format: "yxyx"`. Không đổi sang tag-only/caption-only.

### Chống grid

- Không đặt bbox theo 4 góc phần tư hoặc hàng đều.
- Kiểm tra ít nhất một cặp bbox giao nhau ở vùng thân/chi.
- Không để khoảng trống hình chữ nhật giữa các nhân vật.
- Nếu ảnh ra grid: sửa bbox overlap và `gen_brief`, không thêm mô tả panel.

## Kiểm tra

- Width/height tương thích bội số 16; bbox diện tích dương và nằm trong khung; giữ nguyên chữ cần hiển thị.
- Không tự tạo danh tính hay tuổi; chi tiết ngoại hình phải dựa trên ShotSpec.
- BBox thống nhất với mô tả trái/phải và quan hệ chạm giữa actor/target.
- JSON Layout đúng cú pháp; chạy Fidelity QA ngữ nghĩa riêng.
- Nếu có `render.prompt.json`: đủ `scene_type`, `gen_brief`, `elements`, `bbox_coord_space`; có panel nền; mỗi nhân vật một `obj`; ít nhất một cặp bbox chồng lấn; không grid.
- Layout là tính năng experimental: kiểm tra ảnh thật; model có thể đặt đối tượng lệch bbox.

## Bàn giao

JSON bản nháp có thể chỉnh, JSON cuối gọn để đặt vào positive prompt của MOSS, manifest width/height, bản ánh xạ fidelity và báo cáo QA. Kèm `render.prompt.json` + `prompts.render.jsonl` khi renderer nhận `elements`; renderer/runtime tùy chọn.

## Layout và database

- Đọc `shots.shot_spec_json`, `shot_participants`, `story_castings` theo revision và `layout_templates` để chọn gợi ý bố cục. Không để template ghi đè thông tin đã xác nhận.
- Ghi draft bằng `n2m_workflow.py save-layout`: `shot_layouts` lưu summary/width/height, `shot_layout_items` lưu bbox abs/xyxy và `story_role_id` cho các character items. Trường `role_key` được dùng để map bên draft, không xuất sang prompt.
- Biên dịch bằng `n2m_db.py export-layout` vào `layout_exports` có `compiler_version`, `prompt_sha256`; bản MOSS JSON chỉ có summary, items, bbox_coord_space và bbox_format. Không chuyển metadata DB vào positive prompt.
- Nếu thay bbox/caption cần layout revision mới; export cùng input phải có hash ổn định và không tạo bản ghi export trùng.
- Dùng `DATABASE_OPERATIONS.md` để lấy ví dụ JSON đúng CLI hiện tại.
