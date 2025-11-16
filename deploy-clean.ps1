# ==============================================
# COT Platform - Deploy Script per Windows Server
# ==============================================

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "   COT Platform - Deploy Automatico   " -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Controlla se Docker e' installato
Write-Host "[1/6] Verifica Docker..." -ForegroundColor Yellow
try {
    $dockerVersion = docker --version
    Write-Host "  [OK] Docker installato: $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "  [ERRORE] Docker NON trovato!" -ForegroundColor Red
    Write-Host "  Installa Docker Desktop da: https://docs.docker.com/desktop/install/windows-install/" -ForegroundColor Yellow
    exit 1
}

try {
    $composeVersion = docker-compose --version
    Write-Host "  [OK] Docker Compose installato: $composeVersion" -ForegroundColor Green
} catch {
    Write-Host "  [ERRORE] Docker Compose NON trovato!" -ForegroundColor Red
    exit 1
}

# Controlla file .env
Write-Host ""
Write-Host "[2/6] Verifica configurazione..." -ForegroundColor Yellow
if (-Not (Test-Path ".env")) {
    Write-Host "  [!] File .env non trovato, creo da template..." -ForegroundColor Yellow
    Copy-Item ".env.docker.example" ".env"
    Write-Host "  [ATTENZIONE] Modifica il file .env con i tuoi valori!" -ForegroundColor Red
    Write-Host "  Apri .env e configura:" -ForegroundColor Yellow
    Write-Host "    - DB_PASSWORD" -ForegroundColor Yellow
    Write-Host "    - SECRET_KEY" -ForegroundColor Yellow
    Write-Host "    - OPENAI_API_KEY" -ForegroundColor Yellow
    Write-Host ""
    $continue = Read-Host "  Hai configurato .env? (y/n)"
    if ($continue -ne "y") {
        Write-Host "  Configura .env e riavvia lo script." -ForegroundColor Yellow
        exit 0
    }
} else {
    Write-Host "  [OK] File .env trovato" -ForegroundColor Green
}

# Crea directory necessarie
Write-Host ""
Write-Host "[3/6] Crea directory..." -ForegroundColor Yellow
$dirs = @("data", "logs", "logs\nginx", "nginx\ssl")
foreach ($dir in $dirs) {
    if (-Not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "  [OK] Creata: $dir" -ForegroundColor Green
    } else {
        Write-Host "  [OK] Esiste: $dir" -ForegroundColor Green
    }
}

# Stop containers esistenti
Write-Host ""
Write-Host "[4/6] Stop containers esistenti..." -ForegroundColor Yellow
docker-compose down 2>$null
Write-Host "  [OK] Containers fermati" -ForegroundColor Green

# Build immagini
Write-Host ""
Write-Host "[5/6] Build immagini Docker..." -ForegroundColor Yellow
Write-Host "  (Questo potrebbe richiedere alcuni minuti...)" -ForegroundColor Gray
docker-compose build
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [ERRORE] Build fallito!" -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] Build completato" -ForegroundColor Green

# Avvia servizi
Write-Host ""
Write-Host "[6/6] Avvio servizi..." -ForegroundColor Yellow
docker-compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [ERRORE] Avvio fallito!" -ForegroundColor Red
    exit 1
}

# Attendi che i servizi siano healthy
Write-Host ""
Write-Host "Attendo che i servizi siano pronti..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Verifica stato
Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "   Stato Servizi" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
docker-compose ps

# Test connessione
Write-Host ""
Write-Host "Test connessione..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost/health" -TimeoutSec 5 -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-Host "  [OK] Applicazione raggiungibile!" -ForegroundColor Green
    }
} catch {
    Write-Host "  [AVVISO] Applicazione non ancora pronta (riprova tra 30 secondi)" -ForegroundColor Yellow
}

# Riepilogo finale
Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "   Deploy Completato!" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "SUCCESS: La tua piattaforma COT e' online!" -ForegroundColor Green
Write-Host ""
Write-Host "ACCEDI A: http://localhost" -ForegroundColor Cyan
Write-Host ""
Write-Host "COMANDI UTILI:" -ForegroundColor Yellow
Write-Host "  - Visualizza logs:     docker-compose logs -f app" -ForegroundColor Gray
Write-Host "  - Stop servizi:        docker-compose down" -ForegroundColor Gray
Write-Host "  - Riavvia servizi:     docker-compose restart" -ForegroundColor Gray
Write-Host "  - Stato servizi:       docker-compose ps" -ForegroundColor Gray
Write-Host ""
Write-Host "DOCUMENTAZIONE: DEPLOY_WINDOWS_SERVER.md" -ForegroundColor Gray
Write-Host ""
