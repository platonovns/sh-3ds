"""Normal production boot -> original Load menu -> actual saved room gameplay.
Uses a copy of the card produced by original Stage 10 pickup/save triggers.
No development start, state injection or deserialized flag writes.
"""
import hashlib,json,os,shutil,struct,tempfile
from pathlib import Path
path=Path(__file__).with_name('test_stage10_progression_runtime.py');ns={'__file__':str(path),'__name__':'saved_load'}
exec(compile(path.read_text().split('with tempfile.TemporaryDirectory(')[0],str(path),'exec'),ns)
game=ns['game'];p=ns['p'];scope=ns['scope'];core=ns['core'];Progress=ns['Progress']
assert 'SH_3DS_DEV_SCENE' not in str(game.game_elf)
road=bool(os.environ.get('SH_LOAD_ROAD'))
prior=json.loads((p/'reports'/('stage10-r5-road-school.json' if road else 'stage10-r5-progression-'+scope+'.json')).read_text())
expected=prior['completed'][-1]['save'];assert prior['status']=='PASS'
class Loaded(Progress):
    def __init__(self,card):super().__init__(card);self.loaded=0;self.snapshots=[];self.polls=0
    def save_screen(self,*_):pass
    def tick(self,*_):
        self.ticks+=1;row=self.state_row();self.snapshots.append(row)
        self.loaded=self.loaded+1 if row['sys']==0 and self.map==(3 if scope=='school' else 10) else 0
        if self.ticks%50==0:print(json.dumps(row),flush=True)
        if self.loaded>=20:self.stopped=True;self.uc.emu_stop()
    def read_pad(self,*_):
        self.polls+=1
        if self.state==7:
            selected=int.from_bytes(self.uc.mem_read(game.symbols['g_MainMenu_SelectedEntry'],4),'little')
            if self.title_age>90 and selected!=0:self.ret((1<<6) if self.polls%12==0 else 0)
            elif self.title_age>90:self.ret(2 if self.polls%12==6 else 0)
            else:self.ret()
        elif self.state==8:self.ret(2 if self.polls%20<2 else 0)
        else:self.ret()
with tempfile.TemporaryDirectory(prefix='sh-stage10-load-') as directory:
    card=Path(directory)/'memcard.mcr';shutil.copyfile(p/'build'/('stage10-r5-road-school' if road else 'stage10-r5-progression-'+scope)/'memcard.mcr',card)
    r=Loaded(card);run=game.run(r,seconds=360);core.game_card_unmount()
    final=r.state_row();wanted={int(k):v for k,v in expected['inventory'].items()}
    passed=r.loaded>=20 and not any(run[k] for k in ('failure','invalid','exception')) and final['inventory']==wanted and final['flags']==expected['flags']
    passed=passed and final['save_map']==final['map'] and final['save_room']==final['room'] and final['location']==expected['location']
    passed=passed and final['save_position'][:2]==[expected['position'][0],expected['position'][2]]
    report=dict(status='PASS' if passed else 'FAIL',scope=__doc__,scenario=scope,run=run,final=final,loaded_gameplay_updates=r.loaded,
        rows=r.snapshots,elf_sha256=hashlib.sha256(game.runtime.ELF).hexdigest(),hardware_accepted=False)
    (p/'reports'/('stage10-r5-loaded-'+('road-school' if road else scope)+'.json')).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2));assert passed
