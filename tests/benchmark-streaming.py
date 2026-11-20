#!/usr/bin/env python3
"""Local A/B streaming benchmark against ONE disposable Hyprland desktop.

Run in the temporary Playwright tooling container, with Chromium installed.
The source browser must expose CDP on localhost:19223, serve the aquarium fixture
on its own localhost:8999, and run fullscreen at 2844x1198. noVNC is localhost:16911
and Selkies localhost:16912. This measures synthetic keydown-to-decoded-canvas
latency on the server host, not physical workstation input-to-photon latency.
"""
import argparse
import json
import math
from pathlib import Path
import secrets
import statistics
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


parser = argparse.ArgumentParser()
parser.add_argument('--trials', type=int, default=20)
parser.add_argument('--output', default='/tmp/opencode/stream-benchmark.json')
parser.add_argument('--order', default='novnc,selkies,novnc')
args = parser.parse_args()

SOURCE_MARKER = r"""({paused,nonce}) => {
    if (paused) cancelAnimationFrame(g_requestId);
    window.__sourceBench = {frame: 0, input: 0, events:[], started: performance.now()};
    const marker = document.createElement('canvas');
    marker.width = 288; marker.height = 96;
    Object.assign(marker.style, {position:'fixed',left:'600px',top:'40px',zIndex:99999,width:'288px',height:'96px'});
    document.body.append(marker);
    const ctx = marker.getContext('2d');
    document.addEventListener('keydown', e => {
        if (e.code === 'KeyB' && !e.repeat) {
            __sourceBench.input++;__sourceBench.events.push({sequence:__sourceBench.input,at:Date.now()});e.preventDefault();
        }
    }, true);
    function draw() {
        __sourceBench.frame++;
        ctx.fillStyle='black';ctx.fillRect(0,0,288,96);
        // Constant synchronization cells distinguish the marker from the scene.
        ctx.fillStyle='white';ctx.fillRect(0,0,16,96);
        for(let row=0;row<3;row++) {
            const value=row===0 ? __sourceBench.frame : row===1 ? __sourceBench.input : nonce;
            for(let bit=0;bit<16;bit++) {
                ctx.fillStyle=(value & (1<<bit)) ? 'white':'black';
                ctx.fillRect(32+bit*16,row*32,16,32);
            }
        }
        requestAnimationFrame(draw);
    }
    requestAnimationFrame(draw);
}"""

OBSERVER = r"""({sourceSelector,nonce}) => {
    const probe=document.createElement('canvas');probe.width=288;probe.height=96;
    const ctx=probe.getContext('2d',{willReadFrequently:true});
    window.__observerBench={latencies:[],sent:[],frames:0,lastFrame:-1,input:0,valid:false,pending:null,
        started:performance.now(),longTasks:0,longTaskMs:0,errors:0};
    new PerformanceObserver(list=>{for(const e of list.getEntries()) {
        __observerBench.longTasks++;__observerBench.longTaskMs+=e.duration;
    }}).observe({type:'longtask',buffered:false});
    // Start the timer on the actual DOM event sent into the streaming client.
    window.addEventListener('keydown',e=>{
        if(e.code==='KeyB' && !e.repeat) {
            __observerBench.pending={target:__observerBench.input+1,t:performance.now()};
            __observerBench.sent.push({sequence:__observerBench.input+1,at:Date.now()});
        }
    },true);
    function sample() {
        const b=__observerBench;
        try {
            const video=document.querySelector('video');
            const source=video && video.readyState>=2 && video.videoWidth>0 && getComputedStyle(video).display!=='none'
                ? video : document.querySelector(sourceSelector);
            ctx.drawImage(source,600,40,288,96,0,0,288,96);
            const data=ctx.getImageData(0,0,288,96).data;
            const brightness=(x,y)=>data[(y*288+x)*4];
            if(brightness(8,16)>200 && brightness(24,16)<50) {
                let frame=0,input=0,seenNonce=0;
                for(let bit=0;bit<16;bit++) {
                    if(brightness(40+bit*16,16)>128)frame|=1<<bit;
                    if(brightness(40+bit*16,48)>128)input|=1<<bit;
                    if(brightness(40+bit*16,80)>128)seenNonce|=1<<bit;
                }
                if(seenNonce!==nonce){b.valid=false;requestAnimationFrame(sample);return;}
                b.valid=true;
                if(frame!==b.lastFrame){b.frames++;b.lastFrame=frame;}
                b.input=input;
                if(b.pending && input===b.pending.target){
                    b.latencies.push(performance.now()-b.pending.t);b.pending=null;
                }
            }
        } catch(e) { b.errors++; }
        requestAnimationFrame(sample);
    }
    requestAnimationFrame(sample);
}"""


def percentile(values, p):
    return sorted(values)[min(len(values)-1, int((len(values)-1)*p+.5))] if values else None


def static_psnr(source_png, observer_png):
    # The measurement image carries Pillow in its independent Selkies venv.
    sys.path.append('/opt/selkies-test/lib/python3.14/site-packages')
    from PIL import Image, ImageChops, ImageStat
    import io
    box=(100,160,2744,1098)  # Exclude both clients' controls and changing marker.
    a=Image.open(io.BytesIO(source_png)).convert('RGB').crop(box)
    b=Image.open(io.BytesIO(observer_png)).convert('RGB').crop(box)
    rms=ImageStat.Stat(ImageChops.difference(a,b)).rms
    error=math.sqrt(sum(x*x for x in rms)/3)
    return 20*math.log10(255/error) if error else None


results = []
with sync_playwright() as playwright:
    info = json.load(urllib.request.urlopen('http://127.0.0.1:19223/json/version'))
    source_browser = playwright.chromium.connect_over_cdp(info['webSocketDebuggerUrl'].replace(':9222/', ':19223/'))
    source_page = next(p for p in source_browser.contexts[0].pages if '/aquarium/' in p.url)
    observer_browser = playwright.chromium.launch(executable_path='/usr/bin/chromium',
        args=['--no-sandbox','--disable-dev-shm-usage','--disable-gpu'])
    for backend in args.order.split(','):
        assert backend in ('novnc','selkies','selkies-webrtc')
        for paused in (True, False):
            source_page.goto('http://127.0.0.1:8999/aquarium/aquarium.html?numFish=1000&fitWindow=true')
            source_page.wait_for_function("typeof gl !== 'undefined' && gl && document.querySelector('#fps').textContent !== ''")
            source_page.wait_for_timeout(2500)
            geometry = source_page.evaluate('({w:innerWidth,h:innerHeight,canvasW:canvas.width,canvasH:canvas.height,fish:g_numFish[g.globals.fishSetting]})')
            assert (geometry['w'],geometry['h']) == (2844,1198), geometry
            renderer=source_page.evaluate("gl.getParameter(gl.getExtension('WEBGL_debug_renderer_info').UNMASKED_RENDERER_WEBGL)")
            assert 'NVIDIA' in renderer and 'SwiftShader' not in renderer, renderer
            nonce=secrets.randbelow(65535)+1
            source_page.evaluate(SOURCE_MARKER, {'paused':paused,'nonce':nonce})
            context = observer_browser.new_context(ignore_https_errors=True,viewport={'width':2844,'height':1198})
            if backend.startswith('selkies'):
                mode='webrtc' if backend=='selkies-webrtc' else 'websockets'
                response=context.request.post('https://127.0.0.1:16912/api/switch',data={'mode':mode})
                assert response.ok, response.text()
            page = context.new_page()
            websocket_bytes = [0]
            def on_socket(ws):
                ws.on('framereceived',lambda payload: websocket_bytes.__setitem__(0,websocket_bytes[0]+len(payload)))
            page.on('websocket',on_socket)
            page_errors=[]
            page.on('pageerror',lambda e:page_errors.append(str(e)))
            if backend == 'novnc':
                page.goto('https://127.0.0.1:16911/vnc.html?autoconnect=1&resize=off&quality=9&compression=2')
                page.wait_for_function("document.documentElement.classList.contains('noVNC_connected')")
                selector='#noVNC_container canvas'
                quality=page.evaluate("async()=>{const {default:UI}=await import('./app/ui.js');return {jpeg:UI.rfb.qualityLevel,compression:UI.rfb.compressionLevel}}")
            else:
                page.goto('https://127.0.0.1:16912/')
                page.wait_for_function("window.stream_info")
                page.evaluate("window.postMessage({type:'statsOpen',open:true},location.origin)")
                selector='#stream' if backend=='selkies-webrtc' else '#videoCanvas'
                quality=page.evaluate('window.stream_info')
            # Source CDP navigation does not reset compositor idle. Wake the
            # disposable desktop through the same input path as a real user.
            page.mouse.click(1100,200)
            page.keyboard.press('Escape')
            page.wait_for_timeout(1000)
            page.evaluate(OBSERVER,{'sourceSelector':selector,'nonce':nonce})
            try:
                page.wait_for_function('window.__observerBench.valid',timeout=30000)
            except PlaywrightTimeout:
                print('MARKER FAILURE',page.evaluate('window.__observerBench'),page.evaluate("[...document.querySelectorAll('canvas,video')].map(e=>({id:e.id,w:e.width,h:e.height,rect:e.getBoundingClientRect().toJSON()}))"),flush=True)
                page.screenshot(path='/tmp/opencode/stream-marker-failed.png')
                source_page.screenshot(path='/tmp/opencode/stream-source-failed.png')
                raise
            page.mouse.click(1100,200)
            page.wait_for_timeout(3000)
            psnr = static_psnr(source_page.screenshot(),page.screenshot()) if paused else None
            page.evaluate('''() => {
                const b=__observerBench;b.latencies=[];b.sent=[];b.frames=0;b.started=performance.now();b.longTasks=0;b.longTaskMs=0;
            }''')
            byte_start=websocket_bytes[0]
            timeout=False
            for trial in range(args.trials):
                page.keyboard.press('b')
                try:
                    page.wait_for_function('count=>__observerBench.latencies.length>=count',arg=trial+1,timeout=5000)
                except PlaywrightTimeout:
                    timeout=True
                    break
                page.wait_for_timeout(300)
            measured=page.evaluate('({...__observerBench,elapsed:performance.now()-__observerBench.started})')
            source_state=source_page.evaluate('({...__sourceBench,fpsText:document.querySelector("#fps").textContent})')
            latencies=measured['latencies']
            sent_by_sequence={e['sequence']:e['at'] for e in measured['sent']}
            delivery=[e['at']-sent_by_sequence[e['sequence']] for e in source_state['events'] if e['sequence'] in sent_by_sequence]
            result={'backend':backend,'scene':'paused-aquarium' if paused else '1000-fish-aquarium',
                'geometry':geometry,'renderer':renderer,'quality':quality,'trials_completed':len(latencies),
                'timed_out':timeout,'latency_median_ms':statistics.median(latencies) if latencies else None,
                'latency_p95_ms':percentile(latencies,.95),'latency_max_ms':max(latencies) if latencies else None,
                'input_delivery_ms':delivery,'input_delivery_median_ms':statistics.median(delivery) if delivery else None,
                'static_crop_psnr_db':psnr,
                'observed_unique_fps':measured['frames']/(measured['elapsed']/1000),
                'source_state':source_state,'observer':measured,'page_errors':page_errors,
                'page_websocket_mbps':(websocket_bytes[0]-byte_start)*8/(measured['elapsed']*1000)}
            if backend.startswith('selkies'):
                result['selkies_settings']=page.evaluate('({encoder:window.encoder,crf:window.video_crf,rateControl:window.rate_control_mode,fullcolor:window.video_fullcolor,framerate:window.framerate})')
                result['stream_info']=page.evaluate('window.stream_info')
                result['stream_client']=page.evaluate('window.stream_client')
                result['transport_matches_request']=result['stream_client']['transport']==mode
                result['stream_stats']=page.evaluate('window.stream_stats')
            results.append(result)
            Path(args.output).write_text(json.dumps(results,indent=2))
            print(json.dumps({k:result[k] for k in ['backend','scene','trials_completed','timed_out','latency_median_ms','latency_p95_ms','observed_unique_fps']}),flush=True)
            context.close()
            time.sleep(4)  # Selkies' disconnected-client grace period is 3 s.
    observer_browser.close()
    source_browser.close()
