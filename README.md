# 📸 Instagram Group Sharing

Instagram grup sohbetlerine otomatik link paylaşım aracı.  
**Web UI** ile hesap ve grup yönetimi, tek tıkla gönderim.  
Kullanıcı giriş sistemi ile her kullanıcının verileri ayrı tutulur.

---

## 🚀 Hızlı Başlangıç

### Docker Compose (Lokal Geliştirme — Önerilen)

```bash
docker-compose up -d --build
```

Tarayıcıda aç: **http://localhost:8000**

### Lokal Geliştirme (uv ile)

```bash
uv sync
uv run uvicorn main:app --reload --port 8000
```

---

## ☁️ Canlıya Alma (Ücretsiz — Kredi Kartı Gerekmez)

### Platform Karşılaştırması

| Özellik | Railway ⭐ | Render | Koyeb |
|---|---|---|---|
| Kredi kartı | ❌ Gerekmez | ❌ Gerekmez | ❌ Gerekmez |
| Docker desteği | ✅ Dockerfile | ✅ Dockerfile | ✅ Docker image |
| Persistent volume | ✅ Var | ❌ Free'de yok | ❌ Free'de yok |
| Public URL | ✅ `*.up.railway.app` | ✅ `*.onrender.com` | ✅ `*.koyeb.app` |
| Ücretsiz tier | $5 kredi/ay | 750 saat/ay | 1 nano servis |
| Sleep/Wake | Yok (sürekli çalışır) | 15dk boşta → uyur | Yok |
| **Session korunur mu?** | ✅ Evet | ❌ Kaybolur | ❌ Kaybolur |

> **Öneri:** Instagram session dosyalarının korunması kritik olduğu için **Railway** en iyi seçenektir.

---

### Seçenek 1: Railway (⭐ Önerilen)

**Neden Railway?**
- Kredi kartı gerekmez, GitHub ile kayıt yeterli
- $5 ücretsiz kredi (bu uygulama için yeterli)
- **Persistent volume** desteği — session/config dosyaları kaybolmaz
- GitHub push'ta otomatik deploy

#### 1. Hesap Oluştur

[railway.com](https://railway.com) → **GitHub ile Kayıt Ol**

#### 2. Proje Oluştur

1. Railway Dashboard → **New Project**
2. **Deploy from GitHub repo** → bu repository'yi seç
3. Railway otomatik olarak `Dockerfile`'ı algılar

#### 3. Volume Ekle (Önemli!)

1. Servis'e tıkla → **Settings** → **Volumes**
2. **Add Volume**:
   - Mount Path: `/data`
   - Size: 1 GB
3. **Deploy** et

#### 4. Environment Variables

Settings → Variables:
```
LOG_LEVEL=INFO
DATA_DIR=/data
PORT=8000
```

#### 5. Domain Oluştur

Settings → **Networking** → **Generate Domain**

Public URL: **https://ig-group-sharing.up.railway.app**  
_(İlk açılışta kayıt ekranı gelir, kullanıcı oluşturursunuz.)_

#### Sonraki Deploy'lar

GitHub'a push yaptığınızda otomatik deploy olur:
```bash
git push origin main
```

#### Logları İzle

Railway Dashboard → Servis → **Logs** sekmesi

---

### Seçenek 2: Render (Alternatif)

> ⚠️ **Uyarı:** Render free tier'da persistent disk yok. Her restart'ta Instagram session'ları kaybolur, tekrar giriş yapmak gerekir.

#### 1. Hesap Oluştur

[render.com](https://render.com) → **GitHub ile Kayıt Ol**

#### 2. Web Service Oluştur

1. Dashboard → **New** → **Web Service**
2. GitHub repo'yu bağla
3. Settings:
   - **Name:** ig-group-sharing
   - **Runtime:** Docker
   - **Instance Type:** Free
4. Environment Variables:
   ```
   LOG_LEVEL=INFO
   DATA_DIR=/data
   ```
5. **Create Web Service**

Public URL: **https://ig-group-sharing.onrender.com**

> **Not:** 15 dakika istek gelmezse servis uyur, ilk istek ~1 dakika sürer.

---

### Seçenek 3: Fly.io (Kredi Kartı Gerekir ⚠️)

<details>
<summary>Fly.io detayları (kredi kartı gerektirir)</summary>

| Özellik | Fly.io |
|---|---|
| Docker desteği | ✅ Dockerfile'dan otomatik build |
| Persistent volume | ✅ 1 GB ücretsiz (session/config kaybolmaz) |
| Public URL | ✅ `app-adi.fly.dev` |
| Ücretsiz tier | ✅ shared-cpu-1x + 256 MB RAM |
| Sleep/Wake | Otomatik — istek gelince ~3s'de uyanır |

#### 1. Fly CLI Kur

```powershell
# Windows (PowerShell)
powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"

# macOS / Linux
curl -L https://fly.io/install.sh | sh
```

#### 2. Hesap Oluştur & Giriş Yap

```bash
fly auth signup
# veya mevcut hesap:
fly auth login
```

#### 3. Uygulama Oluştur

```bash
cd instagram-sharing-script
fly launch --copy-config --no-deploy
fly volumes create ig_data --size 1 --region ams
```

#### 4. Deploy Et

```bash
fly deploy
```

#### 5. Aç

```bash
fly open
```

Public URL: **https://ig-group-sharing.fly.dev**

</details>

---

## 📖 Kullanım

### 0. 🔐 Kayıt / Giriş

İlk açılışta uygulama kullanıcısı oluşturun. Kayıt sırasında **şifre ipucu** belirleyebilirsiniz (opsiyonel) — şifrenizi unuttuğunuzda bu ipucuyla sıfırlayabilirsiniz. Sonraki ziyaretlerde otomatik giriş yapar (30 gün cookie).

> **Şifre Sıfırlama:** Giriş ekranında "Şifreni mi unuttun?" linkine tıklayın, kayıt sırasında belirlediğiniz ipucu cevabını girerek yeni şifre oluşturun.

### 1. ⚙️ Konfigürasyon Sekmesi

1. **Hesap ekle** — Instagram kullanıcı adı ve şifresini girin
2. **Giriş yap** — `🔑 Giriş` butonu ile hesaba login olun
3. **Grupları seç** — `📋 Gruplar` butonu ile DM gruplarınızı görün ve seçin

### 2. 📤 Gönder Sekmesi

1. **Link yapıştırın** — Instagram, YouTube, Twitter… herhangi bir link
2. **Mesaj ekleyin** (opsiyonel)
3. **Hesap seçin** — hangi hesaplardan gönderilsin
4. **Delay ayarlayın** — varsayılan 8 saniye
5. **🚀 Gönder**

> **Not:** Instagram linkleri gönderi olarak paylaşılır, diğer linkler metin olarak gönderilir.

---

## 📡 API Endpoint'leri

| Endpoint | Method | Açıklama |
|---|---|---|
| `/health` | GET | Sağlık kontrolü |
| `/api/auth/setup` | GET | İlk kurulum gerekli mi? |
| `/api/auth/register` | POST | Kullanıcı kaydı (opsiyonel şifre ipucu) |
| `/api/auth/login` | POST | Kullanıcı girişi |
| `/api/auth/hint` | GET | Şifre ipucu kontrolü (?username=xxx) |
| `/api/auth/reset-password` | POST | Şifre ipucuyla şifre sıfırlama |
| `/api/auth/logout` | POST | Çıkış |
| `/api/auth/me` | GET | Mevcut oturum |
| `/api/accounts` | GET | Instagram hesaplarını listele |
| `/api/accounts` | POST | Hesap ekle |
| `/api/accounts/{id}` | DELETE | Hesap sil |
| `/api/accounts/{id}/login` | POST | Instagram'a giriş yap |
| `/api/accounts/{id}/groups` | GET | Grupları listele |
| `/api/accounts/{id}/groups` | PUT | Seçili grupları kaydet |
| `/api/send` | POST | Link gönder |

> Tüm `/api/*` endpoint'leri (auth hariç) oturum cookie'si gerektirir.

Swagger UI: **http://localhost:8000/docs**

---

## 📁 Proje Yapısı

```
├── main.py              # FastAPI backend
├── models.py            # Pydantic modelleri
├── pyproject.toml       # Bağımlılıklar
├── uv.lock              # Lock dosyası
├── Dockerfile
├── docker-compose.yml   # Lokal geliştirme
├── railway.toml         # Railway deploy config (⭐ önerilen)
├── render.yaml          # Render.com deploy config
├── fly.toml             # Fly.io deploy config (kredi kartı gerekir)
├── .dockerignore
├── static/
│   ├── index.html       # Web UI (login + ana uygulama)
│   ├── style.css        # Dark theme
│   └── app.js           # Frontend logic
└── /data                # Persistent (volume mount)
    ├── sessions/        # Instagram oturum cache
    └── config/          # Kullanıcı & hesap konfigürasyonu
        ├── users.json
        └── config_{user_id}.json
```

---

## ⚠️ Güvenlik & Uyarılar

- **Rate Limiting:** `delay` parametresini en az 8 saniye tutun
- **2FA:** İki faktörlü doğrulama varsa uygulama şifresi kullanın
- **Session:** Instagram oturumları persistent volume'da korunur
- **Şifreler:** Uygulama kullanıcı şifreleri bcrypt ile hash'lenir
- **Cookie:** `HttpOnly` + `SameSite=Lax` — 30 gün geçerli
