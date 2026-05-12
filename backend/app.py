from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime, timedelta
import joblib  # <-- BIBLIOTECA AI ADĂUGATĂ
import google.generativeai as genai

app = Flask(__name__)
CORS(app)

cred = credentials.Certificate('firebase_key.json')
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://proiectlicenta-da795-default-rtdb.europe-west1.firebasedatabase.app'
})

# ==========================================
# --- CREIERUL INTELIGENȚEI ARTIFICIALE ---
# ==========================================

# 1. Încărcăm modelul la pornirea serverului
try:
    ai_model = joblib.load('creier_sera.joblib')
    print("🧠 Creierul AI a fost încărcat cu succes!")
except Exception as e:
    print(f"⚠️ Eroare la încărcarea modelului AI: {e}")
    ai_model = None

# 2. Funcția care gândește și ia decizii singură
def analizare_ai_automata(event):
    """Această funcție este declanșată automat de Firebase de fiecare dată când ESP32 trimite o valoare nouă."""
    if ai_model and event.data and isinstance(event.data, dict):
        
        # Extragem valorile (ASIGURĂ-TE CĂ NUMELE SUNT EXACT CELE TRIMISE DE ESP32)
        temp = event.data.get('temperatura') 
        soil = event.data.get('umiditate_sol')  # Modificat numele câmpului
        
        if temp is not None and soil is not None:
            # AI-ul analizează datele ([0] extrage valoarea din array-ul prezis)
            decizie_pompa = int(ai_model.predict([[temp, soil]])[0])
            
            # Salvăm decizia înapoi în Firebase sub nodul 'comenzi'
            db.reference('/planta_mea/comenzi').update({
                'pompa_ai': decizie_pompa
            })
            
            status_text = "PORNIRE" if decizie_pompa == 1 else "OPRIRE"
            motiv_text = "Nivel critic de umiditate" if float(soil) < 30 else "Nivel optim de apă"
            
            # Adăugăm intrarea în jurnalul de decizii AI
            current_time_str = datetime.now().strftime('%H:%M:%S')
            
            log_entry = {
                'timestamp': current_time_str,
                'temp': temp,
                'soil': soil,
                'decizie': status_text,
                'motiv': motiv_text
            }
            
            # Folosim push() pentru a genera un ID unic pentru fiecare jurnal
            db.reference('/planta_mea/ai_logs').push(log_entry)
            
            print(f"🤖 AI a decis: Temp {temp}°C, Umiditate {soil}% -> Comandă pompă: {status_text}")

# 3. Punem sistemul să "asculte" non-stop schimbările din nodul 'curent'
try:
    db.reference('/planta_mea/curent').listen(analizare_ai_automata)
    print("👀 Sistemul Flask ascultă după date noi de la ESP32...")
except Exception as e:
    print(f"⚠️ Eroare la pornirea ascultătorului Firebase: {e}")

# ==========================================
# --- RUTE PENTRU PAGINI WEB (FRONTEND) ---
# ==========================================

@app.route('/')
def login_page():
    # Când cineva intră pe site-ul principal, îi dăm pagina de Login
    return render_template('login.html')

@app.route('/dashboard')
def dashboard_page():
    # Aici vom pune mai târziu verificarea de securitate
    return render_template('dashboard.html')

@app.route('/api/current-status', methods=['GET'])
def get_current_status():
    try:
        # Fetch the latest data
        ref_curent = db.reference('/planta_mea/curent')
        data_live = ref_curent.get() or {}

        # Fetch the last 50 records for statistics
        ref_istoric = db.reference('/planta_mea/istoric')
        istoric_data = ref_istoric.order_by_key().limit_to_last(50).get() or {}

        # Calculate statistics
        # Extract float value safely
        live_temp_str = data_live.get('temperatura', 0)
        try:
            avg_temp = float(live_temp_str)
        except (ValueError, TypeError):
            avg_temp = 0.0
            
        watering_count = 0
        
        if istoric_data:
            toate_temp = []
            
            # handle both dict and list structures from Firebase
            items_to_process = []
            if isinstance(istoric_data, dict):
                items_to_process = list(istoric_data.values())
            elif isinstance(istoric_data, list):
                items_to_process = [e for e in istoric_data if e is not None]
                
            for val in items_to_process:
                if not isinstance(val, dict):
                    continue
                    
                temp = val.get('temperatura')
                if temp is not None:
                    try:
                        toate_temp.append(float(temp))
                    except (ValueError, TypeError):
                        pass
                
                # Check for various true states
                pump_status = val.get('pompa_pornita')
                if pump_status is True or pump_status == 'ON' or pump_status == 1 or pump_status == '1':
                    watering_count += 1
            
            if toate_temp:
                avg_temp = sum(toate_temp) / len(toate_temp)

        # Return JSON response
        return jsonify({
            'temperatura': data_live.get('temperatura', 0),
            'umiditate_aer': data_live.get('umiditate_aer', 0),
            'umiditate_sol': data_live.get('umiditate_sol', 0),
            'pompa_pornita': data_live.get('pompa_pornita', False),
            'today_watering': watering_count,
            'avg_temp': round(float(avg_temp), 1),
            'uptime': '99.9%'
        })
    except Exception as e:
        print(f"Eroare stats: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/history', methods=['GET'])
def get_history():
    try:
        ref = db.reference('/planta_mea/istoric')
        data = ref.get()

        if data is None:
            return jsonify([])

        # Extract values from the dictionary and sort by timestamp if available
        if isinstance(data, dict):
            entries = list(data.values())
            # Sort by timestamp if entries have a 'timestamp' field
            if entries and isinstance(entries[0], dict) and 'timestamp' in entries[0]:
                entries.sort(key=lambda x: x.get('timestamp', 0))
            # Get the last 30 entries
            result = entries[-30:]
        elif isinstance(data, list):
            result = [e for e in data if e is not None][-30:]
        else:
            return jsonify([])

        # Mock timestamps for missing ones (calculate backwards from current time)
        now = datetime.now()
        # Round 'now' down to the nearest half hour for cleaner chart labels
        discard_minutes = now.minute % 30
        rounded_now = now - timedelta(minutes=discard_minutes, seconds=now.second, microseconds=now.microsecond)
        
        for i, entry in enumerate(reversed(result)):
            if isinstance(entry, dict) and 'timestamp' not in entry and 'time' not in entry:
                # Progressively subtract 30 minutes for older data points
                mock_time = rounded_now - timedelta(minutes=i * 30)
                entry['timestamp'] = mock_time.isoformat()

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/history')
def history_page():
    return render_template('history.html')

@app.route('/analytics')
def analytics_page():
    return render_template('analytics.html')

@app.route('/settings')
def settings_page():
    return render_template('settings.html')

@app.route('/alerts')
def alerts_page():
    return render_template('alerts.html')

@app.route('/about')
def about_page():
    return render_template('about.html')

@app.route('/api/toggle-pump', methods=['POST', 'OPTIONS'])
def toggle_pump():
    # Handle CORS preflight request
    if request.method == 'OPTIONS':
        return '', 204

    try:
        data = request.get_json()

        if data is None or 'state' not in data:
            return jsonify({'error': 'Missing "state" in request body'}), 400

        state = data['state']

        if not isinstance(state, bool):
            return jsonify({'error': '"state" must be a boolean'}), 400

        # Update Firebase
        ref = db.reference('/planta_mea/comenzi')
        ref.update({'pompa_manuala': state})

        return jsonify({
            'success': True,
            'message': f'Pump set to {"ON" if state else "OFF"}',
            'state': state
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

import google.generativeai as genai # <-- ADAUGĂ ASTA SUS DE TOT LÂNGĂ CELELALTE IMPORTURI

# --- CONFIGURARE GEMINI ---
# Pune cheia ta generată la pasul 1 între ghilimele
genai.configure(api_key="AIzaSyBhtUZtqw2SB15VwTo2jnh3SNjtqmMN_tQ") 

@app.route('/api/chat', methods=['POST', 'OPTIONS'])
def chat_bot():
    if request.method == 'OPTIONS':
        return '', 204

    try:
        data = request.get_json()
        user_message = data.get('message', '')

        # 1. Extragem datele reale din baza de date
        ref_curent = db.reference('/planta_mea/curent').get()
        if not ref_curent:
            ref_curent = {"temperatura": "Necunoscut", "umiditate_sol": "Necunoscut", "pompa_pornita": False}

        # 2. Construim contextul (Ce îi spunem AI-ului înainte să răspundă)
        instructiuni_sistem = f"""Ești un asistent AI expert în agronomie, integrat într-o seră inteligentă.
        Datele curente ale serei în acest moment sunt:
        - Temperatura: {ref_curent.get('temperatura')}°C
        - Umiditate Sol: {ref_curent.get('umiditate_sol')}%
        - Status Pompă: {'PORNITĂ' if ref_curent.get('pompa_pornita') else 'OPRITĂ'}
        
        Răspunde scurt, prietenos și în limba română la întrebarea utilizatorului, folosind aceste date.
        Nu folosi formatare complicată. Fii concis."""

# 3. Folosim modelul rapid și stabil din generația nouă
        model = genai.GenerativeModel('models/gemini-2.5-flash')
        
        # Combinăm invizibil instrucțiunile serei cu mesajul tău
        prompt_complet = instructiuni_sistem + "\n\nÎntrebare utilizator: " + user_message
        
        # 4. Generăm răspunsul
        response = model.generate_content(prompt_complet)

        return jsonify({'success': True, 'reply': response.text})

    except Exception as e:
        print("❌ EROARE ÎN PYTHON:", str(e))  # <-- Adaugă linia asta aici!
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)