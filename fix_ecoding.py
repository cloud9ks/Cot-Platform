import os
import re

def fix_encoding(file_path):
    """Corregge encoding UTF-8 corrotto"""
    replacements = {
        'FunzionalitÃ ': 'Funzionalità',
        'piÃ¹': 'più',
        'Ã¨': 'è',
        'Ãˆ': 'È',
        'Ã ': 'à',
        'â‚¬': '€',
        'Â·': '·',
        'Ã¢â‚¬â€œ': '—',
        'Ã¢â‚¬Â¢': '•',
        'Ã°Å¸': '📈',
        'Ã¯': 'ï',
        'âœ"': '✓',
        'âœ…': '✅',
        'Ã°Å¸â€': '📊',
        'Ã°Å¸Å½Â¯': '📈',
        'Ã°Å¸â€œ': '📋',
        'Ã°Å¸Â¤â€': '🤖',
        'Ã°Å¸â€™Â°': '🌐',
        'Ã°Å¸â€Â§': '🔧',
        'Ã°Å¸â€œâ€¦': '📅',
        'Ã°Å¸â€œË†': '📈',
        'Ã°Å¸â€œâ€¹': '📊',
        'Ã°Å¸â€œâ€': '📊',
        'Ã°Å¸Å½Â¯': '📊',
        'â–²': '▲',
        'â–¼': '▼',
        'â—': '●',
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        for wrong, correct in replacements.items():
            content = content.replace(wrong, correct)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✓ Fixed: {file_path}")
    except Exception as e:
        print(f"✗ Error in {file_path}: {e}")

# Lista file da correggere
html_files = [
    'templates/index.html',
    'templates/register.html',
    'templates/login.html',
    'templates/dashboard.html',
    'templates/features.html',
    'templates/pricing.html',
    'templates/about.html',
    'templates/contact.html'
]

for file_path in html_files:
    if os.path.exists(file_path):
        fix_encoding(file_path)
    else:
        print(f"⚠ File not found: {file_path}")

print("\n✓ Encoding fix completed!")