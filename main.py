import subprocess
import uuid
import os
from flask import Flask, Response, request, jsonify, render_template_string

app = Flask(__name__)
streams = {}

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Proxy Stream</title>
</head>
<body style="background:#000;color:#fff;text-align:center;font-family:sans-serif;">

<h2>🎬 STREAM PROXY</h2>

<input id="url" placeholder="Pega URL de YouTube" style="width:60%;padding:10px;">
<button onclick="go()">PLAY</button>

<p id="status">Esperando...</p>

<video id="v" controls autoplay style="width:90%;margin-top:20px;"></video>

<script>
function go(){
    const url = document.getElementById('url').value;
    const status = document.getElementById('status');
    const video = document.getElementById('v');

    if(!url) return;

    status.innerText = "Preparando...";

    fetch('/prepare',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({url})
    })
    .then(r=>r.json())
    .then(d=>{
        if(d.success){
            status.innerText = "Streaming...";
            video.src = '/stream/' + d.id;
        } else {
            status.innerText = "Error: " + d.error;
        }
    });
}
</script>

</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/prepare', methods=['POST'])
def prepare():
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({"success": False, "error": "URL inválida"})

    stream_id = str(uuid.uuid4())

    # 🔥 comando robusto
    cmd = [
    'yt-dlp',
    '-f', 'bv*+ba/b',
    '-g',
    '--no-check-certificates',
    '--geo-bypass',
    '--add-header', 'User-Agent:Mozilla/5.0',
    '--js-runtimes', 'node',
    url
]

    p = subprocess.run(cmd, capture_output=True, text=True)

    if p.returncode == 0:
        streams[stream_id] = p.stdout.strip().split('\n')[0]
        return jsonify({"success": True, "id": stream_id})

    # 🔥 ahora verás el error real
    return jsonify({
        "success": False,
        "error": p.stderr[:300]
    })


@app.route('/stream/<stream_id>')
def stream(stream_id):
    y_url = streams.get(stream_id)

    if not y_url:
        return "Stream no encontrado", 404

    ffmpeg_cmd = [
        'ffmpeg',
        '-re',
        '-i', y_url,

        '-c:v', 'libx264',
        '-preset', 'veryfast',
        '-tune', 'zerolatency',
        '-crf', '23',

        # 🔥 control de ancho de banda
        '-b:v', '1500k',
        '-maxrate', '1800k',
        '-bufsize', '3000k',

        '-vf', 'scale=1280:-2',

        '-c:a', 'aac',
        '-b:a', '128k',

        '-pix_fmt', 'yuv420p',
        '-movflags', 'frag_keyframe+empty_moov+default_base_moof',

        '-f', 'mp4',
        '-loglevel', 'quiet',
        'pipe:1'
    ]

    def generate():
        proc = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=10**6
        )
        try:
            while True:
                chunk = proc.stdout.read(128 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            proc.terminate()
            proc.wait()

    return Response(
        generate(),
        mimetype='video/mp4',
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, threaded=True)
