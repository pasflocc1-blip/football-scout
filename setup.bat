@echo off
REM ─────────────────────────────────────────────────────────────────
REM setup.bat — Configurazione Git su Windows (UNA VOLTA SOLA)
REM
REM Il Mac NON ha bisogno di questo file.
REM Su Mac basta:  git clone + docker compose up
REM
REM Questo file serve SOLO al PC Windows per configurare Git
REM in modo che i file committati abbiano LF (non CRLF).
REM Senza questa configurazione, i file mandati su GitHub avrebbero
REM CRLF e romperebbero il progetto su Mac e Linux.
REM ─────────────────────────────────────────────────────────────────

echo.
echo  [Windows Setup] Configurazione Git per sviluppo cross-platform
echo  ───────────────────────────────────────────────────────────────

REM Verifica Git
where git >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERRORE] Git non trovato. Scaricalo da: https://git-scm.com/
    pause & exit /b 1
)

REM Verifica Docker
where docker >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERRORE] Docker Desktop non trovato.
    echo Scaricalo da: https://www.docker.com/products/docker-desktop/
    pause & exit /b 1
)

echo [OK] Git e Docker trovati.
echo.

REM ── LA CONFIGURAZIONE CHIAVE ─────────────────────────────────────
REM Dice a Git: quando fai commit, converti CRLF → LF
REM Questo garantisce che GitHub riceva sempre file in LF
REM e il Mac possa fare git clone senza nessun setup.
echo [1/3] Configuro core.autocrlf = input (globale per tutti i progetti)...
git config --global core.autocrlf input
echo       Valore impostato: && git config --global core.autocrlf
echo.

REM ── RINORMALIZZA I FILE ESISTENTI ────────────────────────────────
REM Se hai già fatto clone prima di questa configurazione,
REM potresti avere file con CRLF su disco. Questo li rinormalizza.
echo [2/3] Rinormalizzo i file esistenti (se necessario)...
git add --renormalize . 2>nul
echo       Fatto.
echo.

REM ── CREA .env SE NON ESISTE ──────────────────────────────────────
echo [3/3] Verifico file .env...
IF NOT EXIST ".env" (
    copy .env.example .env >nul
    echo       .env creato. Compila le API key se necessario.
) ELSE (
    echo       .env gia' presente.
)

echo.
echo  ════════════════════════════════════════════════════
echo  Configurazione completata!
echo.
echo  Ora puoi avviare il progetto con:
echo    docker compose up --build
echo.
echo  Il Mac potra' fare git clone e avviare con:
echo    docker compose up --build
echo  (senza nessun altro setup)
echo  ════════════════════════════════════════════════════
echo.
pause
