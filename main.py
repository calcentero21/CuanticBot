from flask import Flask, render_template_string, request, redirect, url_for
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)

# Configuración de zona horaria (Santo Domingo)
tz = pytz.timezone('America/Santo_Domingo')

# Estado inicial: 23 del mes pasado a las 9:00 AM
# Nota: Ajustamos dinámicamente al mes anterior según la fecha actual
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
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            display: flex; flex-direction: column; align-items: center; 
            justify-content: center; height: 100vh; margin: 0;
            background-color: {{ 'body-green' if paid else '#1a1a1a' }};
            transition: background-color 0.5s; color: white; text-align: center;
        }
        .container { padding: 20px; }
        h1 { font-size: 2.5rem; margin-bottom: 10px; }
        #counter { font-size: 3.5rem; font-weight: bold; color: #ffcc00; }
        .status-paid { background-color: #2ecc71 !important; }
        .big-text { font-size: 1.5rem; margin-top: 20px; text-transform: uppercase; opacity: 0.8; }
    </style>
</head>
<body class="{{ 'status-paid' if paid else '' }}">
    <div class="container">
        <h1>PAGINA QUE TE AVISA SI YA PAGARON DEL BHD</h1>
        
        {% if paid %}
            <div id="counter">¡YA PAGARON!</div>
            <div class="big-text">El contador se reiniciará mañana automáticamente.</div>
        {% else %}
            <div id="counter">Cargando...</div>
            <div class="big-text" id="description">Han pasado tiempo desde la última vez</div>
        {% endif %}
    </div>

    <script>
        function updateCounter() {
            const lastDate = new Date("{{ last_date_iso }}");
            const now = new Date();
            const diff = now - lastDate;

            const hours = Math.floor(diff / (1000 * 60 * 60));
            const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((diff % (1000 * 60)) / 1000);

            const timeStr = `${hours}h ${minutes}m ${seconds}s`;
            
            const counterEl = document.getElementById('counter');
            if (counterEl && !{{ paid|tojson }}) {
                counterEl.innerText = timeStr;
                document.getElementById('description').innerText = `HAN PASADO ${timeStr} DESDE LA ULTIMA VEZ QUE PAGARON`;
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
    
    # Resetear el estado si ya es un día diferente al del pago
    now = datetime.now(tz)
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
    return "Pago registrado. <a href='/'>Volver</a>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
