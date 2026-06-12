'use client';

import type { FormEvent, ReactNode } from 'react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Permanent_Marker, Share_Tech_Mono, Russo_One } from 'next/font/google';

const marker = Permanent_Marker({ weight: '400', subsets: ['latin'], display: 'swap' });
const mono   = Share_Tech_Mono({ weight: '400', subsets: ['latin'], display: 'swap' });
const russo  = Russo_One({ weight: '400', subsets: ['latin'], display: 'swap' });

// ─────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────

type CrewKey      = 'explorer' | 'documenter' | 'mentor' | 'reviewer' | 'suggester';
type CrewStatuses = Record<CrewKey, string>;
type ReviewData = {
  strengths?: string[];
  issues?: string[];
  recommendations?: string[];
};
type AnalysisResult = {
  architecture_docs?: Record<string, unknown>;
  onboarding_guide?: string;
  code_review?: ReviewData | string;
  quality_score?: number | string;
  quality_score_label?: string;
  suggested_tasks?: string;
};
type WsMessage = {
  status?: 'processing' | 'completed' | 'error' | 'started';
  step?: string;
  message?: string;
  agent?: string;
  result?: AnalysisResult;
  session_id?: string;
  band_mode?: boolean;
  band_room_id?: string;
  data_summary?: Record<string, unknown>;
};
type QaMessage = {
  role: 'user' | 'mentor' | 'review';
  text: string;
  reviewData?: { strengths?: string[]; issues?: string[]; recommendations?: string[]; score: number; label: string };
};

// ─────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────

const initialCrew: CrewStatuses = {
  explorer: 'idle', documenter: 'idle', mentor: 'idle', reviewer: 'idle', suggester: 'idle',
};

const crewRoster = [
  { key: 'explorer'   as CrewKey, label: 'Explorer',       role: 'maps the repo',     stamp: 'EXP', dot: 'bg-teal-400'  },
  { key: 'documenter' as CrewKey, label: 'Documenter',     role: 'writes the wall',   stamp: 'DOC', dot: 'bg-blue-500'  },
  { key: 'mentor'     as CrewKey, label: 'Mentor',         role: 'guides the route',  stamp: 'MEN', dot: 'bg-[#E4A800]' },
  { key: 'reviewer'   as CrewKey, label: 'Reviewer',       role: 'inspects the code', stamp: 'REV', dot: 'bg-purple-500'},
  { key: 'suggester'  as CrewKey, label: 'Task Suggester', role: 'spots first tasks', stamp: 'TSK', dot: 'bg-red-500'   },
];

// ─────────────────────────────────────────────
// Recent tags helpers (localStorage, max 6)
// ─────────────────────────────────────────────

const RECENT_KEY = 'repowise_recent';
const MAX_RECENT = 6;

function loadRecent(): string[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(RECENT_KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch { return []; }
}

function saveRecent(tags: string[]) {
  try { localStorage.setItem(RECENT_KEY, JSON.stringify(tags)); } catch {}
}

function pushRecent(tags: string[], url: string): string[] {
  const cleaned = tags.filter(t => t !== url);
  const next = [url, ...cleaned].slice(0, MAX_RECENT);
  saveRecent(next);
  return next;
}

function shortLabel(url: string): string {
  // "https://github.com/owner/repo" → "owner/repo"
  const m = url.match(/github\.com\/([^/]+\/[^/]+)/);
  return m ? m[1] : url;
}

const SPRAY_COLORS  = ['#E4A800','#1a1a1a','#e63946','#457b9d','#E4A800bb','#ffffffbb'];
const SPRAY_WORDS   = ['TAGGED','WISE','crew was here','REPO','#einzeinn','DONE','SPRAYED'];

const kwSplitter = /(\b(?:env|config|api|module|file|function|class|export|import|async|await|return|const|let|var|if|else|for|while|app|server|client|route|page|layout|component|hook|state|props|database|service|controller|middleware|auth|error|warning|success|failed|done|processing|pending)\b)/gi;
const kwMatcher  = /\b(?:env|config|api|module|file|function|class|export|import|async|await|return|const|let|var|if|else|for|while|app|server|client|route|page|layout|component|hook|state|props|database|service|controller|middleware|auth|error|warning|success|failed|done|processing|pending)\b/i;

// ─────────────────────────────────────────────
// Spray engine
// ─────────────────────────────────────────────

type Particle =
  | { type?: never; x:number; y:number; vx:number; vy:number; size:number; color:string; alpha:number; life:number; decay:number }
  | { type:'text'; word:string; x:number; y:number; vx:number; vy:number; alpha:number; life:number; decay:number; size:number };
type Drip = { x:number; y:number; vy:number; w:number; color:string; alpha:number; len:number; max:number };

function rnd(a:number,b:number){ return Math.random()*(b-a)+a; }

function createSprayEngine(canvas: HTMLCanvasElement) {
  const ctx = canvas.getContext('2d')!;
  let particles: Particle[] = [];
  let drips: Drip[] = [];
  let raf: number|null = null;
  let active = false;
  let interval: ReturnType<typeof setInterval>|null = null;

  function resize(){
    canvas.width  = canvas.offsetWidth;
    canvas.height = canvas.offsetHeight;
  }
  resize();
  const ro = new ResizeObserver(resize);
  ro.observe(canvas.parentElement ?? canvas);

  function burst(cx:number,cy:number,big:boolean){
    for(let i=0;i<(big?88:18);i++){
      const a=rnd(0,Math.PI*2), s=rnd(big?2:0.5, big?10:3.5);
      particles.push({ x:cx,y:cy, vx:Math.cos(a)*s, vy:Math.sin(a)*s-(big?rnd(1,5):0),
        size:rnd(big?2.5:1,big?8:5), color:SPRAY_COLORS[Math.floor(rnd(0,SPRAY_COLORS.length))],
        alpha:rnd(0.55,0.95), life:rnd(0.4,1), decay:rnd(0.011,0.032) });
    }
  }
  function drip(cx:number,cy:number){
    drips.push({ x:cx+rnd(-22,22),y:cy, vy:rnd(1.8,5), w:rnd(3,9),
      color:Math.random()<0.6?'#E4A800':'#1a1a1a', alpha:rnd(0.5,0.85), len:0, max:rnd(20,78) });
  }
  function word(cx:number,cy:number){
    particles.push({ type:'text', word:SPRAY_WORDS[Math.floor(rnd(0,SPRAY_WORDS.length))],
      x:cx+rnd(-70,70), y:cy+rnd(-35,35), vx:rnd(-0.3,0.3), vy:rnd(-0.6,-1.8),
      alpha:0.88, life:1, decay:0.007, size:Math.floor(rnd(13,28)) });
  }

  function tick(){
    ctx.clearRect(0,0,canvas.width,canvas.height);

    for(let i=drips.length-1;i>=0;i--){
      const d=drips[i];
      ctx.save(); ctx.globalAlpha=d.alpha; ctx.fillStyle=d.color;
      if(d.len<d.max){
        d.len+=d.vy;
        ctx.beginPath(); ctx.roundRect(d.x,d.y,d.w,d.len,d.w/2); ctx.fill();
        ctx.beginPath(); ctx.arc(d.x+d.w/2,d.y+d.len,d.w*0.7,0,Math.PI*2); ctx.fill();
      } else {
        d.alpha-=0.005;
        if(d.alpha<=0){ drips.splice(i,1); ctx.restore(); continue; }
        ctx.beginPath(); ctx.roundRect(d.x,d.y,d.w,d.max,d.w/2); ctx.fill();
        ctx.beginPath(); ctx.arc(d.x+d.w/2,d.y+d.max,d.w*0.7,0,Math.PI*2); ctx.fill();
      }
      ctx.restore();
    }

    for(let i=particles.length-1;i>=0;i--){
      const p=particles[i];
      p.life-=p.decay;
      if(p.life<=0){ particles.splice(i,1); continue; }
      p.vx=(p.vx??0)*0.92;
      p.vy=(p.vy??0)*0.92+0.12;
      p.x+=p.vx??0; p.y+=p.vy;
      ctx.save(); ctx.globalAlpha=p.life*p.alpha;
      if(p.type==='text'){
        ctx.font=`900 ${p.size}px 'Permanent Marker',cursive`;
        ctx.fillStyle=Math.random()<0.5?'#E4A800':'#1a1a1a';
        ctx.fillText(p.word,p.x,p.y);
      } else {
        ctx.fillStyle=p.color;
        ctx.beginPath(); ctx.arc(p.x,p.y,Math.max(0.5,p.size*p.life*0.5),0,Math.PI*2); ctx.fill();
      }
      ctx.restore();
    }

    if(active||particles.length>0||drips.length>0) raf=requestAnimationFrame(tick);
    else raf=null;
  }
  function loop(){ if(!raf) raf=requestAnimationFrame(tick); }

  function trigger(btn:HTMLButtonElement){
    if(active) return;
    active=true;
    const br=btn.getBoundingClientRect(), wr=canvas.getBoundingClientRect();
    const cx=br.left-wr.left+br.width/2, cy=br.top-wr.top+br.height/2;
    burst(cx,cy,true);
    for(let i=0;i<5;i++) drip(cx+rnd(-44,44),cy+rnd(-12,24));
    word(cx,cy-50); loop();
    let t=0;
    interval=setInterval(()=>{
      t++;
      burst(cx+rnd(-30,30),cy+rnd(-18,18),false);
      if(t%4===0) drip(cx+rnd(-55,55),cy+rnd(-12,34));
      if(t%7===0) word(cx+rnd(-90,90),cy+rnd(-65,65));
      loop();
      if(t>24){ clearInterval(interval!); interval=null; active=false; }
    },75);
  }

  function destroy(){
    ro.disconnect();
    if(raf) cancelAnimationFrame(raf);
    if(interval) clearInterval(interval);
  }

  return { trigger, destroy, get isActive(){ return active; } };
}

// ─────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────

function toText(v:unknown){ if(typeof v==='string') return v; if(v==null) return ''; try{ return JSON.stringify(v,null,2); } catch{ return String(v); } }

function highlightKeywords(text:string){
  return text.split(kwSplitter).filter(Boolean).map((p,i)=>
    kwMatcher.test(p)
      ? <span key={i} className="bg-[#E4A800] px-1 font-semibold text-[#1a1a1a]">{p}</span>
      : <span key={i}>{p}</span>
  );
}

function crewFromStep(step:string,prev:CrewStatuses):CrewStatuses{
  const s=step.toLowerCase();
  if(s.includes('explorer'))   return{...prev,explorer:'tagging'};
  if(s.includes('documenter')) return{...prev,explorer:'done',documenter:'tagging'};
  if(s.includes('mentor'))     return{...prev,documenter:'done',mentor:'posted up'};
  if(s.includes('reviewer'))   return{...prev,mentor:'done',reviewer:'inspecting'};
  if(s.includes('suggester'))  return{...prev,reviewer:'done',suggester:'ready'};
  return prev;
}

function apiBase(){ return process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000'; }
function wsBase(){  return apiBase().replace(/^http/,'ws'); }

// ─────────────────────────────────────────────
// Graffiti background SVG
// ─────────────────────────────────────────────

function GraffitiBg() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 1450 900"
      xmlns="http://www.w3.org/2000/svg"
      className="pointer-events-none absolute inset-0 h-full w-full"
      preserveAspectRatio="xMidYMid slice"
      style={{ opacity: 0.045 }}
    >
      {/* tags */}
      <g id="tags" fill="#1a1a1a" fontFamily="Arial Black, Impact, sans-serif">
        <text x="42" y="148" fontSize="96" fontWeight="900" letterSpacing="-2" stroke="#1a1a1a" strokeWidth="8" strokeLinejoin="round">REPO</text>
        <text x="42" y="228" fontSize="96" fontWeight="900" letterSpacing="-2" stroke="#1a1a1a" strokeWidth="8" strokeLinejoin="round">WISE</text>
        <text x="52" y="258" fontSize="18" fontWeight="700" letterSpacing="2">MULTI-AGENT REPO SCOUT</text>
        <g transform="translate(420,310) rotate(-6)"><text fontSize="72" fontWeight="900" stroke="#1a1a1a" strokeWidth="6" strokeLinejoin="round">SCOUT</text></g>
        <g transform="translate(980,80) rotate(3)"><text fontSize="58" fontWeight="900" stroke="#1a1a1a" strokeWidth="5" strokeLinejoin="round">AGENT</text></g>
        <g transform="translate(80,420) rotate(-12)"><text fontSize="48" fontWeight="900" stroke="#1a1a1a" strokeWidth="5" strokeLinejoin="round">BETA</text></g>
        <g transform="translate(60,680) rotate(-3)"><text fontSize="36" fontWeight="900" letterSpacing="3">CODE::NULL</text></g>
        <g transform="translate(180,560) rotate(-8)"><text fontSize="64" fontWeight="900" stroke="#1a1a1a" strokeWidth="5" strokeLinejoin="round">SPRAY</text></g>
        <g transform="translate(1280,48) rotate(5)"><text fontSize="38" fontWeight="900" stroke="#1a1a1a" strokeWidth="4" strokeLinejoin="round">REPO</text></g>
        <g transform="translate(1290,850) rotate(-4)"><text fontSize="42" fontWeight="900" stroke="#1a1a1a" strokeWidth="4" strokeLinejoin="round">WISE</text></g>
        <g transform="translate(740,820) rotate(6)"><text fontSize="52" fontWeight="900" stroke="#1a1a1a" strokeWidth="5" strokeLinejoin="round">GIT</text></g>
        <g transform="translate(48,360) rotate(-18)"><text fontSize="32" fontWeight="900">WALL</text></g>
      </g>
      {/* drips */}
      <g id="drips" fill="#1a1a1a">
        <path d="M 120 0 L 120 60 Q 120 90 110 110 Q 100 130 110 150 Q 120 170 120 200"/><ellipse cx="120" cy="205" rx="7" ry="10"/>
        <path d="M 380 60 L 380 120 Q 380 145 372 162 Q 364 180 372 200 Q 380 218 378 240"/><ellipse cx="378" cy="246" rx="5" ry="8"/>
        <path d="M 720 0 L 720 80 Q 720 105 710 125 Q 700 145 708 168 Q 715 190 714 220"/><ellipse cx="714" cy="226" rx="6" ry="9"/>
        <path d="M 1100 0 L 1100 50 Q 1100 70 1092 88 Q 1084 106 1090 126"/><ellipse cx="1090" cy="132" rx="5" ry="7"/>
        <path d="M 1380 30 L 1380 100 Q 1380 125 1370 145 Q 1360 165 1368 190 Q 1376 210 1374 250"/><ellipse cx="1374" cy="256" rx="6" ry="9"/>
        <path d="M 520 380 L 520 440 Q 520 460 512 478 Q 504 496 510 516"/><ellipse cx="510" cy="522" rx="5" ry="7"/>
        <path d="M 260 580 L 260 650 Q 260 680 250 705 Q 240 730 248 760 Q 256 790 254 840"/><ellipse cx="254" cy="847" rx="7" ry="11"/>
        <path d="M 1050 700 L 1050 760 Q 1050 785 1042 802 Q 1034 820 1040 845"/><ellipse cx="1040" cy="851" rx="5" ry="7"/>
        <path d="M 860 0 L 860 40 Q 860 60 852 78"/><ellipse cx="852" cy="84" rx="4" ry="6"/>
        <path d="M 1200 0 L 1200 30 Q 1200 46 1194 58"/><ellipse cx="1194" cy="63" rx="4" ry="6"/>
      </g>
      {/* shapes */}
      <g id="shapes" fill="none" stroke="#1a1a1a" strokeWidth="3">
        <circle cx="900" cy="120" r="18" strokeWidth="2.5"/>
        <circle cx="960" cy="80" r="14" strokeWidth="2.5"/>
        <circle cx="960" cy="160" r="14" strokeWidth="2.5"/>
        <circle cx="1030" cy="60" r="12" strokeWidth="2"/>
        <circle cx="1030" cy="120" r="12" strokeWidth="2"/>
        <circle cx="1030" cy="180" r="12" strokeWidth="2"/>
        <line x1="918" y1="112" x2="946" y2="86" strokeWidth="1.5"/>
        <line x1="918" y1="128" x2="946" y2="154" strokeWidth="1.5"/>
        <line x1="974" y1="76" x2="1018" y2="64" strokeWidth="1.5"/>
        <line x1="974" y1="86" x2="1018" y2="118" strokeWidth="1.5"/>
        <line x1="974" y1="154" x2="1018" y2="118" strokeWidth="1.5"/>
        <line x1="974" y1="164" x2="1018" y2="178" strokeWidth="1.5"/>
        <rect x="1140" y="60" width="28" height="70" rx="6" strokeWidth="2"/>
        <rect x="1148" y="50" width="12" height="14" rx="3" strokeWidth="2"/>
        <rect x="1143" y="128" width="22" height="8" rx="3" strokeWidth="2"/>
        <rect x="680" y="660" width="60" height="54" rx="8" strokeWidth="2.5"/>
        <rect x="692" y="672" width="14" height="10" rx="2" strokeWidth="2"/>
        <rect x="714" y="672" width="14" height="10" rx="2" strokeWidth="2"/>
        <line x1="694" y1="696" x2="724" y2="696" strokeWidth="2"/>
        <rect x="702" y="654" width="16" height="8" rx="2" strokeWidth="2"/>
        <rect x="780" y="658" width="56" height="56" rx="4" strokeWidth="2.5"/>
        <circle cx="796" cy="678" r="8" strokeWidth="2"/>
        <circle cx="820" cy="678" r="8" strokeWidth="2"/>
        <path d="M 788 700 Q 808 712 828 700" strokeWidth="2"/>
        <rect x="800" y="654" width="8" height="6" rx="1" strokeWidth="1.5"/>
        <rect x="48" y="730" width="100" height="60" rx="4" strokeWidth="4" fill="#1a1a1a" fillOpacity="0.06"/>
        <line x1="1300" y1="400" x2="1420" y2="300" strokeWidth="5" strokeLinecap="round"/>
        <line x1="1320" y1="440" x2="1420" y2="360" strokeWidth="3.5" strokeLinecap="round"/>
        <line x1="1340" y1="480" x2="1430" y2="420" strokeWidth="2" strokeLinecap="round"/>
        <path d="M 1300 700 L 1400 640" strokeWidth="5" strokeLinecap="round"/>
        <path d="M 1385 630 L 1405 638 L 1394 656" strokeWidth="3" strokeLinejoin="round"/>
        <polygon points="1200,300 1240,340 1200,380 1160,340" strokeWidth="2.5"/>
        <circle cx="1070" cy="380" r="24" strokeWidth="2.5"/>
        <line x1="1088" y1="398" x2="1110" y2="420" strokeWidth="3" strokeLinecap="round"/>
        <polyline points="640,800 680,800 680,830 740,830 740,800 800,800 800,840 840,840" strokeWidth="2" strokeLinecap="square"/>
        <circle cx="640" cy="800" r="4" fill="#1a1a1a" stroke="none"/>
        <circle cx="740" cy="800" r="4" fill="#1a1a1a" stroke="none"/>
        <circle cx="800" cy="800" r="4" fill="#1a1a1a" stroke="none"/>
        <circle cx="840" cy="840" r="4" fill="#1a1a1a" stroke="none"/>
        <line x1="1140" y1="200" x2="1440" y2="200" strokeWidth="1.5" strokeDasharray="8 4"/>
        <line x1="600" y1="480" x2="600" y2="520" strokeWidth="2"/>
        <line x1="580" y1="500" x2="620" y2="500" strokeWidth="2"/>
        <circle cx="600" cy="500" r="12" strokeWidth="1.5"/>
      </g>
      {/* marks */}
      <g id="marks" fill="#1a1a1a" fontFamily="Arial Black, Impact, sans-serif">
        <g transform="translate(900,550) rotate(-10)" fontSize="22" fontWeight="900"><text>rw</text></g>
        <g transform="translate(1360,780) rotate(-5)" fontSize="18" fontWeight="900"><text>©rw26</text></g>
        <g transform="translate(48,540) rotate(-15)" fontSize="26" fontWeight="900" stroke="#1a1a1a" strokeWidth="3" strokeLinejoin="round"><text>RW</text></g>
        <g transform="translate(1050,260)">
          <line x1="0" y1="-14" x2="0" y2="14" stroke="#1a1a1a" strokeWidth="2.5"/>
          <line x1="-14" y1="0" x2="14" y2="0" stroke="#1a1a1a" strokeWidth="2.5"/>
          <line x1="-10" y1="-10" x2="10" y2="10" stroke="#1a1a1a" strokeWidth="2.5"/>
          <line x1="10" y1="-10" x2="-10" y2="10" stroke="#1a1a1a" strokeWidth="2.5"/>
        </g>
        <g transform="translate(1240,580)">
          <path d="M 0 0 L 30 0 L 30 -8 L 46 10 L 30 28 L 30 20 L 0 20 Z" stroke="#1a1a1a" strokeWidth="2" strokeLinejoin="round" fill="none"/>
        </g>
        <g transform="translate(840,460)" fill="none" stroke="#1a1a1a" strokeWidth="2.5" strokeLinejoin="round">
          <polyline points="0,24 0,0 10,12 18,0 26,12 36,0 36,24 0,24"/>
        </g>
        <circle cx="160" cy="800" r="4"/>
        <circle cx="180" cy="800" r="4"/>
        <circle cx="200" cy="800" r="4"/>
        <circle cx="220" cy="800" r="4"/>
        <polygon points="1160,500 1180,530 1140,530" fill="none" stroke="#1a1a1a" strokeWidth="2.5" strokeLinejoin="round"/>
      </g>
      {/* texture */}
      <g id="texture" fill="none" stroke="#1a1a1a" strokeWidth="0.6" opacity="0.7">
        <g transform="translate(1180,280)">
          <line x1="0" y1="0" x2="80" y2="80"/><line x1="16" y1="0" x2="80" y2="64"/>
          <line x1="32" y1="0" x2="80" y2="48"/><line x1="48" y1="0" x2="80" y2="32"/>
          <line x1="64" y1="0" x2="80" y2="16"/><line x1="0" y1="16" x2="64" y2="80"/>
          <line x1="0" y1="32" x2="48" y2="80"/><line x1="0" y1="48" x2="32" y2="80"/>
          <line x1="0" y1="64" x2="16" y2="80"/><line x1="80" y1="0" x2="0" y2="80"/>
          <line x1="80" y1="16" x2="16" y2="80"/><line x1="80" y1="32" x2="32" y2="80"/>
          <line x1="80" y1="48" x2="48" y2="80"/><line x1="80" y1="64" x2="64" y2="80"/>
          <line x1="64" y1="0" x2="0" y2="64"/><line x1="48" y1="0" x2="0" y2="48"/>
          <line x1="32" y1="0" x2="0" y2="32"/><line x1="16" y1="0" x2="0" y2="16"/>
        </g>
        <g transform="translate(500,740)">
          <line x1="0" y1="0" x2="100" y2="100"/><line x1="20" y1="0" x2="100" y2="80"/>
          <line x1="40" y1="0" x2="100" y2="60"/><line x1="60" y1="0" x2="100" y2="40"/>
          <line x1="80" y1="0" x2="100" y2="20"/><line x1="0" y1="20" x2="80" y2="100"/>
          <line x1="0" y1="40" x2="60" y2="100"/><line x1="0" y1="60" x2="40" y2="100"/>
          <line x1="0" y1="80" x2="20" y2="100"/>
        </g>
        <g transform="translate(620,280)">
          <line x1="0" y1="0" x2="60" y2="60"/><line x1="12" y1="0" x2="60" y2="48"/>
          <line x1="24" y1="0" x2="60" y2="36"/><line x1="36" y1="0" x2="60" y2="24"/>
          <line x1="48" y1="0" x2="60" y2="12"/><line x1="0" y1="12" x2="48" y2="60"/>
          <line x1="0" y1="24" x2="36" y2="60"/><line x1="0" y1="36" x2="24" y2="60"/>
          <line x1="0" y1="48" x2="12" y2="60"/>
        </g>
        <g transform="translate(1080,720)">
          <line x1="0" y1="0" x2="70" y2="70"/><line x1="14" y1="0" x2="70" y2="56"/>
          <line x1="28" y1="0" x2="70" y2="42"/><line x1="42" y1="0" x2="70" y2="28"/>
          <line x1="56" y1="0" x2="70" y2="14"/><line x1="0" y1="14" x2="56" y2="70"/>
          <line x1="0" y1="28" x2="42" y2="70"/><line x1="0" y1="42" x2="28" y2="70"/>
          <line x1="0" y1="56" x2="14" y2="70"/>
        </g>
        <g fill="#1a1a1a" stroke="none">
          <circle cx="1340" cy="520" r="1.5"/><circle cx="1360" cy="540" r="1.5"/>
          <circle cx="1320" cy="560" r="1.5"/><circle cx="1380" cy="520" r="1.5"/>
          <circle cx="1340" cy="580" r="1.5"/><circle cx="1360" cy="500" r="1.5"/>
          <circle cx="1300" cy="540" r="1.5"/><circle cx="1380" cy="560" r="1.5"/>
          <circle cx="1320" cy="500" r="1.5"/><circle cx="1400" cy="540" r="1.5"/>
          <circle cx="340" cy="460" r="1.5"/><circle cx="360" cy="480" r="1.5"/>
          <circle cx="320" cy="500" r="1.5"/><circle cx="380" cy="460" r="1.5"/>
          <circle cx="340" cy="520" r="1.5"/><circle cx="360" cy="440" r="1.5"/>
          <circle cx="300" cy="480" r="1.5"/><circle cx="380" cy="500" r="1.5"/>
        </g>
      </g>
    </svg>
  );
}

// ─────────────────────────────────────────────
// Main page
// ─────────────────────────────────────────────

export default function Home() {
  const [repoUrl,      setRepoUrl]      = useState('');
  const [statusText,   setStatusText]   = useState('waiting for target...');
  const [isProcessing, setIsProcessing] = useState(false);
  const [result,       setResult]       = useState<AnalysisResult|null>(null);
  const [crewStatus,   setCrewStatus]   = useState<CrewStatuses>(initialCrew);
  const [sessionId,    setSessionId]    = useState<string|null>(null);
  const [bandMode,     setBandMode]     = useState(false);
  const [bandRoomId,   setBandRoomId]   = useState<string|null>(null);
  const [qaInput,      setQaInput]      = useState('');
  const [qaMessages,   setQaMessages]   = useState<QaMessage[]>([]);
  const [isAsking,     setIsAsking]     = useState(false);
  const [isSpraying,   setIsSpraying]   = useState(false);
  const [recentTags,   setRecentTags]   = useState<string[]>([]);

  // Load recent tags from localStorage on mount
  useEffect(() => { setRecentTags(loadRecent()); }, []);

  const canvasRef      = useRef<HTMLCanvasElement>(null);
  const engineRef      = useRef<ReturnType<typeof createSprayEngine>|null>(null);
  const sprayBtnRef    = useRef<HTMLButtonElement>(null);
  const ws             = useRef<WebSocket|null>(null);
  const qaEndRef       = useRef<HTMLDivElement|null>(null);

  useEffect(()=>{
    if(!canvasRef.current) return;
    engineRef.current = createSprayEngine(canvasRef.current);
    return ()=>{ engineRef.current?.destroy(); };
  },[]);

  useEffect(()=>{ return ()=>{ ws.current?.close(); }; },[]);
  useEffect(()=>{ qaEndRef.current?.scrollIntoView({behavior:'smooth'}); },[qaMessages]);

  const archEntries = result?.architecture_docs ? Object.entries(result.architecture_docs) : [];
  const canSubmit   = repoUrl.trim().length>0 && !isProcessing;
  const canAsk      = qaInput.trim().length>0 && !isAsking && sessionId!==null;

  const fireSpray = useCallback(()=>{
    if(!sprayBtnRef.current||!engineRef.current||engineRef.current.isActive) return;
    setIsSpraying(true);
    engineRef.current.trigger(sprayBtnRef.current);
    setTimeout(()=>setIsSpraying(false),2200);
  },[]);

  const startAnalysis = (e:FormEvent<HTMLFormElement>)=>{
    e.preventDefault();
    const repo = repoUrl.trim();
    if(!repo||isProcessing) return;
    fireSpray();
    ws.current?.close();
    setResult(null); setSessionId(null); setQaMessages([]);
    setBandMode(false); setBandRoomId(null);
    setIsProcessing(true);
    // Save to recent tags
    setRecentTags(prev => pushRecent(prev, repo));
    setCrewStatus({explorer:'on the run',documenter:'waiting',mentor:'waiting',reviewer:'waiting',suggester:'waiting'});
    setStatusText('deploying crew...');
    ws.current = new WebSocket(`${wsBase()}/ws/analyze`);
    ws.current.onopen = ()=>{ ws.current?.send(JSON.stringify({repo_url:repo})); };
    ws.current.onmessage = (ev)=>{
      let d:WsMessage;
      try{ d=JSON.parse(ev.data) as WsMessage; } catch{ setStatusText('signal unreadable.'); return; }
      if(d.session_id) setSessionId(d.session_id);
      if(d.band_mode) { setBandMode(true); if(d.band_room_id) setBandRoomId(d.band_room_id); }
      if(d.status==='started'){ setBandMode(!!d.band_mode); return; }
      if(d.status==='processing'){
        const step=d.step||'processing...';
        setStatusText(step);
        setCrewStatus(p=>crewFromStep(step,p));
        return;
      }
      if(d.status==='completed'){
        setStatusText('wall complete. ask the mentor anything.');
        const r = d.result ?? null;
        setResult(r);
        setIsProcessing(false);
        setCrewStatus({explorer:'done',documenter:'done',mentor:'done',reviewer:'done',suggester:'ready'});
        ws.current?.close();
        // Seed initial briefs into chat history so they persist
        const seeds: QaMessage[] = [];
        if(r?.onboarding_guide){
          seeds.push({role:'user',text:'Give me the onboarding guide for this repo.'});
          seeds.push({role:'mentor',text:r.onboarding_guide});
        }
        if(r?.code_review){
          seeds.push({role:'user',text:"What's the code quality looking like?"});
          if(typeof r.code_review==='string'){
            seeds.push({role:'mentor',text:`### Score: ${r.quality_score}/100 [${r.quality_score_label}]\n\n${r.code_review}`});
          } else {
            seeds.push({
              role:'review',
              text:'',
              reviewData: {
                strengths: r.code_review.strengths,
                issues: r.code_review.issues,
                recommendations: r.code_review.recommendations,
                score: typeof r.quality_score === 'number' ? r.quality_score : 0,
                label: r.quality_score_label ?? 'unscored',
              },
            });
          }
        }
        if(r?.suggested_tasks){
          seeds.push({role:'user',text:'Best place to start contributing?'});
          seeds.push({role:'mentor',text:r.suggested_tasks});
        }
        if(seeds.length>0) setQaMessages(seeds);
        return;
      }
      if(d.status==='error'){
        setStatusText(`busted: ${d.message||'analysis failed'}`);
        setIsProcessing(false);
        ws.current?.close();
      }
    };
    ws.current.onerror = ()=>{
      setStatusText('connection severed. is backend running on :8000?');
      setIsProcessing(false);
      ws.current?.close();
    };
  };

  const submitQuestion = async (e:FormEvent<HTMLFormElement>)=>{
    e.preventDefault();
    const q=qaInput.trim();
    if(!q||!sessionId||isAsking) return;
    setQaMessages(p=>[...p,{role:'user',text:q}]);
    setQaInput(''); setIsAsking(true);
    try{
      const res=await fetch(`${apiBase()}/api/session/${sessionId}/ask`,{
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({question:q}),
      });
      if(!res.ok) throw new Error(`HTTP ${res.status}`);
      const data=await res.json() as {answer?:string;error?:string};
      setQaMessages(p=>[...p,{role:'mentor',text:data.answer||data.error||'no answer received.'}]);
    } catch(err){
      setQaMessages(p=>[...p,{role:'mentor',text:`signal lost: ${err instanceof Error?err.message:'unknown error'}`}]);
    } finally{ setIsAsking(false); }
  };

  return (
    <>
      {/* ── Keyframes ── */}
      <style>{`
        @keyframes canShake { 0%,100%{transform:rotate(-4deg) translateX(-2px)} 50%{transform:rotate(4deg) translateX(2px)} }
        @keyframes mistRing  { 0%{transform:scale(0.6);opacity:0.8} 100%{transform:scale(2.4);opacity:0} }
      `}</style>

      {/* ── Spray canvas (fixed, full screen) ── */}
      <canvas
        ref={canvasRef} aria-hidden="true"
        className="pointer-events-none fixed inset-0 z-50 h-full w-full"
        style={{mixBlendMode:'multiply'}}
      />

      {/* ── Root shell: h-screen, no scroll on body ── */}
      <div className={`flex h-screen flex-col overflow-hidden bg-[#f7f6f2] text-[#1a1a1a] ${mono.className} selection:bg-[#E4A800] selection:text-black`}>

        {/* ── Top bar: sidebar title + header in one row ── */}
        <div className="flex flex-1 overflow-hidden">

          {/* ═══ Sidebar ═══ */}
          <aside className="relative flex w-72 flex-shrink-0 flex-col overflow-hidden border-r-4 border-[#1a1a1a] bg-[#f7f6f2]">
            {/* Graffiti bg inside sidebar, more subtle */}
            <div className="pointer-events-none absolute inset-0 overflow-hidden opacity-[0.04]">
              <GraffitiBg />
            </div>

            {/* Logo */}
            <div className="relative z-10 border-b-4 border-dashed border-[#1a1a1a] p-5">
              <div className="flex items-start justify-between gap-3">
                <h1 className={`text-[2.4rem] leading-none ${russo.className}`} style={{letterSpacing:'-1px'}}>
                  repo<span className="text-[#E4A800]">WISE</span>
                </h1>
                <span className="-rotate-3 border-2 border-[#1a1a1a] bg-[#E4A800] px-2 py-1 text-[10px] font-black uppercase shadow-[2px_2px_0_#1a1a1a]">
                  beta wall
                </span>
              </div>
              <p className="mt-2 text-[11px] font-black uppercase tracking-widest text-[#1a1a1a]/60">
                Multi-agent repo scout
              </p>
              {sessionId && (
                <div className="mt-3 border border-dashed border-[#1a1a1a]/30 bg-white/70 px-2 py-1">
                  <p className="truncate text-[10px] font-bold uppercase text-[#1a1a1a]/40">session: {sessionId}</p>
                </div>
              )}
            </div>

            {/* Recent tags */}
            <div className="relative z-10 flex-1 overflow-y-auto p-5">
              <Tag>recent tags</Tag>
              <ul className="mt-4 space-y-3">
                {recentTags.length === 0 && (
                  <li className="border-2 border-dashed border-[#1a1a1a]/20 p-3 text-center">
                    <span className="text-[10px] font-bold uppercase text-[#1a1a1a]/35">no tags yet — spray one!</span>
                  </li>
                )}
                {recentTags.map((t, i) => (
                  <li key={t}>
                    <button
                      type="button"
                      disabled={isProcessing}
                      onClick={() => setRepoUrl(t)}
                      className={`w-full flex items-center gap-3 border-2 border-[#1a1a1a] p-3 shadow-[3px_3px_0_#1a1a1a] transition-all text-left ${
                        i === 0
                          ? 'bg-[#1a1a1a] text-[#E4A800] shadow-[3px_3px_0_#E4A800]'
                          : 'bg-white hover:-translate-y-[1px] hover:shadow-[4px_4px_0_#1a1a1a]'
                      } ${isProcessing ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                    >
                      <span className={`grid h-7 w-7 flex-shrink-0 place-items-center border-2 text-xs font-black ${
                        i === 0 ? 'border-[#E4A800] bg-[#E4A800] text-[#1a1a1a]' : 'border-[#1a1a1a] bg-[#E4A800]'
                      }`}>#{i + 1}</span>
                      <span className="min-w-0 truncate text-sm font-bold">{shortLabel(t)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>

            {/* Crew status — fixed height, never clipped */}
            <div className="relative z-10 flex-shrink-0 border-t-4 border-[#1a1a1a] px-4 py-3">
              <h2 className={`mb-2 text-lg leading-none ${marker.className}`}>crew status</h2>
              <ul className="space-y-1.5">
                {crewRoster.map(c=>(
                  <li key={c.key} className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-1.5 min-w-0">
                      <span className={`h-2.5 w-2.5 flex-shrink-0 border border-[#1a1a1a] ${c.dot}`}/>
                      <span className="truncate text-xs font-bold">{c.label}</span>
                    </span>
                    <span className="flex-shrink-0 border border-[#1a1a1a] bg-white px-1.5 py-0.5 text-[9px] font-bold uppercase shadow-[1px_1px_0_#1a1a1a]">
                      {crewStatus[c.key]}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </aside>

          {/* ═══ Main area ═══ */}
          <div className="relative flex flex-1 flex-col overflow-hidden">
            {/* Shared graffiti background — covers entire main area */}
            <div className="pointer-events-none absolute inset-0 overflow-hidden">
              <GraffitiBg />
            </div>

            {/* ── Top header bar ── */}
            <header className="relative z-10 flex flex-shrink-0 items-center gap-4 border-b-4 border-[#1a1a1a] bg-[#f7f6f2]/90 px-5 py-3 backdrop-blur-sm">
              <div className="w-44 flex-shrink-0">
                <Tag>target</Tag>
                <p className="mt-1 truncate text-[11px] font-bold uppercase text-[#1a1a1a]/60">{statusText}</p>
                {bandMode && <span className="mt-1 inline-block border-2 border-[#E4A800] bg-[#E4A800] px-1.5 py-0.5 text-[8px] font-black uppercase text-[#1a1a1a] shadow-[2px_2px_0_#1a1a1a]">BAND MODE</span>}
              </div>

              <form onSubmit={startAnalysis} className="flex flex-1 items-center gap-3">
                <label className="flex flex-1 items-center border-4 border-[#1a1a1a] bg-white p-1.5 shadow-[4px_4px_0_#1a1a1a] transition-all focus-within:translate-x-[2px] focus-within:translate-y-[2px] focus-within:shadow-[2px_2px_0_#1a1a1a]">
                  <span className="grid h-8 w-8 flex-shrink-0 place-items-center border-2 border-[#1a1a1a] bg-[#E4A800] text-xs font-black">GH</span>
                  <input
                    type="text" placeholder="github.com/owner/repo"
                    className="min-w-0 flex-1 bg-transparent px-3 text-base font-bold outline-none placeholder:text-[#1a1a1a]/30 disabled:cursor-not-allowed"
                    value={repoUrl} onChange={e=>setRepoUrl(e.target.value)} disabled={isProcessing}
                  />
                </label>

                {/* SPRAY BUTTON */}
                <button
                  ref={sprayBtnRef} type="submit" disabled={!canSubmit}
                  className={`relative overflow-visible border-4 border-[#1a1a1a] px-5 py-2.5 font-black uppercase tracking-wide transition-all duration-75 select-none ${russo.className} ${
                    canSubmit
                      ? isSpraying
                        ? 'translate-x-[4px] translate-y-[4px] cursor-wait bg-[#1a1a1a] text-[#E4A800] shadow-none'
                        : 'bg-[#E4A800] text-black shadow-[4px_4px_0_#1a1a1a] hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0_#1a1a1a] active:translate-x-[4px] active:translate-y-[4px] active:shadow-none'
                      : 'cursor-not-allowed bg-gray-300 text-gray-500 shadow-[4px_4px_0_#1a1a1a]'
                  }`}
                >
                  <span className="inline-flex items-center gap-2" style={isSpraying?{animation:'canShake 0.08s infinite'}:undefined}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <rect x="7" y="9" width="8" height="12" rx="2"/>
                      <path d="M10 9V6h4v3"/>
                      <rect x="13" y="4" width="4" height="3" rx="1"/>
                      {isSpraying ? (
                        <><circle cx="20" cy="4" r="1" fill="currentColor" stroke="none"/><circle cx="21" cy="7" r="0.8" fill="currentColor" stroke="none"/><circle cx="20" cy="9.5" r="0.6" fill="currentColor" stroke="none"/></>
                      ) : (
                        <><circle cx="20" cy="4" r="0.8" fill="currentColor" stroke="none" opacity="0.5"/><circle cx="21" cy="7" r="0.6" fill="currentColor" stroke="none" opacity="0.4"/></>
                      )}
                    </svg>
                    {isSpraying?'Spraying...':'Spray'}
                  </span>
                  {isSpraying && (
                    <>
                      <span aria-hidden="true" className="absolute -right-5 -top-5 h-10 w-10 rounded-full border-2 border-[#E4A800] opacity-0" style={{animation:'mistRing 0.6s ease-out infinite'}}/>
                      <span aria-hidden="true" className="absolute -right-5 -top-5 h-10 w-10 rounded-full border-2 border-[#E4A800] opacity-0" style={{animation:'mistRing 0.6s ease-out 0.2s infinite'}}/>
                      <span aria-hidden="true" className="absolute -right-5 -top-5 h-10 w-10 rounded-full border-2 border-[#E4A800] opacity-0" style={{animation:'mistRing 0.6s ease-out 0.4s infinite'}}/>
                    </>
                  )}
                </button>
              </form>
            </header>

            {/* ── Two-panel body — SCROLLS INSIDE, not the page ── */}
            <div className="relative z-10 flex flex-1 overflow-hidden">

              {/* Left: Architecture — own scroll */}
              <section className="flex min-w-0 flex-col border-r-4 border-[#1a1a1a]" style={{flex:'1.05'}}>
                <div className="flex-shrink-0 border-b-2 border-[#1a1a1a]/25 bg-[#f7f6f2]/80 px-6 pt-5 pb-4 backdrop-blur-sm">
                  <p className="mb-1 text-[11px] font-black uppercase text-[#1a1a1a]/50">{archEntries.length} files tagged</p>
                  <div className="flex items-end justify-between gap-4">
                    <h2 className={`text-4xl leading-none ${marker.className}`}>architecture</h2>
                    <span className="border-2 border-[#1a1a1a] bg-[#1a1a1a] px-3 py-1 text-[10px] font-black uppercase text-[#E4A800] shadow-[2px_2px_0_#E4A800]">Explorer + Documenter</span>
                  </div>
                </div>
                <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
                  {!result && !isProcessing && <EmptyState label="STANDBY" title="Awaiting target" body="No repo wall yet."/>}
                  {isProcessing && archEntries.length===0 && <ProcessingWall crewStatus={crewStatus}/>}
                  {archEntries.map(([path,summary],i)=>(
                    <DocCard key={path} index={i} path={path} summary={toText(summary)}/>
                  ))}
                </div>
              </section>

              {/* Right: Mentor Q&A — own scroll */}
              <section className="flex min-w-0 flex-col" style={{flex:'0.95'}}>
                <div className="flex-shrink-0 border-b-2 border-[#1a1a1a]/25 bg-[#f7f6f2]/80 px-6 pt-5 pb-4 backdrop-blur-sm">
                  <p className="mb-1 text-[11px] font-black uppercase text-[#1a1a1a]/50">street-level guidance</p>
                  <div className="flex items-end justify-between gap-4">
                    <h2 className={`text-4xl leading-none ${marker.className}`}>ask the mentor</h2>
                    <span className="border-2 border-[#1a1a1a] bg-[#1a1a1a] px-3 py-1 text-[10px] font-black uppercase text-[#E4A800] shadow-[2px_2px_0_#E4A800]">Mentor</span>
                  </div>
                </div>

                {/* Chat messages */}
                <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">
                  {!result && !isProcessing && <EmptyState label="QUIET" title="Mentor wall is clear" body="Run a repo scan first."/>}
                  {isProcessing && (
                    <Bubble variant="mentor" label="crew feed" raw="Reading tags, sorting files, waiting for the next signal." />
                  )}
                  {qaMessages.map((m,i)=>(
                    m.role === 'review' && m.reviewData ? (
                      <ReviewCard key={i} review={m.reviewData} score={m.reviewData.score} label={m.reviewData.label}/>
                    ) : (
                      <Bubble
                        key={i}
                        variant={m.role==='user'?'user':'mentor'}
                        label={m.role==='user'?'you asked':'mentor says'}
                        raw={m.text}
                      />
                    )
                  ))}
                  {isAsking && (
                    <Bubble variant="mentor" label="mentor is typing">
                      <span className="inline-flex gap-1 text-sm">
                        <span className="animate-bounce" style={{animationDelay:'0ms'}}>▪</span>
                        <span className="animate-bounce" style={{animationDelay:'150ms'}}>▪</span>
                        <span className="animate-bounce" style={{animationDelay:'300ms'}}>▪</span>
                      </span>
                    </Bubble>
                  )}
                  <div ref={qaEndRef}/>
                </div>

                {/* Q&A input — always visible at bottom */}
                {result && (
                  <form onSubmit={submitQuestion} className="flex-shrink-0 flex items-center gap-2 border-t-2 border-[#1a1a1a]/20 bg-[#f7f6f2]/90 px-5 py-3 backdrop-blur-sm">
                    <label className="flex flex-1 items-center border-2 border-dashed border-[#1a1a1a] bg-white px-3 py-2 focus-within:border-solid focus-within:border-[#E4A800]">
                      <span className="grid h-6 w-6 flex-shrink-0 place-items-center border-2 border-[#1a1a1a] bg-white text-xs font-black">Q</span>
                      <input
                        type="text"
                        placeholder={sessionId?'tag your question here...':'run a scan first...'}
                        className="min-w-0 flex-1 bg-transparent px-3 text-sm font-bold outline-none placeholder:text-[#1a1a1a]/35 disabled:cursor-not-allowed"
                        value={qaInput} onChange={e=>setQaInput(e.target.value)}
                        disabled={!sessionId||isAsking}
                      />
                    </label>
                    <button type="submit" disabled={!canAsk}
                      className={`border-2 border-[#1a1a1a] px-4 py-2 text-xs font-black uppercase shadow-[2px_2px_0_#1a1a1a] transition-all ${canAsk?'bg-[#E4A800] text-black hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-[1px_1px_0_#1a1a1a]':'cursor-not-allowed bg-gray-200 text-gray-400'}`}
                    >Ask</button>
                  </form>
                )}
              </section>
            </div>

            {/* ── Footer status bar ── */}
            <footer className="relative z-10 flex flex-shrink-0 border-t-4 border-[#1a1a1a] bg-[#f7f6f2]/90 backdrop-blur-sm">
              <div className="flex flex-1 items-center gap-3 border-r-4 border-[#1a1a1a] px-5 py-3">
                <span className={`h-3 w-3 flex-shrink-0 border border-[#1a1a1a] ${isProcessing?'animate-pulse bg-[#E4A800]':result?'bg-teal-400':'bg-gray-300'}`}/>
                <span className="min-w-0 truncate text-xs font-bold uppercase">{statusText}</span>
                {bandMode && <span className="flex-shrink-0 border border-[#E4A800] bg-[#E4A800]/20 px-1.5 py-0.5 text-[8px] font-black uppercase text-[#E4A800]">via Band</span>}
              </div>
              <div className="flex items-center bg-white px-5 py-3 min-w-[200px]">
                <span className="flex items-center gap-2 text-[10px] font-bold uppercase text-[#1a1a1a]/40">
                  <span className={`h-2 w-2 border border-[#1a1a1a] ${sessionId?'bg-teal-400':'bg-gray-300'}`}/>
                  {sessionId?`session · ${sessionId.slice(0,8)}...`:'no active session'}
                </span>
              </div>
            </footer>
          </div>
        </div>
      </div>
    </>
  );
}

// ─────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────

function Tag({children}:{children:ReactNode}){
  return <span className="inline-block border-2 border-[#1a1a1a] bg-[#E4A800] px-2 py-1 text-[10px] font-black uppercase shadow-[2px_2px_0_#1a1a1a]">{children}</span>;
}

function EmptyState({label,title,body}:{label:string;title:string;body:string}){
  return (
    <div className="relative overflow-hidden border-4 border-dashed border-[#1a1a1a]/25 bg-white/70 p-8 text-center shadow-[5px_5px_0_rgba(26,26,26,0.12)]">
      <div className="absolute -right-8 -top-8 h-24 w-24 rotate-12 border-4 border-[#E4A800] opacity-60"/>
      <span className="mx-auto mb-4 inline-block -rotate-2 border-2 border-[#1a1a1a] bg-[#E4A800] px-3 py-1 text-xs font-black uppercase shadow-[2px_2px_0_#1a1a1a]">{label}</span>
      <h3 className={`text-3xl leading-none text-[#1a1a1a]/80 ${marker.className}`}>{title}</h3>
      <p className="mt-3 text-sm font-bold uppercase text-gray-400">{body}</p>
    </div>
  );
}

function ProcessingWall({crewStatus}:{crewStatus:CrewStatuses}){
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {crewRoster.map(c=>(
        <article key={c.key} className="relative overflow-hidden border-4 border-[#1a1a1a] bg-white/80 p-4 shadow-[5px_5px_0_#1a1a1a]">
          <span className="absolute -right-3 -top-2 rotate-6 border-2 border-[#1a1a1a] bg-[#E4A800] px-2 py-1 text-[10px] font-black">{c.stamp}</span>
          <div className="flex items-center gap-3">
            <span className={`h-4 w-4 border-2 border-[#1a1a1a] ${c.dot}`}/>
            <div className="min-w-0">
              <h3 className="truncate text-sm font-black uppercase">{c.label}</h3>
              <p className="truncate text-xs font-bold uppercase text-gray-400">{crewStatus[c.key]}</p>
            </div>
          </div>
          <p className="mt-4 text-xs font-bold uppercase leading-relaxed text-[#1a1a1a]/65">{c.role}</p>
        </article>
      ))}
    </div>
  );
}

function DocCard({index,path,summary}:{index:number;path:string;summary:string}){
  return (
    <article className="group relative overflow-hidden border-4 border-[#1a1a1a] bg-white/85 p-4 shadow-[6px_6px_0_#1a1a1a] transition-transform hover:-translate-y-1 hover:shadow-[7px_9px_0_#1a1a1a] sm:p-5">
      <span className="absolute -right-3 -top-3 rotate-6 border-2 border-[#1a1a1a] bg-[#E4A800] px-2 py-1 text-[10px] font-black uppercase shadow-[2px_2px_0_#1a1a1a]">file {index+1}</span>
      <h3 className="mb-4 flex min-w-0 items-center gap-3 pr-14 text-sm font-black">
        <span className="grid h-7 w-9 flex-shrink-0 place-items-center border-2 border-[#1a1a1a] bg-[#1a1a1a] text-[10px] text-[#E4A800]">DOC</span>
        <span className="min-w-0 truncate bg-[#E4A800] px-2 py-0.5 text-[#1a1a1a]">{path}</span>
      </h3>
      <p className="whitespace-pre-wrap text-sm leading-6 text-[#1a1a1a]/75">{highlightKeywords(summary)}</p>
    </article>
  );
}

// ─── Inline markdown renderer (no deps) ───────────────────
// Handles: **bold**, *italic*, `code`, # headings, - bullets, blank lines

function renderMarkdown(text: string, isMentor: boolean): ReactNode {
  const codeColor   = isMentor ? 'bg-[#E4A800]/20 text-[#E4A800]' : 'bg-[#1a1a1a]/8 text-[#1a1a1a]';
  const bulletColor = isMentor ? 'bg-[#E4A800]' : 'bg-[#1a1a1a]';
  const headColor   = isMentor ? 'text-[#E4A800]' : 'text-[#1a1a1a]';

  // Split into blocks by blank line
  const blocks = text.split(/\n{2,}/);

  return (
    <div className="space-y-3">
      {blocks.map((block, bi) => {
        const lines = block.split('\n').filter(l => l !== undefined);

        // Bullet list block
        if (lines.every(l => /^[-*]\s/.test(l.trim()) || l.trim() === '')) {
          const items = lines.filter(l => /^[-*]\s/.test(l.trim()));
          return (
            <ul key={bi} className="space-y-1.5 pl-1">
              {items.map((item, ii) => (
                <li key={ii} className="flex items-start gap-2 text-sm leading-5">
                  <span className={`mt-1.5 h-2 w-2 flex-shrink-0 ${bulletColor}`}/>
                  <span>{inlineRender(item.replace(/^[-*]\s+/, ''), isMentor)}</span>
                </li>
              ))}
            </ul>
          );
        }

        // Single-line heading
        if (lines.length === 1) {
          const h3 = lines[0].match(/^###\s+(.*)/);
          const h2 = lines[0].match(/^##\s+(.*)/);
          const h1 = lines[0].match(/^#\s+(.*)/);
          if (h3) return <p key={bi} className={`text-xs font-black uppercase tracking-widest ${headColor}`}>{inlineRender(h3[1], isMentor)}</p>;
          if (h2) return <p key={bi} className={`text-sm font-black uppercase tracking-wide ${headColor}`}>{inlineRender(h2[1], isMentor)}</p>;
          if (h1) return <p key={bi} className={`text-base font-black uppercase ${headColor}`}>{inlineRender(h1[1], isMentor)}</p>;
        }

        // Mixed / paragraph block — render line by line preserving breaks
        return (
          <div key={bi} className="text-sm leading-6">
            {lines.map((line, li) => {
              const h3 = line.match(/^###\s+(.*)/);
              const h2 = line.match(/^##\s+(.*)/);
              const h1 = line.match(/^#\s+(.*)/);
              const bullet = line.match(/^[-*]\s+(.*)/);

              if (h3) return <p key={li} className={`mt-2 text-xs font-black uppercase tracking-widest ${headColor}`}>{inlineRender(h3[1], isMentor)}</p>;
              if (h2) return <p key={li} className={`mt-2 text-sm font-black uppercase tracking-wide ${headColor}`}>{inlineRender(h2[1], isMentor)}</p>;
              if (h1) return <p key={li} className={`mt-2 text-base font-black uppercase ${headColor}`}>{inlineRender(h1[1], isMentor)}</p>;
              if (bullet) return (
                <div key={li} className="flex items-start gap-2 py-0.5">
                  <span className={`mt-2 h-2 w-2 flex-shrink-0 ${bulletColor}`}/>
                  <span>{inlineRender(bullet[1], isMentor)}</span>
                </div>
              );
              if (line.trim() === '') return <br key={li}/>;
              return <p key={li}>{inlineRender(line, isMentor)}</p>;
            })}
          </div>
        );
      })}
    </div>
  );
}

// Inline: **bold**, *italic*, `code`
function inlineRender(text: string, isMentor: boolean): ReactNode {
  const codeClass = isMentor
    ? 'rounded px-1 py-0.5 text-[11px] font-mono bg-[#E4A800]/20 text-[#E4A800]'
    : 'rounded px-1 py-0.5 text-[11px] font-mono bg-[#1a1a1a]/8 text-[#1a1a1a]';

  // Split by code first, then bold, then italic
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g);
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith('`') && part.endsWith('`'))
          return <code key={i} className={codeClass}>{part.slice(1,-1)}</code>;
        if (part.startsWith('**') && part.endsWith('**'))
          return <strong key={i} className="font-black">{part.slice(2,-2)}</strong>;
        if (part.startsWith('*') && part.endsWith('*'))
          return <em key={i} className="italic">{part.slice(1,-1)}</em>;
        return <span key={i}>{part}</span>;
      })}
    </>
  );
}

// ─── Bubble ───────────────────────────────────
function Bubble({
  label, children, variant, raw,
}: {
  label: string;
  children?: ReactNode;
  variant: 'user' | 'mentor';
  raw?: string; // pass raw string to get markdown rendering
}) {
  const isMentor = variant === 'mentor';
  return (
    <article className={`max-w-[38rem] border-4 border-[#1a1a1a] p-4 ${
      isMentor
        ? 'self-start bg-[#1a1a1a] text-white shadow-[6px_6px_0_#E4A800]'
        : 'self-end bg-white text-[#1a1a1a] shadow-[5px_5px_0_#1a1a1a]'
    }`}>
      <div className={`mb-3 w-fit border-2 px-2 py-0.5 text-[10px] font-black uppercase ${
        isMentor ? 'border-[#E4A800] bg-[#E4A800] text-[#1a1a1a]' : 'border-[#1a1a1a] bg-[#E4A800] text-[#1a1a1a]'
      }`}>
        {label}
      </div>
      <div className="font-bold">
        {raw ? renderMarkdown(raw, isMentor) : (
          <div className="whitespace-pre-wrap text-sm leading-6">{children}</div>
        )}
      </div>
    </article>
  );
}

// ─── ReviewCard ──────────────────────────────
function ReviewCard({
  review, score, label,
}: {
  review: { strengths?: string[]; issues?: string[]; recommendations?: string[] };
  score: number;
  label: string;
}) {
  const sections = [
    { key: 'strengths',        title: 'Strengths',              icon: '\u2713', color: 'text-teal-400',  dot: 'bg-teal-400' },
    { key: 'issues',           title: 'Potential Issues',       icon: '\u26A0', color: 'text-red-400',   dot: 'bg-red-400' },
    { key: 'recommendations',  title: 'Improvement Suggestions', icon: '\u2192', color: 'text-[#E4A800]', dot: 'bg-[#E4A800]' },
  ] as const;

  const scoreColor =
    score >= 80 ? 'text-teal-400' :
    score >= 60 ? 'text-green-400' :
    score >= 40 ? 'text-[#E4A800]' :
    score >  0  ? 'text-red-400' :
                  'text-gray-400';

  return (
    <article className="max-w-[38rem] border-4 border-[#1a1a1a] bg-[#1a1a1a] p-4 shadow-[6px_6px_0_#E4A800]">
      {/* Header with score */}
      <div className="mb-4 flex items-center justify-between border-b-2 border-[#E4A800]/30 pb-3">
        <span className="border-2 border-[#E4A800] bg-[#E4A800] px-2 py-0.5 text-[10px] font-black uppercase text-[#1a1a1a]">
          reviewer says
        </span>
        <div className="flex items-center gap-2">
          <span className={`text-2xl font-black ${scoreColor}`}>{score}</span>
          <span className="text-xs font-bold uppercase text-white/50">/100</span>
          <span className="border border-white/20 px-1.5 py-0.5 text-[9px] font-black uppercase text-white/60">
            {label}
          </span>
        </div>
      </div>

      {/* Sections */}
      <div className="space-y-4">
        {sections.map(({ key, title, color, dot }) => {
          const items = review[key as keyof typeof review];
          if (!items || items.length === 0) return null;
          return (
            <div key={key}>
              <div className="mb-2 flex items-center gap-2">
                <span className={`h-2 w-2 flex-shrink-0 ${dot}`}/>
                <span className={`text-[10px] font-black uppercase tracking-widest ${color}`}>{title}</span>
              </div>
              <ul className="space-y-1.5 pl-1">
                {items.map((item, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm leading-5">
                    <span className={`mt-1.5 h-1.5 w-1.5 flex-shrink-0 ${dot} opacity-60`}/>
                    <span className="font-bold text-white/85">{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    </article>
  );
}