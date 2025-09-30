#!/usr/bin/env python3
"""
Script per trovare il database SQLite dell'app COT
"""

import os
import sqlite3
from pathlib import Path
from datetime import datetime

def find_cot_databases():
    """Trova tutti i file cot_data.db nel sistema"""
    
    print("🔍 RICERCA DATABASE COT")
    print("="*50)
    
    # Cartelle da cercare
    search_paths = [
        ".",  # Cartella corrente
        os.path.expanduser("~"),  # Home directory
        os.getcwd(),  # Working directory
        os.path.dirname(os.path.abspath(__file__)),  # Cartella di questo script
    ]
    
    # Cerca anche ricorsivamente nella cartella corrente e parent
    for root, dirs, files in os.walk("."):
        if "cot_data.db" in files:
            search_paths.append(root)
    
    # Se siamo in una sottocartella, cerca anche nella parent
    parent_dir = os.path.dirname(os.getcwd())
    if parent_dir:
        search_paths.append(parent_dir)
    
    found_databases = []
    
    for path in set(search_paths):  # Remove duplicates
        db_path = os.path.join(path, "cot_data.db")
        if os.path.exists(db_path):
            abs_path = os.path.abspath(db_path)
            size = os.path.getsize(abs_path)
            modified = datetime.fromtimestamp(os.path.getmtime(abs_path))
            found_databases.append({
                'path': abs_path,
                'size': size,
                'modified': modified,
                'relative': os.path.relpath(abs_path)
            })
    
    if not found_databases:
        print("❌ Nessun database 'cot_data.db' trovato!")
        print("\n💡 Il database viene creato quando:")
        print("   1. Avvii app_complete.py per la prima volta")
        print("   2. L'app chiama db.create_all()")
        print("\n🚀 Prova ad avviare l'app una volta:")
        print("   python app_complete.py")
        return []
    
    print(f"📁 Trovati {len(found_databases)} database:")
    print()
    
    for i, db in enumerate(found_databases, 1):
        print(f"{i}. 📍 {db['relative']}")
        print(f"   Path completo: {db['path']}")
        print(f"   Dimensione: {db['size']:,} bytes")
        print(f"   Modificato: {db['modified']}")
        
        # Verifica contenuto
        try:
            conn = sqlite3.connect(db['path'])
            cursor = conn.cursor()
            
            # Conta record nelle tabelle principali
            tables_info = []
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            for table in ['cot_data', 'prediction']:
                if table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    tables_info.append(f"{table}: {count} record")
            
            if tables_info:
                print(f"   Contenuto: {', '.join(tables_info)}")
            else:
                print(f"   Tabelle: {', '.join(tables)}")
            
            conn.close()
            
        except Exception as e:
            print(f"   ⚠️ Errore lettura: {e}")
        
        print()
    
    return found_databases

def check_app_database_config():
    """Controlla la configurazione del database nell'app"""
    
    print("\n🔧 CONFIGURAZIONE APP")
    print("="*30)
    
    try:
        # Importa l'app per vedere la config
        import sys
        import os
        
        # Aggiungi la cartella dell'app al path se necessario
        app_dir = os.path.dirname(os.path.abspath(__file__))
        if app_dir not in sys.path:
            sys.path.append(app_dir)
        
        from app_complete import app
        
        with app.app_context():
            db_uri = app.config['SQLALCHEMY_DATABASE_URI']
            print(f"📋 URI Database: {db_uri}")
            
            if db_uri.startswith('sqlite:///'):
                db_file = db_uri.replace('sqlite:///', '')
                
                if db_file.startswith('/'):
                    # Path assoluto
                    expected_path = db_file
                else:
                    # Path relativo - dipende da dove avvii l'app
                    current_dir = os.getcwd()
                    expected_path = os.path.join(current_dir, db_file)
                
                print(f"📍 Path atteso: {expected_path}")
                print(f"🔍 Esiste: {'✅ SI' if os.path.exists(expected_path) else '❌ NO'}")
                
                if not os.path.exists(expected_path):
                    print(f"💡 Il database sarà creato qui quando avvii l'app")
                
                return expected_path
                
    except ImportError as e:
        print(f"⚠️ Non posso importare app_complete.py: {e}")
        print("💡 Assicurati di essere nella cartella corretta")
    except Exception as e:
        print(f"⚠️ Errore: {e}")
    
    return None

def show_current_directory_info():
    """Mostra informazioni sulla cartella corrente"""
    
    print("\n📂 INFORMAZIONI CARTELLA CORRENTE")
    print("="*40)
    print(f"📍 Directory corrente: {os.getcwd()}")
    print(f"📍 Script directory: {os.path.dirname(os.path.abspath(__file__))}")
    
    # Lista file Python nella cartella
    py_files = [f for f in os.listdir('.') if f.endswith('.py')]
    if py_files:
        print(f"🐍 File Python trovati: {', '.join(py_files)}")
    
    # Cerca app_complete.py
    if 'app_complete.py' in py_files:
        print("✅ app_complete.py trovato nella cartella corrente")
    else:
        print("❌ app_complete.py NON trovato nella cartella corrente")
        print("💡 Naviga nella cartella che contiene app_complete.py")

if __name__ == "__main__":
    print("🗃️ DATABASE LOCATOR TOOL")
    print("="*50)
    
    # Mostra info cartella corrente
    show_current_directory_info()
    
    # Trova database esistenti
    databases = find_cot_databases()
    
    # Controlla configurazione app
    expected_path = check_app_database_config()
    
    print("\n🎯 RIASSUNTO")
    print("="*20)
    
    if databases:
        print(f"✅ Database trovati: {len(databases)}")
        most_recent = max(databases, key=lambda x: x['modified'])
        print(f"🕐 Più recente: {most_recent['relative']}")
        
        if len(databases) > 1:
            print("⚠️ ATTENZIONE: Multipli database trovati!")
            print("💡 Usa quello più recente o nella cartella dell'app")
    else:
        print("❌ Nessun database trovato")
        print("🚀 Avvia 'python app_complete.py' per crearlo")
    
    if expected_path:
        print(f"🎯 Path atteso dall'app: {os.path.relpath(expected_path)}")
    
    print("\n" + "="*50)