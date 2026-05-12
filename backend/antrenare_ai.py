import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib

print("Citesc manualul de istorie...")
# 1. Citim datele cu răspunsurile corecte
df = pd.read_csv('date_sera_etichetate.csv')

# --- ATENȚIE AICI ---
# Trece exact numele coloanelor tale pentru temperatură și umiditatea solului
# Dacă în fișierul csv se numesc altfel (ex: 'temp', 'soil'), modifică-le mai jos!
coloane_intrare = ['temperatura', 'umiditate_sol'] 
X = df[coloane_intrare]

# Acesta este rezultatul pe care trebuie să-l învețe (să pornească pompa)
y = df['porneste_pompa']

# 2. Creăm modelul de Inteligență Artificială
model_ai = RandomForestClassifier(n_estimators=100, random_state=42)

# 3. ANTRENAMENTUL! (Aici se întâmplă magia)
print("Antrenez modelul AI... te rog așteaptă o secundă...")
model_ai.fit(X, y)

# 4. Testăm rapid să vedem dacă a învățat bine
acuratete = model_ai.score(X, y) * 100
print(f"Antrenament finalizat! Acuratețea modelului pe datele învățate este: {acuratete}%")

# 5. Salvăm "creierul" pe disc ca să-l putem folosi în aplicația ta web
joblib.dump(model_ai, 'creier_sera.joblib')
print("Creierul a fost salvat fizic în fișierul 'creier_sera.joblib' 🧠✅")