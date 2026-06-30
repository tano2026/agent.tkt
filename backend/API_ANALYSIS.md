# API AGT cấp 1 - Phân tích (từ ABTrip V1.1)

## Tổng quan
- Base URL:  = https://api.abtrip.vn
- Auth: PrivateKey + ApiAccount + ApiPassword (trong body mọi request)
- Format: JSON
- Hệ thống: VN (Vietnam Airlines), QH (Bamboo), VJ (VietJet)

## Endpoints

### 1. SearchFlight

- Input: Adt, Chd, Inf, ListRoute[{Leg, StartPoint, EndPoint, DepartDate}]
- Output: Danh sách chuyến bay, giá, hãng

### 2. GetFareRule

- Input: SessionInfo (từ SearchFlight)
- Output: Quy định giá vé, điều kiện đổi/hoàn

### 3. GetSeatMap

- Input: SessionInfo
- Output: Sơ đồ ghế

### 4. GetAncillary

- Input: SessionInfo
- Output: Dịch vụ bổ sung (hành lý, suất ăn)

### 5. BookFlight

- Input: Forced, System, GuestContact, AgentContact, ListPassenger, ListAirOption, Option, Payment
- Output: BookingCode, OrderCode, TotalPrice

### 6. IssueTicket

- Input: BookingCode
- Output: Xác nhận xuất vé

### 7. RetrieveBooking

- Input: BookingCode
- Output: Chi tiết booking

### 8. GetAirports


### 9. GetAirlines


### 10. GetAircrafts


## Booking Flow
1. SearchFlight -> chọn chuyến
2. GetFareRule -> kiểm tra điều kiện
3. GetSeatMap (tùy chọn) -> chọn ghế
4. GetAncillary (tùy chọn) -> mua thêm dịch vụ
5. BookFlight -> tạo booking
6. IssueTicket -> xuất vé

## Cấu trúc Auth (mọi request)


## Mã lỗi
- : Thành công
- Khác 000: Lỗi (xem Message để biết chi tiết)