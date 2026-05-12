#include <WiFi.h>
#include <FirebaseESP32.h>
#include "DHT.h"
#include "secrets.h"

// --- CREDENȚIALE ---
#define WIFI_SSID SECRET_WIFI_SSID
#define WIFI_PASSWORD SECRET_WIFI_PASSWORD
#define API_KEY SECRET_API_KEY
#define DATABASE_URL "proiectlicenta-da795-default-rtdb.europe-west1.firebasedatabase.app"
#define USER_EMAIL SECRET_USER_EMAIL
#define USER_PASSWORD SECRET_USER_PASSWORD

// --- PINI ---
#define DHTPIN 4
#define DHTTYPE DHT22
const int soilPin = 34;
const int pumpPin = 5;

// --- CALIBRARE & PRAGURI ---
const int AirValue = 2600;
const int WaterValue = 1500;

// --- PRAGURI DINAMICE (Se vor actualiza din Firebase) ---
int prag_umiditate_sol = 20;    // Valoare default (minim)
float prag_temp_max = 30.0;     // Valoare default (maxim)
int durata_pompa_sec = 5;       // Valoare default

// --- OBIECTE FIREBASE & SENZORI ---
FirebaseData firebaseData;
FirebaseAuth auth;
FirebaseConfig config;
DHT dht(DHTPIN, DHTTYPE);

// --- DEFINIRE FUNCȚIE CALLBACK ---
void tokenStatusCallback(TokenInfo info);

// --- VARIABILE MEDIE ISTORIC ---
float sumaTemp = 0;
float sumaUmiditate = 0;
long sumaSol = 0;
int contorCitiri = 0;
unsigned long lastHistoryTime = 0;
const long historyInterval = 60000; // 1 minut

// --- VARIABILE ANTI-FLOOD ALERTE ---
unsigned long lastAlertTime = 0;
const long alertCooldown = 300000; // 5 minute pauză între alerte repetate
bool stareAnterioaraPompa = false; // Memorează starea pompei pentru alertele INFO

// ==========================================
// FUNCȚIE NOUĂ: CITIRE SETĂRI DIN SITE
// ==========================================
unsigned long ultimaCitireSetari = 0;
const long intervalSetari = 10000; // Citeste din Firebase doar o data la 10 secunde

void actualizareSetariDinFirebase() {
  // Evităm să facem spam cu cereri ca să nu blocăm conexiunea catre Firebase
  if (millis() - ultimaCitireSetari >= intervalSetari || ultimaCitireSetari == 0) {
    bool succes = false;
    
    if (Firebase.getInt(firebaseData, "/setari/min_soil_moisture")) {
      prag_umiditate_sol = firebaseData.intData();
      succes = true;
    } else {
      Serial.println("⚠️ Eroare citire sol: " + firebaseData.errorReason());
    }
    
    if (Firebase.getFloat(firebaseData, "/setari/max_temp")) {
      prag_temp_max = firebaseData.floatData();
    }
  
    if (Firebase.getInt(firebaseData, "/setari/pump_duration")) {
      durata_pompa_sec = firebaseData.intData();
    }

    if (succes) {
      Serial.println("✅ Setari reactualizate cu succes din Firebase!");
      Serial.printf("Praguri curente: Udare la sub %d%% | Alerta la peste %.1f°C | Durata pompa: %d sec\n", prag_umiditate_sol, prag_temp_max, durata_pompa_sec);
    }
    
    ultimaCitireSetari = millis();
  }
}

void setup() {
  Serial.begin(115200);
  
  // Conectare WiFi
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Conectare la Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) { 
    delay(300); 
    Serial.print("."); 
  }
  Serial.println("\n✅ Conectat la WiFi!");
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());

  // Configurare Firebase
  config.api_key = API_KEY;
  config.database_url = DATABASE_URL;
  auth.user.email = USER_EMAIL;
  auth.user.password = USER_PASSWORD;
  config.token_status_callback = tokenStatusCallback;
  
  Firebase.begin(&config, &auth);
  Firebase.reconnectWiFi(true);

  // Inițializare Senzori
  dht.begin();
  pinMode(pumpPin, OUTPUT);
}

void loop() {
  if (Firebase.ready()) {
    
    // 0. ACTUALIZARE SETĂRI DIN SITE
    actualizareSetariDinFirebase();
    
    // 1. CITIREA DATELOR
    float t = dht.readTemperature();
    float h = dht.readHumidity();
    int soilRaw = analogRead(soilPin);
    
    // Mapare umiditate sol
    int soilPercent = map(soilRaw, AirValue, WaterValue, 0, 100);
    if (soilPercent < 0) soilPercent = 0;
    if (soilPercent > 100) soilPercent = 100;

    // --- CONTROL POMPĂ (Creier AI + Mod Manual) ---
    bool pompaPornita = false;
    bool comandaManuala = false;
    bool decizieAI = false;

    if (Firebase.getBool(firebaseData, "/planta_mea/comenzi/pompa_manuala")) {
        comandaManuala = firebaseData.boolData();
    }
    if (Firebase.getBool(firebaseData, "/planta_mea/comenzi/pompa_ai")) {
        decizieAI = firebaseData.boolData();
    }

    if (comandaManuala == true) {
        pompaPornita = true; 
    } else {
        pompaPornita = decizieAI;
    }

    digitalWrite(pumpPin, pompaPornita ? HIGH : LOW);

    // 2. ACTUALIZARE LIVE
    FirebaseJson jsonLive;
    jsonLive.set("umiditate_sol", soilPercent);
    jsonLive.set("temperatura", t);
    jsonLive.set("umiditate_aer", h);
    jsonLive.set("pompa_pornita", pompaPornita);
    Firebase.setJSON(firebaseData, "/planta_mea/curent", jsonLive);

    // 3. ADĂUGARE LA MEDIE
    if (!isnan(t) && !isnan(h)) {
        sumaTemp += t;
        sumaUmiditate += h;
        sumaSol += soilPercent;
        contorCitiri++;
    }

    // 4. VERIFICARE ALERTE (Modificat să folosească pragurile dinamice + Alerte Independente)
    if (millis() - lastAlertTime > alertCooldown || lastAlertTime == 0) {
        bool alertaTrimisa = false;

        // A. VERIFICAM UMIDITATEA SOLULUI
        String nivelSol = "";
        String mesajSol = "";
        if (soilPercent < (prag_umiditate_sol / 2)) { 
            nivelSol = "Critical";
            mesajSol = "Sol critic uscat";
        } else if (soilPercent <= prag_umiditate_sol) {
            nivelSol = "Warning";
            mesajSol = "Solul se usuca";
        }
        
        if (nivelSol != "") {
            FirebaseJson jsonAlertSol;
            jsonAlertSol.set("tip", mesajSol);
            jsonAlertSol.set("valoare", soilPercent);
            jsonAlertSol.set("nivel", nivelSol); 
            Firebase.pushJSON(firebaseData, "/planta_mea/alerte", jsonAlertSol);
            Serial.println("!!! ALERTĂ SOL: " + nivelSol + " -> Salvat!");
            alertaTrimisa = true;
            delay(500);
        }

        // B. VERIFICAM TEMPERATURA
        String nivelTemp = "";
        String mesajTemp = "";
        if (t > (prag_temp_max + 5.0)) { 
            nivelTemp = "Critical";
            mesajTemp = "Temperatura critic de mare";
        } else if (t >= prag_temp_max) {
            nivelTemp = "Warning";
            mesajTemp = "Temperatura ridicata";
        }

        if (nivelTemp != "") {
            FirebaseJson jsonAlertTemp;
            jsonAlertTemp.set("tip", mesajTemp);
            jsonAlertTemp.set("valoare", t);
            jsonAlertTemp.set("nivel", nivelTemp); 
            Firebase.pushJSON(firebaseData, "/planta_mea/alerte", jsonAlertTemp);
            Serial.println("!!! ALERTĂ TEMP: " + nivelTemp + " -> Salvat!");
            alertaTrimisa = true;
            delay(500);
        }

        // Daca am trimis cel putin o alerta, resetam cooldown-ul
        if (alertaTrimisa) {
            lastAlertTime = millis();
        }
    }

    // 5. JURNAL INFO (Declanșat doar când se schimbă starea pompei)
    if (pompaPornita != stareAnterioaraPompa) {
        FirebaseJson jsonInfo;
        String mesajInfo = pompaPornita ? "Pompa a fost pornita." : "Pompa a fost oprita.";
        
        jsonInfo.set("tip", mesajInfo);
        jsonInfo.set("valoare", pompaPornita ? 1 : 0);
        jsonInfo.set("nivel", "Info"); 
        
        Serial.print("ℹ️ INFO: " + mesajInfo);
        
        if (Firebase.pushJSON(firebaseData, "/planta_mea/alerte", jsonInfo)) {
            Serial.println(" -> ✅ Salvat cu succes in Firebase!");
        } else {
            Serial.println(" -> ❌ EROARE Firebase: " + firebaseData.errorReason());
        }
        
        stareAnterioaraPompa = pompaPornita; 
        delay(500); // Pauză de respirație pentru ESP32
    }

    // 6. SALVARE ISTORIC
    if (millis() - lastHistoryTime >= historyInterval) {
       if (contorCitiri > 0) {
           FirebaseJson jsonIstoric;
           jsonIstoric.set("temperatura", sumaTemp / contorCitiri);
           jsonIstoric.set("umiditate_aer", sumaUmiditate / contorCitiri);
           jsonIstoric.set("umiditate_sol", (int)(sumaSol / contorCitiri));
           
           Serial.print("Salvare Medie Istoric... ");
           Firebase.pushJSON(firebaseData, "/planta_mea/istoric", jsonIstoric);
       }
       sumaTemp = 0; 
       sumaUmiditate = 0; 
       sumaSol = 0; 
       contorCitiri = 0;
       lastHistoryTime = millis();
    }
  } 
  
  delay(3000);
}

void tokenStatusCallback(TokenInfo info){
    if (info.status == token_status_error){
        Serial.printf("Token Error: %s\n", info.error.message.c_str());
    }
}