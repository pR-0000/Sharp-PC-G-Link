# Exemples PC-G850 / PC-G850 examples

[Français](#francais) · [English](#english)

<a id="francais"></a>

## Français

Ces exemples ciblent les **PC-G850, G850S, G850V et G850VS**, avec un affichage de **24 caractères × 6 lignes**, soit **144 × 48 pixels**. Ils servent à vérifier le transfert et à observer l’affichage, la saisie et l’exécution de petits programmes. Le tableau BASIC vérifie ses variables allouées ; ce n’est pas un contrôle exhaustif de la RAM.

Sélectionner le modèle dans Sharp PC-G Link : les boutons **Exemples** des cadres BASIC et Assembleur proposent alors les entrées **G850**. Les listings chargés suivent la langue choisie dans l’application. Les fichiers peuvent aussi être ouverts avec **Parcourir**.

### Réglages et chargement BASIC

Sauvegarder les données à conserver. Choisir les mêmes paramètres sur le PC et dans **TEXT → Sio → Format** sur le Sharp : **4800 bauds / 8N1, RS/CS, CR LF, EOF 1A**, puis ENTER. Activer **Line number = Yes** pour conserver les numéros du listing. Le bouton des réglages conseillés configure uniquement le PC.

1. Ouvrir un exemple de `basic/fr/` ou le choisir dans **Exemples**.
2. Sur le Sharp, préparer une zone TEXT vide, puis **TEXT → Sio → Load**.
3. Sur le PC, cliquer **Envoyer BASIC** et attendre la fin sur le Sharp.
4. Consulter le listing dans **TEXT → Edit**, puis convertir avec **TEXT → Basic → Basic←text**. La conversion remplace le BASIC présent.
5. En mode BASIC RUN, saisir **RUN**. Le nom du fichier PC n’est pas transmis.

| Fichier | Fonctionnement |
|---|---|
| [01_transfer.bas](basic/fr/01_transfer.bas) | Message sur les six lignes ; une touche termine le programme. |
| [02_lcd.bas](basic/fr/02_lcd.bas) | Quatre pages : grille sur toute la surface, damier au pixel, écran plein et écran vide. Une touche passe à la page suivante. Le damier se dessine progressivement. |
| [03_keyboard.bas](basic/fr/03_keyboard.bas) | Affiche le caractère imprimable, son code et le nombre de pressions. Relâcher la touche entre deux pressions. **Q** quitte ; **BREAK** interrompt le BASIC. |
| [04_calculation.bas](basic/fr/04_calculation.bas) | Stocke et relit les carrés de 0 à 99 dans un tableau de 100 valeurs. La somme attendue est **328350**. Une touche termine le programme. |
| [05_animation.bas](basic/fr/05_animation.bas) | Carré rebondissant dans une fenêtre graphique ; **Q** quitte. |

Le lecteur BASIC utilise **INKEY$**, donc les caractères et codes exposés par le firmware. Les touches de mode et combinaisons réservées ne constituent pas une matrice clavier brute. La mire aide à repérer des lignes ou colonnes manquantes ; elle ne détermine pas la cause d’un défaut matériel. Les programmes restaurent le mode WAIT par défaut en terminant normalement.

### Exemples Z80 prêts à envoyer

Les fichiers BIN et HEX représentent le même programme. Origine et entrée : **0100h**. Dans le cadre Assembleur, choisir le fichier puis **Envoyer ASM** après avoir préparé le Sharp avec les commandes ci-dessous, ENTER après chacune. Les commandes `USER` réservent aussi les zones de travail.

| Exemple | Préparation | Après transfert |
|---|---|---|
| [Signature G850 — HEX](assembler/g850_signature.hex) / [BIN](assembler/g850_signature.bin) | `MON` → `USER01FF` → `R` | `G100`, puis `D180` : les quatre premiers octets doivent être **47 38 35 30**, soit **G850** en ASCII. |
| [Mire LCD Z80 — HEX](assembler/g850_lcd.hex) / [BIN](assembler/g850_lcd.bin) | `MON` → `USER02FF` → `R` | `G100` affiche six bandes de huit pixels de haut. Appuyer sur une touche pour revenir au moniteur. |

La signature n’appelle aucune routine ROM et n’accède à aucun port. Elle écrit quatre octets en **0180h–0183h**, dans sa réservation. La mire utilise les IOCS **BFD0h** (144 colonnes de pixels sur chacune des six lignes) et **BCFDh** (attente clavier), avec un tampon en **0200h–028Fh**. Les motifs des bandes sont **FF, 00, AA, 55, F0, 0F** ; la deuxième bande est volontairement vide. Une touche ramène au moniteur ; une routine IOCS incompatible avec le firmware nécessite une adaptation.

Les sources commentés sont fournis. Pour les reconstruire, installer SjASMPlus et lancer depuis la racine :

```text
python tools/build_g850_examples.py --assembler "chemin/vers/sjasmplus.exe" --lang fr
```

Les adresses, tailles et SHA-256 figurent dans [assembler/manifest.json](assembler/manifest.json). Aucun changement de banque, de contraste ou d’EEPROM FTDI n’est effectué par ces exemples.

[Application et dépannage](../../README.md#francais) · [Référence g800 : sources et IOCS](https://ver0.sakura.ne.jp/pc/) · [Analyse du PC-G850](https://www.akiyan.com/pc-g850_technical_data)

---

<a id="english"></a>

## English

These examples target **PC-G850, G850S, G850V and G850VS**, with **24 characters × 6 rows**, or **144 × 48 pixels**. They help check transfers and observe display, keyboard and small-program execution. The BASIC array checks its allocated variables; it is not an exhaustive RAM test.

Select the model in Sharp PC-G Link: the BASIC and Assembly **Examples** buttons then offer **G850** entries. Loaded listings follow the application language. You can also open the files with **Browse**.

### Serial settings and BASIC loading

Back up data you want to keep. Match PC settings with Sharp **TEXT → Sio → Format**: **4800 baud / 8N1, RS/CS, CR LF, EOF 1A**, then ENTER. Enable **Line number = Yes** to preserve listing numbers. The recommended-settings button configures the PC only.

1. Open an example under `basic/en/` or choose it from **Examples**.
2. On the Sharp, prepare an empty TEXT area, then **TEXT → Sio → Load**.
3. On the PC, click **Send BASIC** and wait for reception to finish on the Sharp.
4. Inspect the listing in **TEXT → Edit**, then convert with **TEXT → Basic → Basic←text**. Conversion replaces the current BASIC program.
5. In BASIC RUN mode, type **RUN**. The PC filename is not transmitted.

| File | Behaviour |
|---|---|
| [01_transfer.bas](basic/en/01_transfer.bas) | Message across all six rows; any key ends the program. |
| [02_lcd.bas](basic/en/02_lcd.bas) | Four pages: full-screen grid, pixel checkerboard, solid screen and blank screen. Press a key for the next page. The checkerboard draws progressively. |
| [03_keyboard.bas](basic/en/03_keyboard.bas) | Displays printable characters, key codes and press count. Release the key between presses. **Q** quits; **BREAK** interrupts BASIC. |
| [04_calculation.bas](basic/en/04_calculation.bas) | Stores and rereads squares from 0 to 99 in a 100-element array. Expected sum: **328350**. Any key ends the program. |
| [05_animation.bas](basic/en/05_animation.bas) | Bouncing square in a graphics window; **Q** quits. |

The BASIC key reader uses **INKEY$**, exposing firmware characters and codes. Mode keys and reserved combinations do not provide a raw keyboard matrix scan. LCD patterns help reveal missing rows or columns; they do not identify the cause of a hardware fault. Programs restore default WAIT mode when ending normally.

### Ready-to-send Z80 examples

BIN and HEX files contain the same program. Origin and entry: **0100h**. In the Assembly section, select a file and use **Send ASM** after preparing the Sharp with the commands below, ENTER after each. `USER` reservations also cover working memory.

| Example | Preparation | After transfer |
|---|---|---|
| [G850 signature — HEX](assembler/g850_signature.hex) / [BIN](assembler/g850_signature.bin) | `MON` → `USER01FF` → `R` | `G100`, then `D180`: the first four bytes should be **47 38 35 30**, ASCII **G850**. |
| [Z80 LCD patterns — HEX](assembler/g850_lcd.hex) / [BIN](assembler/g850_lcd.bin) | `MON` → `USER02FF` → `R` | `G100` draws six eight-pixel bands. Press a key to return to the monitor. |

The signature makes no ROM calls or port accesses. It writes four bytes at **0180h–0183h**, inside its reservation. The LCD program uses IOCS **BFD0h** (144 pixel columns on each of six rows) and **BCFDh** (wait for key), with a buffer at **0200h–028Fh**. Band patterns are **FF, 00, AA, 55, F0, 0F**; the second band is deliberately blank. A key returns to the monitor; firmware with incompatible IOCS routines requires adaptation.

Commented assembly sources are included. To rebuild them, install SjASMPlus and run from the project root:

```text
python tools/build_g850_examples.py --assembler "path/to/sjasmplus.exe" --lang en
```

Addresses, sizes and SHA-256 hashes are recorded in [assembler/manifest.json](assembler/manifest.json). These examples do not change banking, contrast or FTDI EEPROM configuration.

[Application and troubleshooting](../../README.md#english) · [g800 source and IOCS reference](https://ver0.sakura.ne.jp/pc/) · [PC-G850 analysis](https://www.akiyan.com/pc-g850_technical_data)
