# models.py - Modelli Database COT Analysis Platform
"""
Sistema unificato per gestione utenti e abbonamenti
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os

db = SQLAlchemy()

# ==========================================
# CONFIGURAZIONE PIANI
# ==========================================

SUBSCRIPTION_PLANS = {
    'starter': {
        'name': 'Starter',
        'price': 12.99,
        'price_id': os.environ.get('STRIPE_STARTER_PRICE_ID'),
        'trial_days': 30,
        'features': {
            'max_assets': 5,
            'cot_data': True,
            'basic_charts': True,
            'ai_predictions': False,
            'advanced_analysis': False,
            'alerts': False,
            'export_data': False,
            'api_access': False,
        }
    },
    'professional': {
        'name': 'Professional',
        'price': 49.00,
        'price_id': os.environ.get('STRIPE_PROFESSIONAL_PRICE_ID'),
        'trial_days': 0,  # Nessun trial per Professional
        'features': {
            'max_assets': -1,  # Illimitato
            'cot_data': True,
            'basic_charts': True,
            'ai_predictions': True,
            'advanced_analysis': True,
            'alerts': True,
            'export_data': True,
            'api_access': True,
        }
    }
}

# ==========================================
# MODELLO USER
# ==========================================

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    # Info base
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    
    # Ruolo e status
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    email_verified = db.Column(db.Boolean, default=False)
    
    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # ===== STRIPE & SUBSCRIPTION =====
    stripe_customer_id = db.Column(db.String(100), unique=True, index=True)
    subscription_plan = db.Column(db.String(20), default='starter')
    subscription_status = db.Column(db.String(20), default='active')
    stripe_subscription_id = db.Column(db.String(100), unique=True)
    
    # Date abbonamento
    trial_ends_at = db.Column(db.DateTime)
    subscription_current_period_end = db.Column(db.DateTime)
    subscription_cancel_at = db.Column(db.DateTime)
    
    # Preferenze
    email_notifications = db.Column(db.Boolean, default=True)
    newsletter = db.Column(db.Boolean, default=False)
    
    # Relazioni
    subscription_events = db.relationship('SubscriptionEvent', backref='user', lazy='dynamic')
    
    def set_password(self, password):
        """Hash della password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verifica password"""
        return check_password_hash(self.password_hash, password)
    
    # ===== METODI ABBONAMENTO =====
    
    def has_active_subscription(self):
        """Controlla se l'abbonamento è attivo"""
        # Starter è sempre attivo
        if self.subscription_plan == 'starter':
            return True
        
        # Controllo status
        if self.subscription_status not in ['active', 'trialing']:
            return False
        
        # Controllo periodo corrente
        if self.subscription_current_period_end:
            return self.subscription_current_period_end > datetime.utcnow()
        
        return False
    
    def is_in_trial(self):
        """Controlla se è in periodo di prova"""
        if not self.trial_ends_at:
            return False
        return self.trial_ends_at > datetime.utcnow()
    
    def get_plan_info(self):
        """Restituisce info del piano corrente"""
        return SUBSCRIPTION_PLANS.get(self.subscription_plan, SUBSCRIPTION_PLANS['starter'])
    
    def has_feature(self, feature_name):
        """Controlla accesso a una feature"""
        if not self.has_active_subscription():
            return False
        
        plan = self.get_plan_info()
        return plan['features'].get(feature_name, False)
    
    def can_access_asset(self, asset_count):
        """Controlla se può monitorare più asset"""
        if not self.has_active_subscription():
            return False
        
        plan = self.get_plan_info()
        max_assets = plan['features']['max_assets']
        
        # -1 significa illimitato
        if max_assets == -1:
            return True
        
        return asset_count < max_assets
    
    def get_days_until_renewal(self):
        """Giorni rimanenti fino al rinnovo"""
        if not self.subscription_current_period_end:
            return None
        
        delta = self.subscription_current_period_end - datetime.utcnow()
        return max(0, delta.days)
    
    def __repr__(self):
        return f'<User {self.email} - {self.subscription_plan}>'

# ==========================================
# LOG EVENTI ABBONAMENTO
# ==========================================

class SubscriptionEvent(db.Model):
    __tablename__ = 'subscription_events'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Tipo evento
    event_type = db.Column(db.String(50), nullable=False)
    # Possibili valori: 'created', 'updated', 'canceled', 'renewed', 
    # 'trial_started', 'trial_ended', 'payment_failed', 'upgraded', 'downgraded'
    
    # Piano
    old_plan = db.Column(db.String(20))
    new_plan = db.Column(db.String(20))
    
    # Stripe
    stripe_event_id = db.Column(db.String(100))
    stripe_invoice_id = db.Column(db.String(100))
    
    # Metadata (JSON serializzato come stringa)
    metadata = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<SubscriptionEvent {self.event_type} for user {self.user_id}>'

# ==========================================
# FUNZIONI HELPER
# ==========================================

def init_db(app):
    """Inizializza database"""
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
        
        # Crea admin se non esiste
        admin = User.query.filter_by(email='admin@cotanalysis.com').first()
        if not admin:
            admin = User(
                email='admin@cotanalysis.com',
                first_name='Admin',
                last_name='COT',
                is_admin=True,
                subscription_plan='professional',
                subscription_status='active'
            )
            admin.set_password('admin123')  # CAMBIA IN PRODUZIONE!
            db.session.add(admin)
            db.session.commit()
            print("✅ Admin user creato: admin@cotanalysis.com / admin123")

def create_subscription_event(user, event_type, old_plan=None, new_plan=None, 
                             stripe_event_id=None, metadata=None):
    """Helper per creare eventi abbonamento"""
    event = SubscriptionEvent(
        user_id=user.id,
        event_type=event_type,
        old_plan=old_plan,
        new_plan=new_plan,
        stripe_event_id=stripe_event_id,
        metadata=metadata
    )
    db.session.add(event)
    db.session.commit()
    return event
