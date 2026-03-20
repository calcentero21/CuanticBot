import os
import subprocess

import re
import tempfile
import threading
import string
import subprocess
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from yt_dlp import YoutubeDL
import imageio_ffmpeg

# Añadir ffmpeg al PATH
os.environ["PATH"] = os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe()) + os.pathsep + os.environ.get("PATH", "")

# Encontrar Node.js — Render lo instala en /opt/render/project/nodes/
import glob as _glob
_node_dirs = _glob.glob("/opt/render/project/nodes/*/bin")
if _node_dirs:
    os.environ["PATH"] = _node_dirs[0] + ":" + os.environ.get("PATH", "")
    print(f"✅ Node.js encontrado en: {_node_dirs[0]}")
else:
    print("⚠️  Node.js no encontrado en /opt/render/project/nodes/")

# --- CREDENCIALES (desde variables de entorno) ---
BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")

if not BOT_TOKEN or not APP_TOKEN:
    raise ValueError("❌ Faltan variables de entorno: SLACK_BOT_TOKEN y/o SLACK_APP_TOKEN")

app = App(token=BOT_TOKEN)

# --- CONFIGURACIÓN DE COOKIES ---
SCRIPT_DIR = os.getcwd()
COOKIES_FILE = os.path.join(SCRIPT_DIR, "cookies_netscape.txt")
COOKIES_VALID = os.path.exists(COOKIES_FILE)

if COOKIES_VALID:
    print(f"✅ Cookies encontradas: {COOKIES_FILE}")
else:
    print("⚠️  No se encontró cookies_netscape.txt — las descargas pueden fallar en videos restringidos.")


def get_ydl_opts_base():
    opts = {
        "quiet": False,
        "no_warnings": False,
        "socket_timeout": 30,
        "nocheckcertificate": True,
        "extractor_args": {
            "youtube": ["skip=hls/dash", "lang=es"]
        },
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/133.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "es-ES,es;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        "geo_bypass": True,
        "geo_bypass_country": "US",
        "youtube_include_dash_manifest": False,
    }
    if COOKIES_VALID:
        opts["cookiefile"] = COOKIES_FILE
    return opts


def extract_playlist_info(playlist_url):
    try:
        opts = get_ydl_opts_base()
        opts["quiet"] = True
        opts["extract_flat"] = "in_playlist"
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(playlist_url, download=False)
            videos = []
            for entry in (info.get("entries") or []):
                if entry:
                    videos.append({
                        "id": entry.get("id"),
                        "title": entry.get("title", "Sin título"),
                        "url": entry.get("url") or f"https://www.youtube.com/watch?v={entry.get('id')}",
                    })
            return {"title": info.get("title", "Lista"), "videos": videos, "count": len(videos), "success": True, "error": None}
    except Exception as e:
        return {"title": "Lista", "videos": [], "count": 0, "success": False, "error": str(e)}


def extract_video_info(video_url):
    try:
        opts = get_ydl_opts_base()
        opts["quiet"] = True
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            return {"title": info.get("title", "Video"), "duration": info.get("duration", 0), "success": True, "error": None}
    except Exception as e:
        return {"title": "Video", "duration": 0, "success": False, "error": str(e)}


def is_playlist_url(url):
    return "list=" in url or "/playlist?list=" in url or "youtube.com/playlist" in url


# --- LÓGICA DE DESCARGA ---
def descargar_y_subir(video_url, video_title, channel_id, user_id, client, formato="video"):
    valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
    video_title_clean = "".join(c if c in valid_chars else "_" for c in video_title)[:80]

    with tempfile.TemporaryDirectory() as tmp_dir:
        ext = "mp3" if formato == "audio" else "mp4"
        file_path = os.path.join(tmp_dir, f"{video_title_clean}.{ext}")

        target_channel = channel_id
        if channel_id == "dm":
            try:
                dm_channel = client.conversations_open(users=user_id)
                target_channel = dm_channel["channel"]["id"]
            except Exception as e:
                print(f"Error al abrir DM: {e}")
                return

        try:
            client.chat_postMessage(channel=target_channel, text=f"⏳ Procesando: *{video_title}*...")
        except Exception as e:
            print(f"Error enviando mensaje de inicio: {e}")

        estrategias = [
            {
                "nombre": "Estrategia 1: Alta calidad",
                "formato_video": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best",
                "formato_audio": "bestaudio[ext=m4a]/bestaudio/best",
            },
            {
                "nombre": "Estrategia 2: MP4 flexible",
                "formato_video": "best[ext=mp4]/best",
                "formato_audio": "bestaudio/best",
            },
            {
                "nombre": "Estrategia 3: Mejor disponible",
                "formato_video": "best",
                "formato_audio": "best",
            },
        ]

        descarga_exitosa = False
        ultimo_error = None

        for estrategia in estrategias:
            try:
                print(f"\n[DESCARGA] Intentando: {estrategia['nombre']}")
                ydl_opts = get_ydl_opts_base()

                if formato == "audio":
                    ydl_opts.update({
                        "format": estrategia["formato_audio"],
                        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
                        "outtmpl": os.path.join(tmp_dir, video_title_clean),
                    })
                else:
                    ydl_opts.update({
                        "format": estrategia["formato_video"],
                        "outtmpl": file_path,
                        "merge_output_format": "mp4",
                    })

                with YoutubeDL(ydl_opts) as ydl:
                    ydl.download([video_url])

                files = [os.path.join(tmp_dir, f) for f in os.listdir(tmp_dir)]
                if not files:
                    raise Exception("No se generó ningún archivo.")

                actual_file = files[0]
                file_size = os.path.getsize(actual_file)
                print(f"[DESCARGA] ✅ {file_size / 1024 / 1024:.2f} MB")

                try:
                    client.files_upload_v2(
                        channel=target_channel,
                        file=actual_file,
                        title=video_title,
                        initial_comment=f"✅ ¡Aquí tienes! *{video_title}*",
                    )
                    descarga_exitosa = True
                    break
                except Exception as e:
                    client.chat_postMessage(channel=target_channel, text=f"❌ Error al subir archivo: {str(e)[:100]}")
                    descarga_exitosa = True
                    break

            except Exception as e:
                ultimo_error = str(e)
                print(f"[DESCARGA] ❌ {estrategia['nombre']} falló: {ultimo_error[:150]}")
                continue

        if not descarga_exitosa:
            error_lower = (ultimo_error or "").lower()
            msg = "❌ No se pudo descargar el video."
            if "sign in" in error_lower or "bot" in error_lower:
                msg += "\n💡 Problema de autenticación. Las cookies pueden haber expirado."
            elif "age" in error_lower:
                msg += "\n💡 Este video requiere verificación de edad."
            elif "not available" in error_lower:
                msg += "\n💡 El video no está disponible en tu región."
            if ultimo_error:
                msg += f"\n```{ultimo_error[:150]}```"
            try:
                client.chat_postMessage(channel=target_channel, text=msg)
            except Exception as e:
                print(f"Error enviando mensaje de error final: {e}")


def descargar_playlist(playlist_url, playlist_title, channel_id, user_id, client, formato="video"):
    playlist_info = extract_playlist_info(playlist_url)
    if not playlist_info["success"]:
        client.chat_postMessage(channel=channel_id, text=f"❌ No se pudo acceder a la lista.\n{playlist_info['error']}")
        return

    videos = playlist_info["videos"]
    total = len(videos)
    if total == 0:
        client.chat_postMessage(channel=channel_id, text="❌ La lista no contiene videos.")
        return

    client.chat_postMessage(
        channel=channel_id,
        text=f"📥 Iniciando descarga de lista: *{playlist_title}*\nTotal: *{total}* videos 🕐",
    )

    for idx, video in enumerate(videos, 1):
        print(f"\n[PLAYLIST] {idx}/{total}: {video['title']}")
        try:
            client.chat_postMessage(channel=channel_id, text=f"⏳ ({idx}/{total}): *{video['title'][:60]}*...")
        except Exception:
            pass
        descargar_y_subir(video["url"], video["title"], channel_id, user_id, client, formato)


# --- HELPERS PARA MODALES ---
def _build_download_modal(callback_id, title_text, body_text, metadata):
    return {
        "type": "modal",
        "callback_id": callback_id,
        "private_metadata": metadata,
        "title": {"type": "plain_text", "text": title_text},
        "submit": {"type": "plain_text", "text": "Descargar"},
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": body_text}},
            {
                "type": "input",
                "block_id": "actions_1",
                "element": {
                    "type": "radio_buttons",
                    "action_id": "formato_selection",
                    "options": [
                        {"text": {"type": "plain_text", "text": "MP4 (video)"}, "value": "video"},
                        {"text": {"type": "plain_text", "text": "MP3 (solo audio)"}, "value": "audio"},
                    ],
                    "initial_option": {"text": {"type": "plain_text", "text": "MP4 (video)"}, "value": "video"},
                },
                "label": {"type": "plain_text", "text": "Formato"},
            },
            {
                "type": "input",
                "block_id": "actions_3",
                "element": {
                    "type": "radio_buttons",
                    "action_id": "destino_selection",
                    "options": [
                        {"text": {"type": "plain_text", "text": "Canal actual"}, "value": "channel"},
                        {"text": {"type": "plain_text", "text": "Mensaje directo (DM)"}, "value": "dm"},
                    ],
                    "initial_option": {"text": {"type": "plain_text", "text": "Canal actual"}, "value": "channel"},
                },
                "label": {"type": "plain_text", "text": "Destino"},
            },
        ],
    }


# --- MANEJADORES DE COMANDOS ---
@app.command("/buscar")
def handle_buscar(ack, command, say):
    ack()
    query = command["text"].strip()
    if not query:
        say("Uso: `/buscar [tema]`")
        return

    say(f"🔍 Buscando: `{query}`...")

    try:
        import requests
        import json
        from urllib.parse import quote

        search_url = f"https://www.youtube.com/results?search_query={quote(query)}&sp=EgIQAQ%253D%253D"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            "Accept-Language": "es-ES,es;q=0.9",
        }

        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()

        match = re.search(r"var ytInitialData = ({.*?});", response.text)
        if not match:
            say("❌ No se pudieron obtener resultados de YouTube.")
            return

        data = json.loads(match.group(1))
        contents = (
            data.get("contents", {})
            .get("twoColumnSearchResultsRenderer", {})
            .get("primaryContents", {})
            .get("sectionListRenderer", {})
            .get("contents", [])
        )

        videos = []
        for section in contents:
            for item in section.get("itemSectionRenderer", {}).get("contents", []):
                if "videoRenderer" in item:
                    v = item["videoRenderer"]
                    vid_id = v.get("videoId")
                    title = v.get("title", {}).get("runs", [{}])[0].get("text", "Sin título")
                    if vid_id and title:
                        videos.append({"id": vid_id, "title": title, "url": f"https://www.youtube.com/watch?v={vid_id}"})
                    if len(videos) >= 5:
                        break
            if len(videos) >= 5:
                break

        if not videos:
            say("❌ No se encontraron resultados.")
            return

        blocks = [{"type": "header", "text": {"type": "plain_text", "text": "🎥 Resultados"}}]
        for vid in videos:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{vid['title'][:60]}*"},
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Descargar"},
                    "value": f"{vid['url']}||{vid['title'][:100]}",
                    "action_id": "btn_opciones",
                },
            })

        say(blocks=blocks, text="Resultados de búsqueda")

    except Exception as e:
        print(f"[ERROR] Búsqueda falló: {str(e)[:150]}")
        say("❌ Error en búsqueda. Intenta con `/descargar [URL]` si tienes el link.")


@app.command("/descargar")
def handle_descargar_directo(ack, command, say, client):
    ack()
    url = command["text"].strip()

    if not url:
        say("Uso: `/descargar [URL o Video ID]`\nEjemplos:\n• `/descargar https://www.youtube.com/watch?v=dQw4w9WgXcQ`\n• `/descargar dQw4w9WgXcQ`")
        return

    # Completar URL si es solo un ID
    if not url.startswith("http"):
        if len(url) >= 10 and all(c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in url):
            url = f"https://www.youtube.com/watch?v={url}"
        else:
            say("❌ Por favor proporciona una URL de YouTube válida o un Video ID.")
            return

    if not ("youtube.com" in url or "youtu.be" in url):
        say("❌ Por favor proporciona una URL de YouTube válida.")
        return

    channel_id = command["channel_id"]
    user_id = command["user_id"]

    if is_playlist_url(url):
        say("📥 Analizando lista de reproducción...")
        playlist_info = extract_playlist_info(url)
        if not playlist_info["success"]:
            say("❌ No se pudo acceder a la lista de reproducción.")
            return
        metadata = f"{url}|{channel_id}|{user_id}|{playlist_info['title'][:100]}"
        body_text = f"📥 *{playlist_info['title'][:60]}*\n\n{playlist_info['count']} videos"
        client.views_open(
            trigger_id=command["trigger_id"],
            view=_build_download_modal("modal_playlist", "Descargar Playlist", body_text, metadata),
        )
    else:
        say("⏳ Obteniendo información del video...")
        info = extract_video_info(url)
        if not info["success"]:
            say("❌ No se pudo acceder al video. Verifica la URL e intenta de nuevo.")
            return
        metadata = f"{url}|{channel_id}|{user_id}|{info['title'][:100]}"
        client.views_open(
            trigger_id=command["trigger_id"],
            view=_build_download_modal("modal_descargar", "Descargar", f"*{info['title'][:60]}*", metadata),
        )


@app.action("btn_opciones")
def handle_opciones(ack, body, client):
    ack()
    val = body["actions"][0]["value"]
    url, title = (val.split("||", 1) + ["Video"])[:2]
    channel_id = body.get("channel", {}).get("id", "")
    user_id = body["user"]["id"]

    if is_playlist_url(url):
        playlist_info = extract_playlist_info(url)
        metadata = f"{url}|{channel_id}|{user_id}|{playlist_info['title']}"
        body_text = f"📥 *{playlist_info['title'][:60]}*\n\n{playlist_info['count']} videos"
        client.views_open(
            trigger_id=body["trigger_id"],
            view=_build_download_modal("modal_playlist", "Descargar Playlist", body_text, metadata),
        )
    else:
        metadata = f"{url}|{channel_id}|{user_id}|{title}"
        client.views_open(
            trigger_id=body["trigger_id"],
            view=_build_download_modal("modal_descargar", "Descargar", f"*{title[:60]}*", metadata),
        )


def _process_modal(view, body, client, logger, is_playlist=False):
    try:
        valores = view["state"]["values"]
        formato = valores["actions_1"]["formato_selection"]["selected_option"]["value"]
        destino = valores["actions_3"]["destino_selection"]["selected_option"]["value"]
        partes = view["private_metadata"].split("|", 3)
        url = partes[0]
        channel_id = partes[1]
        user_id = partes[2] if len(partes) > 2 else body["user"]["id"]
        title = partes[3] if len(partes) > 3 else ("Lista" if is_playlist else "Video")
        canal_final = "dm" if destino == "dm" else channel_id
        user_id_actual = body["user"]["id"]

        if is_playlist:
            threading.Thread(
                target=descargar_playlist,
                args=(url, title, canal_final, user_id_actual, client, formato),
                daemon=True,
            ).start()
        else:
            threading.Thread(
                target=descargar_y_subir,
                args=(url, title, canal_final, user_id_actual, client, formato),
                daemon=True,
            ).start()
    except Exception as e:
        logger.error(f"❌ Error procesando modal: {e}", exc_info=True)


@app.view("modal_descargar")
def handle_modal_submission(ack, body, client, view, logger):
    ack()
    threading.Thread(target=_process_modal, args=(view, body, client, logger, False), daemon=True).start()


@app.view("modal_playlist")
def handle_playlist_submission(ack, body, client, view, logger):
    ack()
    threading.Thread(target=_process_modal, args=(view, body, client, logger, True), daemon=True).start()




if __name__ == "__main__":
    import urllib.parse
    from http.server import HTTPServer, BaseHTTPRequestHandler

    UPLOAD_PASSWORD = os.environ.get("UPLOAD_PASSWORD", "")
    COOKIES_PATH_WRITABLE = "/opt/render/project/src/cookies_netscape.txt"

    class Handler(BaseHTTPRequestHandler):

        def do_GET(self):
            if self.path == "/":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"OK - Bot is running")

            elif self.path == "/upload":
                # Formulario HTML para subir cookies
                html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Subir Cookies</title>
    <style>
        body { font-family: sans-serif; max-width: 600px; margin: 60px auto; padding: 0 20px; }
        textarea { width: 100%; height: 300px; font-family: monospace; font-size: 12px; }
        input[type=password], input[type=submit] { margin-top: 10px; padding: 8px 16px; }
        input[type=submit] { background: #4CAF50; color: white; border: none; cursor: pointer; border-radius: 4px; }
    </style>
</head>
<body>
    <h2>🍪 Subir cookies_netscape.txt</h2>
    <form method="POST" action="/upload">
        <label>Contraseña:</label><br>
        <input type="password" name="password" required><br><br>
        <label>Contenido del archivo cookies_netscape.txt:</label><br>
        <textarea name="cookies" placeholder="# Netscape HTTP Cookie File&#10;..." required></textarea><br>
        <input type="submit" value="Subir cookies">
    </form>
</body>
</html>"""
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html.encode())

            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):
            if self.path == "/upload":
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8")
                params = urllib.parse.parse_qs(body)

                password = params.get("password", [""])[0]
                cookies_content = params.get("cookies", [""])[0]

                if not UPLOAD_PASSWORD:
                    self._respond(500, "❌ Variable UPLOAD_PASSWORD no configurada en Render.")
                    return

                if password != UPLOAD_PASSWORD:
                    self._respond(403, "❌ Contraseña incorrecta.")
                    return

                if not cookies_content.strip():
                    self._respond(400, "❌ El contenido está vacío.")
                    return

                try:
                    with open(COOKIES_PATH_WRITABLE, "w") as f:
                        f.write(cookies_content)

                    # Actualizar variable global
                    global COOKIES_VALID, COOKIES_PATH
                    COOKIES_VALID = True
                    COOKIES_PATH = COOKIES_PATH_WRITABLE

                    self._respond(200, "✅ Cookies guardadas correctamente. El bot las usará desde ahora.")
                    print("[COOKIES] ✅ Cookies actualizadas via /upload")
                except Exception as e:
                    self._respond(500, f"❌ Error guardando archivo: {e}")
            else:
                self.send_response(404)
                self.end_headers()

        def _respond(self, code, message):
            self.send_response(code)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(message.encode())

        def log_message(self, *args):
            pass

    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), Handler)

    print("\n" + "=" * 60)
    print("⚡ Slack YouTube Bot — Iniciando en Render")
    print("=" * 60)
    print(f"✅ Cookies: {'Sí' if COOKIES_VALID else 'No (descargas públicas solamente)'}")
    print(f"🌐 Servidor HTTP en puerto {port}")
    print(f"🍪 Subir cookies: /upload")
    print("🚀 Bot en Socket Mode...\n")

    threading.Thread(target=server.serve_forever, daemon=True).start()

    handler = SocketModeHandler(app, APP_TOKEN)
    handler.start()
