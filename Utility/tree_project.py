import os


def print_tree(startpath, exclude_dirs):
    for root, dirs, files in os.walk(startpath):
        # Filtra le cartelle da escludere "in place"
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        # Calcola il livello di profondità
        level = root.replace(startpath, '').count(os.sep)
        indent = ' ' * 4 * (level)

        # Stampa il nome della cartella corrente
        if root == startpath:
            print(f"{os.path.abspath(root)}")
        else:
            print(f"{indent}├── {os.path.basename(root)}/")

        # Stampa i file nella cartella corrente
        sub_indent = ' ' * 4 * (level + 1)
        for f in files:
            if f != os.path.basename(__file__):  # Salta lo script stesso
                print(f"{sub_indent}└── {f}")


# Configurazione
folders_to_ignore = ['venv', '.idea', '__pycache__', 'uploads', '.git']

if __name__ == "__main__":
    # Avvia dalla cartella corrente
    print_tree("../", folders_to_ignore)