"""Static evidence inventory of every retail overlay after the school.

This is a source inventory, not a reachability proof or hardware acceptance.
Raw event conditions, callback indices and source locations remain available so
future chapters can distinguish shared maps and later-state edges.
"""
from pathlib import Path
import hashlib, json, re
from functools import cache

ROOT = Path(__file__).resolve().parents[2]
PORT = ROOT / '3ds_port'
MAPS = [f'map{g}_s{s:02}' for g, n in ((2,5),(3,7),(4,7),(5,4),(6,6),(7,4)) for s in range(n)]
SCENES = {
    'map2_s00':('normal','Old Silent Hill streets, K. Gordon, church exterior, bridge, later waterworks'),
    'map2_s01':('normal','Balkan Church, Dahlia, altar pickups, save'),
    'map2_s02':('normal','Central Silent Hill streets; hospital/antique/police approaches; later return states'),
    'map2_s03':('unused','NO_STAGE placeholder; no normal incoming overlay edge'),
    'map2_s04':('shared','Police station; normal/alternate exits selected by original flags'),
    'map3_s00':('normal','Hospital reception and Kaufmann scene'),
    'map3_s01':('normal','Hospital ordinary floors, kitchen, office, basement, generator'),
    'map3_s02':('alternate','Hospital world-change/elevator and Alessa'),
    'map3_s03':('alternate','Hospital plate puzzle, wards, bloodsucker, storage, videotape'),
    'map3_s04':('alternate','Hospital examination, Lisa, Queen plate, return transition'),
    'map3_s05':('alternate','Hospital basement/hidden passage, storeroom, lighter/alcohol, video, hammer'),
    'map3_s06':('normal','Returned hospital, Dahlia and antique key'),
    'map4_s00':('unused','Placeholder, no normal incoming overlay edge'),
    'map4_s01':('shared','Antique shop, Cybil, altar and underground passage'),
    'map4_s02':('alternate','Central town streets and mall/hospital approaches'),
    'map4_s03':('alternate','Mall/Twinfeeler arena, rifle and FMV'),
    'map4_s04':('alternate','Hospital Lisa visions and return streets/Floatstinger exit'),
    'map4_s05':('alternate','Floatstinger arena, city return'),
    'map4_s06':('unused','No normal incoming overlay edge or event records'),
    'map5_s00':('normal','First sewer, key rooms, ambush, locked exits'),
    'map5_s01':('normal','Resort streets, motel/bar/store approaches, lakefront transition'),
    'map5_s02':('normal','Annie bar/Kaufmann and Indian Runner interiors'),
    'map5_s03':('normal','Norman motel/garage/motorcycle, Kaufmann ending dependency'),
    'map6_s00':('alternate','Resort/lakefront streets, boat, lighthouse and sewer approaches'),
    'map6_s01':('alternate','Boat, Cybil and Dahlia story scene'),
    'map6_s02':('alternate','Lighthouse/Alessa and return'),
    'map6_s03':('alternate','Second sewer, Hanged Scratcher/Mumbler, amusement arrival'),
    'map6_s04':('alternate','Amusement park, carousel/Cybil arena, Alessa/Dahlia, Nowhere transition'),
    'map6_s05':('unused','No normal incoming overlay edge or event records'),
    'map7_s00':('nowhere','Nowhere arrival and Lisa scene'),
    'map7_s01':('nowhere','Nowhere first interconnected maze/puzzles/Lisa'),
    'map7_s02':('nowhere','Nowhere second maze, generator, five-item final door, story actors'),
    'map7_s03':('nowhere','Final arena, Incubator/Incubus and ending scripts'),
}

def clean(text):
    return re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)

def tokens(text, pattern):
    return sorted(set(re.findall(pattern, text)))

@cache
def read(p):
    return p.read_text(errors='replace')

@cache
def includes(p):
    result=[]
    for name in re.findall(r'#include\s+"([^"\n]+)"',read(p)):
        candidates=(p.parent/name, ROOT/'include'/name, ROOT/'src/maps'/name,
                    ROOT/name, PORT/name, ROOT/'pc_port/include'/name)
        q=next((q.resolve() for q in candidates if q.is_file()),None)
        if q and q.is_relative_to(ROOT):result.append(q)
    return result

def evidence(paths, pattern):
    return [dict(file=p.relative_to(ROOT).as_posix(), line=i, code=line.strip())
            for p in sorted(paths) for i,line in enumerate(read(p).splitlines(),1)
            if re.search(pattern,line)]

def closure(paths):
    result=set(paths); pending=list(paths)
    while pending:
        p=pending.pop()
        # Record engine headers, but recurse only into gameplay map modules.
        if not (p.is_relative_to(ROOT/'src/maps') or p.is_relative_to(ROOT/'include/maps')):
            continue
        for q in includes(p):
            if q not in result:
                result.add(q);pending.append(q)
    return result

def audit():
    file_ids={int(m[2]):m[1] for m in re.finditer(r'(FILE_XA_\w+)\s*=\s*(\d+)',(ROOT/'include/main/fileenum.h.USA.inc').read_text())}
    maps={}
    for name in MAPS:
        folder=ROOT/'src/maps'/name
        direct=sorted(p for p in folder.iterdir() if p.suffix in ('.h','.c'))
        included=closure(direct)
        text='\n'.join(p.read_text() for p in direct)
        header=(folder/(name+'_header.c')).read_text()
        data=(folder/(name+'_events_data.c')).read_text()
        events=[]
        for m in re.finditer(r'\{([^{}]+)\}',data,re.S):
            fields=dict(re.findall(r'\.(\w+)\s*=\s*([^,\n]+)',clean(m[1])))
            fields={k:v.strip() for k,v in fields.items()}
            if 'sysState' in fields:
                events.append(dict(index=len(events),line=data[:m.start()].count('\n')+1,**fields))
        cb=re.search(r'g_MapEventFuncs\[\][^=]*=\s*\{(.*?)\};',header,re.S)
        callbacks=re.findall(r'\b(?:MapEvent_\w+|func_\w+)\b',clean(cb[1])) if cb else []
        for e in events:
            if e.get('sysState') in ('SysState_LoadOverlay','SysState_LoadRoom'):
                e['arrival_pose_source']=name
                e['arrival_pose_index']=int(e.get('eventParam','0'))
            if e.get('sysState')=='SysState_Fmv':
                e['original_file']=file_ids[2072-int(e.get('eventParam','0'))]
            if e.get('sysState')=='SysState_EventCallback':
                idx=e.get('eventParam','0')
                if idx.isdigit() and int(idx)<len(callbacks): e['callback']=callbacks[int(idx)]
        points=(folder/'map_points.h').read_text()
        extracted=ROOT/'pc_port/build_gen/extracted_data'/(name+'_extracted_data.c')
        config=ROOT/'configs/USA/maps'/('sym.'+name+'.txt')
        missing=tokens('\n'.join(read(p) for p in included if p.is_relative_to(ROOT/'src/maps')),
                       r'INCLUDE_ASM\([^\n]+|INCLUDE_RODATA\([^\n]+')
        maps[name]=dict(
            overlay_index=10+MAPS.index(name),
            baseline_status='already_linked_school_base' if name=='map2_s00' else 'source_exists_not_in_3ds_target',
            world_variant=SCENES[name][0],scene_groups=SCENES[name][1],
            classification=['likely_content_only_addition','shared_native_engine_available','ARM_compatibility_unverified'] if not missing else ['requires_compatibility_work','unresolved_assembly'],
            map_info=re.search(r'\.mapInfo\s*=\s*([^,\n]+)',header)[1].strip(),
            events=events,callbacks=callbacks,
            transitions=[e for e in events if e['sysState']=='SysState_LoadOverlay'],
            room_transitions=[e for e in events if e['sysState']=='SysState_LoadRoom'],
            use=[e for e in events if e.get('activationType')=='TriggerActivationType_Item'],
            save=[e for e in events if 'SaveMenu' in e['sysState']],
            fmv=[e for e in events if e['sysState']=='SysState_Fmv'],
            point_count=len(re.findall(r'\.positionX\s*=',points)),
            characters=tokens(clean((folder/'chara_spawns.h').read_text())+header.split('.charaGroupIds')[-1].split('.charaSpawnInfos')[0],r'Chara_\w+'),
            character_update_callbacks=tokens(header,r'\b\w+_Update\b'),
            character_modules=[p.name for p in direct if p.name.startswith('Chara_') or p.name=='characters.c'],
            items=tokens(text,r'InvItemId_\w+'),flags=tokens(text,r'(?:EventFlag|EvnetFlag)_\w+'),
            item_interactions=evidence(direct,r'Event_ItemTake\(|Player_ItemRemove\(|Event_InvItemCmd\(|requiredItemId'),
            flags_and_persistence=evidence(direct,r'Savegame_EventFlag|g_SavegamePtr->|Player_ItemRemove|Event_InvItemCmd'),
            resources=evidence(direct,r'FILE_(?:ANIM|TIM|XA|BG|CHARA)_|Fs_Queue|Chara_(?:Load|Spawn)|WorldObject_.*"'),
            audio=evidence(direct,r'\.bgmIdx|\.ambientAudioIdx|Audio|Sound|Sfx_|Bgm|FILE_XA_'),
            scripted_calls=evidence(direct,r'void (?:MapEvent_|func_)|SysState_Fmv|Stream_|Fmv|Game_StateSetNext'),
            unresolved_assembly=missing,
            source_sha256={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted(set(direct+[extracted,config]))},
            shared_implementation_files=sorted(p.relative_to(ROOT).as_posix() for p in included if p not in direct))
    return dict(schema=1,scope='Every MAP2_S00..MAP7_S03 retail source overlay; conditional back edges retained',
        baseline='44997c1f3 (School checkpoint over accepted Stage 11A B)',
        method='Static event/header/include/resource scan, with evidence locations. No assertion that all listed edges are reachable in the post-school state.',
        limitations=['Room names are a curated roadmap; point and event indices are authoritative.',
                    'Source-only compatibility classification is provisional until each chapter compiles and links.',
                    'Includes and resource lists are references, not proof of runtime asset lifetime or hardware throughput.'],
        terminal_dependencies=dict(
            maps=['map7_s03','map6_s02 (optional Channeling Stone ending)'],
            status='source_exists_not_linked_requires_compatibility',
            modules=['src/bodyprog/ranking.c','src/bodyprog/credits_init.c','src/screens/credits/credits.c'],
            overlay='FILE_VIN_STF_ROLL_BIN',
            inherited_halting_stubs=['func_8008F94C','func_800904F4','Results_DisplayInfo'],
            note='Native-FMV does not implement staff roll, ranking or Next Fear save progression.',
            evidence=evidence([ROOT/'3ds_port/source/game_services.c',ROOT/'src/maps/map7_s03/map7_s03_3.c',
                               ROOT/'src/maps/map6_s02/map6_s02_2.c',ROOT/'src/bodyprog/credits_init.c'],
                              r'Results_DisplayInfo|results screen|GameFs_StfRollBinLoad|func_801E2|isNextFearMode|clearGameEndings|SaveLocationId_NextFear')),
        maps=maps)

if __name__=='__main__':
    result=audit();out=PORT/'reports/remaining-game-coverage.json'
    out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(result,indent=2)+'\n')
    for name,row in result['maps'].items():
        print(name,len(row['events']),'events;',row['map_info'],
              '->',','.join(sorted(set(e['mapIdx'] for e in row['transitions']))),
              'actors',','.join(row['characters']),
              'FMV',','.join(e.get('eventParam','0') for e in row['fmv']))
        print(' ITEMS',','.join(row['items']))
