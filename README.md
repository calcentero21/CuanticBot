# 🎬 YouTube Slack Bot — Deploy en Render

Bot de Slack para buscar y descargar videos de YouTube directamente en tus canales.

## Comandos disponibles

| Comando | Descripción |
|---------|-------------|
| `/buscar [tema]` | Busca los 5 mejores resultados en YouTube |
| `/descargar [URL o ID]` | Descarga un video o playlist en MP4/MP3 |

---

## 🚀 Deploy en Render paso a paso

### 1. Sube el código a GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/TU_USUARIO/TU_REPO.git
git push -u origin main
```

### 2. Crea el servicio en Render

1. Ve a [render.com](https://render.com) → **New → Blueprint** (si usas `render.yaml`)
   — o — **New → Background Worker** (manual)
2. Conecta tu repositorio de GitHub
3. Configura:
   - **Runtime:** Python 3
   - **Build Command:** `apt-get update -qq && apt-get install -y -qq ffmpeg && pip install -r requirements.txt`
   - **Start Command:** `python main.py`

### 3. Agrega las variables de entorno

En el dashboard de Render → tu servicio → **Environment**:

| Variable | Valor | Dónde obtenerlo |
|----------|-------|-----------------|
| `SLACK_BOT_TOKEN` | `xoxb-...` | [api.slack.com](https://api.slack.com) → tu app → *OAuth & Permissions* |
| `SLACK_APP_TOKEN` | `xapp-1-...` | [api.slack.com](https://api.slack.com) → tu app → *Basic Information → App-Level Tokens* |

### 4. Deploy

Haz clic en **Deploy** y espera a que el log muestre:
```
⚡ Slack YouTube Bot — Iniciando en Render
🚀 Bot en Socket Mode...
```

---

## 🍪 Cookies de YouTube (opcional pero recomendado)

Las cookies permiten descargar videos que requieren login (restringidos por edad, privados, etc.).

### Cómo generar las cookies localmente

1. Instala las dependencias: `pip install yt-dlp selenium webdriver-manager`
2. Ejecuta este script en tu máquina:

```python
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

options = Options()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
# Sin headless para que puedas iniciar sesión manualmente
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.get("https://www.youtube.com")

input("Inicia sesión en YouTube y luego presiona ENTER...")

cookies = driver.get_cookies()
lines = ["# Netscape HTTP Cookie File\n"]
for c in cookies:
    domain  = c.get("domain", ".youtube.com")
    path    = c.get("path", "/")
    secure  = "TRUE" if c.get("secure") else "FALSE"
    expiry  = str(int(c.get("expiry", 9999999999)))
    name    = c.get("name", "")
    value   = c.get("value", "")
    lines.append(f"{domain}\tTRUE\t{path}\t{secure}\t{expiry}\t{name}\t{value}")

with open("cookies_netscape.txt", "w") as f:
    f.write("\n".join(lines))

print("✅ cookies_netscape.txt generado")
driver.quit()
```

3. Sube `cookies_netscape.txt` al disco de Render (el `render.yaml` ya configura un disco persistente en `/opt/render/project/src`).

> ⚠️ Las cookies expiran cada 2-3 semanas. Repite el proceso cuando el bot deje de descargar videos restringidos.

---

## ⚙️ Configuración de la app en Slack

Asegúrate de que tu app en [api.slack.com](https://api.slack.com) tenga:

**Slash Commands:**
- `/buscar`
- `/descargar`

**OAuth Scopes (Bot Token):**
- `commands`
- `chat:write`
- `files:write`
- `im:write`
- `channels:read`

**Socket Mode:** Habilitado ✅

**App-Level Token:** Con scope `connections:write` ✅

---

## 🐛 Solución de problemas

| Problema | Solución |
|----------|----------|
| Bot no responde en Slack | Verifica que el servicio en Render esté corriendo (no pausado) |
| Error de autenticación | Regenera las cookies y vuelve a subirlas |
| Video no disponible en tu región | Normal, YouTube bloquea por región |
| Archivo muy grande | Slack tiene límite de ~1 GB; videos muy largos fallarán |
| `ffmpeg: command not found` | Verifica el Build Command en Render incluye la instalación de ffmpeg |

---

## 📁 Estructura del proyecto

```
youtube-slack-bot/
├── main.py               # Código principal del bot
├── requirements.txt      # Dependencias Python
├── render.yaml           # Configuración de Render
├── cookies_netscape.txt  # (Opcional) Cookies de YouTube
└── README.md             # Esta guía
```
