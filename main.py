from flask import Flask, render_template_string
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)

# Zona horaria
tz = pytz.timezone('America/Santo_Domingo')

# Fecha inicial (23 del mes pasado a las 9:00 AM)
now = datetime.now(tz)
last_month = now.replace(day=1) - timedelta(days=1)
last_payment_date = tz.localize(datetime(last_month.year, last_month.month, 23, 9, 0, 0))

is_paid_today = False

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>¿Ya pagaron?</title>

<style>
    body {
        margin: 0;
        height: 100vh;
        font-family: 'Segoe UI', sans-serif;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        text-align: center;
        background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
        transition: all 0.5s ease;
    }

    body.paid {
        background: linear-gradient(135deg, #11998e, #38ef7d);
    }

    .card {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(10px);
        padding: 40px;
        border-radius: 20px;
        box-shadow: 0 0 40px rgba(0,0,0,0.5);
        max-width: 500px;
        width: 90%;
        animation: fadeIn 1s ease;
    }

    h1 {
        font-size: 2rem;
        margin-bottom: 10px;
        letter-spacing: 1px;
    }

    #counter {
        font-size: 3rem;
        font-weight: bold;
        margin: 20px 0;
        color: #ffd166;
    }

    .desc {
        font-size: 1.1rem;
        opacity: 0.8;
        letter-spacing: 1px;
    }

    .paid-text {
        font-size: 2.5rem;
        font-weight: bold;
        color: white;
        animation: pulse 1.5s infinite;
    }

    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }

    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.08); }
        100% { transform: scale(1); }
    }
</style>

</head>

<body class="{{ 'paid' if paid else '' }}">

<div class="card">
    <h1>💸 ESTADO 💸</h1>

    {% if paid %}
        <div class="paid-text">✔ YA PAGARON</div>
        <div class="desc">El contador se reiniciará automáticamente mañana.</div>
    {% else %}
        <div id="counter">Cargando...</div>
        <div class="desc" id="description">Calculando tiempo desde el último pago...</div>
    {% endif %}
</div>

<script>
function updateCounter() {
    const lastDate = new Date("{{ last_date_iso }}");
    const now = new Date();
    const diff = now - lastDate;

    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    const hours = Math.floor((diff / (1000 * 60 * 60)) % 24);
    const minutes = Math.floor((diff / (1000 * 60)) % 60);
    const seconds = Math.floor((diff / 1000) % 60);

    const timeStr = `${days}d ${hours}h ${minutes}m ${seconds}s`;

    const counterEl = document.getElementById("counter");

    if (counterEl && !{{ paid|tojson }}) {
        counterEl.innerText = timeStr;
        document.getElementById("description").innerText =
            `Han pasado ${timeStr} desde el último pago`;
    }
}

if (!{{ paid|tojson }}) {
    setInterval(updateCounter, 1000);
    updateCounter();
}
</script>

</body>
</html>
"""

@app.route('/')
def index():
    global is_paid_today, last_payment_date

    now = datetime.now(tz)

    # Reset automático al día siguiente
    if is_paid_today and now.date() > last_payment_date.date():
        is_paid_today = False

    return render_template_string(
        HTML_TEMPLATE,
        paid=is_paid_today,
        last_date_iso=last_payment_date.isoformat()
    )

@app.route('/set')
def set_payment():
    global is_paid_today, last_payment_date
    is_paid_today = True
    last_payment_date = datetime.now(tz)
    return "💸 SI YA PAGARON. 💸<a href='/'>Volver</a>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
