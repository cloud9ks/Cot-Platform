# ==============================================
# COT Platform - Backup Automatico Database
# ==============================================
# Usa questo script con Task Scheduler per backup automatici

$BackupDir = "C:\backups\cot-platform"
$Date = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupFile = "$BackupDir\cot_$Date.sql"

# Crea directory backup se non esiste
if (-Not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
    Write-Host "✓ Creata directory backup: $BackupDir" -ForegroundColor Green
}

# Esegui backup
Write-Host "🔄 Backup database in corso..." -ForegroundColor Yellow
docker exec cot-postgres pg_dump -U cotuser cot_platform > $BackupFile

if ($LASTEXITCODE -eq 0) {
    $FileSize = (Get-Item $BackupFile).Length / 1MB
    Write-Host "✓ Backup completato: $BackupFile ($([math]::Round($FileSize, 2)) MB)" -ForegroundColor Green

    # Comprimi backup
    Write-Host "🗜️ Compressione backup..." -ForegroundColor Yellow
    Compress-Archive -Path $BackupFile -DestinationPath "$BackupFile.zip" -Force
    Remove-Item $BackupFile
    Write-Host "✓ Backup compresso: $BackupFile.zip" -ForegroundColor Green
} else {
    Write-Host "✗ Backup fallito!" -ForegroundColor Red
    exit 1
}

# Mantieni solo ultimi 7 giorni
Write-Host "🧹 Pulizia backup vecchi..." -ForegroundColor Yellow
$OldBackups = Get-ChildItem "$BackupDir\cot_*.sql.zip" | Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-7)}
$OldBackups | ForEach-Object {
    Write-Host "  - Rimuovo: $($_.Name)" -ForegroundColor Gray
    Remove-Item $_.FullName
}
Write-Host "✓ Pulizia completata" -ForegroundColor Green

# Riepilogo
Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
$AllBackups = Get-ChildItem "$BackupDir\cot_*.sql.zip" | Sort-Object LastWriteTime -Descending
Write-Host "Backup disponibili: $($AllBackups.Count)" -ForegroundColor Cyan
$TotalSize = ($AllBackups | Measure-Object -Property Length -Sum).Sum / 1MB
Write-Host "Spazio totale: $([math]::Round($TotalSize, 2)) MB" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
