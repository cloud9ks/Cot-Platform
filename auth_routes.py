# auth_routes.py - Routes Autenticazione e Abbonamenti
"""
Gestione login, registrazione, pagamenti Stripe e abbonamenti
"""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, create_subscription_event, SUBSCRIPTION_PLANS
import stripe
import os
from datetime import datetime, timedelta

# Inizializza Stripe
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

# Blueprint
auth_bp = Blueprint('auth', __name__)

# ==========================================
# REGISTRAZIONE
# ==========================================

@auth_bp.route('/register', methods=['GET'])
def register_page():
    """Pagina registrazione"""
    plan = request.args.get('plan', 'starter')
    if plan not in SUBSCRIPTION_PLANS:
        plan = 'starter'
    return render_template('register.html', selected_plan=plan)

@auth_bp.route('/auth/register', methods=['POST'])
def register():
    """API Registrazione utente"""
    data = request.get_json()
    
    # Validazione
    required = ['firstName', 'lastName', 'email', 'password', 'plan']
    if not all(data.get(field) for field in required):
        return jsonify({'error': 'Tutti i campi sono obbligatori'}), 400
    
    email = data['email'].lower().strip()
    plan = data['plan']
    
    # Controlla email esistente
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email già registrata'}), 400
    
    # Valida piano
    if plan not in SUBSCRIPTION_PLANS:
        return jsonify({'error': 'Piano non valido'}), 400
    
    try:
        # Crea Stripe Customer
        stripe_customer = stripe.Customer.create(
            email=email,
            name=f"{data['firstName']} {data['lastName']}",
            metadata={
                'platform': 'cot_analysis',
                'plan': plan
            }
        )
        
        # Crea utente
        user = User(
            email=email,
            first_name=data['firstName'],
            last_name=data['lastName'],
            stripe_customer_id=stripe_customer.id,
            subscription_plan=plan,
            subscription_status='incomplete',  # Sarà 'active' dopo il pagamento
            newsletter=data.get('marketing', False)
        )
        user.set_password(data['password'])
        
        # Se piano Starter, attiva subito il trial
        if plan == 'starter':
            user.subscription_status = 'trialing'
            user.trial_ends_at = datetime.utcnow() + timedelta(days=30)
        
        db.session.add(user)
        db.session.commit()
        
        # Log evento
        create_subscription_event(
            user=user,
            event_type='user_created',
            new_plan=plan
        )
        
        # Login automatico
        login_user(user)
        
        # Determina redirect
        if plan == 'starter':
            # Starter va diretto alla dashboard (trial gratuito)
            return jsonify({
                'success': True,
                'redirect': '/dashboard',
                'message': 'Account creato! Hai 30 giorni di prova gratuita.'
            })
        else:
            # Professional va al checkout
            return jsonify({
                'success': True,
                'redirect': '/checkout',
                'message': 'Account creato! Completa il pagamento per attivare.'
            })
        
    except stripe.error.StripeError as e:
        return jsonify({'error': f'Errore Stripe: {str(e)}'}), 500
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Errore nella registrazione'}), 500

# ==========================================
# LOGIN
# ==========================================

@auth_bp.route('/login', methods=['GET'])
def login_page():
    """Pagina login"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@auth_bp.route('/auth/login', methods=['POST'])
def login():
    """API Login"""
    data = request.get_json()
    
    email = data.get('email', '').lower().strip()
    password = data.get('password', '')
    
    if not email or not password:
        return jsonify({'error': 'Email e password obbligatori'}), 400
    
    # Trova utente
    user = User.query.filter_by(email=email).first()
    
    if not user or not user.check_password(password):
        return jsonify({'error': 'Credenziali non valide'}), 401
    
    if not user.is_active:
        return jsonify({'error': 'Account disattivato'}), 403
    
    # Login
    login_user(user, remember=True)
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'success': True,
        'redirect': '/dashboard',
        'message': f'Benvenuto {user.first_name}!'
    })

@auth_bp.route('/logout')
@login_required
def logout():
    """Logout utente"""
    logout_user()
    return redirect(url_for('index'))

# ==========================================
# CHECKOUT STRIPE
# ==========================================

@auth_bp.route('/checkout')
@login_required
def checkout_page():
    """Pagina checkout per piani a pagamento"""
    # Solo per utenti che devono pagare
    if current_user.subscription_plan == 'starter' and current_user.has_active_subscription():
        return redirect(url_for('dashboard'))
    
    plan_info = current_user.get_plan_info()
    
    return render_template('checkout.html', 
                         plan=plan_info,
                         user=current_user,
                         stripe_key=os.environ.get('STRIPE_PUBLISHABLE_KEY'))

@auth_bp.route('/api/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    """Crea sessione Stripe Checkout"""
    data = request.get_json()
    plan = data.get('plan', current_user.subscription_plan)
    
    if plan not in SUBSCRIPTION_PLANS:
        return jsonify({'error': 'Piano non valido'}), 400
    
    plan_info = SUBSCRIPTION_PLANS[plan]
    
    try:
        # Crea Stripe Checkout Session
        checkout_session = stripe.checkout.Session.create(
            customer=current_user.stripe_customer_id,
            payment_method_types=['card'],
            mode='subscription',
            line_items=[{
                'price': plan_info['price_id'],
                'quantity': 1,
            }],
            success_url=request.host_url + 'checkout/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.host_url + 'checkout/cancel',
            metadata={
                'user_id': current_user.id,
                'plan': plan
            },
            allow_promotion_codes=True,  # Permette codici sconto
            billing_address_collection='required',
        )
        
        return jsonify({
            'success': True,
            'checkoutUrl': checkout_session.url,
            'sessionId': checkout_session.id
        })
        
    except stripe.error.StripeError as e:
        return jsonify({'error': f'Errore Stripe: {str(e)}'}), 500

@auth_bp.route('/checkout/success')
@login_required
def checkout_success():
    """Pagina successo dopo pagamento"""
    session_id = request.args.get('session_id')
    
    if session_id:
        try:
            # Recupera sessione Stripe
            session = stripe.checkout.Session.retrieve(session_id)
            
            # Aggiorna utente (verrà comunque aggiornato dal webhook)
            if session.payment_status == 'paid':
                current_user.subscription_status = 'active'
                db.session.commit()
        except:
            pass
    
    return render_template('checkout_success.html')

@auth_bp.route('/checkout/cancel')
@login_required
def checkout_cancel():
    """Pagina cancellazione checkout"""
    return render_template('checkout_cancel.html')

# ==========================================
# GESTIONE ABBONAMENTO
# ==========================================

@auth_bp.route('/api/subscription/cancel', methods=['POST'])
@login_required
def cancel_subscription():
    """Cancella abbonamento (alla fine del periodo)"""
    if not current_user.stripe_subscription_id:
        return jsonify({'error': 'Nessun abbonamento attivo'}), 400
    
    try:
        # Cancella alla fine del periodo
        subscription = stripe.Subscription.modify(
            current_user.stripe_subscription_id,
            cancel_at_period_end=True
        )
        
        # Aggiorna database
        current_user.subscription_cancel_at = datetime.fromtimestamp(
            subscription.current_period_end
        )
        db.session.commit()
        
        # Log
        create_subscription_event(
            user=current_user,
            event_type='subscription_canceled',
            old_plan=current_user.subscription_plan
        )
        
        return jsonify({
            'success': True,
            'message': f'Abbonamento cancellato. Resterà attivo fino al {current_user.subscription_cancel_at.strftime("%d/%m/%Y")}'
        })
        
    except stripe.error.StripeError as e:
        return jsonify({'error': f'Errore: {str(e)}'}), 500

@auth_bp.route('/api/subscription/reactivate', methods=['POST'])
@login_required
def reactivate_subscription():
    """Riattiva abbonamento cancellato"""
    if not current_user.stripe_subscription_id:
        return jsonify({'error': 'Nessun abbonamento da riattivare'}), 400
    
    try:
        # Rimuovi cancellazione programmata
        stripe.Subscription.modify(
            current_user.stripe_subscription_id,
            cancel_at_period_end=False
        )
        
        current_user.subscription_cancel_at = None
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Abbonamento riattivato con successo!'
        })
        
    except stripe.error.StripeError as e:
        return jsonify({'error': f'Errore: {str(e)}'}), 500

@auth_bp.route('/api/subscription/portal', methods=['POST'])
@login_required
def customer_portal():
    """Crea sessione Customer Portal Stripe"""
    try:
        portal_session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=request.host_url + 'profile'
        )
        
        return jsonify({
            'success': True,
            'url': portal_session.url
        })
        
    except stripe.error.StripeError as e:
        return jsonify({'error': f'Errore: {str(e)}'}), 500

# ==========================================
# WEBHOOK STRIPE
# ==========================================

@auth_bp.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    """Gestisce webhook Stripe"""
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError:
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError:
        return jsonify({'error': 'Invalid signature'}), 400
    
    # Gestisci eventi
    event_type = event['type']
    event_data = event['data']['object']
    
    print(f"📬 Webhook ricevuto: {event_type}")
    
    if event_type == 'checkout.session.completed':
        handle_checkout_completed(event_data)
    elif event_type == 'customer.subscription.updated':
        handle_subscription_updated(event_data)
    elif event_type == 'customer.subscription.deleted':
        handle_subscription_deleted(event_data)
    elif event_type == 'invoice.payment_succeeded':
        handle_payment_succeeded(event_data)
    elif event_type == 'invoice.payment_failed':
        handle_payment_failed(event_data)
    
    return jsonify({'success': True})

# Handler webhook

def handle_checkout_completed(session):
    """Checkout completato"""
    customer_id = session.get('customer')
    subscription_id = session.get('subscription')
    
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        return
    
    user.stripe_subscription_id = subscription_id
    user.subscription_status = 'active'
    db.session.commit()
    
    create_subscription_event(
        user=user,
        event_type='payment_completed',
        new_plan=user.subscription_plan,
        stripe_event_id=session.get('id')
    )

def handle_subscription_updated(subscription):
    """Abbonamento aggiornato"""
    user = User.query.filter_by(
        stripe_subscription_id=subscription['id']
    ).first()
    
    if not user:
        return
    
    user.subscription_status = subscription['status']
    user.subscription_current_period_end = datetime.fromtimestamp(
        subscription['current_period_end']
    )
    db.session.commit()

def handle_subscription_deleted(subscription):
    """Abbonamento eliminato"""
    user = User.query.filter_by(
        stripe_subscription_id=subscription['id']
    ).first()
    
    if not user:
        return
    
    old_plan = user.subscription_plan
    
    # Downgrade a starter
    user.subscription_plan = 'starter'
    user.subscription_status = 'canceled'
    user.stripe_subscription_id = None
    user.subscription_current_period_end = None
    db.session.commit()
    
    create_subscription_event(
        user=user,
        event_type='subscription_deleted',
        old_plan=old_plan,
        new_plan='starter'
    )

def handle_payment_succeeded(invoice):
    """Pagamento riuscito"""
    customer_id = invoice.get('customer')
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    
    if user:
        user.subscription_status = 'active'
        db.session.commit()

def handle_payment_failed(invoice):
    """Pagamento fallito"""
    customer_id = invoice.get('customer')
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    
    if user:
        user.subscription_status = 'past_due'
        db.session.commit()
        
        # TODO: Invia email di notifica
