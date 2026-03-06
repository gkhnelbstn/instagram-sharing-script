# 📸 Instagram Group Sharing

Instagram grup sohbetlerine otomatik link paylaşım aracı.  
**Web UI** ile hesap ve grup yönetimi, tek tıkla gönderim.

---

## 🚀 Hızlı Başlangıç

### Docker Compose (Önerilen)

```bash
docker-compose up -d --build
```

Tarayıcıda aç: **http://localhost:8000**

### Lokal Geliştirme (uv ile)

```bash
uv sync
uv run uvicorn main:app --reload --port 8000
```

### Sadece Docker

```bash
docker build -t insta-sender .
docker run -d -p 8000:8000 -v insta-sessions:/app/sessions insta-sender
```

---

## 📖 Kullanım

### 1. ⚙️ Konfigürasyon Sekmesi

1. **Hesap ekle** — Instagram kullanıcı adı ve şifresini girin
2. **Giriş yap** — `🔑 Giriş` butonu ile hesaba login olun
3. **Grupları seç** — `📋 Gruplar` butonu ile DM gruplarınızı görün, gönderi yapılacak grupları seçin ve kaydedin

### 2. 📤 Gönder Sekmesi

1. **Link yapıştırın** — Instagram gönderi/reel linki
2. **Hesap seçin** — hangi hesaplardan gönderilsin
3. **Delay ayarlayın** — gönderimler arası bekleme süresi (varsayılan 8 saniye)
4. **🚀 Gönder** — tıklayın ve sonuçları izleyin

---

## 📡 API Endpoint'leri

| Endpoint | Method | Açıklama |
|---|---|---|
| `/health` | GET | Sağlık kontrolü |
| `/api/accounts` | GET | Hesapları listele |
| `/api/accounts` | POST | Hesap ekle |
| `/api/accounts/{id}` | DELETE | Hesap sil |
| `/api/accounts/{id}/login` | POST | Hesaba giriş yap |
| `/api/accounts/{id}/groups` | GET | Grupları listele |
| `/api/accounts/{id}/groups` | PUT | Seçili grupları kaydet |
| `/api/send` | POST | Link gönder |

Detaylı API dokümantasyonu: **http://localhost:8000/docs**

---

## ⚠️ Güvenlik & Uyarılar

- **Rate Limiting:** `delay` parametresini en az 8 saniye tutun
- **2FA:** İki faktörlü doğrulama varsa uygulama şifresi kullanın
- **Session:** Oturumlar `sessions/` klasöründe cache'lenir

---

## 📁 Proje Yapısı

```
├── main.py              # FastAPI backend
├── models.py            # Pydantic modelleri
├── pyproject.toml       # uv bağımlılıkları
├── Dockerfile
├── docker-compose.yml
├── static/
│   ├── index.html       # Web UI
│   ├── style.css        # Dark theme
│   └── app.js           # Frontend logic
├── sessions/            # Oturum cache
└── config.json          # Hesap & grup konfigürasyonu
```
