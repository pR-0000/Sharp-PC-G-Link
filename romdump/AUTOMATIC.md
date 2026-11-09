# Sauvegarde ROM automatique

**Français** · [English](AUTOMATIC_EN.md) · [Sharp PC-G Link](../README.md)

Le parcours se limite à **envoyer le dumper, puis recevoir les ROM**. Le programme prépare automatiquement les identifiants, fichiers de vérification et dossiers.

## Sauvegarder sa ROM

Deux actions suffisent ; **aucune session à créer ou à reprendre manuellement**.

1. Choisir le modèle et **4800 / 8N1**, également dans **TEXT → Sio → Format** sur le Sharp. Le dossier de destination est mémorisé ; s’il est vide, il est demandé au premier envoi.
2. Sauvegarder les programmes à conserver, car le dumper remplace le programme assembleur en RAM. Sur G801 : **MON → USER0AFF → R**. Cliquer **1. Envoyer le dumper** sur le PC.
3. Attendre la fin du chargement. Cliquer **2. Recevoir la ROM entière** sur le PC, puis saisir **G100 une seule fois** sur le Sharp.
4. Attendre la confirmation de fin. **Ouvrir le dossier** retrouve les images et le rapport de vérification. Chaque sauvegarde terminée reçoit automatiquement son propre sous-dossier daté, sans écraser les précédentes.

Les deux lectures, CRC, captures de contrôle et informations de reprise restent gérés automatiquement. Après interruption, appuyer sur **BREAK sur le Sharp**, puis renvoyer le dumper et relancer la réception depuis la même fenêtre ; les blocs déjà vérifiés sont conservés. Il n’y a ni commande W ni G103 entre les blocs.

Le dumper automatique utilise les routines du firmware : son support matériel est établi pour le **PC-G805** ; les autres profils et révisions de ROM nécessitent une vérification. Le nombre de sélecteurs sondés ne prouve pas la taille physique de la ROM. Aucune ROM personnelle n’est incluse dans le projet ni ses archives.

## Réglages et erreurs

**Erreur de transfert ou R revient immédiatement au moniteur : vérifier TEXT → Sio → Format en premier**, surtout après RESET. Choisir **4800 bauds, 8 bits, aucune parité, 1 stop, RS/CS, CR LF, EOF 1A**, puis ENTER, avec les mêmes réglages sur le PC. Le PC ne configure pas le Sharp à distance. Le PC-G820 accède au moniteur avec **CALL #5,&HC000** ; les indications s’adaptent au modèle.

Le profil G801 propose cinq sélecteurs, dont **04 pour la police**. Les options de banques et de lectures s’appliquent à l’envoi du dumper ; garder deux lectures. Les profils E200/G80X/G81X/G820/G830 emploient le port 19h, les G850 le port 69h. La compatibilité des routines natives dépend de la révision du firmware.

## Fichiers et intégrité

Dans le sous-dossier daté : `base.bin` contient les 64 octets de vecteurs RAM, `fixed.bin` la fenêtre 8000h–BFFFh, `banks/` les fenêtres de 16 Ko sondées. `report.json` donne les SHA-256 et les banques identiques ou uniformes. Un export `g800/` est créé sur G801 si la fenêtre fixe correspond à la banque 00 et cinq banques ont été lues.

Les fichiers `session.json`, `chunks/` et `captures/` sont des détails de vérification et de récupération conservés automatiquement. Le mot session décrit ici le stockage interne, pas une étape demandée à l’utilisateur. Ne pas les modifier pendant le transfert. Les sauvegardes déjà terminées ne sont pas écrasées.

Les trames de 544 octets portent un identifiant, l’adresse, la banque, le numéro de lecture et un CRC-16/CCITT-FALSE. Le PC sauvegarde avant ACK ; un CRC incorrect demande une retransmission, jusqu’à cinq tentatives. Deux lectures concordantes et un marqueur END valide sont nécessaires pour annoncer le succès. Un paquet retransmis ne devient pas une nouvelle lecture indépendante.

## Développement et anciennes sauvegardes

[rom_stream.asm](rom_stream.asm) contient l’agent original de 678 octets. Les échanges utilisent les routines natives BCE8h/BCEBh/BFAFh/BCE2h et restaurent la banque avant chaque appel. Aucun port LCD ni sélecteur RAM n’est modifié. `sharp_link/romstream.py` implémente le protocole ; `sharp_link/romstream_gui.py` l’interface.

```text
python romdump/build_agent.py --assembler "chemin/vers/sjasmplus.exe"
python -m unittest discover -s tests -v
python romdump/check_stream.py --rom-dir "chemin/vers/sauvegarde-ROM"
```

La reprise d’un dossier existant après fermeture reste accessible aux utilisateurs avancés : `python "Sharp PC-G Link.pyw" --rom-dump --session "chemin/session.json"`. Les anciens dumps manuels ouvrent leur interface historique. Pour une nouvelle sauvegarde, ouvrir simplement l’onglet Sauvegarde ROM.

Les ports de banque sont recoupés avec [MAME](https://github.com/mamedev/mame/blob/master/src/mame/sharp/pce220.cpp) et [g800](https://ver0.sakura.ne.jp/pc/g800src.0.11.4.tgz). Les appels série ciblent le firmware PC-G805 ; aucune ROM n’est redistribuée.
