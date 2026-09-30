# ChargebackDisputeX — Context Priming & Technical Architecture
**Dự Án: ChargebackDisputeX — Autonomous Adjudicated E-Commerce Chargeback Protocol**
**Track: Agentic Commerce Infrastructure / Onchain Justice**

---

## 0. CÁC QUYẾT ĐỊNH CỐT LÕI (GROUND TRUTH)

| # | Hạng mục | Đã chốt | Hệ quả bắt buộc |
|---|---|---|---|
| **D1** | **Mạng triển khai** | **studionet** (GenLayer Studio hosted, `https://studio.genlayer.com`) | Contract deploy trên studionet (Chain ID `61999`). Không nhầm lẫn với testnet. |
| **D2** | **Kênh nộp bài** | **GenLayer Portal — track Builders** (`portal.genlayer.foundation`) | Nộp qua Portal dashboard: GitHub repo + Live contract address + Demo docs. |
| **D3** | **API non-deterministic** | **`gl.vm.run_nondet(leader_fn, validator_fn)`** | So sánh ngữ nghĩa rời rạc (Discrete Consensus Binding): 4 enum chuẩn xác. |

---

## 1. Bản Chất Bài Toán & Định Vị Dự Án

### Vấn Đề Cốt Lõi Của Thanh Toán Thương Mại Điện Tử Bằng Crypto
- **Tính bất biến (Irreversibility):** Thanh toán bằng tiền mã hoá (Crypto, USDT, USDC) trên blockchain truyền thống mang tính một chiều và không thể đảo ngược. Khác với thẻ tín dụng truyền thống (Visa/Mastercard) có quy trình khiếu nại hoàn tiền (chargeback), blockchain thiếu hoàn toàn cơ chế bảo vệ người tiêu dùng.
- **Rủi ro gian lận thương mại (E-Commerce Fraud):** Nếu người bán ác ý không giao hàng, gửi hộp rỗng hoặc cung cấp mã vận đơn giả mạo, người mua chịu mất trắng 100% tài sản.
- **Bế tắc của Smart Contract truyền thống:** Hợp đồng thông minh Solidity không thể tự kết nối trực tiếp vào hệ thống tracking của các hãng vận chuyển quốc tế (DHL, FedEx, UPS, USPS) để đọc và đối soát hành trình thực tế của bưu kiện.

### GenLayer Fit (Trục 1: Agentic Commerce Infrastructure & Onchain Justice)
`ChargebackDisputeX` giải quyết bài toán cốt lõi này bằng việc ứng dụng Intelligent Contract trên GenLayer:
1. **Escrow Đơn Hàng & Tiền Cọc Trách Nhiệm (Seller Fulfillment Bond):**
   - Người mua ký quỹ 100% giá trị đơn hàng vào hợp đồng.
   - Người bán đặt cọc cam kết (`seller_bond`) nhằm chứng minh thiện chí giao hàng chuẩn xác.
2. **Canonical Host Whitelist & Tracking Number Binding:**
   - URL tra cứu bắt buộc thuộc danh mục tên miền chính thức của các hãng vận tải uy tín (`dhl.com`, `fedex.com`, `ups.com`, `usps.com`, `17track.net`, `parcelsapp.com`, v.v.).
   - Mã vận đơn (`tracking_number`) bắt buộc phải xuất hiện trực tiếp trong chuỗi URL nhằm triệt tiêu hoàn toàn nguy cơ giả mạo đường link (URL spoofing) hoặc replay attack.
3. **Thẩm Định Thực Nghiệm Đa Trạm (Web Render & LLM Multi-Validator):**
   - Khi có tranh chấp ("Hàng báo thất lạc / Không nhận được hàng / Đơn hàng bị hoàn trả"), validator GenLayer truy cập trực tiếp trang tra cứu bưu chính thông qua `gl.nondet.web.render(url, mode="text")`.
   - Validator LLM phân tích văn bản thực tế, trích xuất sự kiện vận chuyển và biểu quyết trạng thái đơn hàng.
4. **Quy Tắc Giải Ngân Tất Định Rời Rạc (Discrete Determinism):**
   - `DELIVERED_CONFIRMED`: Kiện hàng đã giao thành công tới người nhận → giải ngân 100% tiền hàng + hoàn cọc cho người bán.
   - `LOST_OR_RETURNED`: Bưu kiện bị thất lạc, vỡ hỏng hoặc hoàn trả người gửi → hoàn tiền 100% cho người mua và tịch thu tiền cọc bồi hoàn cho người mua.
   - `INVALID_OR_UNTRACKED`: Mã vận đơn giả mạo hoặc không tồn tại trong hệ thống bưu bưu cục → xử phạt người bán gian lận, hoàn 100% tiền mua + toàn bộ tiền cọc cho người mua.
   - `IN_TRANSIT`: Bưu kiện đang lưu thông hợp lệ → giữ nguyên quỹ ký quỹ trong trạng thái `CREATED` và cho phép gia hạn bảo vệ.

---

## 2. Tiêu Chuẩn Kỹ Thuật Đạt Điểm Tuyệt Đối & Khắc Phục Lỗi Deploy

- **Dòng 1 chuẩn tuyệt đối:** `# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }` không có khoảng trắng hay comment nào phía trên.
- **An toàn chuyển tiền:** Tuyệt đối không dùng `@gl.evm.contract_interface` hay `gl.eth.send_value`. Sử dụng chuẩn GenLayer Studio: `gl.get_contract_at(recipient).emit_transfer(value=u256(int(amount)))`.
- **Discrete Consensus Binding (Tránh bất đồng thuận AI):** `validator_fn` so sánh chính xác 100% giá trị enum `verdict`, không so sánh chuỗi `reason` tự do của LLM.
- **An toàn Storage Types:** Dùng `bigint` cho toàn bộ số dư và tiền tệ (không dùng `int`), `TreeMap[str, OrderEscrow]` cho danh sách đơn hàng với key `str`, `@allow_storage @dataclass` cho struct lưu trữ.
- **Không tái khởi tạo TreeMap trong `__init__`:** Tuân thủ quy tắc auto-initialization của GenVM để tránh lỗi `AssertionError: TreeMap <- TreeMap`.
