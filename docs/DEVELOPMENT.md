# Développer Sharp PC-G Link

[English](DEVELOPMENT_EN.md) · [Accueil](../README.md)

Le seul point d’entrée public est **Sharp PC-G Link.pyw**. `sharp_link/gui.py` possède la fenêtre, les préférences et la liaison série commune ; `RomDumpPanel` est intégré comme deuxième onglet. Les anciennes interfaces restent disponibles pour les sessions manuelles, via `--rom-dump --manual` ou `--session chemin/session.json`.

Depuis la racine, avec Python 3.10+ :

```text
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python tools/render_manual.py
python tools/package_source.py --lang fr
```

Les tests de l’interface utilisent de vrais widgets Tk et des ports simulés. Ils nécessitent une session graphique. Ils ne font aucun transfert vers un appareil connecté et n’utilisent pas les préférences personnelles.

Pour construire la version Windows autonome et les archives :

```text
python -m pip install -r tools/requirements-build.txt
python tools/build_windows.py
```

Les résultats sont placés dans `dist/` et dans `deliverables/` à côté du dépôt. Le build embarque les agents ROM, exemples et guides hors ligne. L’exécutable n’a pas besoin de Python sur la machine de destination. Les archives ne contiennent ni environnement local, ni INI personnel, ni ROM utilisateur.

`tools/setup/` conserve des scripts console de dépannage pour les associations `.pyw` défectueuses. `tools/legacy/` contient les anciens points d’entrée ; ils ne sont pas requis pour un nouvel utilisateur. Le lanceur racine propose lui-même la préparation graphique des dépendances si nécessaire.

Pour reconstruire ou tester le code Z80, voir [le guide ROM](../romdump/AUTOMATIC.md). Les binaires de l’agent fournis suffisent à l’utilisation normale.
