"""Original saved town state -> three locks -> darkness -> school -> save.
Nearby fixture entries replace long walking segments. Original item use,
conditions, room/overlay transitions, scripted event and save logic execute.
"""
import hashlib,json,shutil,struct,tempfile,time
from pathlib import Path
from unicorn.arm_const import UC_ARM_REG_PC,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_R0,UC_ARM_REG_R1
path=Path(__file__).with_name('test_stage10_saved_load_runtime.py');ns={'__file__':str(path),'__name__':'road_school'}
exec(compile(path.read_text().split("with tempfile.TemporaryDirectory(prefix='sh-stage10-load-')")[0],str(path),'exec'),ns)
game=ns['game'];p=ns['p'];core=ns['core'];Progress=ns['Progress'];Loaded=ns['Loaded']
assert ns['scope']=='town'
folder=p/'build/stage10-r5-road-school';folder.mkdir(exist_ok=True)
class Road(Loaded):
    def __init__(self,card):
        super().__init__(card);self.route_ids=struct.unpack('<6I',self.uc.mem_read(game.symbols['stage10_progression_route_flags'],24))
    def state_row(self):
        row=super().state_row()
        if hasattr(self,'route_ids'):
            save=struct.unpack('<I',self.uc.mem_read(game.symbols['g_SavegamePtr'],4))[0]
            row['route_flags']=[bool(int.from_bytes(self.uc.mem_read(save+self.meta[2]+(f//32)*4,4),'little')&(1<<(f%32))) for f in self.route_ids]
        return row
    def tick(self,*_):
        self.ticks+=1;self.leg_age+=1;row=self.state_row();self.rows.append(row)
        if self.ticks%100==0:print(json.dumps(dict(leg=self.leg,age=self.leg_age,**row)),flush=True)
        if self.leg<0:
            self.loaded=self.loaded+1 if row['sys']==0 and self.map==10 else 0
            if self.loaded>=10:self.action='next';self.uc.emu_stop()
        elif self.leg==0 and row['sys']==0 and all(row['route_flags'][:4]):
            assert all(t[3] not in row['inventory'] for t in self.targets[2:5]),row
            self.completed.append(dict(leg=self.leg,row=row));self.action='next';self.uc.emu_stop()
        elif self.leg==1 and row['sys']==0 and row['route_flags'][5]:
            self.completed.append(dict(leg=self.leg,row=row));self.action='next';self.uc.emu_stop()
        elif self.leg==2 and row['sys']==0 and self.map==3:
            self.completed.append(dict(leg=self.leg,row=row));self.action='next';self.uc.emu_stop()
        if self.leg_age>1500:self.error=dict(reason='route stalled',leg=self.leg,row=row);self.action='stop';self.uc.emu_stop()
    def read_pad(self,*_):
        if self.leg<0:return super().read_pad()
        self.ret(2 if self.leg_age%12<2 else 0)
    def save_screen(self,*_):
        if self.leg==3:self.action='save';self.uc.emu_stop()
with tempfile.TemporaryDirectory(prefix='sh-stage10-road-') as directory:
    card=Path(directory)/'memcard.mcr';shutil.copyfile(p/'build/stage10-r5-progression-town/memcard.mcr',card)
    r=Road(card);u=r.uc;u.reg_write(UC_ARM_REG_SP,0x1001ffc0);u.reg_write(UC_ARM_REG_LR,0x30000000)
    u.reg_write(UC_ARM_REG_R0,game.symbols['fs_result']);u.reg_write(UC_ARM_REG_R1,game.symbols['vram'])
    pc=game.symbols['game3ds_run'];deadline=time.monotonic()+1800;saved=None
    try:
        while time.monotonic()<deadline and not r.failure and not r.invalid and not r.error:
            u.emu_start(pc,0x30000000,timeout=30_000_000,count=200_000_000);pc=u.reg_read(UC_ARM_REG_PC)
            if r.action=='next':
                r.action=None;r.leg+=1;r.leg_age=0;poi=(24,24,45,89)[r.leg]
                context=u.context_save();stack=bytes(u.mem_read(0x10000000,0x20000))
                valid=r.call('stage10_progression_place',poi,1);u.mem_write(0x10000000,stack);u.context_restore(context)
                assert valid,('fixture facing',r.leg,poi)
                print(json.dumps(dict(start_leg=r.leg,poi=poi,map=r.map,room=r.room)),flush=True)
            elif r.action=='save':
                before=r.state_row();saved=r.call('stage10_progression_save_current');assert saved==0,saved
                core.game_card_unmount();(folder/'memcard.mcr').write_bytes(card.read_bytes())
                second=Progress(card);second.call('PsxMemory_Init');assert second.call('stage10_progression_load')==0
                after=second.state_row();assert after['inventory']==before['inventory'] and after['flags']==before['flags'],(before,after)
                assert (after['save_map'],after['save_room'],after['save_position'],after['location'])==(before['save_map'],before['save_room'],before['save_position'],4),(before,after)
                r.completed.append(dict(save=before,reloaded=after));break
            elif r.action=='stop' or r.stopped:break
        else:r.error=r.error or 'deadline'
    except Exception as error:r.error=repr(error)
    finally:
        core.game_card_unmount()
        for f in r.handles.values():f.close()
    report=dict(status='PASS' if saved==0 and not r.error else 'FAIL',scope=__doc__,ticks=r.ticks,completed=r.completed,
        rows=r.rows,error=r.error,failure=r.failure,invalid=r.invalid,elf_sha256=hashlib.sha256(game.runtime.ELF).hexdigest(),hardware_accepted=False)
    (p/'reports/stage10-r5-road-school.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2));assert report['status']=='PASS'
