# populate_db.py - Esegui questo script per aggiungere dati di test

from app_complete import app, db, COTData
from datetime import datetime, timedelta
import random

with app.app_context():
    # Genera dati di test per gli ultimi 30 giorni
    symbols = ['GOLD', 'EUR', 'USD', 'GBP']
    
    for symbol in symbols:
        for i in range(30):
            date = datetime.now() - timedelta(days=i)
            
            # Genera dati casuali ma realistici
            nc_long = random.randint(150000, 300000)
            nc_short = random.randint(100000, 250000)
            c_long = random.randint(180000, 350000)
            c_short = random.randint(150000, 320000)
            
            net_pos = nc_long - nc_short
            sentiment = ((nc_long - nc_short) / (nc_long + nc_short)) * 100
            
            data = COTData(
                symbol=symbol,
                date=date,
                non_commercial_long=nc_long,
                non_commercial_short=nc_short,
                non_commercial_spreads=0,
                commercial_long=c_long,
                commercial_short=c_short,
                net_position=net_pos,
                sentiment_score=sentiment
            )
            
            db.session.add(data)
    
    db.session.commit()
    print("Database popolato con dati di test!")