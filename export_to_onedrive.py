import os

def export_all_to_onedrive():
    """Stub d'export : crée un fichier d'export dans /var/www/skyjo/exports et retourne le chemin."""
    export_dir = os.path.join(os.path.dirname(__file__), 'exports')
    os.makedirs(export_dir, exist_ok=True)
    path = os.path.join(export_dir, 'export_' + str(int(__import__('time').time())) + '.txt')
    with open(path, 'w') as f:
        f.write('Export dummy')
    return path
