#!/usr/bin/env python3
"""
Script per applicare patch minime per modalità produzione
Modifica solo le parti necessarie del codice esistente
"""

import os
import shutil
from datetime import datetime

print("=" * 60)
print("🔧 COT Platform - Auto Patcher")
print("   Applica modifiche minime per Admin/User separation")
print("=" * 60)
print()

# =================== BACKUP ===================
def create_backup():
    """Crea backup dei file da modificare"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = f"backup_patch_{timestamp}"
    os.makedirs(backup_dir, exist_ok=True)
    
    files = ['app_complete.py']
    if os.path.exists('templates/dashboard.html'):
        files.append('templates/dashboard.html')
    
    for file in files:
        if os.path.exists(file):
            dest = os.path.join(backup_dir, file.replace('/', '_'))
            shutil.copy2(file, dest)
            print(f"✅ Backup: {file}")
    
    return backup_dir

# =================== PATCH APP_COMPLETE.PY ===================
def patch_app_complete():
    """Applica patch a app_complete.py"""
    print("\n🔧 Patching app_complete.py...")
    
    if not os.path.exists('app_complete.py'):
        print("❌ File app_complete.py non trovato!")
        return False
    
    with open('app_complete.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check se già patchato
    if 'is_admin' in content and 'admin_required' in content:
        print("ℹ️  File già patchato - skip")
        return True
    
    # Trova dove inserire il codice User
    # Cerca la prima classe Model dopo gli import
    lines = content.split('\n')
    insert_pos = -1
    
    for i, line in enumerate(lines):
        if 'class COTData(db.Model):' in line or 'class Prediction(db.Model):' in line:
            insert_pos = i
            break
    
    if insert_pos == -1:
        print("⚠️  Non ho trovato dove inserire User model")
        print("   Dovrai aggiungere manualmente (vedi MINIMAL_PATCHES.md)")
        return False
    
    # Codice da inserire
    user_model_code = '''
# =================== USER MODEL & ADMIN DECORATOR ===================
from flask_login import LoginManager, UserMixin, login_required, current_user
from functools import wraps

# Setup Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    """Modello User con supporto admin"""
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    first_name = db.Column(db.String(80))
    last_name = db.Column(db.String(80))
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)  # 🆕 Campo admin
    subscription_plan = db.Column(db.String(20), default='starter')
    subscription_status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    """Decoratore per route che richiedono privilegi admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Login richiesto'}), 401
        if not current_user.is_admin:
            return jsonify({'error': 'Privilegi admin richiesti'}), 403
        return f(*args, **kwargs)
    return decorated_function

'''
    
    # Inserisci prima del primo Model
    lines.insert(insert_pos, user_model_code)
    
    # Trova e proteggi route /api/scrape/<symbol>
    for i, line in enumerate(lines):
        if '@app.route(\'/api/scrape/<symbol>\')' in line:
            # Aggiungi decoratori prima
            if '@login_required' not in lines[i-1]:
                lines.insert(i+1, '@login_required')
                lines.insert(i+2, '@admin_required  # 🆕 Solo admin')
                print("✅ Protetta route /api/scrape/<symbol>")
    
    # Aggiungi nuove API alla fine (prima di if __name__)
    new_apis = '''
# =================== API USER/ADMIN ===================
@app.route('/api/user/info')
@login_required
def get_user_info():
    """Info utente corrente"""
    return jsonify({
        'id': current_user.id,
        'email': current_user.email,
        'name': f"{current_user.first_name or ''} {current_user.last_name or ''}",
        'is_admin': current_user.is_admin,
        'subscription_plan': current_user.subscription_plan
    })

'''
    
    # Trova if __name__ == '__main__'
    for i, line in enumerate(lines):
        if "if __name__ == '__main__':" in line:
            lines.insert(i, new_apis)
            print("✅ Aggiunte nuove API")
            break
    
    # Salva file modificato
    with open('app_complete.py', 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print("✅ app_complete.py patchato con successo!")
    return True

# =================== PATCH DASHBOARD.HTML ===================
def patch_dashboard():
    """Applica patch a dashboard.html"""
    print("\n🔧 Patching templates/dashboard.html...")
    
    dashboard_path = 'templates/dashboard.html'
    if not os.path.exists(dashboard_path):
        print("⚠️  File dashboard.html non trovato - skip")
        return False
    
    with open(dashboard_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check se già patchato
    if 'current_user.is_admin' in content:
        print("ℹ️  File già patchato - skip")
        return True
    
    # Trova i bottoni Aggiorna e Analisi AI
    # Cerca pattern comune
    patterns = [
        'id="btnRefresh"',
        'id="btnRun"',
        'Analisi AI',
    ]
    
    found = any(p in content for p in patterns)
    if not found:
        print("⚠️  Non ho trovato i bottoni da modificare")
        print("   Modifica manualmente (vedi MINIMAL_PATCHES.md)")
        return False
    
    # Sostituisci la sezione bottoni con versione condizionale
    # Questo è generico - potrebbe dover essere adattato
    old_buttons = '''<button class="btn btn-outline-primary" id="btnRefresh">'''
    
    if old_buttons in content:
        new_buttons = '''{% if current_user.is_authenticated and current_user.is_admin %}
<span class="badge bg-purple me-2">
  <i class="fa-solid fa-crown"></i> ADMIN
</span>
<button class="btn btn-outline-primary" id="btnRefresh">'''
        
        content = content.replace(old_buttons, new_buttons)
        
        # Chiudi l'if dopo i bottoni admin
        # Cerca il bottone "Analisi AI" e aggiungi dopo
        btnrun_pos = content.find('id="btnRun"')
        if btnrun_pos > 0:
            # Trova la fine di quel bottone
            close_pos = content.find('</button>', btnrun_pos)
            if close_pos > 0:
                content = (content[:close_pos+9] + 
                          '\n{% else %}\n' +
                          '<span class="badge bg-success">\n' +
                          '  <i class="fa-solid fa-clock-rotate-left"></i>\n' +
                          '  Auto-aggiornamento attivo\n' +
                          '</span>\n' +
                          '{% endif %}' +
                          content[close_pos+9:])
        
        print("✅ Bottoni condizionali aggiunti")
    
    # Aggiungi info alert per utenti
    # Cerca i tabs o il symbol selector
    tab_pos = content.find('<ul class="nav nav-tabs')
    if tab_pos > 0:
        info_alert = '''
<!-- Info per utenti normali -->
{% if current_user.is_authenticated and not current_user.is_admin %}
<div class="alert alert-info d-flex align-items-start gap-3 mb-4">
  <i class="fa-solid fa-circle-info fs-4"></i>
  <div>
    <h6 class="mb-1">Dati Aggiornati Automaticamente</h6>
    <p class="mb-0 small">
      Il sistema aggiorna automaticamente le analisi ogni Martedì alle 21:00.
      Visualizzi sempre i dati più recenti!
    </p>
  </div>
</div>
{% endif %}

'''
        content = content[:tab_pos] + info_alert + content[tab_pos:]
        print("✅ Info alert aggiunto")
    
    # Salva
    with open(dashboard_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ dashboard.html patchato con successo!")
    return True

# =================== CREATE ADMIN SCRIPT ===================
def create_admin_script():
    """Crea script per creare utente admin"""
    print("\n📝 Creando script create_admin.py...")
    
    script_content = '''#!/usr/bin/env python3
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
    admin_email = input("\\nEmail admin: ").strip()
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

print("\\n🎉 Setup admin completato!")
'''
    
    with open('create_admin.py', 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    print("✅ Script create_admin.py creato!")
    return True

# =================== CHECK REQUIREMENTS ===================
def check_requirements():
    """Verifica requirements.txt"""
    print("\n📋 Verificando requirements.txt...")
    
    if not os.path.exists('requirements.txt'):
        print("⚠️  requirements.txt non trovato - skip")
        return False
    
    with open('requirements.txt', 'r') as f:
        content = f.read()
    
    if 'Flask-Login' in content:
        print("✅ Flask-Login già presente")
        return True
    
    # Aggiungi Flask-Login
    with open('requirements.txt', 'a') as f:
        f.write('\nFlask-Login>=0.6.3\n')
    
    print("✅ Flask-Login aggiunto a requirements.txt")
    print("   Esegui: pip install Flask-Login")
    return True

# =================== MAIN ===================
def main():
    print("📦 Creazione backup...")
    backup_dir = create_backup()
    print(f"✅ Backup salvato in: {backup_dir}/")
    print()
    
    success = True
    
    # Applica patch
    if not patch_app_complete():
        success = False
    
    if not patch_dashboard():
        print("⚠️  Dashboard non patchata - modifica manualmente")
    
    if not create_admin_script():
        success = False
    
    if not check_requirements():
        print("⚠️  Requirements non aggiornati")
    
    print()
    print("=" * 60)
    
    if success:
        print("✅ PATCH APPLICATE CON SUCCESSO!")
        print()
        print("📋 PROSSIMI PASSI:")
        print()
        print("1. Installa Flask-Login:")
        print("   pip install Flask-Login")
        print()
        print("2. Crea utente admin:")
        print("   python create_admin.py")
        print()
        print("3. Testa l'applicazione:")
        print("   python app_complete.py")
        print()
        print("4. Accedi come admin e verifica i controlli")
        print()
    else:
        print("⚠️  ALCUNE PATCH NON APPLICATE")
        print()
        print("Consulta MINIMAL_PATCHES.md per modifiche manuali")
        print()
    
    print(f"🔄 In caso di problemi, ripristina dal backup: {backup_dir}/")
    print("=" * 60)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Operazione annullata dall'utente")
    except Exception as e:
        print(f"\n\n❌ Errore: {e}")
        import traceback
        traceback.print_exc()
