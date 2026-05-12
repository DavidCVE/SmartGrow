import requests
import pandas as pd

# Ne conectăm la 'dispecerul' tău (asigură-te că app.py rulează în alt terminal)
url = 'http://127.0.0.1:5000/api/history'

print("Descarc datele din baza de date...")
response = requests.get(url)

if response.status_code == 200:
    date_istoric = response.json()
    
    # Transformăm datele într-un tabel frumos cu Pandas
    df = pd.DataFrame(date_istoric)
    
    # Salvăm tabelul pe calculator
    df.to_csv('date_sera.csv', index=False)
    print("Succes! Am salvat datele în fișierul 'date_sera.csv'.")
else:
    print("Eroare! Nu am putut lua datele. Serverul Flask (app.py) este pornit?")