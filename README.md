# Sharp PC-G Link 1.7.1

[Français](#francais) · [English](#english)

<a id="francais"></a>

## Français

Transfert de programmes BASIC et assembleur, et sauvegarde des ROM des Sharp PC-E200 / PC-G, dans une même application Windows en français et en anglais. © 2026 P.RAIMBAULT. Licence [MIT](LICENSE.txt) ; [provenance](NOTICE.md).

### Lancer l’application

**Version Windows autonome :** extraire toute l’archive, puis ouvrir **Sharp PC-G Link.exe**. Python n’est pas nécessaire.

**Version source / GitHub :** installer Python 3.10 ou supérieur avec Tkinter, extraire tout le dossier, puis double-cliquer sur **Sharp PC-G Link.pyw**, le seul lanceur à la racine. Si pyserial manque, une fenêtre propose de préparer un environnement local `.venv` et d’installer `pyserial==3.5`. Internet est nécessaire pour cette préparation seulement. Les lancements suivants réutilisent les dépendances disponibles. Sous Windows, les fichiers `.pyw` doivent être associés à Python.

Conserver ensemble le lanceur et les sous-dossiers. Ne pas lancer depuis l’archive ZIP. Le [pilote VCP FTDI](https://ftdichip.com/drivers/vcp-drivers/) est nécessaire si le câble n’expose pas encore de port COM. L’application ne programme pas l’inversion des signaux FTDI.



Il faut un adaptateur série compatible avec le connecteur et les niveaux électriques du Sharp, avec **RTS/CTS**, et un câble USB de données. Un adaptateur RS-232 classique ne se branche pas directement. Extraire le programme dans un dossier accessible en écriture pour enregistrer les préférences.

### Une fenêtre, deux onglets

- **Transfert de programmes** : boutons distincts **Envoyer BASIC** et **Envoyer ASM**, éditeur BASIC, aperçu mémoire, réception, référence et journal.
- **Sauvegarde ROM** : envoi du dumper, puis réception automatique de toutes les banques choisies. Aucune session à préparer. Un seul `G100` lance le parcours sur le Sharp, avec deux lectures par bloc, CRC, acquittements et contrôle de fin.

Les réglages série au-dessus des onglets sont communs. Une seule opération série peut être active à la fois. La langue, le modèle, le port, la trame, les temporisations et les adresses sont enregistrés automatiquement dans `sharp_pc_g_link.ini`, à côté du lanceur ou de l’exécutable. Les réglages existants sont conservés lors des mises à jour.

### Régler la liaison avant le transfert

Au premier lancement : **1200 bauds / 7N1**. Pour accélérer, utiliser **Conseillés : 4800 / 8N1**. Le dumper ROM nécessite **4800 / 8N1**. RTS/CTS est imposé ; XON/XOFF est désactivé.

**Sur le Sharp, ouvrir TEXT → Sio → Format**, sélectionner les mêmes débit, bits de données, parité et bits de stop que sur le PC, puis **valider avec ENTER**. Régler **RS/CS**, **CR LF**, **EOF 1A** et, pour un listing BASIC numéroté, **Line number = Yes** si proposés. L’application ne change pas les réglages du Sharp à distance.

**En cas d’erreur de transfert, d’I/O DEVICE ERROR ou si la commande `R` revient directement au moniteur : revérifier TEXT → Sio → Format en premier**, notamment après un RESET. Contrôler ensuite le port COM, le câble, le mode RS/CS et l’inversion FTDI. Le retour immédiat de `R` ne prouve pas une panne de mémoire.

### Charger un programme

**BASIC :** choisir un `.bas` ou un exemple, puis sur le Sharp **TEXT → Sio → Load** et sur le PC **Envoyer BASIC**. Après réception, retrouver le listing dans **TEXT → Edit**, le convertir avec **TEXT → Basic → Basic←text**, puis **BASIC / RUN MODE → RUN**. Le nom de fichier PC n’est pas transmis. Sauvegarder le BASIC existant avant la conversion, qui le remplace.

**Assembleur :** choisir un `.bin` ou `.hex` dans le cadre Assembleur. Pour un BIN, respecter son adresse d’assemblage. Sur le Sharp, ouvrir **MON**, réserver la mémoire avec la commande `USER` indiquée par le programme, puis **R**. Cliquer sur **Envoyer ASM**, attendre la fin et exécuter `G` suivi de l’adresse d’entrée, par exemple `G100`. L’application affiche les commandes pour les exemples inclus ; suivre la documentation de chaque programme pour sa réservation. Le PC-G820 utilise un autre accès au moniteur, détaillé dans le manuel.

Si `FRE` indique une quantité incohérente proche de 64 Ko sur un G801 de 8 Ko : sauvegarder les données, faire **RESET**, puis répondre **Y** à **MEMORY CLEAR O.K. ?**. Cette confirmation efface la mémoire. Revérifier ensuite `FRE` et les réglages SIO.

### Sauvegarder sa ROM

Deux actions suffisent ; **aucune session à créer ou à reprendre manuellement**.

1. Choisir le modèle et **4800 / 8N1**, également dans **TEXT → Sio → Format** sur le Sharp. Le dossier de destination est mémorisé ; s’il est vide, il est demandé au premier envoi.
2. Sauvegarder les programmes à conserver, car le dumper remplace le programme assembleur en RAM. Sur G801 : **MON → USER0AFF → R**. Cliquer **1. Envoyer le dumper** sur le PC.
3. Attendre la fin du chargement. Cliquer **2. Recevoir la ROM entière** sur le PC, puis saisir **G100 une seule fois** sur le Sharp.
4. Attendre la confirmation de fin. **Ouvrir le dossier** retrouve les images et le rapport de vérification. Chaque sauvegarde terminée reçoit automatiquement son propre sous-dossier daté, sans écraser les précédentes.

Les deux lectures, CRC, captures de contrôle et informations de reprise restent gérés automatiquement. Après interruption, appuyer sur **BREAK sur le Sharp**, puis renvoyer le dumper et relancer la réception depuis la même fenêtre ; les blocs déjà vérifiés sont conservés. Il n’y a ni commande W ni G103 entre les blocs.

Le dumper automatique utilise les routines du firmware : son support matériel est établi pour le **PC-G805** ; les autres profils et révisions de ROM nécessitent une vérification. Le nombre de sélecteurs sondés ne prouve pas la taille physique de la ROM. Aucune ROM personnelle n’est incluse dans le projet ni ses archives.

### Guides et contenu du dépôt

- [Manuel de transfert et dépannage](docs/TRANSFER.md) — procédures détaillées, paramètres, réception, diagnostic CTS et exemples.
- [Guide de sauvegarde ROM](romdump/AUTOMATIC.md) — modèles, reprise, fichiers et limites.
- `examples/` : exemples BASIC et assembleur ; `sharp_link/` : application ; `romdump/` : agent et documentation.
- `tools/` et `tests/` : maintenance et développement ; [guide développeur](docs/DEVELOPMENT.md).

Les profils de transfert couvrent PC-E200, PC-G801, G802, G803, G805, G811, G813, G815, G820, G830, G850, G850S, G850V et G850VS. Choisir un modèle ne rend pas tout programme compatible avec sa RAM, son écran ou ses routines ROM.

---

<a id="english"></a>

## English

[Français](#francais)

BASIC and assembly program transfer, plus Sharp PC-E200 / PC-G ROM backup, in one French/English Windows application. © 2026 P.RAIMBAULT. [MIT license](LICENSE.txt); [provenance](NOTICE.md).

### Start the application

**Standalone Windows release:** extract the entire archive and open **Sharp PC-G Link.exe**. Python is not required.

**Source / GitHub release:** install Python 3.10 or newer with Tkinter, extract the entire folder, and double-click **Sharp PC-G Link.pyw**, the only launcher at the root. If pyserial is missing, a setup window offers to create a local `.venv` and install `pyserial==3.5`. Internet is needed for this preparation only. Later launches reuse the available dependencies. Windows must associate `.pyw` files with Python.

Keep the launcher and its subfolders together. Do not run from inside a ZIP archive. Install the [FTDI VCP driver](https://ftdichip.com/drivers/vcp-drivers/) if the cable does not expose a COM port. The application does not program FTDI signal inversion.



Use a serial adapter matching the Sharp connector and electrical levels, with **RTS/CTS**, and a USB data cable. A standard RS-232 adapter cannot connect directly. Extract the application into a writable folder so it can save preferences.

### One window, two tabs

- **Program transfer:** separate **Send BASIC** and **Send ASM** buttons, BASIC editor, memory preview, reception, reference and log.
- **ROM backup:** send the dumper, then automatically receive all selected banks. No session setup is required. A single `G100` on Sharp runs the sequence with two reads per block, CRC, acknowledgements and an end marker.

Serial settings above the tabs are shared. Only one serial operation can run at a time. Language, model, port, framing, delays and addresses are saved automatically in `sharp_pc_g_link.ini` beside the launcher or executable. Updates preserve existing preferences.

### Configure the link before transferring

First-run defaults: **1200 baud / 7N1**. For faster transfers use **Recommended: 4800 / 8N1**. ROM backup requires **4800 / 8N1**. RTS/CTS is enforced; XON/XOFF is disabled.

**On Sharp, open TEXT → Sio → Format**, select the same baud rate, data bits, parity and stop bits as on the PC, then **confirm with ENTER**. Select **RS/CS**, **CR LF**, **EOF 1A**, and **Line number = Yes** for numbered BASIC listings where available. The application cannot configure Sharp remotely.

**If transfer fails, I/O DEVICE ERROR appears, or `R` returns immediately to the monitor, check TEXT → Sio → Format first**, especially after RESET. Then check the COM port, cable, RS/CS mode and FTDI inversion. An immediate return from `R` does not prove a memory fault.

### Load a program

**BASIC:** select a `.bas` or an example. On Sharp choose **TEXT → Sio → Load**, then click **Send BASIC** on the PC. After reception, find the listing in **TEXT → Edit**, convert it using **TEXT → Basic → Basic←text**, then select **BASIC / RUN MODE → RUN**. The PC filename is not sent. Back up any existing BASIC program before conversion, which replaces it.

**Assembly:** select a `.bin` or `.hex` in the Assembly section. For BIN files, use the original assembly address. On Sharp, enter **MON**, reserve memory using the program’s documented `USER` command, then enter **R**. Click **Send ASM**, wait for loading to finish, and run `G` followed by the entry address, such as `G100`. The application shows commands for its included examples; follow each program’s documentation for its reservation. PC-G820 uses a different monitor entry, described in the manual.

If `FRE` reports an implausible value near 64 KB on an 8 KB G801: back up your data, press **RESET**, and answer **Y** to **MEMORY CLEAR O.K. ?**. This confirmation erases memory. Afterwards check `FRE` and the SIO settings again.

### Back up your ROM

Two actions are enough; **there is no session to create or resume manually**.

1. Choose the model and **4800 / 8N1**, also in Sharp **TEXT → Sio → Format**. The destination folder is remembered; if blank, it is requested on the first upload.
2. Back up programs you want to keep: the dumper replaces the assembly program in RAM. On G801 enter **MON → USER0AFF → R**, then click **1. Send dumper** on the PC.
3. Wait for loading to finish. Click **2. Receive entire ROM** on the PC, then enter **G100 once** on Sharp.
4. Wait for verified completion. Use **Open folder** to find the images and verification report. Each completed backup automatically gets its own dated subfolder, preserving earlier backups.

Independent reads, CRC, audit captures and recovery information are managed automatically. After interruption, press **BREAK on Sharp**, send the dumper again, and restart reception in the same window; verified blocks are retained. No W or G103 commands are needed between blocks.

The automatic dumper uses firmware routines: hardware support is established for the **PC-G805**; other profiles and ROM revisions require verification. Probed selectors do not establish physical ROM size. Personal ROMs are excluded from the project and release archives.

### Guides and repository contents

- [Transfer and troubleshooting manual](docs/TRANSFER_EN.md) — detailed procedures, framing, reception, CTS diagnostics and examples.
- [ROM backup guide](romdump/AUTOMATIC_EN.md) — models, resuming, outputs and limits.
- `examples/`: BASIC and assembly examples; `sharp_link/`: application; `romdump/`: agent and documentation.
- `tools/` and `tests/`: maintenance and development; [developer guide](docs/DEVELOPMENT_EN.md).

Transfer profiles cover PC-E200, PC-G801, G802, G803, G805, G811, G813, G815, G820, G830, G850, G850S, G850V and G850VS. Selecting a model does not make every program compatible with its RAM, display or ROM routines.
