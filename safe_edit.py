#!/usr/bin/env python3
import re

with open('d:/iNew/app/services/ai_copilot.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the deep_dive prompt
old_prompt = """    "deep_dive": f"""Bạn là một chuyên gia phân tích bình luận thời sự và biên kịch Podcast/Radio hàng đầu.
Hãy chuyển hóa nội dung bài viết sau thành một KỊCH BẢN PHÁT THANH / BÌNH LUẬN CHUYÊN SÂU có thời lượng khoảng {target_mins} PHÚT (tương đương khoảng {target_words} từ, tốc độ đọc ~150-160 từ/phút).

YÊU CẦU CẤU TRÚC CHI TIẾT:
1. TIÊU ĐỀ BÀN TIN: Hấp dẫn, sâu sắc, mang tính gợi mở.
2. PHẦN 1: LỜI CHÀO & ĐẶT VẤN ĐỀ (Khoảng 1-2 phút): Hook gây ấn tượng, nêu bật vì sao sự kiện này quan trọng và đáng chú ý ngay lúc này.
3. PHẦN 2: BỐI CẢNH LỊCH SỬ & NGUỒN CƠN (Khoảng 2-3 phút): Xâu chuỗi dòng sự kiện, diễn biến từ đầu dẫn tới tình huống hiện tại.
4. PHẦN 3: PHÂN TÍNH ĐA CHIỀU & MỔ XẺ BẢN CHẤT (Khoảng 4-6 phút):
    - Luận điểm 1: Diễn biến cốt lõi, số liệu cụ thể và các phát ngôn chính thức.
    - Luận điểm 2: Tác động trực tiếp đến đời sống, kinh tế, xã hội hoặc các bên liên quan.
    - Luận điểm 3: Góc nhìn chuyên gia, phân tích phản biện và các tranh cãi (nếu có).
5. PHẦN 4: DỰ BÁO TƯƠNG LAI & CÁC KỊCH BẢN CÓ THỀ XẢY RA (Khoảng 2-3 phút).
6. PHẦN 5: LỜI BÌNH KẾT & CÂU HỎI MỞ CHO THÍNH GIẢ (Khoảng 1-2 phút).

YÊU CẦY VĂN PHONG PHÁT THANH:
- Văn phong tự nhiên như một phát thanh viên đang trò chuyện trực tiếp, câu từ gãy gọn, có nhịp thở và câu nối chuyển tiếp mượt mà.
- Mở rộng đầy đủ các từ viết tắt (UBND -> Ủy ban nhân dân, TP.HCM -> Thành phố Hồ Chí Minh, tỷ/triệu viết rõ chữ) để máy đọc TTS phát âm chuẩn xác.

Nội dung bài viết:
\"\"",

"""

new_prompt = """    "deep_dive": f"""Bạn là một chuyên gia phân tích bình luận thời sự và biên kịch Podcast/Radio hàng đầu.
Hãy chuyển hóa nội dung bài viết sau thành một KỊCH BẢN PHÁT THANH / BÌNH LUẬN CHUYÊN SÂU có thời lượng khoảng {target_mins} PHÚT (tương đương khoảng {target_words} từ, tốc độ đọc ~150-160 từ/phút).

CHỌN ĐỘ DÀI THÙC CHÍNH:
- Nếu {duration_minutes} phút ngắn (≤ 60s): Tối ưu khoảng 800-900 từ, trọng tâm vào điểm mấu chốt và câu chuyện hấp dẫn
- Nếu {duration_minutes} phút trung bình (3-5 phút): Khoảng 480-800 từ, cân bằng bối cảnh lịch sử và phân tích đa chiều
- Nếu {duration_minutes} phút dài (10-15 phút): Khoảng 1600-2400 từ, sâu sát mọi khía cạnh including bối lịch sử, tác động xã hội, các quan điểm chuyên gia và dự báo

YÊU CẦU CẤU TRÚC CHI TIẾT:
1. TIÊU ĐỀ BÀN TIN: Hấp dẫn, sâu sắc, mang tính gợi mở.
2. PHẦN 1: LỜI CHÀO & ĐẶT VẤN ĐỀ (Khoảng 1-2 phút): Hook gây ấn tượng, nêu bật vì sao sự kiện này quan trọng và đáng chú ý ngay lúc này.
3. PHẦN 2: BỐI CẢNH LỊCH SỬ & NGUỒN CƠN (Khoảng 2-3 phút): Xâu chuỗi dòng sự kiện, diễn biến từ đầu dẫn tới tình huống hiện tại.
4. PHẦN 3: PHÂN TÍNH ĐA CHIỀU & MỔ XẺ BẢN CHẤT (Khoảng 4-6 phút cho {duration_minutes} phút dài):
    - Luận điểm 1: Diễn biến cốt lõi, số liệu cụ thể và các phát ngôn chính thức.
    - Luận điểm 2: Tác động trực tiếp đến đời sống, kinh tế, xã hội hoặc các bên liên quan.
    - Luận điểm 3: Góc nhìn chuyên gia, phân tích phản biện và các tranh cãi (nếu có).
5. PHẦN 4: DỰ BÁO TƯƠNG LAI & CÁC KỊCH BẢN CÓ THỀ XẢY RA (Khoảng 2-3 phút).
6. PHẦN 5: LỜI BÌNH KẾT & CÂU HỎI MỞ CHO THÍNH GIẢ (Khoảng 1-2 phút).

YÊU CẦY VĂN PHONG PHÁT THANH:
- Văn phong tự nhiên như một phát thanh viên đang trò chuyện trực tiếp, câu từ gãy gọn, có nhịp thở và câu nối chuyển tiếp mượt mà.
- Mở rộng đầy đủ các từ viết tắt (UBND -> Ủy ban nhân dân, TP.HCM -> Thành phố Hồ Chí Minh, tỷ/triệu viết rõ chữ) để máy đọc TTS phát âm chuẩn xác.
- Sử dụng cấu trúc câu ngắn gọn, có dấu chấm phẩy rõ ràng để máy đọc lấy hơi tự nhiên.
- Chèn các câu nối chuyển mượt mà giữa các phần (ví dụ: "Để hiểu rõ hơn về nguyên nhân này, chúng ta hãy cùng nhìn lại..."; "Tuy nhiên, góc nhìn từ các chuyên gia lại cho thấy một bức tranh hoàn toàn khác...").

Nội dung bài viết:
\"\"",

"""

if old_prompt in content:
    content = content.replace(old_prompt, new_prompt)
    print('Replaced deep_dive prompt')
else:
    print('old_prompt not found - checking what exists...')
    # Let's find what's actually there
    import re
    match = re.search(r'\"deep_dive\":.*?Nội dung bài viết:', content, re.DOTALL)
    if match:
        print("Found deep_dive section:")
        print(match.group()[:500])
    else:
        print("Could not find deep_dive section")

with open('d:/iNew/app/services/ai_copilot.py', 'w', encoding='utf-8') as f:
    f.write(content)