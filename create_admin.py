#!/usr/bin/env python3
"""Script per creare utente admin"""

from app_complete import app, db, User
from werkzeug.security import generate_password_hash
from sqlalchemy import inspect, text

with app.app_context():
    # Aggiungi colonna is_admin se non esiste
    try:
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('user')]
        
        if 'is_admin' not in columns:
            with db.engine.connect() as conn:
                conn.execute(text('ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0'))
                conn.commit()
            print("✅ Colonna is_admin aggiunta")
        else:
            print("ℹ️  Colonna is_admin già presente")
    except Exception as e:
        print(f"Verifica colonna: {e}")
    
    # Crea o aggiorna admin
    admin_email = input("\nEmail admin: ").strip()
    admin_password = input("Password admin (min 8 caratteri): ").strip()
    
    if len(admin_password) < 8:
        print("❌ Password troppo corta!")
        exit(1)
    
    existing = User.query.filter_by(email=admin_email).first()
    if existing:
        existing.is_admin = True
        db.session.commit()
        print(f"✅ {admin_email} è ora admin")
    else:
        admin = User(
            email=admin_email,
            first_name="Admin",
            last_name="System",
            password_hash=generate_password_hash(admin_password),
            is_admin=True,
            subscription_plan='enterprise',
            subscription_status='active'
        )
        db.session.add(admin)
        db.session.commit()
        print(f"✅ Admin creato: {admin_email}")

print("\n🎉 Setup admin completato!")
