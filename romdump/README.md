# Sauvegarde ROM : ancien mode manuel

[English](README_EN.md) · [Accueil](../README.md#francais)

Pour une nouvelle sauvegarde, utiliser l’onglet **Sauvegarde ROM** du lanceur racine : [guide automatique](AUTOMATIC.md). Ce document décrit le mode manuel conservé pour reprendre les sauvegardes au format historique.

## Préparation

Lancer `python "Sharp PC-G Link.pyw" --rom-dump --manual`. L’interface est FR/EN et utilise le fichier INI de Link. Régler **4800 / 8N1**, **RS/CS**, **CR LF**, **EOF 1A** dans **TEXT → Sio → Format**, puis ENTER. Vérifier ces valeurs en cas d’erreur ou si R revient immédiatement au moniteur.

Sauvegarder les programmes à conserver : l’agent remplace le programme en RAM. Choisir le modèle, le port et le nombre de sélecteurs de banques. Garder **deux lectures indépendantes par bloc**. Le nombre de sélecteurs ne prouve pas la taille physique de la ROM.

## Charger et recevoir

1. Cliquer **Nouvelle session** et choisir le dossier parent ; un sous-dossier unique est créé.
2. Sur le Sharp : **MON → USER1400 → R**, puis **Envoyer l’agent** côté PC. Sur PC-G820, CALL #5,&HC000 remplace MON.
3. Pour chaque bloc, saisir **G100** sur le Sharp, attendre le retour au moniteur, cliquer **Recevoir le bloc**, puis saisir **W300,1400** sur le Sharp.
4. Pour la seconde lecture, utiliser **G103**, puis **Recevoir le bloc → W300,1400**. Suivre les commandes affichées jusqu’à la fin.

G100 avance après la copie ; G103 relit la même source. Une simple retransmission du tampon W ne compte pas comme une lecture indépendante. En cas d’interruption ou de CRC incorrect, refaire **Recevoir le bloc → W300,1400**, sans avancer avec G100.

## Reprendre et fichiers

**Reprendre** ouvre `session.json`, vérifie les empreintes et prépare l’agent au premier bloc manquant. Recharger cet agent avec MON → USER1400 → R et suivre les commandes affichées. Ne pas mélanger des machines ou des révisions de firmware.

`base.bin` contient les 64 octets de vecteurs RAM ; `fixed.bin` la fenêtre 8000h–BFFFh ; `banks/` contient les fenêtres de 16 Ko par sélecteur. `report.json` décrit empreintes, miroirs et intégrité. `chunks/`, `captures/` et `session.json` servent à la reprise. L’export g800 est conditionnel au profil et à la cohérence du mappage ; les ROM utilisateur ne sont pas distribuées.

L’agent manuel s’exécute en RAM, sauvegarde et restaure le registre de banque 19h et utilise le moniteur pour le transfert. Aucun appel aux routines série ROM n’est requis. Ce mode conserve ses propres limites de profils : les modèles à sélection 69h nécessitent le parcours automatique.

Voir [le guide développeur](../docs/DEVELOPMENT.md) pour reconstruire les agents et exécuter les vérifications.
