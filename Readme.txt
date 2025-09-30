1)attivazione ambiente 

.\.venv\Scripts\activate

2)Aggiorna pip/setuptools/wheel e pulisci cache

python -m pip install --upgrade pip setuptools wheel
pip cache purge

3) Installa le dipendenze (combo compatibile con Python 3.12 su Windows)

pip install -r requirements.txt

5) Fix rapido se vedi l’errore “No module named 'pydantic_core._pydantic_core'”

pip uninstall -y pydantic pydantic-core
pip install --upgrade pip setuptools wheel
pip install --no-cache-dir "pydantic>=2.8"python.ap
pip install Flask-SQLAlchemy SQLAlchemy
pip install Flask-APScheduler APScheduler

6)Verifica versioni chiave

python -c "import numpy, scipy, sklearn, pandas, flask, yfinance, pydantic; print('numpy', numpy.__version__, '| scipy', scipy.__version__, '| sklearn', sklearn.__version__, '| pandas', pandas.__version__, '| flask', flask.__version__, '| yfinance', yfinance.__version__, '| pydantic', pydantic.__version__)"


