#!/usr/bin/env python3
"""
Ricrea il database da zero con schema corretto
ATTENZIONE: Cancella tutti i dati esistenti!
"""

import os
from datetime import datetime

def recreate_database():
    """Ricrea completamente il database"""
    
    db_path = 'cot_data.db'
    
    # Backup se esiste
    if os.path.exists(db_path):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f'cot_data_backup_{timestamp}.db'
        
        import shutil
        shutil.copy2(db_path, backup_path)
        print(f"💾 Backup creato: {backup_path}")
        
        # Cancella database esistente
        os.remove(db_path)
        print(f"🗑️ Database esistente cancellato")
    
    # Importa e inizializza app
    from app_complete import app, db
    
    with app.app_context():
        print("🏗️ Creazione nuovo database...")
        db.create_all()
        print("✅ Database ricreato con schema aggiornato")
        
        # Verifica tabelle
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"📋 Tabelle create: {tables}")
        
        # Verifica colonne prediction
        columns = [col['name'] for col in inspector.get_columns('prediction')]
        print(f"🎯 Colonne in prediction: {columns}")

if __name__ == "__main__":
    print("🚨 DATABASE RECREATE TOOL")
    print("ATTENZIONE: Questo cancellerà TUTTI i dati esistenti!")
    print("="*60)
    
    confirm = input("Sei sicuro? Scrivi 'SI' per continuare: ")
    
    if confirm.upper() == 'SI':
        recreate_database()
        print("\n✅ Database ricreato!")
        print("🚀 Ora esegui scraping per popolare i dati")
    else:
        print("❌ Operazione annullata")
    
    print("\n" + "="*60)