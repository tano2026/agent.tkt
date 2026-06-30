# ABTrip - Phòng Vé Máy Bay Agent

## 🚀 Giới thiệu
Hệ thống quản lý đặt vé máy bay với 3 Agent chính:
- **Ticketing:** Chatbot đặt vé qua ngôn ngữ tự nhiên (API AGT cấp 1)
- **Marketing:** Automation đa kênh tự động
- **Kế toán:** Nghiệp vụ kế toán cơ bản, công nợ, báo giá

## 💡 Kiến trúc Hybrid Deployment
- **Máy Local:** Phát triển (Dev) với Docker Compose
- **VPS:** Production với Nginx, Crawler, CI/CD

## 🏗️ Công nghệ
| Layer | Công nghệ |
|-------|-----------|
| Frontend | Next.js + TailwindCSS |
| Backend | FastAPI (Python) / Node.js |
| Database | PostgreSQL 15 (Supabase) |
| Cache | Redis 7 |
| NLP | Claude / Gemini |
| API Đặt vé | AGT cấp 1 (ABTrip) |

## 🐳 Khởi động Local

### Yêu cầu
- Docker Desktop
- Git

### Các bước

1. Clone repo:
   

2. Cấu hình biến môi trường:
   

3. Khởi động:
   

4. Truy cập:
   - Frontend: http://localhost:4321
   - Backend:  http://localhost:8765

### Cổng dịch vụ
| Service | Cổng Local | Cổng Container |
|---------|-----------|----------------|
| Frontend | 4321 | 3000 |
| Backend | 8765 | 8000 |
| Database | 5987 | 5432 |
| Redis | 7103 | 6379 |

## 📋 API AGT cấp 1
Xem chi tiết tại [backend/API_ANALYSIS.md](backend/API_ANALYSIS.md)

## 🛑 Dừng hệ thống
