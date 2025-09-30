# subscription_system.py
"""
Sistema di gestione abbonamenti per COT Analysis Platform
Integra con Stripe per pagamenti e gestione degli abbonamenti
"""

from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
import stripe
import os
from enum import Enum

# Configurazione Stripe
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', 'sk_test_...')  # Inserisci la tua chiave

# Piani di abbonamento
SUBSCRIPTION_PLANS = {
    'starter': {
        'name': 'Starter',
        'price': 0,
        'stripe_price_id': None,
        'features': {
            'assets_limit': 3,
            'cot_data': 'basic',
            'ai_predictions': False,
            'alerts': False,
            'technical_analysis': 'basic',
            'backtesting': False,
            'api_access': False,
            'support': 'community'
        }
    },
    'professional': {
        'name': 'Professional', 
        'price': 49,
        'stripe_price_id': 'price_professional_monthly',  # ID da Stripe Dashboard
        'features': {
            'assets_limit': -1,  # illimitato
            'cot_data': 'realtime',
            'ai_predictions': True,
            'alerts': True,
            'technical_analysis': 'advanced',
            'backtesting': True,
            'api_access': 'limited',
            'support': 'email'
        }
    },
    'enterprise': {
        'name': 'Enterprise',
        'price': 199,
        'stripe_price_id': 'price_enterprise_monthly',  # ID da Stripe Dashboard
        'features': {
            'assets_limit': -1,
            'cot_data': 'realtime',
            'ai_predictions': True,
            'alerts': True,
            'technical_analysis': 'advanced',
            'backtesting': True,
            'api_access': 'full',
            'support': '24/7',
            'team_users': 10,
            'white_label': True
        }
    }
}

class SubscriptionStatus(Enum):
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    UNPAID = "unpaid"
    TRIALING = "trialing"

# Modelli Database
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    password_hash = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Stripe info
    stripe_customer_id = db.Column(db.String(100))
    
    # Subscription info
    subscription_plan = db.Column(db.String(20), default='starter')
    subscription_status = db.Column(db.String(20), default='active')
    subscription_id = db.Column(db.String(100))  # Stripe subscription ID
    trial_ends_at = db.Column(db.DateTime)
    subscription_ends_at = db.Column(db.DateTime)
    
    def has_feature(self, feature_name):
        """Controlla se l'utente ha accesso a una specifica funzionalità"""
        plan = SUBSCRIPTION_PLANS.get(self.subscription_plan, SUBSCRIPTION_PLANS['starter'])
        return plan['features'].get(feature_name, False)
    
    def get_asset_limit(self):
        """Restituisce il numero massimo di asset monitorabili"""
        plan = SUBSCRIPTION_PLANS.get(self.subscription_plan, SUBSCRIPTION_PLANS['starter'])
        return plan['features'].get('assets_limit', 3)
    
    def is_subscription_active(self):
        """Controlla se l'abbonamento è attivo"""
        if self.subscription_plan == 'starter':
            return True
        return (self.subscription_status == 'active' and 
                (not self.subscription_ends_at or self.subscription_ends_at > datetime.utcnow()))

class SubscriptionEvent(db.Model):
    """Log degli eventi di abbonamento per tracking"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_type = db.Column(db.String(50), nullable=False)  # created, upgraded, canceled, etc.
    old_plan = db.Column(db.String(20))
    new_plan = db.Column(db.String(20))
    stripe_event_id = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    metadata = db.Column(db.Text)  # JSON per info aggiuntive

# Routes per gestione abbonamenti
@app.route('/register')
def register():
    plan = request.args.get('plan', 'starter')
    if plan not in SUBSCRIPTION_PLANS:
        plan = 'starter'
    return render_template('register.html', selected_plan=plan, plans=SUBSCRIPTION_PLANS)

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json()
    
    # Validazione dati
    if not all([data.get('email'), data.get('first_name'), data.get('last_name'), data.get('password')]):
        return jsonify({'error': 'Tutti i campi sono obbligatori'}), 400
    
    # Controlla se l'utente esiste già
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email già registrata'}), 400
    
    try:
        # Crea customer Stripe
        stripe_customer = stripe.Customer.create(
            email=data['email'],
            name=f"{data['first_name']} {data['last_name']}",
            metadata={
                'source': 'cot_analysis_platform'
            }
        )
        
        # Crea utente
        user = User(
            email=data['email'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            stripe_customer_id=stripe_customer.id,
            subscription_plan=data.get('plan', 'starter')
        )
        
        # Hash password (implementa hashing sicuro)
        # user.password_hash = hash_password(data['password'])
        
        db.session.add(user)
        db.session.commit()
        
        # Se piano Professional, avvia trial
        if data.get('plan') == 'professional':
            user.subscription_status = 'trialing'
            user.trial_ends_at = datetime.utcnow() + timedelta(days=30)
            db.session.commit()
        
        login_user(user)
        
        return jsonify({
            'success': True,
            'redirect': '/dashboard' if data.get('plan') == 'starter' else '/checkout'
        })
        
    except stripe.error.StripeError as e:
        return jsonify({'error': 'Errore nella creazione dell\'account'}), 500
    except Exception as e:
        return jsonify({'error': 'Errore interno del server'}), 500

@app.route('/checkout')
@login_required
def checkout():
    """Pagina checkout per piani a pagamento"""
    if current_user.subscription_plan == 'starter':
        return redirect(url_for('pricing'))
    
    plan = SUBSCRIPTION_PLANS.get(current_user.subscription_plan)
    if not plan or not plan['stripe_price_id']:
        return redirect(url_for('pricing'))
    
    return render_template('checkout.html', plan=plan, user=current_user)

@app.route('/api/create-subscription', methods=['POST'])
@login_required
def create_subscription():
    """Crea abbonamento Stripe"""
    data = request.get_json()
    plan_id = data.get('plan')
    payment_method_id = data.get('payment_method_id')
    
    if plan_id not in SUBSCRIPTION_PLANS or not payment_method_id:
        return jsonify({'error': 'Dati mancanti'}), 400
    
    plan = SUBSCRIPTION_PLANS[plan_id]
    
    try:
        # Allega payment method al customer
        stripe.PaymentMethod.attach(
            payment_method_id,
            customer=current_user.stripe_customer_id
        )
        
        # Imposta come default payment method
        stripe.Customer.modify(
            current_user.stripe_customer_id,
            invoice_settings={'default_payment_method': payment_method_id}
        )
        
        # Crea subscription
        subscription = stripe.Subscription.create(
            customer=current_user.stripe_customer_id,
            items=[{'price': plan['stripe_price_id']}],
            trial_period_days=30 if plan_id == 'professional' else None,
            metadata={
                'user_id': current_user.id,
                'plan': plan_id
            }
        )
        
        # Aggiorna utente
        current_user.subscription_id = subscription.id
        current_user.subscription_plan = plan_id
        current_user.subscription_status = subscription.status
        
        if subscription.trial_end:
            current_user.trial_ends_at = datetime.fromtimestamp(subscription.trial_end)
        
        db.session.commit()
        
        # Log evento
        event = SubscriptionEvent(
            user_id=current_user.id,
            event_type='subscription_created',
            new_plan=plan_id,
            stripe_event_id=subscription.id
        )
        db.session.add(event)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'subscription_id': subscription.id,
            'redirect': '/dashboard'
        })
        
    except stripe.error.StripeError as e:
        return jsonify({'error': f'Errore pagamento: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': 'Errore interno del server'}), 500

@app.route('/api/cancel-subscription', methods=['POST'])
@login_required
def cancel_subscription():
    """Cancella abbonamento"""
    if not current_user.subscription_id:
        return jsonify({'error': 'Nessun abbonamento attivo'}), 400
    
    try:
        # Cancella su Stripe (alla fine del periodo)
        subscription = stripe.Subscription.modify(
            current_user.subscription_id,
            cancel_at_period_end=True
        )
        
        # Aggiorna stato locale
        current_user.subscription_status = 'canceled'
        current_user.subscription_ends_at = datetime.fromtimestamp(subscription.current_period_end)
        db.session.commit()
        
        # Log evento
        event = SubscriptionEvent(
            user_id=current_user.id,
            event_type='subscription_canceled',
            old_plan=current_user.subscription_plan
        )
        db.session.add(event)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Abbonamento cancellato. Resterà attivo fino alla fine del periodo.'
        })
        
    except stripe.error.StripeError as e:
        return jsonify({'error': f'Errore nella cancellazione: {str(e)}'}), 400

@app.route('/api/change-plan', methods=['POST'])
@login_required
def change_plan():
    """Cambia piano di abbonamento"""
    data = request.get_json()
    new_plan = data.get('plan')
    
    if new_plan not in SUBSCRIPTION_PLANS:
        return jsonify({'error': 'Piano non valido'}), 400
    
    old_plan = current_user.subscription_plan
    
    try:
        if new_plan == 'starter':
            # Downgrade a gratuito
            if current_user.subscription_id:
                stripe.Subscription.delete(current_user.subscription_id)
                current_user.subscription_id = None
            
            current_user.subscription_plan = 'starter'
            current_user.subscription_status = 'active'
            current_user.subscription_ends_at = None
            
        else:
            # Upgrade/Change piano
            plan = SUBSCRIPTION_PLANS[new_plan]
            
            if current_user.subscription_id:
                # Modifica subscription esistente
                subscription = stripe.Subscription.retrieve(current_user.subscription_id)
                stripe.Subscription.modify(
                    current_user.subscription_id,
                    items=[{
                        'id': subscription['items']['data'][0].id,
                        'price': plan['stripe_price_id']
                    }],
                    proration_behavior='always_invoice'
                )
            else:
                # Crea nuovo subscription
                subscription = stripe.Subscription.create(
                    customer=current_user.stripe_customer_id,
                    items=[{'price': plan['stripe_price_id']}]
                )
                current_user.subscription_id = subscription.id
            
            current_user.subscription_plan = new_plan
            current_user.subscription_status = 'active'
        
        db.session.commit()
        
        # Log evento
        event = SubscriptionEvent(
            user_id=current_user.id,
            event_type='plan_changed',
            old_plan=old_plan,
            new_plan=new_plan
        )
        db.session.add(event)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Piano cambiato da {old_plan} a {new_plan}'
        })
        
    except stripe.error.StripeError as e:
        return jsonify({'error': f'Errore nel cambio piano: {str(e)}'}), 400

@app.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    """Gestisce webhook da Stripe per sincronizzare stati"""
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    endpoint_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
    
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError:
        return jsonify({'error': 'Invalid signature'}), 400
    
    # Gestisci eventi Stripe
    if event['type'] == 'invoice.payment_succeeded':
        handle_payment_succeeded(event['data']['object'])
    elif event['type'] == 'invoice.payment_failed':
        handle_payment_failed(event['data']['object'])
    elif event['type'] == 'customer.subscription.updated':
        handle_subscription_updated(event['data']['object'])
    elif event['type'] == 'customer.subscription.deleted':
        handle_subscription_deleted(event['data']['object'])
    
    return jsonify({'success': True})

def handle_payment_succeeded(invoice):
    """Gestisce pagamento riuscito"""
    subscription_id = invoice.get('subscription')
    if not subscription_id:
        return
    
    user = User.query.filter_by(subscription_id=subscription_id).first()
    if user:
        user.subscription_status = 'active'
        db.session.commit()

def handle_payment_failed(invoice):
    """Gestisce pagamento fallito"""
    subscription_id = invoice.get('subscription')
    if not subscription_id:
        return
    
    user = User.query.filter_by(subscription_id=subscription_id).first()
    if user:
        user.subscription_status = 'past_due'
        db.session.commit()
        
        # Invia email di notifica (implementa sistema email)
        # send_payment_failed_email(user)

def handle_subscription_updated(subscription):
    """Gestisce aggiornamenti subscription"""
    user = User.query.filter_by(subscription_id=subscription['id']).first()
    if user:
        user.subscription_status = subscription['status']
        if subscription.get('current_period_end'):
            user.subscription_ends_at = datetime.fromtimestamp(subscription['current_period_end'])
        db.session.commit()

def handle_subscription_deleted(subscription):
    """Gestisce cancellazione subscription"""
    user = User.query.filter_by(subscription_id=subscription['id']).first()
    if user:
        user.subscription_plan = 'starter'
        user.subscription_status = 'active'
        user.subscription_id = None
        user.subscription_ends_at = None
        db.session.commit()

# Decoratori per controllo accessi
def require_plan(min_plan):
    """Decoratore che richiede un piano minimo"""
    def decorator(f):
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({'error': 'Login richiesto'}), 401
            
            plan_hierarchy = ['starter', 'professional', 'enterprise']
            user_level = plan_hierarchy.index(current_user.subscription_plan)
            required_level = plan_hierarchy.index(min_plan)
            
            if user_level < required_level:
                return jsonify({
                    'error': 'Piano insufficiente',
                    'required_plan': min_plan,
                    'current_plan': current_user.subscription_plan,
                    'upgrade_url': '/pricing'
                }), 403
            
            if not current_user.is_subscription_active():
                return jsonify({
                    'error': 'Abbonamento scaduto',
                    'renew_url': '/pricing'
                }), 403
            
            return f(*args, **kwargs)
        decorated_function.__name__ = f.__name__
        return decorated_function
    return decorator

def require_feature(feature_name):
    """Decoratore che richiede una specifica funzionalità"""
    def decorator(f):
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({'error': 'Login richiesto'}), 401
            
            if not current_user.has_feature(feature_name):
                return jsonify({
                    'error': f'Funzionalità {feature_name} non disponibile',
                    'upgrade_url': '/pricing'
                }), 403
            
            return f(*args, **kwargs)
        decorated_function.__name__ = f.__name__
        return decorated_function
    return decorator

# Routes API con controllo accessi
@app.route('/api/predictions')
@login_required
@require_feature('ai_predictions')
def get_predictions():
    """Endpoint per previsioni AI - solo piani Professional+"""
    # La tua logica esistente per le previsioni
    return jsonify({'predictions': []})

@app.route('/api/alerts')
@login_required
@require_feature('alerts')
def get_alerts():
    """Endpoint per alert - solo piani Professional+"""
    # La tua logica per gli alert
    return jsonify({'alerts': []})

@app.route('/api/advanced-analysis')
@login_required
@require_plan('professional')
def advanced_analysis():
    """Analisi avanzata - solo Professional+"""
    # Logica analisi avanzata
    return jsonify({'analysis': {}})

@app.route('/api/user/subscription')
@login_required
def get_user_subscription():
    """Restituisce info abbonamento utente corrente"""
    plan = SUBSCRIPTION_PLANS.get(current_user.subscription_plan, SUBSCRIPTION_PLANS['starter'])
    
    return jsonify({
        'plan': current_user.subscription_plan,
        'status': current_user.subscription_status,
        'features': plan['features'],
        'trial_ends_at': current_user.trial_ends_at.isoformat() if current_user.trial_ends_at else None,
        'subscription_ends_at': current_user.subscription_ends_at.isoformat() if current_user.subscription_ends_at else None,
        'is_active': current_user.is_subscription_active()
    })

# Template filters per Jinja2
@app.template_filter('currency')
def currency_filter(amount):
    """Formatta valuta"""
    return f"€{amount:,.0f}" if amount else "Gratuito"

@app.template_filter('feature_check')
def feature_check(user, feature_name):
    """Controlla se utente ha accesso a funzionalità"""
    if not user:
        return False
    return user.has_feature(feature_name)

# Inizializzazione database
def init_subscription_db():
    """Inizializza tabelle per abbonamenti"""
    db.create_all()
    
    # Crea utenti di esempio per testing (rimuovi in produzione)
    if not User.query.first():
        test_users = [
            {
                'email': 'starter@example.com',
                'first_name': 'Test',
                'last_name': 'Starter',
                'subscription_plan': 'starter'
            },
            {
                'email': 'pro@example.com', 
                'first_name': 'Test',
                'last_name': 'Professional',
                'subscription_plan': 'professional',
                'subscription_status': 'active'
            },
            {
                'email': 'enterprise@example.com',
                'first_name': 'Test', 
                'last_name': 'Enterprise',
                'subscription_plan': 'enterprise',
                'subscription_status': 'active'
            }
        ]
        
        for user_data in test_users:
            user = User(**user_data)
            db.session.add(user)
        
        db.session.commit()
        print("Utenti di esempio creati")

# Usage Analytics per business intelligence
class UsageMetric(db.Model):
    """Traccia utilizzo features per analytics"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    feature = db.Column(db.String(50), nullable=False)
    endpoint = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    metadata = db.Column(db.Text)  # JSON per dati aggiuntivi

def track_usage(feature_name, metadata=None):
    """Helper per tracciare utilizzo funzionalità"""
    if current_user.is_authenticated:
        metric = UsageMetric(
            user_id=current_user.id,
            feature=feature_name,
            endpoint=request.endpoint,
            metadata=metadata
        )
        db.session.add(metric)
        db.session.commit()

# Revenue Analytics
@app.route('/admin/analytics')
@login_required  # Aggiungi controllo admin
def admin_analytics():
    """Dashboard analytics per admin"""
    # MRR (Monthly Recurring Revenue)
    active_subs = User.query.filter(
        User.subscription_plan != 'starter',
        User.subscription_status == 'active'
    ).all()
    
    mrr = sum(SUBSCRIPTION_PLANS[user.subscription_plan]['price'] for user in active_subs)
    
    # Statistiche per piano
    plan_stats = {}
    for plan_id in SUBSCRIPTION_PLANS.keys():
        count = User.query.filter_by(subscription_plan=plan_id).count()
        plan_stats[plan_id] = count
    
    # Churn rate (utenti cancellati negli ultimi 30 giorni)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    churned = SubscriptionEvent.query.filter(
        SubscriptionEvent.event_type == 'subscription_canceled',
        SubscriptionEvent.created_at >= thirty_days_ago
    ).count()
    
    return jsonify({
        'mrr': mrr,
        'plan_distribution': plan_stats,
        'churned_last_30_days': churned,
        'total_users': User.query.count(),
        'active_subscriptions': len(active_subs)
    })

if __name__ == '__main__':
    # Setup per sviluppo
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cot_subscriptions.db'
    app.config['SECRET_KEY'] = 'dev-secret-key-change-in-production'
    
    db.init_app(app)
    
    with app.app_context():
        init_subscription_db()
    
    print("Sistema abbonamenti inizializzato!")
    print("Endpoints disponibili:")
    print("- POST /api/register - Registrazione utente")
    print("- GET /checkout - Pagina checkout")
    print("- POST /api/create-subscription - Crea abbonamento")
    print("- POST /api/cancel-subscription - Cancella abbonamento")
    print("- POST /api/change-plan - Cambia piano")
    print("- GET /api/user/subscription - Info abbonamento utente")
    print("- POST /webhook/stripe - Webhook Stripe")
    app.run(debug=True)