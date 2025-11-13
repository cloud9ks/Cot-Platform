# 🚀 Deploy COT Platform su Windows Server 2022 con Docker

Guida completa per hostare la piattaforma COT sul tuo server privato Windows Server 2022.

## 📋 Prerequisiti

### 1. Installa Docker Desktop per Windows Server

1. Scarica Docker Desktop:
   ```
   https://docs.docker.com/desktop/install/windows-install/
   ```

2. Oppure installa Docker Engine direttamente:
   ```powershell
   # Apri PowerShell come Amministratore
   Install-Module -Name DockerMsftProvider -Repository PSGallery -Force
   Install-Package -Name docker -ProviderName DockerMsftProvider
   Restart-Computer -Force
   ```

3. Verifica installazione:
   ```powershell
   docker --version
   docker-compose --version
   ```

### 2. Installa Git (se non presente)

```powershell
# Scarica da: https://git-scm.com/download/win
# Oppure con winget:
winget install --id Git.Git -e --source winget
```

## 🔧 Setup Iniziale

### 1. Clona il Repository

```powershell
cd C:\
git clone https://github.com/tuo-username/cot-platform.git
cd cot-platform
```

### 2. Configura Variabili d'Ambiente

```powershell
# Copia il file example
copy .env.docker.example .env

# Modifica con i tuoi valori
notepad .env
```

**Valori OBBLIGATORI da modificare:**
- `DB_PASSWORD`: Password PostgreSQL (cambiarla!)
- `SECRET_KEY`: Chiave segreta Flask (genera con: `python -c "import secrets; print(secrets.token_hex(32))"`)
- `OPENAI_API_KEY`: La tua chiave OpenAI

**Valori OPZIONALI:**
- `STRIPE_*`: Solo se usi pagamenti
- `TWELVE_DATA_API_KEY`: Solo se hai account TwelveData

### 3. Crea Directory Necessarie

```powershell
mkdir data
mkdir logs
mkdir logs\nginx
mkdir nginx\ssl
```

## 🚀 Avvio Applicazione

### Build e Start

```powershell
# Build delle immagini Docker
docker-compose build

# Avvia tutti i servizi
docker-compose up -d

# Verifica che tutto sia partito
docker-compose ps
```

Dovresti vedere:
```
NAME                IMAGE               STATUS              PORTS
cot-postgres        postgres:15-alpine  Up (healthy)        0.0.0.0:5432->5432/tcp
cot-app             cot-platform_app    Up (healthy)        0.0.0.0:10000->10000/tcp
cot-nginx           nginx:alpine        Up                  0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
```

### Verifica Funzionamento

1. **Apri browser** e vai a:
   ```
   http://localhost
   ```

2. **Verifica logs**:
   ```powershell
   # Logs Flask app
   docker-compose logs -f app

   # Logs PostgreSQL
   docker-compose logs -f db

   # Logs Nginx
   docker-compose logs -f nginx
   ```

## 🗄️ Inizializzazione Database

```powershell
# Accedi al container Flask
docker exec -it cot-app bash

# Dentro il container, crea le tabelle
python
>>> from app_complete import db
>>> db.create_all()
>>> exit()

# Esci dal container
exit
```

## 🌐 Accesso da Rete Esterna

### Opzione A: Accesso tramite IP Pubblico

Se hai IP pubblico statico:

1. **Configura Windows Firewall**:
   ```powershell
   # Apri porta 80 (HTTP)
   New-NetFirewallRule -DisplayName "COT Platform HTTP" -Direction Inbound -LocalPort 80 -Protocol TCP -Action Allow

   # Apri porta 443 (HTTPS) - opzionale
   New-NetFirewallRule -DisplayName "COT Platform HTTPS" -Direction Inbound -LocalPort 443 -Protocol TCP -Action Allow
   ```

2. **Configura Router** (Port Forwarding):
   - Porta esterna 80 → IP server:80
   - Porta esterna 443 → IP server:443

3. Accedi da: `http://tuo-ip-pubblico`

### Opzione B: Usa un Dominio con HTTPS

1. **Acquista un dominio** (es. GoDaddy, Namecheap)

2. **Punta il dominio al tuo IP pubblico**:
   - Tipo A record: `@` → `tuo.ip.pubblico`
   - Tipo A record: `www` → `tuo.ip.pubblico`

3. **Installa certificato SSL** (Let's Encrypt):
   ```powershell
   # Usa certbot o win-acme per Windows
   # https://github.com/win-acme/win-acme

   # Oppure copia certificati manualmente in:
   C:\cot-platform\nginx\ssl\cert.pem
   C:\cot-platform\nginx\ssl\key.pem
   ```

4. **Decommenta sezione HTTPS** in `nginx/nginx.conf` (righe 72-100)

5. **Riavvia Nginx**:
   ```powershell
   docker-compose restart nginx
   ```

## 🛠️ Comandi Utili

```powershell
# Avvia servizi
docker-compose up -d

# Stop servizi
docker-compose down

# Riavvia singolo servizio
docker-compose restart app

# Visualizza logs in tempo reale
docker-compose logs -f app

# Ricostruisci dopo modifiche codice
docker-compose up -d --build

# Backup database
docker exec cot-postgres pg_dump -U cotuser cot_platform > backup_$(Get-Date -Format "yyyyMMdd_HHmmss").sql

# Restore database
cat backup.sql | docker exec -i cot-postgres psql -U cotuser -d cot_platform

# Accedi al database direttamente
docker exec -it cot-postgres psql -U cotuser -d cot_platform

# Pulisci tutto (ATTENZIONE: cancella dati!)
docker-compose down -v
```

## 🔄 Aggiornamento Applicazione

```powershell
# 1. Pull nuove modifiche
git pull origin main

# 2. Ricostruisci e riavvia
docker-compose up -d --build

# 3. Applica eventuali migrazioni DB
docker exec -it cot-app python migrations.py
```

## 📊 Monitoraggio

### Verifica Salute Servizi

```powershell
# Health check HTTP
curl http://localhost/health

# Statistiche container
docker stats
```

### Logs Persistenti

I logs sono salvati in:
- `C:\cot-platform\logs\` - Logs applicazione Flask
- `C:\cot-platform\logs\nginx\` - Logs Nginx

## 🐛 Troubleshooting

### App non parte

```powershell
# Verifica logs
docker-compose logs app

# Riavvia container
docker-compose restart app
```

### Database non connette

```powershell
# Verifica che PostgreSQL sia healthy
docker-compose ps

# Testa connessione manuale
docker exec -it cot-postgres psql -U cotuser -d cot_platform -c "SELECT 1;"
```

### Scraping COT non funziona

```powershell
# Verifica che Chrome sia installato nel container
docker exec -it cot-app google-chrome --version

# Testa scraping manuale
docker exec -it cot-app python -c "from collectors.cot_scraper import COTScraper; print('OK')"
```

### Porta già in uso

```powershell
# Trova processo che usa porta 80
netstat -ano | findstr :80

# Termina processo (sostituisci PID)
taskkill /PID <PID> /F
```

## 🔐 Sicurezza

### Checklist Produzione

- [ ] Cambia `DB_PASSWORD` in `.env`
- [ ] Genera nuovo `SECRET_KEY` in `.env`
- [ ] Usa HTTPS con certificato SSL valido
- [ ] Configura backup automatici database
- [ ] Limita accesso PostgreSQL (porta 5432 solo localhost)
- [ ] Abilita Windows Defender Firewall
- [ ] Aggiorna regolarmente con `docker-compose pull`

### Backup Automatico (Task Scheduler)

Crea un task in Windows Task Scheduler:

```powershell
# Script: C:\cot-platform\backup.ps1
$date = Get-Date -Format "yyyyMMdd_HHmmss"
docker exec cot-postgres pg_dump -U cotuser cot_platform > "C:\backups\cot_$date.sql"

# Mantieni solo ultimi 7 giorni
Get-ChildItem "C:\backups\cot_*.sql" | Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-7)} | Remove-Item
```

Esegui ogni giorno alle 3:00 AM.

## 📞 Supporto

Se hai problemi:
1. Controlla i logs: `docker-compose logs -f app`
2. Verifica `.env` sia configurato correttamente
3. Testa connessione database manuale
4. Verifica firewall Windows non blocca porte

## 🎉 Congratulazioni!

La tua piattaforma COT è ora hostata sul tuo server privato!

**Accedi a**: `http://tuo-server-ip` oppure `http://tuo-dominio.com`

**Vantaggi rispetto a Render**:
- ✅ Nessun cold start
- ✅ Scraping COT funziona perfettamente (Chrome headless)
- ✅ Database persistente locale
- ✅ Controllo totale su logs e debugging
- ✅ Costi fissi (niente sorprese da 200€/mese!)
