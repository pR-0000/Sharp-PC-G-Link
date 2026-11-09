"""Compact, bilingual reference displayed on demand, away from transfer controls."""

REFERENCE = {
    "fr": """SIO — FORMAT
Par défaut : 1200 bauds · 7 bits · aucune parité · 1 stop · RS/CS (RTS/CTS).
Fin de ligne CR LF · fin de fichier 1A · Line number Yes pour un listing BASIC numéroté.
Les paramètres du Sharp se règlent dans TEXT → Sio → Format.
Vérifier les valeurs affichées dans le menu Format du Sharp, notamment après RESET.
Pour accélérer les transferts, passer à 4800 bauds / 8N1 des deux côtés, puis valider avec ENTER.
8N1 = 8 bits, parité none, 1 stop. Le PC et le Sharp doivent avoir les mêmes paramètres.
Le débit sélectionné dans l'application ne modifie pas les paramètres du Sharp.
Depuis la version 1.3.0, bits de données (7/8), parité (N/E/O) et stop (1/2) sont réglables.
N = none / aucune, E = even / paire, O = odd / impaire. Le journal et le rappel montrent la trame choisie.
Le bouton « Conseillés : 4800 / 8N1 » rétablit débit et trame sans changer port ni temporisations.
RTS/CTS est imposé dans l'application ; choisir RS/CS sur le Sharp. XON/XOFF est désactivé.

BASIC
Sélectionner un .bas/.txt ou un exemple, puis éventuellement modifier le listing dans Source BASIC.
Sharp : TEXT → Sio → Load. Envoyer BASIC transmet le contenu de l'éditeur.
Après RECEIVING et retour au menu : TEXT → Edit affiche le listing (au besoin, flèche bas).
Le nom du fichier PC n'est pas transmis et aucun fichier nommé n'est créé automatiquement sur le Sharp.
Après réception : TEXT → Basic → Basic←text ; BASIC en RUN MODE, puis RUN.
La conversion remplace le programme BASIC présent : le sauvegarder auparavant si nécessaire.
Sans conversion, RUN ne lance pas le texte reçu.
Un listing ASCII est nécessaire ; les fichiers BASIC tokenisés/cassette ne sont pas pris en charge.
LOAD saisi seul en BASIC n'est pas le parcours SIO de cet outil : utiliser le menu TEXT → Sio → Load.
Le manuel du PC-E220 documente LOAD "nom" pour un programme en RAM, pas pour SIO.
Aucun LOAD série natif n'a été établi sur le G801 ; ne pas lui appliquer la syntaxe OPEN/LOAD des PC-E500.

ASSEMBLEUR Z80
BIN : renseigner l'adresse de chargement utilisée à l'assemblage (hexadécimal, 0100 par défaut).
HEX/IHX : les adresses sont celles du fichier. Le champ de chargement BIN est alors désactivé.
Le bouton Envoyer ASM convertit automatiquement le BIN en Intel HEX pour le moniteur Sharp.
Le champ Entrée sert au rappel de la commande G ; aucune commande de lancement n'est envoyée automatiquement.

Sharp : MON, USERxxxx (réservation suffisante), R ; puis Envoyer ASM. Après réception : Gxxxx.
PC-G820 : CALL #5,&HC000 remplace MON. Sauvegarder les programmes présents avant de modifier USER.
Les adresses acceptées ne garantissent pas que toute la RAM soit libre ; vérifier la mémoire du modèle.

EXEMPLE PC-G801
pcg801_signature.bin et pcg801_signature.hex contiennent le même code, chargé à 0100h.
MON → USER01FF → R → Envoyer ASM → G100 → D110.
Le dump à 0110 doit commencer par 50 43 47 21 (PCG!). Le programme revient par RET, sans appel ROM.
Un logiciel G850 utilisant son écran ou ses routines ROM n'est pas nécessairement compatible G801.

RÉCEPTION
Démarrer Recevoir côté PC avant TEXT → Sio → Save sur le Sharp.
BASIC : convertir préalablement vers TEXT (TEXT → Basic → Text←basic).
Code machine : utiliser Wdébut,fin dans MON. Les adresses sont hexadécimales.
La réception se termine sur 1A. En l'absence de fin, les données partielles peuvent être enregistrées.

ADAPTATEUR / DIAGNOSTIC
Adaptateur FTDI : inversion TXD/RXD/RTS#/CTS# programmée dans l'EEPROM FTDI, pas dans les octets transmis.
Attente CTS : vérifier Load/R, le branchement, le mode SIO et le profil FTDI. Annuler interrompt l'opération.
CTS actif n'est pas une détection de LOAD : un envoi immédiat hors LOAD ne suffit pas à prouver un défaut.
Contrôler CTS : observation 60 s dans le journal, sans écrire ni lire de données ; RTS/DTR activés à l'ouverture.
Annuler ferme le port. Pendant le contrôle, émission/réception sont désactivées ; arrêter avant l'envoi.
Test câble seul : Sharp déconnecté, USB débranché pendant le câblage, entrée CTS FTDI reliée à GND via 10 kΩ.
Rebrancher USB, choisir le bon port et Contrôler CTS : INACTIF attendu si l'inversion CTS# est effective.
Si ACTIF persiste : vérifier fil CTS, masse, port choisi et relecture FT_PROG ; ce n'est pas une mesure de tension.
Annuler puis débrancher USB avant de rétablir le montage. Avec le Sharp, relever CTS au repos puis dans Sio/Load.
Émission terminée n'est pas un acquittement de fichier : vérifier le Sharp. Si nécessaire : 1200 bauds et 100 ms/ligne.
ERROR 10 après LOAD en BASIC : erreur de syntaxe ; passer par TEXT → Sio → Load.
I/O DEVICE ERROR dans Sio : vérifier l'accord débit/bits/parité/stop, RS/CS, câblage et inversion FTDI.
Erreur de transfert ou R revient directement au moniteur : vérifier TEXT → Sio → Format, puis ENTER.
Le PC ne configure pas le Sharp ; revérifier après RESET. La sauvegarde ROM exige 4800 / 8N1 des deux côtés.
Noter si l'erreur apparaît avant l'envoi PC ou pendant la réception ; elle n'établit pas une panne de RAM.
Avant l'envoi : essayer Envoyer BASIC côté PC, puis immédiatement TEXT → Sio → Load (attente CTS : 20 s).
Le port et RTS ne sont activés qu'au début du transfert PC ; cet ordre est un essai de diagnostic.
MEMORY OVER : vérifier FRE en BASIC/RUN et la mémoire occupée par BASIC, TEXT, les fichiers et USER.
FRE = 65535 ou 63230 est incohérent sur un G801 de 8 Kio ; vérifier l'état mémoire avant de poursuivre.
Si FRE annonce environ 64 Ko : sauvegarder, faire RESET, puis répondre Y à « MEMORY CLEAR O.K. ? ».
Cette opération efface les données ; vérifier ensuite la mémoire disponible.
Vérifier ensuite FRE et les réglages SIO, qui peuvent avoir changé ; aucun RESET n'est lancé par le logiciel.
Après sauvegarde, MON → USER affiche la réservation assembleur ; USER00FF la libère pour réutiliser la RAM.
Ne plus exécuter l'ancien code après libération. Revenir en BASIC/RUN et contrôler FRE avant de reprendre.
Une réservation pour un gros programme assembleur peut laisser trop peu de mémoire pour un listing BASIC.
La libération USER ne remplace pas RESET avec confirmation de l'effacement si l'état mémoire est incohérent.
Vérifier de nouveau FRE puis les réglages SIO. Une valeur encore anormale demande un diagnostic mémoire/alimentation.

PRÉFÉRENCES
Français/English s'applique immédiatement. Langue, port, modèle, débit, bits/parité/stop, temporisations et adresses sont enregistrés
dans sharp_pc_g_link.ini, à côté du script ou de l'exécutable. Aucune réinstallation n'est nécessaire.
""",
    "en": """SIO — FORMAT
Defaults: 1200 baud · 7 data bits · no parity · 1 stop bit · RS/CS (RTS/CTS).
CR LF line endings · 1A end of file · Line number Yes for numbered BASIC listings.
Set the Sharp parameters in TEXT → Sio → Format.
Check the values displayed in the Sharp Format menu, especially after RESET.
For faster transfers, select 4800 baud / 8N1 on both devices, then confirm with ENTER.
8N1 = 8 data bits, parity none, 1 stop bit. Both devices must use matching settings.
Selecting a baud rate in this application does not configure the Sharp.
Since version 1.3.0, data bits (7/8), parity (N/E/O) and stop bits (1/2) are configurable.
N = none, E = even, O = odd. The log and matching-settings reminder show the selected frame.
Recommended: 4800 / 8N1 restores baud rate and framing without changing the port or delays.
RTS/CTS is always enabled in the application; select RS/CS on the Sharp. XON/XOFF is disabled.

BASIC
Select a .bas/.txt file or an example, then optionally edit the listing in BASIC source.
Sharp: TEXT → Sio → Load. Send BASIC transmits the editor contents.
After RECEIVING returns to the menu: TEXT → Edit displays the listing (press Down if needed).
The PC filename is not transmitted and no named file is created automatically on the Sharp.
After reception: TEXT → Basic → Basic←text; switch BASIC to RUN MODE, then RUN.
Conversion replaces the existing BASIC program: back it up first if needed.
Without conversion, RUN does not execute the received text.
An ASCII listing is required; tokenized BASIC/cassette files are not supported.
Typing LOAD alone in BASIC is not this tool's SIO workflow: use the TEXT → Sio → Load menu.
The PC-E220 manual documents LOAD "name" for a program stored in RAM, not SIO.
No native serial LOAD has been established for the G801; do not apply PC-E500 OPEN/LOAD syntax to it.

Z80 ASSEMBLY
BIN: enter the load address used when assembling the program (hexadecimal, 0100 by default).
HEX/IHX: addresses come from the file. The BIN load address field is disabled in this case.
Send ASM automatically converts BIN data to Intel HEX for the Sharp monitor.
The Entry point field only generates the G command reminder; no execution command is sent automatically.

Sharp: MON, USERxxxx (reserve enough memory), R; then Send ASM. After reception: Gxxxx.
PC-G820: use CALL #5,&HC000 instead of MON. Back up existing programs before changing USER.
Accepted addresses do not guarantee that all RAM is free; check the target model's available memory.

PC-G801 EXAMPLE
pcg801_signature.bin and pcg801_signature.hex contain the same code, loaded at 0100h.
MON → USER01FF → R → Send ASM → G100 → D110.
The dump at 0110 must start with 50 43 47 21 (PCG!). The program returns with RET and uses no ROM calls.
G850 software using its display or ROM routines is not necessarily compatible with the G801.

RECEPTION
Start Receive on the PC before TEXT → Sio → Save on the Sharp.
BASIC: first convert to TEXT (TEXT → Basic → Text←basic).
Machine code: use Wstart,end in MON. Addresses are hexadecimal.
Reception ends at 1A. If the end marker is missing, partial data can still be saved.

ADAPTER / DIAGNOSTICS
FTDI adapter: TXD/RXD/RTS#/CTS# inversion is configured in the FTDI EEPROM, not in the transmitted bytes.
Waiting for CTS: check Load/R, cabling, SIO mode and the FTDI profile. Cancel stops the operation.
CTS active does not detect LOAD: immediate transmission outside LOAD does not establish a fault.
Check CTS: observe the log for 60 s without writing or reading data; RTS/DTR are asserted on open.
Cancel closes the port. Sending/receiving are disabled during the check; stop it before transmitting.
Cable-only test: disconnect the Sharp, unplug USB while wiring, connect FTDI CTS input to GND through 10 kΩ.
Reconnect USB, select the correct port and Check CTS: expect INACTIVE if CTS# inversion is effective.
If ACTIVE persists: check the CTS wire, ground, selected port and FT_PROG readback; this is not a voltage reading.
Cancel and unplug USB before restoring the wiring. With the Sharp, note CTS at idle and in Sio/Load.
Completed transmission is not a file acknowledgement: check the Sharp. If needed: 1200 baud and 100 ms/line.
ERROR 10 after LOAD in BASIC: syntax error; use TEXT → Sio → Load.
I/O DEVICE ERROR in Sio: check matching baud/bits/parity/stop, RS/CS, cabling and FTDI inversion.
On transfer errors or R immediately returning to the monitor: check TEXT → Sio → Format and confirm ENTER.
PC settings do not configure Sharp; check them again after RESET. ROM backup requires 4800 / 8N1 on both sides.
Note whether it occurs before PC transmission or during reception; it does not establish a RAM failure.
Before transmission: try Send BASIC on the PC, then immediately TEXT → Sio → Load (CTS wait: 20 s).
The port opens and RTS is asserted only when a PC transfer starts; this order is a diagnostic test.
MEMORY OVER: check FRE in BASIC/RUN and memory used by BASIC, TEXT, stored files and USER.
FRE = 65535 or 63230 is inconsistent on an 8 KiB G801; check its memory state before continuing.
If FRE reports about 64 KB: back up, press RESET, then answer Y to "MEMORY CLEAR O.K. ?".
This erases data; check available memory afterwards.
Check FRE and the SIO settings afterwards, as they may have changed; the software does not perform RESET.
After backing up, MON → USER displays the assembly reservation; USER00FF releases it for RAM reuse.
Do not run the old code after releasing it. Return to BASIC/RUN and check FRE before retrying.
A large assembly reservation can leave too little memory to receive a BASIC listing.
Releasing USER does not replace RESET with memory clear confirmation when the memory state is inconsistent.
Check FRE again, then the SIO settings. A still abnormal value requires memory/power-supply diagnosis.

PREFERENCES
Français/English takes effect immediately. Language, port, model, baud rate, data bits/parity/stop bits, delays and addresses are stored
in sharp_pc_g_link.ini beside the script or executable. No reinstallation is required.
""",
}
