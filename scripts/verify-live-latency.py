#!/usr/bin/env python3
"""Run: docker exec -i frigate python3 - cam3_kitchen < scripts/verify-live-latency.py

Compares direct camera and live-restream decoded frame hashes for 35 seconds.
No video is saved. Uses one extra direct camera connection plus a live viewer.
Excludes the first 8 seconds and requires >=100 unique matching frames.
A 1-second P95 is the default NVR-delay acceptance limit, not a phone guarantee.
Use while the camera's recording input still points directly to its RTSP URL.
WSL invocation wakes the distro and cannot measure unattended availability.
"""
import subprocess, threading, time, statistics, json, argparse, math, yaml
FF='/usr/lib/ffmpeg/7.0/bin/ffmpeg'
parser=argparse.ArgumentParser(description='Measure added NVR video delay using identical frames; not phone latency.')
parser.add_argument('camera')
parser.add_argument('--max-p95',type=float,default=1.0)
args=parser.parse_args()
if not math.isfinite(args.max_p95) or args.max_p95 <= 0:
    parser.error('--max-p95 must be finite and positive')
with open('/config/config.yml') as f: config=yaml.safe_load(f)
if args.camera not in config.get('go2rtc',{}).get('streams',{}):
    parser.error('camera is not a configured live stream')
inputs=config['cameras'][args.camera]['ffmpeg']['inputs']
source=next(i['path'] for i in inputs if 'record' in i.get('roles',[]))
if not source.startswith('rtsp://') or '127.0.0.1' in source:
    parser.error('requires a direct camera RTSP recording input as reference')
urls={'direct':source,'restream':f'rtsp://127.0.0.1:8554/{args.camera}?video=h264'}
results={}; start=time.monotonic()
def capture(label,url):
    cmd=[FF,'-hide_banner','-loglevel','error','-fflags','nobuffer','-flags','low_delay',
         '-rtsp_transport','tcp','-timeout','10000000','-analyzeduration','1000000',
         '-probesize','1000000','-threads','1','-i',url,'-map','0:v:0','-an',
         '-threads','1','-fps_mode','passthrough','-f','framemd5','pipe:1']
    p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
    rows=[]; errors=[]
    def read():
        for line in p.stdout:
            if not line.startswith('#') and ',' in line:
                rows.append((line.strip().split(',')[-1].strip(),time.monotonic()-start))
    def err():
        for line in p.stderr: errors.append(line.rstrip())
    t=threading.Thread(target=read); e=threading.Thread(target=err); t.start();e.start()
    completed_capture=False
    try: p.wait(timeout=35)
    except subprocess.TimeoutExpired:
        completed_capture=True
        p.terminate()
        try:p.wait(timeout=3)
        except subprocess.TimeoutExpired:p.kill();p.wait()
    t.join();e.join();results[label]={'rows':rows,'errors':errors[-4:],'completed_capture':completed_capture}
threads=[threading.Thread(target=capture,args=x) for x in urls.items()]
for t in threads:t.start()
for t in threads:t.join()
maps={}
for k,v in results.items():
    buckets={}
    for h,t in v['rows']:buckets.setdefault(h,[]).append(t)
    maps[k]={h:ts[0] for h,ts in buckets.items() if len(ts)==1}
    print(json.dumps({'input':k,'frames':len(v['rows']),'first_frame_seconds':round(v['rows'][0][1],3) if v['rows'] else None,'diagnostic_tail':v['errors']}))
delta=[maps['restream'][h]-t for h,t in maps['direct'].items() if h in maps['restream'] and t>8]
print(json.dumps({'matching_unique_frames':len(delta),'restream_added_video_delay_seconds':{'min':round(min(delta),3),'median':round(statistics.median(delta),3),'max':round(max(delta),3)} if delta else None,'note':'Relative arrival of identical decoded frames, not camera-to-phone end-to-end latency.'}))
if delta:
    ordered=sorted(delta)
    late=[maps['restream'][h]-t for h,t in maps['direct'].items() if h in maps['restream'] and t>18]
    print(json.dumps({'p95_seconds':round(ordered[int(.95*(len(ordered)-1))],3),'frames_over_1_second':sum(d>1 for d in delta),'late_median_seconds':round(statistics.median(late),3) if late else None,'late_max_seconds':round(max(late),3) if late else None}))

ok=(all(v['completed_capture'] for v in results.values()) and len(delta)>=100
    and sorted(delta)[int(.95*(len(delta)-1))] <= args.max_p95)
print(json.dumps({'camera':args.camera,'ok':ok,'max_p95_seconds':args.max_p95,'minimum_matching_frames':100}),flush=True)
raise SystemExit(0 if ok else 1)
