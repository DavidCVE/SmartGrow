import pandas as pd

# 1. Citim manualul de istorie pe care tocmai l-ai descărcat
df = pd.read_csv('date_sera.csv')

# (Opțional) Afișăm cum se numesc coloanele tale exact, ca să fim siguri
print("Coloanele tale sunt:", df.columns.tolist())

# 2. Creăm regula de bun simț (răspunsul corect)
def trebuie_udat(rand):
    # AICI pui numele exact al coloanei tale pentru umiditatea solului!
    # De obicei este 'soil_moisture' sau 'umiditate_sol'. 
    # Modifică dacă e nevoie.
    
    umiditate = float(rand['umiditate_sol']) # <-- Verifică acest nume!
    
    # Dacă umiditatea solului scade sub 30%, planta are nevoie de apă (1)
    if umiditate < 30.0:
        return 1
    else:
        return 0

# 3. Adăugăm o coloană nouă numită 'porneste_pompa' cu răspunsurile noastre
df['porneste_pompa'] = df.apply(trebuie_udat, axis=1)

# 4. Salvăm noul manual complet
df.to_csv('date_sera_etichetate.csv', index=False)
print("Succes! Am adăugat coloana cu decizii și am salvat fișierul 'date_sera_etichetate.csv'.")