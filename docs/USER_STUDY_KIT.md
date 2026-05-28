# SUS User Study Kit — FYP

Toàn bộ tài liệu cần để chạy user study đo SUS (System Usability Scale)
cho hệ thống. Kit gồm 4 phần:

1. **Recruitment** — chọn ai, bao nhiêu người.
2. **Demo script** — chạy với từng participant (10-15 phút).
3. **Google Form** — questions để copy-paste vào Forms.
4. **Scoring** — sau khi thu xong responses, chạy script ra mean SUS.

> **Target theo proposal:** mean SUS score > 70 ("Good" band).

---

## 1. Recruitment

### Tiêu chí participant

Theo proposal Section 6 (Targeted Users):

| Persona | Vai trò | Quan trọng cho user study |
|---|---|---|
| **Loan Officer** | Primary user | ⭐⭐⭐ Bắt buộc có ít nhất 2 |
| **Credit Committee** | Secondary | ⭐⭐ Nice to have |
| **SME Applicant** | Indirect | ⭐ Optional (chỉ phỏng vấn cảm nhận) |

### Số lượng

- **Tối thiểu 5 người** để SUS score có ý nghĩa thống kê (Nielsen 1993).
- **Lý tưởng 8-10 người** để cho phép drop 1-2 outliers.

### Nguồn recruit khả thi cho bạn

| Nguồn | Số người dự kiến | Ưu / nhược |
|---|---|---|
| **Kollect Systems** (nơi bạn thực tập) | 2-3 | Ưu: đã quen domain, có thể demo onsite. Nhược: cần xin phép manager. |
| **APU Finance/FinTech seniors** | 3-5 | Ưu: dễ tiếp cận. Nhược: chưa là loan officer thật, score có thể optimistic. |
| **LinkedIn outreach** (Malaysian banking) | 1-2 | Ưu: real loan officer. Nhược: low response rate. |
| **Supervisor + 1-2 academic staff** | 2 | Ưu: feedback chất lượng cao. Nhược: bias vì biết project. |

### Recruitment checklist

- [ ] Soạn 1 email/message ngắn (template ở dưới).
- [ ] Schedule 15-20 phút mỗi người (10 phút demo + 5 phút điền form +
      buffer).
- [ ] Reserve 1 phòng yên tĩnh (hoặc Zoom nếu remote).
- [ ] Chuẩn bị laptop có hệ thống đã setup sẵn (xem TESTING_GUIDE.md).
- [ ] **In sẵn 1 bản consent form** (template ở dưới) — bắt buộc theo
      ethical research practice ở APU.

### Email/Message template

> Hi [tên],
>
> Em đang làm Final Year Project về một AI system hỗ trợ loan officer
> đánh giá hồ sơ vay SME ở Malaysia. Hệ thống đã hoàn thành và cần
> feedback từ người dùng thực để hoàn thiện.
>
> Em mong anh/chị dành 15-20 phút để:
> 1. Xem em demo hệ thống (~10 phút)
> 2. Điền 1 questionnaire ngắn (10 câu, ~5 phút)
>
> Tất cả responses sẽ ẩn danh. Anh/chị có thể giúp em vào ngày/giờ
> nào tuần này được không?
>
> Cảm ơn anh/chị ạ,
> Tran Quang Dat (TP079959)

### Consent form (in 1 trang)

```
RESEARCH PARTICIPATION CONSENT FORM

Project: Agentic AI for Multi-Document Financial Analysis in Malaysian
         SME Lending (APU FYP)
Researcher: Tran Quang Dat (TP079959@mail.apu.edu.my)

By signing below, I confirm that:
1. I have been informed of the project's purpose.
2. My participation is voluntary; I can withdraw at any time.
3. My responses to the SUS questionnaire will be anonymised.
4. No personal data will be collected beyond my role/seniority band.
5. Aggregated results may appear in the FYP final report and any
   subsequent publication.

Participant name:    _______________________________
Role/Position:       _______________________________
Date:                _______________________________
Signature:           _______________________________
```

---

## 2. Demo script (10 phút)

Đọc/làm theo đúng thứ tự này cho **mỗi** participant để đảm bảo
consistency. Đừng tùy ý explain thêm — bias score.

### Setup trước participant đến

- [ ] Backend chạy (`uv run uvicorn app.main:app`)
- [ ] Frontend chạy (`npm run dev`)
- [ ] Browser mở sẵn http://localhost:5173/
- [ ] 4 PDF sample sẵn ở `data/samples/`
- [ ] Page đã refresh (không có state cũ)

### Script (đọc to)

> "Cảm ơn anh/chị đến giúp em hôm nay. Em sẽ demo trong khoảng 10 phút
> rồi anh/chị điền 1 form ngắn. Mục đích là đánh giá hệ thống dễ
> dùng không — không có câu trả lời đúng/sai, anh/chị cứ phản hồi
> thật."

#### Phần A — Context (1 phút)

> "Hệ thống này hỗ trợ loan officer đánh giá hồ sơ vay của SME ở
> Malaysia. SME thường nộp 4 loại giấy tờ: bank statement, đăng ký
> kinh doanh SSM, audited financials, và tờ khai thuế Form C. Bình
> thường loan officer phải đọc thủ công và đối chiếu — mất 2-6 tuần.
> Hệ thống tự làm việc đó trong khoảng 1 phút."

#### Phần B — Demo upload (3 phút)

1. **Chỉ vào drop zone**: "Đây là nơi anh/chị thả PDF vào. Em sẽ
   upload 4 file mẫu của một công ty tên ACME."
2. Click "browse to select", chọn 4 PDF, click Open.
3. "4 file đã sẵn sàng. Em click Analyse package."
4. **Trong khi chờ (~40-60s)**: "Hệ thống đang chạy 6 step: parse PDF,
   trích số liệu, đối chiếu giữa các file, tính tỷ số tài chính,
   đánh giá 5C, sinh risk summary. Em có thể nói thêm khi đợi nếu
   anh/chị muốn."

#### Phần C — Demo kết quả (5 phút)

5. **Risk summary card xuất hiện**: "Đây là bản tóm tắt rủi ro.
   Anh/chị thấy mấy tag màu xanh trong câu? Đó là citations — em
   click một cái."
6. Click 1 citation → modal mở. "Đây là dòng PDF gốc mà AI đã dùng
   để viết câu đó. Mọi claim đều trace ngược được — yêu cầu của BNM."
7. Đóng modal. Cuộn xuống card 5C: "5 cột này là 5C credit assessment:
   Character, Capacity, Capital, Collateral, Conditions. Mỗi cột có
   rating và evidence."
8. Cuộn tiếp: "Card Validation findings sẽ flag mọi bất thường giữa
   các file. Lần này không có vì 4 file đều consistent."
9. Cuối cùng card Reasoning trail: "Mỗi step có thời gian — đây là
   audit log mà BNM yêu cầu."

#### Phần D — Hands-on (1 phút)

> "Bây giờ anh/chị tự click thử 2-3 citations khác, hoặc cuộn xem
> các cards. Có thắc mắc gì cứ hỏi em — nhưng em sẽ không gợi ý điều
> hướng."

**Quan sát**: ghi chép participant gặp khó ở đâu (vào sổ tay, đừng
hỏi out loud).

#### Phần E — Chuyển qua questionnaire

> "Cảm ơn anh/chị. Bây giờ em xin anh/chị điền form này. 10 câu, mỗi
> câu chọn 1 trong 5 mức từ 'Hoàn toàn không đồng ý' đến 'Hoàn toàn
> đồng ý'. Có cả câu tích cực lẫn tiêu cực — anh/chị cứ đọc kỹ rồi
> chọn."

Đưa link Google Form (hoặc giấy in nếu không có Wi-Fi).

---

## 3. Google Form template

Tạo Form mới tại https://forms.google.com với cấu hình sau.

### Form metadata

- **Title:** *FYP Usability Study — SME Loan Risk Analyser*
- **Description:**
  > Cảm ơn bạn đã tham gia. Form gồm 10 câu hỏi SUS (System Usability
  > Scale) + 2 câu thông tin nền + 1 câu open-ended. Khoảng 5 phút.
  > Tất cả responses ẩn danh.
- **Settings:**
  - ☑ Collect email addresses → **OFF** (giữ anonymous)
  - ☑ Limit to 1 response → **OFF** (cho phép resubmit nếu sai)
  - ☑ Show progress bar → **ON**

### Section 1: Background (2 câu, không tính vào SUS)

**Q0.1 — Role:** (Multiple choice, required)
- Loan officer hoặc Credit analyst (active)
- Finance/banking student
- Other finance professional
- Other (please specify) — *short answer*

**Q0.2 — Years of experience in credit assessment:** (Multiple choice,
required)
- Less than 1 year
- 1-3 years
- 3-5 years
- More than 5 years

### Section 2: SUS Questionnaire (10 câu, REQUIRED)

Mỗi câu là **Linear scale 1-5** với labels:
- 1 = Strongly disagree
- 5 = Strongly agree

> ⚠️ QUAN TRỌNG: Thứ tự câu phải đúng như SUS gốc (Brooke 1986). Đừng
> đảo. Câu lẻ là positive, câu chẵn là negative.

**Q1.** I think that I would like to use this system frequently.

**Q2.** I found the system unnecessarily complex.

**Q3.** I thought the system was easy to use.

**Q4.** I think that I would need the support of a technical person to
        use this system.

**Q5.** I found the various functions in this system were well
        integrated.

**Q6.** I thought there was too much inconsistency in this system.

**Q7.** I would imagine that most people would learn to use this system
        very quickly.

**Q8.** I found the system very cumbersome to use.

**Q9.** I felt very confident using the system.

**Q10.** I needed to learn a lot of things before I could get going
         with this system.

### Section 3: Open feedback (1 câu, optional)

**Q11.** Comments / suggestions: *(Paragraph)*

> *"Anything that worked well, was confusing, or you'd want changed?"*

### Form trả về CSV như thế nào

Sau khi đủ responses:

1. Mở Google Form → tab **Responses** → icon Sheets (góc trên phải).
2. Sheets sẽ tự tạo, có columns:
   - `Timestamp`
   - `Role`
   - `Years of experience in credit assessment`
   - `I think that I would like to use this system frequently.`
   - `I found the system unnecessarily complex.`
   - ... (8 SUS questions còn lại)
   - `Comments / suggestions`

3. **File → Download → CSV** → lưu vào
   `c:/Tommy/Documents/GitHub/FYP/data/sus_responses.csv`.

4. Chạy script scoring (xem mục 4).

---

## 4. Scoring

### Cách scoring đã code sẵn

Mình đã ship 2 thứ:

- **`backend/app/evaluation/sus.py`** — function
  `score_sus_responses(respondent, [r1..r10]) → SUSResult` với scoring
  rule chuẩn (positive: response-1, negative: 5-response, sum × 2.5).

- **`backend/scripts/score_sus.py`** — đọc CSV export từ Google Form,
  apply scoring cho từng row, in ra:
  - Per-respondent score
  - Mean / median / stddev
  - Band distribution (Excellent / Good / OK / Poor)
  - Verdict so với proposal target (>70)

### Cách chạy

```bash
cd c:/Tommy/Documents/GitHub/FYP/backend
uv run python -m scripts.score_sus ../data/sus_responses.csv
```

### Template CSV

Nếu không dùng Google Forms (hoặc muốn nhập tay từ giấy), template
ở `data/sus_responses_template.csv` — copy thành `sus_responses.csv`
rồi fill.

---

## 5. After the study — analysis checklist

- [ ] **Mean SUS** ≥ 70 → PASS proposal target, tô vào Chapter 5
      (Evaluation) của final report.
- [ ] **Mean SUS** 50-70 → "OK band". Phải defend trong Discussion
      chapter: lý do, limitations, future work.
- [ ] **Mean SUS** < 50 → có vấn đề UX nghiêm trọng. Cần iterate trước
      khi submit final report.
- [ ] **Open feedback (Q11)** — đọc kỹ, tổng hợp 3-5 themes phổ biến
      nhất, đưa vào "Limitations & Future Work" section.
- [ ] **Per-role breakdown** — score của loan officer có khác student
      không? Đáng kể? Đưa thành 1 sub-section ngắn trong Evaluation.

---

## 6. Timeline gợi ý

| Tuần | Việc |
|---|---|
| 1 | Tạo Google Form, soạn email, in consent form, xác định 8-10 participants tiềm năng |
| 2 | Send invitations, schedule slots |
| 3-4 | Chạy demo + thu responses (1 slot/người, ~20 phút/slot) |
| 5 | Score, phân tích, viết Chapter 5.x "Usability Evaluation" |

---

## Phụ lục — Tại sao SUS chứ không phải custom questionnaire?

- **Tiêu chuẩn ngành (Brooke 1986)** — examiners FYP biết SUS, không
  cần explain dài về methodology.
- **Quick** — 10 câu, 5 phút.
- **Comparable** — benchmark database của SUS scores có sẵn cho hàng
  trăm hệ thống, dễ defend "system X scores Y → tốt hơn Z% systems".
- **Validated** — đã có meta-analyses chứng minh reliability ở Cronbach
  α > 0.9.

Tham khảo thêm:
- Brooke, J. (1996). *SUS: A "quick and dirty" usability scale.*
- Sauro, J., & Lewis, J. R. (2016). *Quantifying the User Experience.*
