# Dalla cartella backend (sei già lì da quello che vedo)
# D:\Progetti\football-scout\backend>

# Crea l'ambiente virtuale
python -m venv .venv

Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\.venv\Scripts\Activate.ps1

#Svuota la cache di pip e forza il download del wheel corretto
python -m pip cache purge

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -m pip install -r requirements.txt --only-binary=psycopg2-binary
cd ..
copy .env.example .env
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000


Get-ChildItem "C:\Program Files\PostgreSQL"