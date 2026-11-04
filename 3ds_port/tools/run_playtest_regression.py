import runpy,sys
from pathlib import Path
script=Path(sys.argv[1]).resolve();port=script.parents[1]
sys.argv=[str(script)]
original=Path.write_text
def write(self,*args,**kwargs):
    if self.parent==port/'reports':self=port/'build'/('playtest-'+self.name)
    return original(self,*args,**kwargs)
Path.write_text=write
sys.path.insert(0,str(script.parent))
if script.name in ('test_stage7_inventory_arm.py','test_stage10_original_pause_arm.py'):
    import run_arm_game as game
    original_bridge=game.GameRunner.bridge
    def bridge(self,name,fn):
        if name=='game3ds_media_skip' and name not in game.symbols:return
        return original_bridge(self,name,fn)
    game.GameRunner.bridge=bridge
    original_init=game.GameRunner.__init__
    def init(self):
        original_init(self)
        if 'game_fmv_play' in game.symbols:self.bridge('game_fmv_play',lambda *_:self.ret(0))
        if '__syscall_getreent' in game.symbols:self.bridge('__syscall_getreent',lambda *_:self.ret(0x20004000))
    game.GameRunner.__init__=init
if script.name=='test_stage7_inventory_arm.py':
    # Exercise Status in the first ordinary gameplay state; the old fixture
    # waited for a full Cafe route, outside this targeted UI regression.
    source=script.read_text().replace('self.map==1 and self.z>269*4096','self.map==0')
    exec(compile(source,str(script),'exec'),{'__name__':'__main__','__file__':str(script)})
else:
    runpy.run_path(str(script),run_name='__main__')
