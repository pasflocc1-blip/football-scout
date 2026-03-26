import os
import argparse

# Crea File Unico py 
# D:\Progetti\football-scout\Utility\concat_project.py . --ext .md --ignore venv -o football-scout_Backend.txt
# D:\Progetti\football-scout\Utility\concat_project.py . --ext .md --ignore venv -o football-scout_Frontend.txt

# Estensioni da includere
DEFAULT_EXTENSIONS = {".py", ".vue", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml", ".env.example", ".md", ".sql"}

# Cartelle da ignorare
DEFAULT_IGNORE = {
    ".git", ".svn", "__pycache__", ".pytest_cache",
    "node_modules", ".next", ".nuxt", "dist", "build",
    ".venv", "venv", "env", ".idea", ".vscode",
}

def should_ignore_dir(name, ignore_set):
    return name in ignore_set

def collect_files(root_path, extensions, ignore_dirs):
    collected = []
    for dirpath, dirnames, filenames in os.walk(root_path):
        # Rimuovi cartelle da ignorare (modifica in-place per os.walk)
        dirnames[:] = [d for d in dirnames if not should_ignore_dir(d, ignore_dirs)]

        for filename in sorted(filenames):
            _, ext = os.path.splitext(filename)
            if ext in extensions:
                full_path = os.path.join(dirpath, filename)
                relative_path = os.path.relpath(full_path, root_path)
                collected.append((relative_path, full_path))

    return sorted(collected)

def concat_files(root_path, output_file, extensions, ignore_dirs):
    files = collect_files(root_path, extensions, ignore_dirs)

    if not files:
        print("⚠️  Nessun file trovato con le estensioni specificate.")
        print(f"⚠️ root_path : {root_path}")
        return

    with open(output_file, "w", encoding="utf-8") as out:
        out.write(f"PROGETTO: {os.path.abspath(root_path)}\n")
        out.write(f"TOTALE FILE: {len(files)}\n")
        out.write("=" * 60 + "\n\n")

        for relative_path, full_path in files:
            separator = "=" * 60
            out.write(f"{separator}\n")
            out.write(f"FILE: {relative_path}\n")
            out.write(f"{separator}\n")

            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                out.write(content)
                if not content.endswith("\n"):
                    out.write("\n")
            except Exception as e:
                out.write(f"[ERRORE LETTURA FILE: {e}]\n")

            out.write("\n\n")

    print(f"✅ Concatenati {len(files)} file in: {output_file}")
    print("\nFile inclusi:")
    for relative_path, _ in files:
        print(f"  {relative_path}")

def main():
    parser = argparse.ArgumentParser(
        description="Concatena tutti i file sorgente di un progetto in un unico file .txt"
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Percorso della cartella radice del progetto (default: cartella corrente)"
    )
    parser.add_argument(
        "-o", "--output",
        default="progetto_completo.txt",
        help="Nome del file di output (default: progetto_completo.txt)"
    )
    parser.add_argument(
        "--ext",
        nargs="*",
        default=None,
        help="Estensioni da includere (es. --ext .py .js). Default include le più comuni."
    )
    parser.add_argument(
        "--ignore",
        nargs="*",
        default=[],
        help="Cartelle aggiuntive da ignorare"
    )
    args = parser.parse_args()

    extensions = set(args.ext) if args.ext else DEFAULT_EXTENSIONS
    ignore_dirs = DEFAULT_IGNORE | set(args.ignore)

    concat_files(
        root_path=args.path,
        output_file=args.output,
        extensions=extensions,
        ignore_dirs=ignore_dirs
    )

if __name__ == "__main__":
    main()