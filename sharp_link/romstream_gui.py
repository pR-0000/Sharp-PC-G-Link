"""FR/EN single-run ROM backup wizard; no hardware action without a button."""
from datetime import datetime
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
import subprocess
import sys
import uuid
import os
from dataclasses import replace

from serial.tools import list_ports
from .config import config_path,load_settings,save_settings
from .protocol import MODELS,prepare
from .romdump import RomError
from .romstream import StreamSession,profile,receive_stream
from .transport import Settings,Cancelled,friendly_error,send

TEXT={
 'title':('Sharp PC-G — sauvegarde ROM automatique','Sharp PC-G — automatic ROM backup'),
 'model':('Modèle','Model'),'banks':('Sélecteurs de banque','Bank selectors'),
 'reads':('Lectures / bloc','Reads / block'),'port':('Port série','Serial port'),
 'refresh':('Actualiser','Refresh'),'new':('Nouvelle session…','New session…'),
 'resume':('Reprendre…','Resume…'),'upload':('1. Envoyer le dumper','1. Send dumper'),
 'destination':('Destination des ROM','ROM destination'),'browse':('Parcourir…','Browse…'),
 'receive':('2. Recevoir la ROM entière','2. Receive entire ROM'),
 'cancel':('Annuler côté PC','Cancel on PC'),'manual':('Ancien mode manuel…','Older manual mode…'),
 'folder':('Ouvrir le dossier','Open folder'),
 'initial':('Sur le Sharp : {monitor} → USER0AFF → R, puis « 1. Envoyer le dumper ».\nEnsuite « 2. Recevoir la ROM entière » sur le PC, puis G100 une seule fois sur le Sharp.',
            'On Sharp: {monitor} → USER0AFF → R, then “1. Send dumper”.\nNext click “2. Receive entire ROM” on PC, then run G100 once on Sharp.'),
 'note':('Un seul G100 lance toutes les lectures et leur vérification. Routines natives PC-G805 ; compatibilité selon firmware.\nLes autres profils nécessitent une vérification ; le nombre de banques sondées ne prouve pas la capacité physique de la ROM.',
         'One G100 runs all reads and verification. PC-G805 native routines; firmware-dependent compatibility.\nOther profiles require verification; the number of probed banks does not prove physical ROM capacity.'),
 'install':('Sur le Sharp : {monitor} → USER0AFF → R, puis « Envoyer le dumper ».\nEnsuite cliquer « Recevoir la ROM entière » sur le PC AVANT de saisir G100 une seule fois sur le Sharp.',
            'On Sharp: {monitor} → USER0AFF → R, then “Send dumper”.\nNext click “Receive entire ROM” on PC BEFORE running G100 once on Sharp.'),
 'ready':('Dumper envoyé. Vérifier la fin de réception sur le Sharp.\nCliquer « Recevoir la ROM entière », puis G100 sur le Sharp. Aucun W/G103 n’est nécessaire.',
          'Dumper sent. Check that Sharp reception finished.\nClick “Receive entire ROM”, then G100 on Sharp. No W/G103 commands are needed.'),
 'armed':('Réception armée : saisir G100 une seule fois sur le Sharp.\nLes lectures et banques suivantes seront traitées automatiquement.',
          'Receiver ready: run G100 once on Sharp.\nAll subsequent reads and banks will be processed automatically.'),
 'block':('Bloc {index}/{total} — banque {bank}, {source:04X}h — lecture {reads}/{required}.',
          'Block {index}/{total} — bank {bank}, {source:04X}h — read {reads}/{required}.'),
 'done':('ROM reçue et vérifiée, marqueur de fin reçu. Retour au moniteur sur le Sharp.\nFichiers : {path}',
         'ROM received and verified, end marker received. Sharp returns to its monitor.\nFiles: {path}'),
 'retry':('Trame CRC incorrecte : retransmission automatique demandée ({count}/5).',
          'Frame CRC failed: automatic retransmission requested ({count}/5).'),
 'help':('Erreur ou R revient au moniteur ? Vérifier TEXT → Sio → Format : 4800 / 8N1, RS/CS, CR LF, EOF 1A ; ENTER.\nL’agent remplace le programme en RAM. Pour interrompre le Sharp, appuyer sur BREAK. Guide : romdump/AUTOMATIC.md.',
         'Transfer error or R returns to monitor? Check TEXT → Sio → Format: 4800 / 8N1, RS/CS, CR LF, EOF 1A; ENTER.\nThe agent replaces the program in RAM. Press BREAK to stop Sharp. Guide: romdump/AUTOMATIC_EN.md.'),
 'stopped':('Réception arrêtée côté PC. Appuyer sur BREAK sur le Sharp avant de reprendre.',
            'PC reception stopped. Press BREAK on Sharp before resuming.'),
 'busy':('Une opération est en cours.','An operation is running.'),
 'no_session':('Envoyer le dumper avant de recevoir les ROM.','Send the dumper before receiving ROM data.'),
 'error':('Erreur','Error'),
 'format':('Pour la sauvegarde ROM, choisir 4800 / 8N1 dans la liaison série et dans TEXT → Sio → Format sur le Sharp. Valider avec ENTER. Si R revient immédiatement au moniteur, revérifier ces réglages.',
           'For ROM backup, select 4800 / 8N1 in the serial settings and Sharp TEXT → Sio → Format. Confirm with ENTER. If R returns immediately to the monitor, recheck these settings.'),
 'profile_mismatch':('Le modèle sélectionné a changé. Envoyer de nouveau le dumper pour ce modèle.',
                     'The selected model has changed. Send the dumper again for this model.'),
}


class RomDumpPanel(ttk.Frame):
    def __init__(self,parent,host=None,settings_file=None):
        super().__init__(parent)
        self.host=host
        self.settings_file=host.settings_file if host else (settings_file or config_path())
        self.saved=load_settings(self.settings_file)
        self.language=host.language if host else self.saved['language']
        self.session=None;self.busy=False;self.agent_loaded=False;self.controls=[]
        self.receiving=False;self.current_block=None
        self.cancel=threading.Event();self.events=queue.Queue();self.labels=[]
        self.model=host.model if host else tk.StringVar(value=self.saved['model'] if self.saved['model'] in MODELS else 'PC-G801')
        self.banks=tk.StringVar(value=str(profile(self.model.get())['default_banks']))
        self.reads=tk.StringVar(value='2');self.port=tk.StringVar(value=self.saved['port'])
        self.lang=tk.StringVar(value='English' if self.language=='en' else 'Français')
        self.destination=tk.StringVar(value=self.saved['rom_directory'])
        self.instructions=tk.StringVar();self.note=tk.StringVar();self.hint=tk.StringVar();self.session_path=tk.StringVar()
        root=ttk.Frame(self,padding=8);root.pack(fill='both',expand=True)
        if not host:
            row=ttk.Frame(root);row.pack(fill='x')
            self.label(row,'title',font=('Segoe UI',16,'bold')).pack(side='left')
            language=ttk.Combobox(row,textvariable=self.lang,values=('Français','English'),state='readonly',width=11)
            language.pack(side='right');language.bind('<<ComboboxSelected>>',self.change_language)
        row=ttk.Frame(root,padding=(0,4,0,8));row.pack(fill='x')
        if not host:
            self.label(row,'model').pack(side='left')
            models=ttk.Combobox(row,textvariable=self.model,values=MODELS,state='readonly',width=13)
            models.pack(side='left',padx=(6,15));models.bind('<<ComboboxSelected>>',self.change_model)
        self.label(row,'banks').pack(side='left')
        self.bank_box=ttk.Combobox(row,textvariable=self.banks,state='readonly',width=4)
        self.controls.append((self.bank_box,'readonly'))
        self.bank_box.pack(side='left',padx=(6,15))
        self.label(row,'reads').pack(side='left')
        reads_box=ttk.Combobox(row,textvariable=self.reads,values=(1,2),state='readonly',width=3)
        reads_box.pack(side='left',padx=6);self.controls.append((reads_box,'readonly'))
        if not host:
            row=ttk.Frame(root);row.pack(fill='x')
            self.label(row,'port').pack(side='left')
            self.port_box=ttk.Combobox(row,textvariable=self.port,width=40)
            self.port_box.pack(side='left',fill='x',expand=True,padx=6)
            self.button(row,'refresh',self.refresh).pack(side='left')
        ttk.Label(row,text='4800 / 8N1 · RTS/CTS',padding=(12,0)).pack(side='right')
        ttk.Label(root,textvariable=self.note,wraplength=920,justify='left').pack(anchor='w',pady=12)
        row=ttk.Frame(root);row.pack(fill='x')
        self.label(row,'destination').pack(side='left')
        destination_entry=ttk.Entry(row,textvariable=self.destination,state='readonly')
        destination_entry.pack(side='left',fill='x',expand=True,padx=8)
        self.controls.append((destination_entry,'readonly'))
        self.button(row,'browse',self.choose_destination).pack(side='right')
        row=ttk.Frame(root);row.pack(fill='x',pady=(10,0))
        self.upload_button=self.button(row,'upload',self.upload);self.upload_button.pack(side='left',padx=(8,6))
        self.rx_button=self.button(row,'receive',self.receive);self.rx_button.pack(side='left')
        self.cancel_button=self.button(row,'cancel',self.cancel.set,managed=False)
        self.cancel_button.pack(side='right')
        self.folder_button=self.button(row,'folder',self.open_folder,managed=False)
        self.folder_button.pack(side='right',padx=(8,0))
        ttk.Label(root,textvariable=self.instructions,wraplength=920,justify='left',font=('Segoe UI',11)).pack(anchor='w',pady=14)
        self.progress=ttk.Progressbar(root,maximum=100);self.progress.pack(fill='x',pady=8)
        self.log=tk.Text(root,height=10,font=('Consolas',10),state='disabled');self.log.pack(fill='both',expand=True)
        row=ttk.Frame(root);row.pack(fill='x',pady=(12,0))
        ttk.Label(row,textvariable=self.hint,wraplength=920 if host else 760,justify='left').pack(side='left')
        if not host:self.button(row,'manual',self.manual).pack(side='right')
        self.change_model();self.translate();self.refresh()
        self.model_trace=self.model.trace_add('write',self.change_model) if host else None
        self.poll_id=self.after(80,self.poll);self.update_controls(False)

    def t(self,key,**values):return TEXT[key][self.language=='en'].format(**values)
    def label(self,parent,key,**kwargs):
        widget=ttk.Label(parent,**kwargs);self.labels.append((widget,key));return widget
    def button(self,parent,key,command,managed=True):
        widget=ttk.Button(parent,command=command);self.labels.append((widget,key))
        if managed:self.controls.append((widget,'normal'))
        return widget
    def translate(self):
        if self.host:self.language=self.host.language
        for widget,key in self.labels:widget.configure(text=self.t(key))
        self.note.set(self.t('note'));self.hint.set(self.t('help'));self.update_step()
    def change_language(self,event=None):
        self.language='en' if self.lang.get()=='English' else 'fr';self.saved['language']=self.language
        if self.host:self.host.set_language(self.language);return
        save_settings(self.settings_file,self.saved);self.translate()
    def change_model(self,*args):
        p=profile(self.model.get());self.bank_box.configure(values=tuple(range(1,p['maximum_banks']+1)))
        self.banks.set(str(p['default_banks']))
        if self.session and self.model.get()!=self.session.model:self.agent_loaded=False
        self.update_step()
        self.update_controls(self.busy or bool(self.host and self.host.is_busy()))
    def refresh(self):
        if not self.host:self.port_box.configure(values=tuple(p.device for p in list_ports.comports()))
    def append(self,text):
        self.log.configure(state='normal');self.log.insert('end',str(text)+'\n');self.log.see('end');self.log.configure(state='disabled')
    def error(self,error):
        text=error.render(self.language) if isinstance(error,RomError) else friendly_error(error,self.language)
        self.append(text);messagebox.showerror(self.t('error'),text,parent=self)
    def available(self):
        if self.busy or (self.host and self.host.is_busy()):self.error(RomError(*TEXT['busy']));return False
        return True
    def choose_destination(self):
        if not self.available():return False
        folder=filedialog.askdirectory(parent=self,initialdir=self.destination.get() or None)
        if not folder:return False
        if self.destination.get()!=folder:self.agent_loaded=False
        self.destination.set(folder)
        self.update_step();self.update_controls(False)
        if self.host:self.host.save_config()
        else:
            self.saved['rom_directory']=folder;save_settings(self.settings_file,self.saved)
        return True

    def prepare_dump(self):
        if not self.destination.get().strip() and not self.choose_destination():return False
        parent=Path(self.destination.get()).expanduser()
        signature=(self.model.get(),int(self.banks.get()),int(self.reads.get()))
        if self.session and not self.session.info['complete'] and self.session.path.parent==parent and signature==(self.session.model,self.session.bank_count,self.session.info['required_reads']):
            return True
        name=self.model.get()+'-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]
        self.session=StreamSession.create(parent/name,*signature)
        self.agent_loaded=False;self.session_path.set(str(self.session.path));self.append(str(self.session.path))
        self.update_step();self.update_controls(False)
        if self.host:self.host.save_config()
        return True
    def resume(self):
        if not self.available():return
        path=filedialog.askopenfilename(parent=self,filetypes=[('Session','session.json')])
        if path:self.open_session(path)
    def open_session(self,path):
        try:
            self.session=StreamSession(Path(path).parent);self.session.write_agent();self.agent_loaded=False
            self.model.set(self.session.model);self.change_model();self.banks.set(str(self.session.bank_count))
            self.reads.set(str(self.session.info['required_reads']));self.update_step()
            self.destination.set(str(self.session.path.parent))
            self.session_path.set(str(self.session.path));self.update_controls(False)
        except Exception as error:self.error(error)
    def update_step(self):
        monitor='CALL #5,&HC000' if self.model.get()=='PC-G820' else 'MON'
        if not self.session:self.instructions.set(self.t('initial',monitor=monitor));return
        total=len(self.session.plan)*self.session.info['required_reads']
        self.progress['value']=100*sum(x['reads'] for x in list(self.session.info['blocks'].values()))/total
        if self.session.info['complete']:self.instructions.set(self.t('done',path=self.session.path))
        elif self.receiving:
            if self.current_block:self.show_block(self.current_block)
            else:self.instructions.set(self.t('armed'))
        elif not self.agent_loaded:
            monitor='CALL #5,&HC000' if self.session.model=='PC-G820' else 'MON'
            self.instructions.set(self.t('install',monitor=monitor))
        else:self.instructions.set(self.t('ready'))
    def settings(self):
        if self.host:
            settings=self.host.get_settings()
            if (settings.baud,settings.frame)!=(4800,'8N1'):raise RomError(*TEXT['format'])
            return replace(settings,receive_timeout=180,idle_timeout=20)
        self.saved['port']=self.port.get();save_settings(self.settings_file,self.saved)
        return Settings(self.port.get(),baud=4800,data_bits=8,parity='N',stop_bits=1,receive_timeout=180,idle_timeout=20)
    def start(self,action):
        if not self.available():return
        if not self.session:self.error(RomError(*TEXT['no_session']));return
        if self.host and self.model.get()!=self.session.model:self.error(RomError(*TEXT['profile_mismatch']));return
        try:settings=self.settings()
        except Exception as error:self.error(error);return
        self.busy=True;self.cancel.clear();self.update_controls(True)
        if self.host:self.host.update_controls()
        def worker():
            try:self.events.put(('done',action(settings)))
            except Exception as error:self.events.put(('error',error))
        threading.Thread(target=worker,daemon=True).start()
    def upload(self):
        if not self.available():return
        try:
            self.settings()
            if not self.prepare_dump():return
        except Exception as error:self.error(error);return
        self.agent_loaded=False
        def action(settings):
            path=self.session.write_agent()
            program=prepare(path.read_text(),name=path.name,mode='hex',model=self.session.model)
            send(program,settings,self.cancel,lambda *args:None);return 'upload'
        self.start(action)
    def receive(self):
        if not self.available():return
        if not self.agent_loaded:self.error(RomError(*TEXT['no_session']));return
        def action(settings):
            receive_stream(settings,self.cancel,lambda k,v:self.events.put((k,v)),self.session)
            return 'receive'
        self.start(action)
    def show_block(self,value):
        self.progress['value']=100*value['verified_reads']/value['total_reads']
        bank=('RAM/fixe' if self.language=='fr' else 'RAM/fixed') if value['bank']==255 else f'{value["bank"]:02X}'
        self.instructions.set(self.t('block',index=value['index']+1,total=len(self.session.plan),bank=bank,source=value['source'],reads=value['reads'],required=self.session.info['required_reads']))
    def update_controls(self,busy):
        for widget,state in self.controls:widget.configure(state='disabled' if busy else state)
        complete=bool(self.session and self.session.info['complete'])
        self.rx_button.configure(state='disabled' if busy or not self.agent_loaded or complete else 'normal')
        self.cancel_button.configure(state='normal' if self.busy else 'disabled')
        self.folder_button.configure(state='normal' if self.session else 'disabled')
    def open_folder(self):
        if not self.session:return
        if sys.platform=='win32':os.startfile(self.session.path)
        else:subprocess.Popen(['open' if sys.platform=='darwin' else 'xdg-open',str(self.session.path)])
    def poll(self):
        while not self.events.empty():
            event,value=self.events.get_nowait()
            if event=='armed':
                self.receiving=True;self.current_block=None
                self.instructions.set(self.t('armed'));self.append(self.t('armed'))
            elif event=='retry':self.append(self.t('retry',count=value))
            elif event=='block':
                self.current_block=value;self.show_block(value)
            elif event=='complete':
                self.receiving=False;self.current_block=None
                self.instructions.set(self.t('done',path=value));self.append(self.t('done',path=value))
            elif event in ('done','error'):
                self.busy=False;self.receiving=False
                if event=='error':self.agent_loaded=False
                elif value=='upload':self.agent_loaded=True
                self.update_controls(False)
                if self.host:self.host.update_controls()
                if event=='error':
                    if isinstance(value,Cancelled):self.append(self.t('stopped'));self.instructions.set(self.t('stopped'))
                    else:self.error(value)
                elif value=='upload':self.agent_loaded=True;self.update_step();self.append(self.t('ready'))
                if self.host and self.host.closing:self.host.destroy();return
        self.poll_id=self.after(80,self.poll)
    def manual(self):
        if not self.available():return
        from .gui import resources
        command=[sys.executable,'--rom-dump','--manual'] if getattr(sys,'frozen',False) else [sys.executable,str(resources()/'Sharp PC-G Link.pyw'),'--rom-dump','--manual']
        subprocess.Popen(command,cwd=resources())
    def close(self):
        if self.busy:self.cancel.set();return
        self.destroy()
    def destroy(self):
        if getattr(self,'poll_id',None):
            try:self.after_cancel(self.poll_id)
            except tk.TclError:pass
        if getattr(self,'model_trace',None):
            try:self.model.trace_remove('write',self.model_trace)
            except tk.TclError:pass
        super().destroy()


class AutoRomDumpApp(RomDumpPanel):
    """Compatibility harness for developers; public entry uses LinkApp's tab."""
    def __init__(self,settings_file=None):
        self.window=tk.Tk()
        super().__init__(self.window,settings_file=settings_file)
        self.pack(fill='both',expand=True)
        self.window.title(self.t('title'));self.window.geometry('1050x740');self.window.minsize(970,700)
        self.window.protocol('WM_DELETE_WINDOW',self.close)
    def withdraw(self):self.window.withdraw()
    def destroy(self):
        if getattr(self,'_destroying',False):return
        self._destroying=True
        super().destroy();self.window.destroy()
