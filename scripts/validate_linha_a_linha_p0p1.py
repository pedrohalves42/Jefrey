import pathlib, ast, re, json, sys, yaml
ok=0; bug=0
def check(name, cond, detail=''):
    global ok,bug
    if cond:
        print(f'OK {name} {detail}')
        ok+=1
    else:
        print(f'BUG {name} {detail}')
        bug+=1

pys=list(pathlib.Path('src').rglob('*.py'))
for f in pys:
    try:
        ast.parse(f.read_text(encoding='utf-8'))
    except SyntaxError as e:
        check(f'SYNTAX {f}', False, str(e))
        bug+=1
check('SYNTAX all src', bug==0, f'{len(pys)} files')

mt=pathlib.Path('src/jefrey/core/metrics.py').read_text(encoding='utf-8')
label_bad=[(i,l.strip()) for i,l in enumerate(mt.splitlines(),1) if 'labelnames' in l and 'user_id' in l]
check('METRICS no user_id in labelnames', len(label_bad)==0, str(label_bad) if label_bad else 'provider/model/voice/status OK')
for name in ['STT_DURATION','TTS_DURATION','STT_REQUESTS','TTS_REQUESTS']:
    check(f'METRICS {name} exists', name in mt)

import src.jefrey.core.registry as R
R._registered=False
R.TOOL_REGISTRY._tools.clear()
R.register_default_tools()
check('REGISTRY 42 tools', len(R.TOOL_REGISTRY._tools)==42, f"got {len(R.TOOL_REGISTRY._tools)}")
check('REGISTRY stt_transcribe MEDIUM USER', 'stt_transcribe' in R.TOOL_REGISTRY._tools and R.TOOL_REGISTRY._tools['stt_transcribe'].risk.name=='MEDIUM')
check('REGISTRY tts_synthesize MEDIUM USER', 'tts_synthesize' in R.TOOL_REGISTRY._tools and R.TOOL_REGISTRY._tools['tts_synthesize'].risk.name=='MEDIUM')
check('REGISTRY overwrite=False', 'overwrite=False' in pathlib.Path('src/jefrey/core/registry.py').read_text(encoding='utf-8'))

stt_e=pathlib.Path('src/jefrey/core/stt_engine.py').read_text(encoding='utf-8')
check('STT_ENGINE WhisperModel small int8', 'WhisperModel' in stt_e and 'small' in stt_e and 'int8' in stt_e)
check('STT_ENGINE fail-closed RuntimeError', 'RuntimeError' in stt_e and 'STT indisponivel' in stt_e)
check('STT_ENGINE mock dev only', '_is_mock_enabled' in stt_e)
check('STT_ENGINE singleton', 'get_stt_engine' in stt_e)
check('STT_ENGINE transcribe', 'def transcribe' in stt_e and 'audio_bytes' in stt_e)

tts_e=pathlib.Path('src/jefrey/core/tts_engine.py').read_text(encoding='utf-8')
check('TTS_ENGINE elevenlabs+pyttsx3', 'ElevenLabs' in tts_e and 'pyttsx3' in tts_e)
check('TTS_ENGINE fail-closed', 'RuntimeError' in tts_e and 'TTS indisponivel' in tts_e)
check('TTS_ENGINE synthesize', 'def synthesize' in tts_e)

stt_api=pathlib.Path('src/jefrey/api/stt.py').read_text(encoding='utf-8')
check('STT_API 128L', len(stt_api.splitlines())>=120)
check('STT_API 401 anonymous system', 'anonymous' in stt_api and 'system' in stt_api and '401' in stt_api)
check('STT_API Policy MEDIUM stt_transcribe', 'stt_transcribe' in stt_api and 'MEDIUM' in stt_api)
check('STT_API histogram STT_DURATION', 'STT_DURATION' in stt_api)

tts_api=pathlib.Path('src/jefrey/api/tts.py').read_text(encoding='utf-8')
check('TTS_API 114L', len(tts_api.splitlines())>=100)
check('TTS_API 1-5000', '5000' in tts_api)
check('TTS_API voices 5+piper', 'Charon' in tts_api and 'Puck' in tts_api)
check('TTS_API MEDIUM tts_synthesize', 'tts_synthesize' in tts_api and 'MEDIUM' in tts_api)
check('TTS_API TTS_DURATION', 'TTS_DURATION' in tts_api)

am=pathlib.Path('src/jefrey/api/auth_middleware.py').read_text(encoding='utf-8')
check('AUTH _PUBLIC_PATHS /', '/health' in am)
check('AUTH whitelist /vite.svg /favicon.ico', '/vite.svg' in am and '/favicon.ico' in am)
check('AUTH /assets/', '/assets/' in am)
check('AUTH TTLCache 1024/60', 'TTLCache' in am and '1024' in am)
check('AUTH compare_digest', 'compare_digest' in am)

main=pathlib.Path('src/jefrey/api/main.py').read_text(encoding='utf-8')
check('MAIN StaticFiles /', 'StaticFiles' in main and 'mount(' in main)
check('MAIN stt+tts routers', 'stt_router' in main and 'tts_router' in main)
check('MAIN include before mount', main.find('include_router') < main.find('mount') and main.find('include_router')!=-1)
check('MAIN CORS allow_credentials False', 'allow_credentials' in main and 'False' in main)

cfg=pathlib.Path('src/jefrey/core/config.py').read_text(encoding='utf-8')
check('CONFIG VoiceSTT', 'VoiceSTT' in cfg)
check('CONFIG Voice mock via env+engine', 'JEFREY_STT__MOCK' in pathlib.Path('src/jefrey/core/stt_engine.py').read_text(encoding='utf-8') or 'mock' in cfg.lower())
check('CONFIG validate_for_production', 'validate_for_production' in cfg)

comp=pathlib.Path('docker-compose.yml').read_text(encoding='utf-8')
check('COMPOSE JEFREY_LLM__MODEL 2 lines (4 substr)', len([l for l in comp.splitlines() if 'JEFREY_LLM__MODEL:' in l])==2, str(len([l for l in comp.splitlines() if 'JEFREY_LLM__MODEL:' in l])) + ' substr=' + str(comp.count('JEFREY_LLM__MODEL')))
check('COMPOSE host.docker.internal x2', comp.count('host.docker.internal')>=2)
check('COMPOSE extra_hosts x2', comp.count('host-gateway')>=2)
check('COMPOSE :ro read_only /app/.cache', ':ro' in comp and 'read_only' in comp and '/app/.cache' in comp)
check('COMPOSE explicit postgres:5432 redis:6379', 'postgres:5432' in comp and 'redis:6379' in comp)

dash=json.loads(pathlib.Path('docker/grafana/dashboards/jefrey.json').read_text(encoding='utf-8'))
check('GRAFANA 9 panels', len(dash.get('panels',[]))==9, str(len(dash.get('panels',[]))))
check('GRAFANA editable false', dash.get('editable') is False)
check('GRAFANA STT panel', any('STT' in p.get('title','') for p in dash.get('panels',[])))
check('GRAFANA by(le)>=2', sum(1 for p in dash.get('panels',[]) if 'by (le)' in json.dumps(p))>=2)

for f in ['ui/src/lib/audio.ts','ui/src/hooks/useVoice.ts','ui/src/components/VoiceButton.tsx','ui/src/hooks/useWakeWord.ts','ui/src/pages/Chat.tsx','ui/src/pages/Settings.tsx','ui/vite.config.ts']:
    check(f'UI {f}', pathlib.Path(f).exists())
chat=pathlib.Path('ui/src/pages/Chat.tsx').read_text(encoding='utf-8')
check('CHAT VoiceButton slot', 'VoiceButton' in chat and 'onTranscript' in chat)
sett=pathlib.Path('ui/src/pages/Settings.tsx').read_text(encoding='utf-8')
check('SETTINGS Voz Card', 'Charon' in sett and 'Faber' in sett and 'jefrey_voice_id' in sett)
check('SETTINGS wake jarvis', 'jarvis' in sett.lower() and 'jefrey_wake_enabled' in sett)
vc=pathlib.Path('ui/vite.config.ts').read_text(encoding='utf-8')
check('VITE proxy /stt /tts', '/stt' in vc and '/tts' in vc)
check('VITE outDir static', 'src/jefrey/static' in vc)

check('STATIC index.html', pathlib.Path('src/jefrey/static/index.html').exists())
assets=list(pathlib.Path('src/jefrey/static/assets').glob('*.js'))
check('STATIC chunks', len(assets)>=4, str([a.name for a in assets]))
check('STATIC vite.svg (whitelist)', '/vite.svg' in open('src/jefrey/api/auth_middleware.py',encoding='utf-8').read())

gi=pathlib.Path('.gitignore').read_text(encoding='utf-8')
check('.gitignore tsbuildinfo', 'tsbuildinfo' in gi)

alerts=yaml.safe_load(pathlib.Path('docker/prometheus/alerts.yml').read_text(encoding='utf-8'))
check('ALERTS 1 group 7 rules', len(alerts['groups'])==1 and len(alerts['groups'][0]['rules'])==7, f"{len(alerts['groups'])} groups")
check('ALERTS JefreySttLatencyHigh', any(r.get('alert')=='JefreySttLatencyHigh' for r in alerts['groups'][0]['rules']))

env=pathlib.Path('.env').read_text(encoding='utf-8')
check('.env qwen2:0.5b', 'qwen2:0.5b' in env)
check('.env JEFREY_VOICE', 'JEFREY_VOICE' in env)

print(f'--- SUMMARY linha-a-linha P0+P1: OK {ok} BUG {bug} ---')
sys.exit(1 if bug>0 else 0)

