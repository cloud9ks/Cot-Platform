# decorators.py - Decoratori per controllo accessi basato su abbonamento
"""
Decoratori per limitare accesso a routes e feature in base al piano
"""

from functools import wraps
from flask import jsonify, redirect, url_for, flash
from flask_login import current_user
from models import SUBSCRIPTION_PLANS

# ==========================================
# DECORATORE: RICHIEDE FEATURE SPECIFICA
# ==========================================

def require_feature(feature_name):
    """
    Decoratore che verifica se l'utente ha accesso a una feature
    
    Uso:
        @require_feature('ai_predictions')
        def my_route():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Controlla autenticazione
            if not current_user.is_authenticated:
                if request.is_json:
                    return jsonify({
                        'error': 'Autenticazione richiesta',
                        'login_url': '/login'
                    }), 401
                return redirect(url_for('auth.login_page'))
            
            # Controlla abbonamento attivo
            if not current_user.has_active_subscription():
                if request.is_json:
                    return jsonify({
                        'error': 'Abbonamento scaduto',
                        'renew_url': '/pricing'
                    }), 403
                flash('Il tuo abbonamento è scaduto. Rinnova per continuare.', 'warning')
                return redirect(url_for('pricing'))
            
            # Controlla feature
            if not current_user.has_feature(feature_name):
                plan_info = current_user.get_plan_info()
                
                if request.is_json:
                    return jsonify({
                        'error': f'Feature "{feature_name}" non disponibile nel tuo piano',
                        'current_plan': current_user.subscription_plan,
                        'required_plan': 'professional',
                        'upgrade_url': '/pricing'
                    }), 403
                
                flash(f'Questa funzionalità richiede il piano Professional. Effettua l\'upgrade!', 'warning')
                return redirect(url_for('pricing'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ==========================================
# DECORATORE: RICHIEDE PIANO MINIMO
# ==========================================

def require_plan(min_plan):
    """
    Decoratore che verifica il piano minimo richiesto
    
    Uso:
        @require_plan('professional')
        def my_route():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.is_json:
                    return jsonify({
                        'error': 'Autenticazione richiesta',
                        'login_url': '/login'
                    }), 401
                return redirect(url_for('auth.login_page'))
            
            # Gerarchia piani
            plan_hierarchy = ['starter', 'professional']
            
            try:
                user_level = plan_hierarchy.index(current_user.subscription_plan)
                required_level = plan_hierarchy.index(min_plan)
            except ValueError:
                return jsonify({'error': 'Piano non valido'}), 400
            
            if user_level < required_level:
                if request.is_json:
                    return jsonify({
                        'error': f'Piano insufficiente. Richiesto: {min_plan}',
                        'current_plan': current_user.subscription_plan,
                        'required_plan': min_plan,
                        'upgrade_url': '/pricing'
                    }), 403
                
                flash(f'Questa funzione richiede il piano {min_plan}. Effettua l\'upgrade!', 'warning')
                return redirect(url_for('pricing'))
            
            if not current_user.has_active_subscription():
                if request.is_json:
                    return jsonify({
                        'error': 'Abbonamento scaduto',
                        'renew_url': '/pricing'
                    }), 403
                flash('Il tuo abbonamento è scaduto. Rinnova per continuare.', 'warning')
                return redirect(url_for('pricing'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ==========================================
# DECORATORE: SOLO ADMIN
# ==========================================

def admin_required(f):
    """
    Decoratore per routes riservate agli admin
    
    Uso:
        @admin_required
        def admin_panel():
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.is_json:
                return jsonify({'error': 'Autenticazione richiesta'}), 401
            return redirect(url_for('auth.login_page'))
        
        if not current_user.is_admin:
            if request.is_json:
                return jsonify({'error': 'Accesso negato - solo admin'}), 403
            flash('Accesso negato', 'danger')
            return redirect(url_for('dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function

# ==========================================
# HELPER: GET FEATURE AVAILABILITY
# ==========================================

def get_feature_availability():
    """
    Restituisce dict con disponibilità features per utente corrente
    Utile per nascondere/mostrare elementi UI
    """
    if not current_user.is_authenticated:
        return {feature: False for feature in ['ai_predictions', 'advanced_analysis', 'alerts', 'export_data', 'api_access']}
    
    plan = current_user.get_plan_info()
    return plan['features']

# ==========================================
# CONTEXT PROCESSOR
# ==========================================

def subscription_context_processor():
    """
    Context processor per rendere disponibili info abbonamento nei template
    
    Aggiungi in app.py:
        app.context_processor(subscription_context_processor)
    """
    if current_user.is_authenticated:
        return {
            'user_plan': current_user.subscription_plan,
            'user_features': get_feature_availability(),
            'has_active_subscription': current_user.has_active_subscription(),
            'is_in_trial': current_user.is_in_trial(),
            'subscription_plans': SUBSCRIPTION_PLANS
        }
    return {
        'user_plan': None,
        'user_features': {},
        'has_active_subscription': False,
        'is_in_trial': False,
        'subscription_plans': SUBSCRIPTION_PLANS
    }

# ==========================================
# ESEMPI DI USO NELLE ROUTES
# ==========================================

"""
ESEMPIO 1: Proteggere route che richiede AI predictions

@app.route('/api/ai-analysis')
@login_required
@require_feature('ai_predictions')
def ai_analysis():
    # Solo utenti Professional possono accedere
    return jsonify({'analysis': 'advanced data'})


ESEMPIO 2: Proteggere route che richiede piano Professional

@app.route('/api/advanced-tools')
@login_required
@require_plan('professional')
def advanced_tools():
    # Solo Professional+
    return jsonify({'tools': 'professional tools'})


ESEMPIO 3: Route solo admin

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = User.query.all()
    return render_template('admin/users.html', users=users)


ESEMPIO 4: Controllo condizionale nel codice

@app.route('/api/export-data')
@login_required
def export_data():
    # Controllo manuale
    if not current_user.has_feature('export_data'):
        return jsonify({
            'error': 'Export disponibile solo per Professional',
            'upgrade_url': '/pricing'
        }), 403
    
    # Procedi con export
    return generate_export()


ESEMPIO 5: Nel template Jinja2

{% if user_features.ai_predictions %}
    <button onclick="runAiAnalysis()">Analisi AI</button>
{% else %}
    <button onclick="showUpgrade()" disabled>
        Analisi AI (Pro)
        <i class="fas fa-lock"></i>
    </button>
{% endif %}
"""
