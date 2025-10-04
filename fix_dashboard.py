# fix_dashboard_issues.py
"""
Script per risolvere i problemi della dashboard:
1. Rende admin l'utente alessandro.baruffi99@gmail.com
2. Rimuove i pulsanti di debug strani
3. Aggiunge link al profilo
4. Sistema visualizzazione simboli
"""

from app_complete import app, db, User
from flask import Flask
import os

def fix_all_issues():
    """Risolve tutti i problemi identificati"""
    
    with app.app_context():
        print("\n" + "="*60)
        print("🔧 FIXING DASHBOARD ISSUES")
        print("="*60 + "\n")
        
        # 1. RENDI ADMIN L'UTENTE
        print("1️⃣ Controllo utente Alessandro...")
        user = User.query.filter_by(email='alessandro.baruffi99@gmail.com').first()
        
        if user:
            if not user.is_admin:
                user.is_admin = True
                db.session.commit()
                print(f"✅ {user.email} è ora ADMIN!")
            else:
                print(f"✅ {user.email} era già admin")
            
            # Info piano
            print(f"   Piano: {user.subscription_plan}")
            print(f"   Status: {user.subscription_status}")
            if user.trial_ends_at:
                print(f"   Trial scade: {user.trial_ends_at}")
        else:
            print("❌ Utente alessandro.baruffi99@gmail.com non trovato!")
            print("   Devi prima registrarti sulla piattaforma")
        
        print()
        
        # 2. FIX DASHBOARD.HTML
        print("2️⃣ Rimuovo pulsanti di debug dalla dashboard...")
        
        dashboard_path = 'templates/dashboard.html'
        if os.path.exists(dashboard_path):
            with open(dashboard_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Rimuovi i pulsanti strani se esistono
            debug_buttons = [
                'limit — limit',
                'message — message', 
                'symbols — symbols'
            ]
            
            modified = False
            for btn_text in debug_buttons:
                if btn_text in content:
                    print(f"   ⚠️  Trovato pulsante debug: '{btn_text}'")
                    modified = True
            
            if modified:
                # Cerca e rimuovi le righe con questi pulsanti
                lines = content.split('\n')
                new_lines = []
                skip_next = False
                
                for i, line in enumerate(lines):
                    # Salta righe con i pulsanti debug
                    if any(debug in line for debug in debug_buttons):
                        print(f"   🗑️  Rimuovo: {line.strip()[:80]}...")
                        continue
                    new_lines.append(line)
                
                # Salva backup
                with open(dashboard_path + '.backup', 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"   💾 Backup salvato: {dashboard_path}.backup")
                
                # Salva versione pulita
                with open(dashboard_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(new_lines))
                print("   ✅ Dashboard pulita dai pulsanti debug")
            else:
                print("   ✅ Nessun pulsante debug trovato")
        else:
            print(f"   ⚠️  File {dashboard_path} non trovato")
        
        print()
        
        # 3. AGGIUNGI LINK PROFILO
        print("3️⃣ Verifica link al profilo...")
        
        if os.path.exists(dashboard_path):
            with open(dashboard_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if '/profile' not in content:
                print("   ⚠️  Link profilo mancante - va aggiunto manualmente")
                print("   📝 Aggiungi questo HTML nel menu della dashboard:")
                print("""
                <a href="/profile" class="btn btn-outline-secondary">
                    <i class="fa-solid fa-user"></i> Profilo
                </a>
                """)
            else:
                print("   ✅ Link profilo già presente")
        
        print()
        
        # 4. INFO SIMBOLI
        print("4️⃣ Info sui simboli...")
        print("   I simboli sono caricati via JavaScript da /api/symbols")
        print("   Se non appaiono, controlla:")
        print("   - La route /api/symbols in app_complete.py")
        print("   - La console del browser (F12) per errori JavaScript")
        print("   - Che il piano Starter limiti a 5 simboli")
        
        print()
        print("="*60)
        print("✅ CONTROLLI COMPLETATI")
        print("="*60)
        print()
        print("🔄 PROSSIMI PASSI:")
        print("1. Riavvia l'app: python app_complete.py")
        print("2. Fai login con: alessandro.baruffi99@gmail.com")
        print("3. Dovresti vedere il badge 'ADMIN' in alto")
        print("4. Il pulsante 'Analisi AI' sarà ora cliccabile")
        print()

if __name__ == '__main__':
    fix_all_issues()
