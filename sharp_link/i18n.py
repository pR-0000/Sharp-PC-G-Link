"""Shared, thread-safe UI and protocol messages. No process-wide language state."""
from dataclasses import dataclass, field

LANGUAGES = {"fr": "Français", "en": "English"}

# Stable keys keep saved settings and worker events independent of the UI language.
CATALOG = {
    "rom_dump": ("Sauvegarde ROM", "ROM backup"),
    "rom_busy": ("Terminer ou annuler le transfert avant d'ouvrir la sauvegarde ROM.", "Finish or cancel the transfer before opening ROM backup."),
    "language": ("Langue", "Language"),
    "serial_settings": ("Liaison série", "Serial settings"),
    "model": ("Modèle", "Model"),
    "port": ("Port", "Port"),
    "refresh": ("Actualiser", "Refresh"),
    "baud": ("Bauds", "Baud"),
    "data_bits": ("Bits de données", "Data bits"),
    "parity": ("Parité", "Parity"),
    "stop_bits": ("Bits de stop", "Stop bits"),
    "recommended_settings": ("Conseillés : 4800 / 8N1", "Recommended: 4800 / 8N1"),
    "check_cts": ("Contrôler CTS", "Check CTS"),
    "log_cts": ("CONTRÔLE CTS — {port} / {baud} {frame} — 60 s, aucune donnée envoyée ; RTS/DTR activés à l'ouverture. Annuler pour arrêter.", "CTS CHECK — {port} / {baud} {frame} — 60 s, no data sent; RTS/DTR asserted on open. Cancel to stop."),
    "cts_active": ("CTS ACTIF vu par le pilote — autorisation d'émettre, sans preuve du mode LOAD. Aucune donnée envoyée.", "Driver reports CTS ACTIVE — permission to send, no proof of LOAD mode. No data sent."),
    "cts_inactive": ("CTS INACTIF vu par le pilote — émission bloquée. Aucune donnée envoyée.", "Driver reports CTS INACTIVE — transmission blocked. No data sent."),
    "cts_initial_active": ("CTS actif dès l'ouverture — le logiciel ne détecte pas LOAD ; préparer la réception du Sharp avant l'envoi.", "CTS active on open — the software does not detect LOAD; prepare Sharp reception before sending."),
    "cts_initial_inactive": ("CTS inactif à l'ouverture — aucun octet ne sera envoyé tant que CTS reste inactif.", "CTS inactive on open — no bytes will be sent while CTS stays inactive."),
    "cts_done": ("Contrôle CTS terminé — aucune donnée envoyée ; port fermé.", "CTS check complete — no data sent; port closed."),
    "flow_required": ("RTS/CTS : activé", "RTS/CTS: enabled"),
    "serial_hint_g801": (
        "PC-G801 : après RESET, 1200 / 7N1 observés ; 4800 / 8N1 conseillés pour accélérer les transferts.\nPC actuel : {baud} bauds / {frame}. Reporter ces paramètres dans TEXT → Sio → Format, puis ENTER.",
        "PC-G801: 1200 / 7N1 observed after RESET; use 4800 / 8N1 for faster transfers.\nCurrent PC settings: {baud} baud / {frame}. Apply matching settings in TEXT → Sio → Format, then ENTER.",
    ),
    "serial_hint": (
        "Sharp : reporter {baud} bauds / {frame} dans TEXT → Sio → Format, puis valider avec ENTER.\nConseillés : 4800 / 8N1. N = none, E = even, O = odd. Les réglages du PC ne configurent pas le Sharp.",
        "Sharp: set {baud} baud / {frame} in TEXT → Sio → Format, then confirm with ENTER.\nRecommended: 4800 / 8N1. N = none, E = even, O = odd. PC settings do not configure the Sharp.",
    ),
    "line_delay": ("Pause / ligne (ms)", "Line delay (ms)"),
    "char_delay": ("Pause / caractère (ms)", "Character delay (ms)"),
    "browse": ("Parcourir…", "Browse…"),
    "examples": ("Exemples", "Examples"),
    "send_basic": ("Envoyer BASIC", "Send BASIC"),
    "send_asm": ("Envoyer ASM", "Send ASM"),
    "basic_frame": ("BASIC — listing ASCII (.bas / .txt)", "BASIC — ASCII listing (.bas / .txt)"),
    "asm_frame": ("Assembleur Z80 — binaire (.bin) / Intel HEX (.hex / .ihx)", "Z80 assembly — binary (.bin) / Intel HEX (.hex / .ihx)"),
    "basic_hint": ("1. Sharp : TEXT → Sio → Load ; puis Envoyer BASIC sur le PC. Le listing arrive dans l'éditeur TEXT.\n2. Vérifier TEXT → Edit, puis convertir : TEXT → Basic → Basic←text ; revenir en BASIC/RUN et taper RUN.", "1. Sharp: TEXT → Sio → Load; then Send BASIC on the PC. The listing goes into the TEXT editor.\n2. Check TEXT → Edit, then convert: TEXT → Basic → Basic←text; return to BASIC/RUN and type RUN."),
    "asm_hint": ("Sharp : {mon} → USER{reserve:04X} → R  |  Exécution : G{entry:04X} (à vérifier pour ce programme).", "Sharp: {mon} → USER{reserve:04X} → R  |  Run: G{entry:04X} (verify the program's entry point)."),
    "asm_empty_hint": ("Sharp : MON → USER… → R  |  Les .bin sont convertis en Intel HEX avant émission.", "Sharp: MON → USER… → R  |  .bin files are converted to Intel HEX before transmission."),
    "load_address": ("Chargement BIN (hex)", "BIN load address (hex)"),
    "entry_address": ("Entrée (hex)", "Entry point (hex)"),
    "no_file": ("Aucun fichier sélectionné", "No file selected"),
    "basic_tab": ("Source BASIC", "BASIC source"),
    "asm_tab": ("Code / mémoire", "Code / memory"),
    "receive_tab": ("Réception", "Receive"),
    "help_tab": ("Référence", "Reference"),
    "save_source": ("Enregistrer sous…", "Save as…"),
    "editor_hint": ("Le bouton Envoyer BASIC utilise le contenu de cet éditeur.", "Send BASIC transmits the contents of this editor."),
    "receive": ("Recevoir", "Receive"),
    "save_receive": ("Enregistrer la réception…", "Save received data…"),
    "receive_hint": ("Démarrer la réception ici, puis TEXT → Sio → Save sur le Sharp. En moniteur : Wdébut,fin.", "Start receiving here, then TEXT → Sio → Save on the Sharp. Monitor: Wstart,end."),
    "log_frame": ("Transfert / journal", "Transfer / log"),
    "clear_log": ("Effacer le journal", "Clear log"),
    "cancel": ("Annuler", "Cancel"),
    "manual": ("Manuel", "Manual"),
    "ready": ("Prêt.", "Ready."),
    "no_ports": ("Aucun port série détecté.", "No serial ports detected."),
    "ports_error": ("Détection des ports impossible : {detail}", "Port enumeration failed: {detail}"),
    "no_port": ("Sélectionner le port série de l'adaptateur.", "Select the adapter's serial port."),
    "bad_baud": ("Vitesse non prise en charge.", "Unsupported baud rate."),
    "bad_frame": ("Trame invalide : choisir 7 ou 8 bits, parité N/E/O et 1 ou 2 bits de stop.", "Invalid framing: choose 7 or 8 data bits, N/E/O parity and 1 or 2 stop bits."),
    "bad_delays": ("Temporisations invalides (ligne : 0–2000 ms ; caractère : 0–100 ms).", "Invalid delays (line: 0–2000 ms; character: 0–100 ms)."),
    "bad_timeouts": ("Les délais doivent être positifs.", "Timeouts must be positive."),
    "settings_error": ("Réglages invalides : {detail}", "Invalid settings: {detail}"),
    "ini_error": ("Enregistrement du fichier INI impossible : {detail}", "Could not save the INI file: {detail}"),
    "choose_basic": ("Choisir un listing BASIC", "Select a BASIC listing"),
    "choose_asm": ("Choisir un binaire Z80 ou un fichier Intel HEX", "Select a Z80 binary or Intel HEX file"),
    "basic_files": ("Listings BASIC", "BASIC listings"),
    "asm_files": ("Programmes Z80", "Z80 programs"),
    "all_files": ("Tous les fichiers", "All files"),
    "program_files": ("Programme", "Program"),
    "file_error": ("Erreur de fichier", "File error"),
    "save_error": ("Enregistrement impossible", "Save failed"),
    "source_saved": ("Source enregistré : {path}", "Source saved: {path}"),
    "receive_saved": ("Réception enregistrée : {path}", "Received data saved: {path}"),
    "save_basic_title": ("Enregistrer le listing BASIC", "Save BASIC listing"),
    "save_receive_title": ("Enregistrer les octets reçus (sans EOF 1A)", "Save received bytes (without EOF 1A)"),
    "new_receive": ("Nouvelle réception", "New reception"),
    "replace_receive": ("Remplacer la réception précédente ? Enregistrer les données à conserver avant de continuer.", "Replace the previous reception? Save any data you want to keep before continuing."),
    "close_busy": ("Interrompre le transfert et fermer ?", "Cancel the transfer and close?"),
    "close_rx": ("Fermer sans enregistrer les données reçues ?", "Close without saving the received data?"),
    "close_source": ("Fermer sans enregistrer le listing BASIC modifié ?", "Close without saving the modified BASIC listing?"),
    "discard_source": ("Remplacer le listing BASIC modifié sans l'enregistrer ?", "Replace the modified BASIC listing without saving?"),
    "unsaved": ("Modifications non enregistrées", "Unsaved changes"),
    "busy_title": ("Transfert en cours", "Transfer in progress"),
    "rx_title": ("Données reçues", "Received data"),
    "opening": ("Ouverture du port série…", "Opening serial port…"),
    "sending": ("Envoi en cours…", "Sending…"),
    "cts_wait": ("Attente CTS — activer Load ou R sur le Sharp.", "Waiting for CTS — start Load or R on the Sharp."),
    "cts_timeout": ("CTS reste inactif : émission bloquée. Vérifier Load/R, le branchement, le mode SIO et l'inversion FTDI.", "CTS remains inactive: transmission blocked. Check Load/R, cabling, SIO mode and FTDI inversion."),
    "drain_timeout": ("Émission bloquée : vérifier la réception du Sharp et le signal CTS.", "Transmission stalled: check Sharp reception and CTS."),
    "short_write": ("Écriture série incomplète. Le programme peut être partiellement reçu.", "Incomplete serial write. The program may have been partially received."),
    "cancelled": ("Transfert annulé. Arrêter aussi le transfert sur le Sharp (BREAK).", "Transfer cancelled. Stop the transfer on the Sharp too (BREAK)."),
    "cancelling": ("Annulation…", "Cancelling…"),
    "rx_ready": ("Prêt à recevoir — Sharp : TEXT → Sio → Save ou MON → W.", "Ready to receive — Sharp: TEXT → Sio → Save or MON → W."),
    "rx_large": ("Réception supérieure à 256 Kio : arrêt. Vérifier les réglages série.", "Reception exceeds 256 KiB: stopped. Check serial settings."),
    "rx_timeout": ("Aucune donnée reçue. Vérifier Sio → Save, le port et les réglages.", "No data received. Check Sio → Save, the port and serial settings."),
    "rx_incomplete": ("Réception interrompue sans marqueur EOF 1A. Les données partielles restent disponibles.", "Reception interrupted without EOF 1A. Partial data remains available."),
    "serial_timeout": ("Délai d'écriture série dépassé. Vérifier CTS et la réception du Sharp ; relancer Load/R avant un nouvel essai.", "Serial write timed out. Check CTS and Sharp reception; restart Load/R before retrying."),
    "serial_error": ("Port série indisponible : {detail}\nVérifier le câble et fermer les autres logiciels utilisant ce port.", "Serial port unavailable: {detail}\nCheck the cable and close other applications using this port."),
    "tx_progress": ("TX {current} / {total} octets — {seconds:.1f} s", "TX {current} / {total} bytes — {seconds:.1f} s"),
    "tx_done": ("{count} octets émis — vérifier la réception sur le Sharp (sans acquittement du fichier).", "{count} bytes transmitted — verify reception on the Sharp (no file acknowledgement)."),
    "tx_basic_done": ("{count} octets émis — Sharp : TEXT → Edit, puis TEXT → Basic → Basic←text ; BASIC/RUN → RUN. Réception à vérifier.", "{count} bytes transmitted — Sharp: TEXT → Edit, then TEXT → Basic → Basic←text; BASIC/RUN → RUN. Verify reception."),
    "basic_after_send": ("BASIC — le nom du fichier PC n'est pas transmis : chercher les lignes dans TEXT → Edit (au besoin, flèche bas), pas dans une liste de fichiers.\nConvertir avec TEXT → Basic → Basic←text : cela remplace le programme BASIC présent. Sauvegarder celui-ci avant conversion si nécessaire.\nRevenir en BASIC/RUN, puis RUN. Sans conversion, RUN ne lance pas le listing reçu. Aucun acquittement du fichier n'est reçu par le PC.", "BASIC — the PC filename is not transmitted: look for the lines in TEXT → Edit (press Down if needed), not in a file list.\nConvert with TEXT → Basic → Basic←text: this replaces the existing BASIC program. Back it up before conversion if needed.\nReturn to BASIC/RUN, then RUN. Without conversion, RUN does not execute the received listing. The PC receives no file acknowledgement."),
    "rx_progress": ("RX {count} octets — attente EOF 1A.", "RX {count} bytes — waiting for EOF 1A."),
    "rx_done": ("{count} octets reçus — EOF 1A reçu.", "{count} bytes received — EOF 1A received."),
    "rx_partial": ("Réception partielle : {count} octets ; données disponibles pour enregistrement.", "Partial reception: {count} bytes; data is available to save."),
    "rx_none": ("Aucune donnée reçue.", "No received data."),
    "preview_limit": ("\n[Aperçu limité à 20 000 octets]", "\n[Preview limited to 20,000 bytes]"),
    "log_start": ("Sharp PC-G Link {version} — configuration : {path}", "Sharp PC-G Link {version} — settings: {path}"),
    "log_error": ("ERREUR : {detail}", "ERROR: {detail}"),
    "log_cancel": ("ANNULÉ : {detail}", "CANCELLED: {detail}"),
    "log_send": ("TX {name} — {port} / {baud} {frame} / RTS/CTS={flow}", "TX {name} — {port} / {baud} {frame} / RTS/CTS={flow}"),
    "log_receive": ("RX — {port} / {baud} {frame} / RTS/CTS={flow}", "RX — {port} / {baud} {frame} / RTS/CTS={flow}"),
    "validation_error": ("Erreur : {detail}", "Error: {detail}"),
    "basic_summary": ("{lines} lignes — {size} octets SIO (CR LF + 1A)", "{lines} lines — {size} SIO bytes (CR LF + 1A)"),
    "asm_summary": ("{kind} — {count} octets — {start:04X}–{end:04X} — {size} octets SIO", "{kind} — {count} bytes — {start:04X}–{end:04X} — {size} SIO bytes"),
    "binary_kind": ("BIN → Intel HEX", "BIN → Intel HEX"),
    "hex_kind": ("Intel HEX", "Intel HEX"),
    "binary_preview": ("{name}\n{count} octets · chargement {start:04X}–{end:04X}\n\n", "{name}\n{count} bytes · load {start:04X}–{end:04X}\n\n"),
    "binary_address_hint": ("Le champ de chargement s'applique uniquement aux fichiers BIN.", "The load address field applies to BIN files only."),
    "example_hello": ("Bonjour / test de transfert", "Hello / transfer test"),
    "example_calculation": ("Somme des carrés (385)", "Sum of squares (385)"),
    "example_game": ("Deviner un nombre", "Guess the number"),
    "example_bin": ("Signature PC-G801 (.bin)", "PC-G801 signature (.bin)"),
    "example_hex": ("Signature PC-G801 (.hex)", "PC-G801 signature (.hex)"),
    "file_large": ("Fichier trop volumineux (maximum 256 Kio).", "File is too large (maximum 256 KiB)."),
    "not_text": ("Ce fichier n'est pas un texte UTF-8/ASCII. Utiliser un listing texte ; pour un binaire Z80, utiliser la section Assembleur.", "This is not UTF-8/ASCII text. Use a text listing; for a Z80 binary, use the Assembly section."),
    "embedded_eof": ("Marqueur EOF (1A) à l'intérieur du fichier : contenu refusé.", "Embedded EOF (1A) inside the file: rejected."),
    "file_empty": ("Le fichier est vide.", "The file is empty."),
    "non_ascii": ("Ligne {line} : caractère {char!r} non ASCII imprimable. Utiliser un texte sans accents, tabulations ni caractères spéciaux.", "Line {line}: {char!r} is not printable ASCII. Use text without accents, tabs or special characters."),
    "hex_after_eof": ("Intel HEX, ligne {line} : données après l'enregistrement de fin.", "Intel HEX, line {line}: data after the EOF record."),
    "hex_invalid": ("Intel HEX, ligne {line} : enregistrement invalide.", "Intel HEX, line {line}: invalid record."),
    "hex_checksum": ("Intel HEX, ligne {line} : longueur ou somme de contrôle incorrecte.", "Intel HEX, line {line}: invalid length or checksum."),
    "hex_bad_eof": ("Intel HEX : enregistrement de fin incorrect.", "Intel HEX: invalid EOF record."),
    "hex_empty_record": ("Intel HEX : enregistrement de données vide.", "Intel HEX: empty data record."),
    "hex_range": ("Intel HEX : seules les adresses RAM 0100–7FFF sont acceptées.", "Intel HEX: only RAM addresses 0100–7FFF are accepted."),
    "hex_overlap": ("Intel HEX : adresse {address:04X} écrite plusieurs fois.", "Intel HEX: address {address:04X} is written more than once."),
    "hex_type": ("Intel HEX : type {kind:02X} non pris en charge. Exporter un fichier 16 bits avec uniquement les types 00 et 01.", "Intel HEX: unsupported type {kind:02X}. Export a 16-bit file using types 00 and 01 only."),
    "hex_missing_eof": ("Intel HEX : données ou enregistrement de fin :00000001FF manquant.", "Intel HEX: missing data or EOF record :00000001FF."),
    "bad_format": ("Format de transfert inconnu.", "Unknown transfer format."),
    "small_ram": ("Adresse finale {end:04X} trop élevée pour le parcours RAM 8 Kio ({model}). Vérifier la taille et la mémoire disponible.", "End address {end:04X} exceeds the 8 KiB RAM range ({model}). Check program size and available memory."),
    "bad_basic_line": ("BASIC, ligne {line} : numéro absent, répété ou hors ordre. Utiliser des lignes numérotées croissantes, par exemple 10 PRINT \"HELLO\".", "BASIC, line {line}: missing, duplicate or out-of-order line number. Use increasing numbered lines, for example 10 PRINT \"HELLO\"."),
    "long_line": ("Une ligne dépasse 255 caractères. La scinder avant le transfert.", "A line exceeds 255 characters. Split it before transfer."),
    "bad_address": ("Adresse hexadécimale invalide : {value!r}. Utiliser 0100, 0x0100 ou &H0100.", "Invalid hexadecimal address: {value!r}. Use 0100, 0x0100 or &H0100."),
    "binary_range": ("Le binaire doit tenir entièrement dans la plage RAM 0100–7FFFh.", "The binary must fit entirely within RAM addresses 0100–7FFFh."),
    "binary_suffix": ("Sélectionner un fichier .bin, .hex ou .ihx.", "Select a .bin, .hex or .ihx file."),
    "basic_suffix": ("Sélectionner un listing .bas ou .txt.", "Select a .bas or .txt listing."),
    "hex_note": ("{count} octets de code/données, adresses {start:04X}–{end:04X}.", "{count} code/data bytes, addresses {start:04X}–{end:04X}."),
    "entry_note": ("Le point d'entrée n'est pas décrit par ce fichier : consulter sa documentation.", "This file does not specify an entry point: consult its documentation."),
    "basic_note": ("{count} lignes BASIC numérotées ; Line number = Yes sur le Sharp.", "{count} numbered BASIC lines; set Line number = Yes on the Sharp."),
    "text_note": ("Texte ASCII à charger dans l'éditeur TEXT.", "ASCII text for the TEXT editor."),
    "large_text_note": ("Vérifier la mémoire libre sur ce modèle à 8 Kio.", "Check free memory on this 8 KiB model."),
    "startup_error": ("Démarrage impossible. Ouvrir Sharp PC-G Link.pyw ; Python 3.10+ avec Tkinter est requis.\n\n{detail}", "Unable to start. Open Sharp PC-G Link.pyw; Python 3.10+ with Tkinter is required.\n\n{detail}"),
}


def tr(language: str, key: str, **params) -> str:
    pair = CATALOG[key]
    return pair[1 if language == "en" else 0].format(**params)


@dataclass(frozen=True)
class Message:
    key: str
    params: dict = field(default_factory=dict)

    def render(self, language="fr"):
        return tr(language, self.key, **self.params)

    def __str__(self):
        return self.render()


def msg(key, **params):
    return Message(key, params)


class LocalizedError(Exception):
    def __init__(self, key, **params):
        self.message = msg(key, **params)
        super().__init__(str(self.message))

    def render(self, language="fr"):
        return self.message.render(language)
