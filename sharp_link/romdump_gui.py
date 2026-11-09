"""FR/EN ROM backup wizard. All serial operations require a user button press."""
from datetime import datetime
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import uuid

from serial.tools import list_ports
from .config import config_path, load_settings, save_settings
from .protocol import prepare
from .romdump import DumpSession, MODELS, RomError, receive_hex
from .transport import Cancelled, Settings, friendly_error, send

TEXT={
 'title':('Sharp PC-G — sauvegarde ROM','Sharp PC-G — ROM backup'),
 'model':('Modèle','Model'),'banks':('Banques sondées','Bank selectors'),
 'reads':('Lectures / bloc','Reads / block'),'port':('Port série','Serial port'),
 'refresh':('Actualiser','Refresh'),'new':('Nouvelle session…','New session…'),
 'resume':('Reprendre…','Resume…'),'upload':('1. Envoyer l’agent','1. Upload agent'),
 'receive':('2. Recevoir le bloc','2. Receive block'),'cancel':('Annuler','Cancel'),
 'help':('Guide FR/EN : romdump/README.md. Sauvegarder les programmes du Sharp ; l’agent remplace le programme en RAM.',
         'FR/EN guide: romdump/README_EN.md. Back up Sharp programs; the agent replaces the program in RAM.'),
 'note':('G801 : 5 banques, dont la police en banque 04. G805 : 16 sélecteurs sondés par défaut.\nLe nombre de sélecteurs ne prouve pas la capacité physique. Deux lectures sont comparées.',
         'G801: 5 banks, including the font in bank 04. G805: probe 16 selectors by default.\nThe selector count does not prove physical capacity. Two independent reads are compared.'),
 'extended':('Ancienne session à 4 banques conservée. Copie étendue à 5 banques :\n{path}\nRecharger l’agent ; seuls les 4 blocs de la banque 04 restent à lire.',
             'Original four-bank session preserved. Copy extended to five banks:\n{path}\nReload the agent; only the four bank-04 blocks remain if all earlier reads were complete.'),
 'initial':('Créer ou reprendre une session. Régler les deux côtés sur 4800 / 8N1, RS/CS, CR LF, EOF 1A.\nFermer la liaison série dans Sharp PC-G Link avant de continuer.',
            'Create or resume a session. Match 4800 / 8N1, RS/CS, CR LF, EOF 1A on both ends.\nClose the serial connection in Sharp PC-G Link first.'),
 'install':('Sur le Sharp : MON → USER1400 → R. Cliquer ensuite sur « Envoyer l’agent ».\nAprès le chargement, rester dans le moniteur. Aucun assembleur n’est requis.',
            'On the Sharp: MON → USER1400 → R. Then click “Upload agent”.\nAfter loading, remain in the monitor. No assembler is required.'),
 'step':('Bloc {number}/{total} — {name}, source {source:04X}h, {size} octets.\nSur le Sharp : {command}, ENTER ; attendre le retour au moniteur.\nCliquer sur « Recevoir le bloc », puis saisir W300,1400, ENTER sur le Sharp.',
         'Block {number}/{total} — {name}, source {source:04X}h, {size} bytes.\nOn the Sharp: {command}, ENTER; wait for the monitor prompt.\nClick “Receive block”, then type W300,1400, ENTER on the Sharp.'),
 'done':('Dump terminé et blocs vérifiés. Fichiers dans :\n{path}\nLa commande de contraste reste à identifier dans cette ROM.',
         'Dump complete and blocks verified. Files saved in:\n{path}\nThe contrast command still needs identification in this ROM.'),
 'waiting':('Réception armée : saisir W300,1400 sur le Sharp…','Receiver ready: type W300,1400 on the Sharp…'),
 'sent':('Agent transmis — vérifier la fin de réception sur le Sharp.','Agent sent — check that reception finished on the Sharp.'),
 'saved':('Bloc {index} : CRC et checksum HEX valides. {reads}/{required} lectures distinctes.','Block {index}: CRC and HEX checksums valid. {reads}/{required} distinct reads.'),
 'busy':('Une opération est en cours. Annuler et attendre sa fin.','An operation is running. Cancel and wait for it to finish.'),
 'error':('Erreur','Error'),'stopped':('Opération annulée.','Operation canceled.'),
 'no_session':('Créer une session d’abord.','Create a session first.'),
}

class RomDumpApp(tk.Tk):
    def __init__(self,settings_file=None):
        super().__init__();self.settings_file=settings_file or config_path()
        self.saved=load_settings(self.settings_file);self.language=self.saved['language']
        self.geometry('990x690');self.minsize(890,620)
        self.session=None;self.last_copy=None;self.agent_loaded=False;self.busy=False;self.events=queue.Queue();self.cancel=threading.Event()
        self.model=tk.StringVar(value=self.saved['model'] if self.saved['model'] in MODELS else 'PC-G801')
        self.banks=tk.StringVar(value='5' if self.model.get()=='PC-G801' else '16')
        self.reads=tk.StringVar(value='2');self.port=tk.StringVar(value=self.saved['port'])
        self.lang=tk.StringVar(value='Français' if self.language=='fr' else 'English');self.labels=[]
        self.instructions=tk.StringVar();self.note=tk.StringVar();self.hint=tk.StringVar()
        root=ttk.Frame(self,padding=16);root.pack(fill='both',expand=True)
        row=ttk.Frame(root);row.pack(fill='x')
        language=ttk.Combobox(row,textvariable=self.lang,values=('Français','English'),state='readonly',width=12)
        language.pack(side='right');language.bind('<<ComboboxSelected>>',self.change_language)
        self.label(row,'title',font=('Segoe UI',17,'bold')).pack(side='left')
        row=ttk.Frame(root,padding=(0,16,0,8));row.pack(fill='x')
        self.label(row,'model').pack(side='left');combo=ttk.Combobox(row,textvariable=self.model,values=MODELS,state='readonly',width=11)
        combo.pack(side='left',padx=(6,18));combo.bind('<<ComboboxSelected>>',self.change_model)
        self.label(row,'banks').pack(side='left');ttk.Combobox(row,textvariable=self.banks,values=tuple(range(1,17)),state='readonly',width=4).pack(side='left',padx=(6,18))
        self.label(row,'reads').pack(side='left');ttk.Combobox(row,textvariable=self.reads,values=(1,2),state='readonly',width=3).pack(side='left',padx=6)
        row=ttk.Frame(root);row.pack(fill='x')
        self.label(row,'port').pack(side='left');self.port_box=ttk.Combobox(row,textvariable=self.port,width=47)
        self.port_box.pack(side='left',fill='x',expand=True,padx=6);self.button(row,'refresh',self.refresh).pack(side='left')
        ttk.Label(row,text='4800 / 8N1 · RTS/CTS',padding=(12,0)).pack(side='right')
        ttk.Label(root,textvariable=self.note,wraplength=920,justify='left').pack(anchor='w',pady=10)
        row=ttk.Frame(root);row.pack(fill='x',pady=(0,10))
        self.button(row,'new',self.new_session).pack(side='left');self.button(row,'resume',self.resume).pack(side='left',padx=6)
        self.upload_button=self.button(row,'upload',self.upload);self.upload_button.pack(side='left',padx=(18,6))
        self.rx_button=self.button(row,'receive',self.receive);self.rx_button.pack(side='left')
        self.button(row,'cancel',self.cancel.set).pack(side='right')
        ttk.Label(root,textvariable=self.instructions,wraplength=920,justify='left',font=('Segoe UI',11)).pack(anchor='w',pady=10)
        self.progress=ttk.Progressbar(root,maximum=100);self.progress.pack(fill='x',pady=8)
        self.log=tk.Text(root,height=10,font=('Consolas',10),state='disabled');self.log.pack(fill='both',expand=True)
        ttk.Label(root,textvariable=self.hint,wraplength=920).pack(anchor='w',pady=(10,0))
        self.translate();self.refresh();self.poll_id=self.after(80,self.poll_events);self.protocol('WM_DELETE_WINDOW',self.close)
    def t(self,key,**values):return TEXT[key][self.language=='en'].format(**values)
    def label(self,parent,key,**kwargs):
        widget=ttk.Label(parent,**kwargs);self.labels.append((widget,key));return widget
    def button(self,parent,key,command):
        widget=ttk.Button(parent,command=command);self.labels.append((widget,key));return widget
    def translate(self):
        self.title(self.t('title'))
        for widget,key in self.labels:widget.configure(text=self.t(key))
        self.note.set(self.t('note'));self.hint.set(self.t('help'));self.update_step()
    def change_language(self,event=None):
        self.language='en' if self.lang.get()=='English' else 'fr';self.saved['language']=self.language
        save_settings(self.settings_file,self.saved);self.translate()
    def change_model(self,event=None):self.banks.set('5' if self.model.get()=='PC-G801' else '16')
    def refresh(self):self.port_box.configure(values=tuple(p.device for p in list_ports.comports()))
    def append(self,text):
        self.log.configure(state='normal');self.log.insert('end',text+'\n');self.log.see('end');self.log.configure(state='disabled')
    def error(self,error):
        text=error.render(self.language) if isinstance(error,RomError) else friendly_error(error,self.language)
        self.append(text);messagebox.showerror(self.t('error'),text,parent=self)
    def available(self):
        if self.busy:self.error(RomError(*TEXT['busy']));return False
        return True
    def new_session(self):
        if not self.available():return
        folder=filedialog.askdirectory(parent=self)
        if not folder:return
        try:
            name=self.model.get()+'-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]
            self.session=DumpSession.create(Path(folder)/'rom-dumps'/name,self.model.get(),int(self.banks.get()),int(self.reads.get()))
            self.last_copy=None;self.agent_loaded=False;self.append(str(self.session.path));self.instructions.set(self.t('install'))
        except Exception as error:self.error(error)
    def resume(self):
        if not self.available():return
        path=filedialog.askopenfilename(parent=self,filetypes=[('Session','session.json')])
        if not path:return
        self.open_session(path)
    def open_session(self,path):
        try:
            self.session=DumpSession(Path(path).parent)
            if self.session.model=='PC-G801' and self.session.bank_count==4:
                self.session=self.session.extended_copy(5);self.append(self.t('extended',path=self.session.path))
            self.session.write_agent();self.last_copy=None;self.agent_loaded=False
            self.model.set(self.session.model);self.banks.set(str(self.session.bank_count));self.reads.set(str(self.session.info['required_reads']))
            self.update_step()
        except Exception as error:self.error(error)
    def update_step(self):
        if not self.session:self.instructions.set(self.t('initial'));return
        job=self.session.pending()
        self.progress['value']=100*sum(min(r['reads'],self.session.info['required_reads']) for r in self.session.info['blocks'].values())/(len(self.session.plan)*self.session.info['required_reads'])
        if job is None:self.instructions.set(self.t('done',path=self.session.path));return
        if not self.agent_loaded:self.instructions.set(self.t('install'));return
        name=('vecteurs RAM' if self.language=='fr' else 'RAM vectors') if job.index==0 else ('8000–BFFF' if job.bank==255 else f'bank {job.bank:02X}')
        command='G103' if self.last_copy==job.index else 'G100'
        self.instructions.set(self.t('step',number=job.index+1,total=len(self.session.plan),name=name,source=job.source,size=job.size,command=command))
    def settings(self):
        self.saved['port']=self.port.get();save_settings(self.settings_file,self.saved)
        return Settings(self.port.get(),baud=4800,data_bits=8,parity='N',stop_bits=1,receive_timeout=180,idle_timeout=15)
    def start(self,work):
        if not self.available():return
        if not self.session:self.error(RomError(*TEXT['no_session']));return
        try:settings=self.settings()
        except Exception as error:self.error(error);return
        self.busy=True;self.cancel.clear();self.upload_button.state(['disabled']);self.rx_button.state(['disabled'])
        def worker():
            try:self.events.put(('done',work(settings)))
            except Exception as error:self.events.put(('error',error))
        threading.Thread(target=worker,daemon=True).start()
    def upload(self):
        def work(settings):
            path=self.session.write_agent();program=prepare(path.read_text(),name=path.name,mode='hex',model=self.session.model)
            send(program,settings,self.cancel,lambda *args:None);return ('upload',None)
        self.start(work)
    def receive(self):
        def work(settings):
            self.events.put(('message','waiting'))
            raw=receive_hex(settings,self.cancel,lambda count:self.events.put(('bytes',count)))
            job=self.session.accept(raw);return ('receive',job)
        self.start(work)
    def poll_events(self):
        while not self.events.empty():
            event,value=self.events.get_nowait()
            if event=='message':self.append(self.t(value))
            elif event=='bytes':pass
            else:
                self.busy=False;self.upload_button.state(['!disabled']);self.rx_button.state(['!disabled'])
                if event=='error':
                    if isinstance(value,Cancelled):self.append(self.t('stopped'))
                    else:self.error(value)
                elif value[0]=='upload':self.last_copy=None;self.agent_loaded=True;self.append(self.t('sent'));self.update_step()
                else:
                    job=value[1];self.last_copy=job.index;record=self.session.info['blocks'][str(job.index)]
                    self.append(self.t('saved',index=job.index,reads=record['reads'],required=self.session.info['required_reads']));self.update_step()
        self.poll_id=self.after(80,self.poll_events)
    def close(self):
        if self.busy:self.cancel.set();return
        self.destroy()
    def destroy(self):
        if getattr(self,'poll_id',None):
            try:self.after_cancel(self.poll_id)
            except tk.TclError:pass
        super().destroy()

def main():
    import argparse
    parser=argparse.ArgumentParser(description='Sharp PC-G ROM backup / sauvegarde ROM')
    parser.add_argument('--rom-dump',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--manual',action='store_true',help='Ancien mode par blocs / older per-block mode')
    parser.add_argument('--session',type=Path,help='session.json to resume / à reprendre')
    args=parser.parse_args()
    import json
    legacy=args.manual or (args.session and json.loads(args.session.read_text(encoding='utf-8')).get('version')==1)
    if legacy:
        app=RomDumpApp()
        if args.session:app.open_session(args.session)
    else:
        from .gui import LinkApp
        app=LinkApp();app.open_rom_dump()
        if args.session:app.rom_panel.open_session(args.session)
    app.mainloop()
if __name__=='__main__':main()
