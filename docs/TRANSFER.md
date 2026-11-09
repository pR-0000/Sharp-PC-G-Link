# Manuel de transfert

[English](TRANSFER_EN.md) · [Accueil](../README.md#francais)

## Préparer la liaison

Choisir le modèle et le port série. Un adaptateur compatible avec les niveaux électriques et le connecteur Sharp, avec RTS/CTS, est nécessaire. Un port RS-232 classique ne se branche pas directement. Si l’adaptateur FTDI nécessite une inversion TXD/RXD/RTS#/CTS#, elle doit être configurée dans son EEPROM ; le logiciel ne l’effectue pas.

Les valeurs initiales sont **1200 bauds / 7N1**, RTS/CTS activé, XON/XOFF désactivé, CR LF et EOF 1A. Le délai initial est de **50 ms par ligne**, sans pause supplémentaire entre caractères. Le bouton **Conseillés : 4800 / 8N1** sélectionne le débit et la trame recommandés sans changer le port, le modèle ni les délais. Les champs acceptent 7 ou 8 bits, parité N/E/O et 1 ou 2 bits de stop.

Sur le Sharp : **TEXT → Sio → Format**, mêmes débit/bits/parité/stop, **RS/CS**, **CR LF**, **EOF 1A**, puis **ENTER**. Pour les listings numérotés, choisir **Line number = Yes** si proposé. L’application ne configure pas le Sharp à distance. **Revérifier ce menu après RESET et en cas d’erreur ou de retour immédiat au moniteur après R.** La sauvegarde ROM exige 4800 / 8N1.

Les profils couvrent PC-E200, PC-G801/G802/G803/G805/G811/G813/G815/G820/G830/G850/G850S/G850V/G850VS. Le choix du modèle ne garantit pas la compatibilité d’un programme avec sa RAM, son écran ou ses appels ROM. PC-E500, PC-1600 et l’enregistrement cassette ne sont pas pris en charge.

## Envoyer du BASIC

1. Ouvrir un `.bas` ou `.txt` ASCII numéroté, ou choisir un exemple dans **Exemples**.
2. Modifier éventuellement le listing dans **Source BASIC**. **Envoyer BASIC transmet le contenu de l’éditeur**, même si les modifications ne sont pas enregistrées. **Enregistrer sous** permet de conserver une copie.
3. Sur le Sharp : sauvegarder les données à conserver, préparer une zone TEXT vide si nécessaire, puis **TEXT → Sio → Load**.
4. Cliquer **Envoyer BASIC** sur le PC et attendre le retour du Sharp au menu.
5. Ouvrir **TEXT → Edit** pour voir le listing, au besoin avec la flèche bas. Le nom du fichier PC n’est pas transmis.
6. Convertir par **TEXT → Basic → Basic←text**, puis passer en **BASIC / RUN MODE** et saisir **RUN**.

La conversion remplace le programme BASIC existant. Le texte reçu n’est pas encore un programme BASIC tokenisé : **RUN ne l’exécute pas avant conversion**. La commande BASIC `LOAD` seule ne remplace pas le menu **TEXT → Sio → Load**. Les images BASIC tokenisées et les fichiers cassette ne sont pas acceptés.

Le logiciel vérifie les numéros croissants de 1 à 65279, les doublons, l’ordre et les lignes de plus de 255 caractères. Les accents et contrôles indésirables sont refusés. Les fins de ligne sont normalisées en CR LF, avec un seul marqueur EOF 1A.

Les exemples inclus proposent un message (`01_bonjour.bas`), la somme des carrés de 1 à 10, résultat **385** (`02_calcul.bas`), et un nombre à deviner (`03_devine.bas`).

## Envoyer un programme Z80

**BIN :** saisir l’adresse d’origine utilisée à l’assemblage. Les octets sont convertis automatiquement en Intel HEX. **HEX/IHX :** les adresses proviennent du fichier ; le champ de chargement BIN est désactivé. Checksums, longueurs, recouvrements et limites sont contrôlés. Seuls les enregistrements 00 (données) et 01 (fin) sont acceptés.

Les adresses sont hexadécimales : `0100`, `0x0100` et `&H0100` sont acceptés. **Changer l’adresse de chargement ne reloge pas le code.** Le champ **Entrée** sert uniquement à afficher la commande `G` ; il ne lance pas le programme.

Après sauvegarde du contenu utile : **MON → USERxxxx → R** sur le Sharp, puis **Envoyer ASM** sur le PC. Une fois le transfert terminé, saisir **Gxxxx** avec le point d’entrée documenté. Sur PC-G820, utiliser **CALL #5,&HC000** pour entrer dans le moniteur.

La suggestion USER couvre le fichier jusqu’à la fin de page ; prévoir aussi la RAM nécessaire aux variables et à la pile du programme. Les adresses acceptées sont 0100–7FFFh, limitées à 0100–17E2h sur les profils 8 Kio G801/G802/G803/G820. Ce contrôle ne mesure pas la RAM libre sur l’appareil. Un source `.asm` doit être assemblé avant envoi.

### Exemple autonome inclus

Choisir **Signature PC-G801 (.bin)** ou **(.hex)**. Les deux fichiers représentent le même programme de 16 octets, d’origine et d’entrée **0100h**, sans appel ROM ni accès matériel.

```text
MON
USER01FF
R
```

Cliquer **Envoyer ASM**, attendre la fin, puis saisir :

```text
G100
D110
```

La mémoire à 0110h doit commencer par **50 43 47 21**, soit `PCG!`. Le programme revient au moniteur par RET. Le source est fourni dans `examples/assembler/pcg801_signature.asm`.

## Recevoir et enregistrer

Dans le panneau **Réception**, cliquer **Recevoir**, attendre l’état de disponibilité, puis lancer **TEXT → Sio → Save** sur le Sharp. Pour le BASIC, convertir d’abord avec **TEXT → Basic → Text←basic**. Pour une zone machine, utiliser `Wdébut,fin` dans MON ; par exemple `W100,113` pour l’exemple après exécution.

**Enregistrer la réception** conserve les octets reçus sans le marqueur EOF 1A final. L’aperçu peut remplacer visuellement des caractères non ASCII, mais le fichier conserve les octets originaux. Sans EOF, la réception signale une erreur après 10 secondes d’inactivité ; les données partielles peuvent être enregistrées. Le logiciel ne les sauvegarde pas automatiquement.

Le journal affiche les paramètres, attentes CTS, erreurs et fins de transfert. **Annuler** interrompt une attente ; utiliser aussi BREAK sur le Sharp si nécessaire. Une émission terminée côté PC n’est pas un acquittement de fichier : vérifier la réception sur le Sharp.

## Diagnostic et mémoire

**Contrôler CTS** observe le signal pendant 60 secondes sans écrire d’octet UART ni lire les données reçues. L’ouverture du port active néanmoins RTS/DTR : ce n’est pas une mesure passive de tension. Annuler ferme le port ; arrêter le contrôle avant de transférer. **CTS actif ne prouve pas que Load est lancé.**

**I/O DEVICE ERROR ou R revient au moniteur :** vérifier d’abord TEXT → Sio → Format et ENTER, puis le port, RS/CS, le câblage, la masse et les inversions de l’adaptateur. Si l’erreur précède tout envoi, les octets du fichier n’en sont pas la cause. Si le port est occupé, fermer les autres logiciels série. Une attente CTS se termine en erreur après 20 secondes ; vérifier que le Sharp attend dans Load ou R. Si des caractères sont perdus, essayer 1200 bauds des deux côtés et 100 ms par ligne.

**ERROR 10 après LOAD en BASIC :** utiliser TEXT → Sio → Load, puis Basic←text. **MEMORY OVER :** vérifier `FRE` en BASIC/RUN et la mémoire occupée par BASIC, TEXT, les fichiers et les réservations USER.

**Si FRE annonce une valeur incohérente proche de 64 Ko sur un appareil de 8 Ko : sauvegarder les données, faire RESET et répondre Y à « MEMORY CLEAR O.K. ? ». Cette confirmation efface la mémoire.** Vérifier ensuite FRE et le format SIO. L’application ne lit pas FRE et ne déclenche pas RESET.

Pour libérer une ancienne réservation assembleur après sauvegarde : `MON`, puis `USER` affiche la réservation ; `USER00FF` la libère. Ne plus exécuter l’ancien code. Cela ne remplace pas un RESET avec effacement lorsque l’état mémoire est incohérent.

## Préférences et sauvegarde ROM

La langue s’applique immédiatement. Langue, modèle, port, débit, trame, délais, adresses et dossier ROM sont enregistrés dans **sharp_pc_g_link.ini**, à côté du lanceur ou de l’exécutable. Les messages déjà inscrits au journal gardent leur langue. Les mises à jour préservent le fichier existant ; le modèle de configuration est `sharp_link/defaults.ini`.

L’onglet **Sauvegarde ROM** utilise un agent préassemblé et deux actions : envoyer le dumper, puis recevoir toutes les données après un seul G100. Voir le [guide ROM](../romdump/AUTOMATIC.md) pour les limites de compatibilité et les fichiers produits.

## Références et développement

[readrom](https://github.com/fu-sen/readrom) documente le moniteur et les sauvegardes ; [z88dk](https://github.com/z88dk/z88dk/wiki/Platform---Sharp-PC) décrit la famille Sharp. Le [programme SIO de z88dk](https://github.com/z88dk/z88dk/blob/master/examples/g800/send.py) fournit une référence pour RTS/CTS et les pauses entre lignes. Voir le [guide développeur](DEVELOPMENT.md) pour les tests et la construction.
