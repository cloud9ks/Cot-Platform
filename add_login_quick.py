#!/usr/bin/env python3
"""Script per aggiungere sistema login automaticamente"""

import os
import shutil
from datetime import datetime

print("🔐 Aggiunta sistema login...")

# Backup
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
backup_dir = f"backup_login_{timestamp}"
os.makedirs(backup_dir, exist_ok=True)
shutil.copy2('app_complete.py', f"{backup_dir}/app_complete.py")
print(f"✅ Backup: {backup_dir}/")

# Leggi app_complete.py
with open('app_complete.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Aggiungi redirect all'import Flask se non c'è
if 'from flask import' in content and 'redirect' not in content.split('from flask import')[1].split('\n')[0]:
    content = content.replace(
        'from flask import Flask,',
        'from flask import Flask, redirect,'
    )
    print("✅ Aggiunto import redirect")

# Trova if __name__ e aggiungi route login prima
login_routes = '''
# =================== AUTENTICAZIONE ROUTES ===================
from werkzeug.security import check_password_hash
from flask_login import login_user, logout_user

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Pagina di login"""
    if request.method == 'GET':
        if current_user.is_authenticated:
            return redirect('/dashboard')
        return render_template('login.html')
    
    data = request.get_json() if request.is_json else request.form
    email = data.get('email', '').strip()
    password = data.get('password', '')
    
    if not email or not password:
        return jsonify({'error': 'Email e password richiesti'}), 400
    
    user = User.query.filter_by(email=email).first()
    
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'error': 'Credenziali non valide'}), 401
    
    login_user(user, remember=True)
    
    return jsonify({
        'success': True,
        'redirect': '/dashboard',
        'is_admin': user.is_admin
    })

@app.route('/logout')
@login_required
def logout():
    """Logout"""
    logout_user()
    return redirect('/login')

'''

if '/login' not in content:
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if "if __name__ == '__main__':" in line:
            lines.insert(i, login_routes)
            print("✅ Aggiunte route login/logout")
            break
    content = '\n'.join(lines)

# Proteggi dashboard
content = content.replace(
    "@app.route('/dashboard')\ndef dashboard():",
    "@app.route('/dashboard')\n@login_required\ndef dashboard():"
)
print("✅ Dashboard protetta con @login_required")

# Salva
with open('app_complete.py', 'w', encoding='utf-8') as f:
    f.write(content)

# Crea login.html
os.makedirs('templates', exist_ok=True)

login_html = '''<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Login - COT Analysis Platform</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    body {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .login-card {
      background: white;
      border-radius: 20px;
      box-shadow: 0 20px 60px rgba(0,0,0,0.3);
      padding: 50px 40px;
      max-width: 450px;
    }
    .logo i {
      font-size: 4rem;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .btn-login {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      border: none;
      padding: 12px;
      font-weight: 600;
      color: white;
    }
    .form-control {
      padding: 12px 15px;
      border-radius: 10px;
    }
  </style>
</head>
<body>
  <div class="login-card">
    <div class="text-center mb-4">
      <i class="fa-solid fa-chart-line"></i>
      <h1 class="h3 mt-3">COT Analysis</h1>
      <p class="text-muted">Professional Trading Platform</p>
    </div>

    <div id="alert"></div>

    <form id="loginForm">
      <div class="mb-3">
        <label class="form-label">Email</label>
        <input type="email" class="form-control" id="email" required>
      </div>
      <div class="mb-3">
        <label class="form-label">Password</label>
        <input type="password" class="form-control" id="password" required>
      </div>
      <button type="submit" class="btn btn-login w-100" id="btnLogin">
        Accedi
      </button>
    </form>
  </div>

  <script>
    document.getElementById('loginForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = document.getElementById('btnLogin');
      btn.disabled = true;
      btn.textContent = 'Accesso...';

      try {
        const res = await fetch('/login', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            email: document.getElementById('email').value,
            password: document.getElementById('password').value
          })
        });

        const data = await res.json();

        if (res.ok && data.success) {
          document.getElementById('alert').innerHTML = 
            '<div class="alert alert-success">✅ Accesso riuscito!</div>';
          setTimeout(() => window.location.href = data.redirect, 1000);
        } else {
          document.getElementById('alert').innerHTML = 
            '<div class="alert alert-danger">' + (data.error || 'Errore') + '</div>';
          btn.disabled = false;
          btn.textContent = 'Accedi';
        }
      } catch (error) {
        document.getElementById('alert').innerHTML = 
          '<div class="alert alert-danger">Errore di connessione</div>';
        btn.disabled = false;
        btn.textContent = 'Accedi';
      }
    });
  </script>
</body>
</html>'''

with open('templates/login.html', 'w', encoding='utf-8') as f:
    f.write(login_html)

print("✅ Creato templates/login.html")

print("\n" + "="*60)
print("✅ SISTEMA LOGIN AGGIUNTO!")
print("="*60)
print("\n📋 CREDENZIALI ADMIN:")
print("   Email: alessandro.baruffi99@gmail.com")
print("   Password: Rolex_20k")
print("\n🚀 AVVIA APP:")
print("   python app_complete.py")
print("\n🌐 ACCEDI:")
print("   http://localhost:5000/login")
print("\n" + "="*60)
