
"use strict";
const ZONE_NAMES={AE:"Atlantic City Electric",AEP:"AEP (Ohio and Appalachia)",AP:"Allegheny Power",ATSI:"FirstEnergy Ohio",BC:"Baltimore Gas and Electric",CE:"ComEd (Chicago)",DAY:"Dayton",DEOK:"Duke Ohio and Kentucky",DOM:"Dominion (Virginia)",DPL:"Delmarva",DUQ:"Duquesne (Pittsburgh)",EKPC:"East Kentucky",JC:"Jersey Central",ME:"Met-Ed",PE:"PECO (Philadelphia)",PEP:"Pepco (Washington)",PL:"PPL (Pennsylvania)",PN:"Penelec",PS:"PSEG (New Jersey)",RECO:"Rockland"};
const SHORT={DOM:"Dominion",AEP:"AEP"};
const FUELS=[["gas","Gas","--f-gas"],["coal","Coal","--f-coal"],["nuclear","Nuclear","--f-nuclear"],["hydro","Hydro","--f-hydro"],["wind","Wind","--f-wind"],["solar","Solar","--f-solar"],["other","Other","--f-other"]];
const NS="http://www.w3.org/2000/svg";
const has=id=>!!document.getElementById(id);
const $=id=>document.getElementById(id)||document.createElement("div");
const css=v=>getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const fmt=(x,d=0)=>x==null||!isFinite(x)?"n/a":Number(x).toLocaleString("en-US",{minimumFractionDigits:d,maximumFractionDigits:d});
const sign=(x,d=1)=>x==null?"n/a":(x>0?"+":x<0?"−":"")+fmt(Math.abs(x),d);
const listJoin=a=>a.length<3?a.join(" and "):a.slice(0,-1).join(", ")+" and "+a[a.length-1];
const monthsBetween=(a,b)=>{const [ya,ma]=a.split("-").map(Number),[yb,mb]=b.split("-").map(Number);return (yb-ya)*12+(mb-ma);};
const pval=p=>p==null?"n/a":p<0.001?"p < 0.001":"p = "+(p<0.01?p.toFixed(3):p.toFixed(2));
const monthName=m=>{const [y,mo]=m.split("-");return ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][+mo-1]+" "+y;};
function S(tag,attrs,parent){const e=document.createElementNS(NS,tag);for(const k in attrs)e.setAttribute(k,attrs[k]);if(parent)parent.appendChild(e);return e;}
function T(parent,x,y,str,attrs){const t=S("text",Object.assign({x,y},attrs||{}),parent);t.textContent=str;return t;}
const lin=(d0,d1,r0,r1)=>v=>r0+(v-d0)/(d1-d0||1)*(r1-r0);
function ticks(lo,hi,n){const span=hi-lo||1,step0=Math.pow(10,Math.floor(Math.log10(span/n)));const err=span/n/step0;const step=step0*(err>=7.5?10:err>=3.5?5:err>=1.5?2:1);const out=[];for(let v=Math.ceil(lo/step)*step;v<=hi+step*1e-9;v+=step)out.push(+v.toFixed(10));return out;}
function path(pts){let d="",pen=false;for(const p of pts){if(p==null||p[1]==null||!isFinite(p[1])){pen=false;continue;}d+=(pen?"L":"M")+p[0].toFixed(1)+" "+p[1].toFixed(1);pen=true;}return d;}
const tip=document.createElement("div");tip.className="tip";tip.setAttribute("role","status");document.body.appendChild(tip);
function showTip(html,ev){tip.innerHTML=html;tip.style.opacity=1;const w=tip.offsetWidth,h=tip.offsetHeight;let x=ev.clientX+16,y=ev.clientY+16;if(x+w>innerWidth-8)x=ev.clientX-w-16;if(y+h>innerHeight-8)y=ev.clientY-h-16;tip.style.left=Math.max(8,x)+"px";tip.style.top=Math.max(8,y)+"px";}
function hideTip(){tip.style.opacity=0;}
function frame(host,height){host.innerHTML="";const W=Math.max(300,host.clientWidth||600);const svg=S("svg",{viewBox:`0 0 ${W} ${height}`,width:W,height:height,role:"img"},host);return {svg,W,H:height};}
function yAxis(svg,y,tk,x0,x1,f){for(const t of tk){S("line",{x1:x0,x2:x1,y1:y(t),y2:y(t),class:"grid"},svg);T(svg,x0-8,y(t)+4,f(t),{"text-anchor":"end"});}}
function yearAxis(svg,months,x,yBase){months.forEach((m,i)=>{if(m.endsWith("-01")){S("line",{x1:x(i),x2:x(i),y1:yBase,y2:yBase+5,class:"axis-line"},svg);T(svg,x(i),yBase+20,m.slice(0,4),{"text-anchor":"middle"});}});}
function hoverLayer(svg,x0,x1,y0,y1,n,xOf,onMove){
  const cross=S("line",{y1:y0,y2:y1,stroke:"#555","stroke-dasharray":"3 3",opacity:0},svg);
  const r=S("rect",{x:x0,y:y0,width:x1-x0,height:y1-y0,fill:"transparent"},svg);
  const move=ev=>{const b=svg.getBoundingClientRect();const px=(ev.clientX-b.left)*(svg.viewBox.baseVal.width/b.width);let i=Math.round((px-x0)/(x1-x0)*(n-1));i=Math.max(0,Math.min(n-1,i));cross.setAttribute("x1",xOf(i));cross.setAttribute("x2",xOf(i));cross.setAttribute("opacity",1);const html=onMove(i);if(html)showTip(html,ev);};
  r.addEventListener("pointermove",move);r.addEventListener("pointerdown",move);
  r.addEventListener("pointerleave",()=>{cross.setAttribute("opacity",0);hideTip();});
}
function pressGroup(host,items,current,onPick){host.innerHTML="";items.forEach(([key,label])=>{const b=document.createElement("button");b.type="button";b.textContent=label;b.setAttribute("aria-pressed",key===current);b.addEventListener("click",()=>onPick(key));host.appendChild(b);});}
function roll12(a){return a.map((_,i)=>{if(i<11)return null;let s=0,n=0;for(let j=i-11;j<=i;j++){if(a[j]!=null){s+=a[j];n++;}}return n>=11?s/n:null;});}

let R=null;const state={scmZone:"AEP",scmKind:"levels",mefRegion:"PJM"};

/* ---------- hero ---------- */
function drawHero(){
  const svg=$("heroArt");svg.innerHTML="";const W=svg.clientWidth||innerWidth,H=svg.clientHeight||innerHeight;
  svg.setAttribute("viewBox",`0 0 ${W} ${H}`);
  const s=R.synthetic_control.AEP.levels;const a=roll12(s.actual_index),b=roll12(s.synthetic_index);
  const idx=a.map((v,i)=>v==null?-1:i).filter(i=>i>=0);if(!idx.length)return;
  const vals=idx.flatMap(i=>[a[i],b[i]]);const lo=Math.min(...vals),hi=Math.max(...vals);
  const x=lin(idx[0],idx[idx.length-1],W*0.04,W*0.985),y=lin(lo-(hi-lo)*0.55,hi+(hi-lo)*0.12,H*0.9,H*0.14);
  const t0=s.months.indexOf(s.treatment_start);
  if(t0>=idx[0]){S("line",{x1:x(t0),x2:x(t0),y1:H*0.14,y2:H*0.9,stroke:"#3a3a3a","stroke-dasharray":"2 6"},svg);T(svg,x(t0)+10,H*0.14+14,"January 2023",{style:"fill:#8a8a8a;font-size:13px"});}
  const fill=S("path",{d:path(idx.map(i=>[x(i),y(a[i])]))+path(idx.slice().reverse().map(i=>[x(i),y(b[i])])).replace("M","L")+"Z",fill:css("--hot"),opacity:.13},svg);
  const pb=S("path",{d:path(idx.map(i=>[x(i),y(b[i])])),fill:"none",stroke:css("--cool"),"stroke-width":2},svg);
  const pa=S("path",{d:path(idx.map(i=>[x(i),y(a[i])])),fill:"none",stroke:css("--hot"),"stroke-width":3},svg);
  if(!matchMedia("(prefers-reduced-motion:reduce)").matches&&!drawHero.done){
    drawHero.done=true;
    for(const p of [pa,pb]){const L=p.getTotalLength();p.style.strokeDasharray=L;p.style.strokeDashoffset=L;p.getBoundingClientRect();p.style.transition="stroke-dashoffset 2.6s cubic-bezier(.3,.1,.2,1)";p.style.strokeDashoffset=0;}
    fill.style.opacity=0;fill.style.transition="opacity 1.2s 2.2s";requestAnimationFrame(()=>fill.style.opacity=.13);
  }
}

/* ---------- headline figures and prose ---------- */
function fillText(){
  const h=R.headline,sc=R.synthetic_control,aep=sc.AEP.levels,dom=sc.DOM.levels,domA=sc.DOM.acceleration,zs=R.zone_share;
  const hours=R.meta.records_analyzed||null;
  const gw=h.since_2023.extra_load_mw/1000;
  $("figures").innerHTML=[
    [fmt(R.meta.records_analyzed/1e6,1)+"M","hourly records analyzed, "+R.meta.data_start.slice(0,4)+" to "+monthName(R.meta.data_end.slice(0,7))],
    [fmt(gw,1)+" GW","of round-the-clock demand in two PJM zones beyond their pre-2023 paths"],
    [fmt(h.since_2023.mt_co2_per_year,1)+" Mt","of CO₂ a year to supply it at PJM’s marginal rate"],
    [sign(h.marginal_vs_average_pct,0)+"%","carbon in PJM’s marginal MWh compared with its average MWh"]
  ].map(([b,s])=>`<div><b class="num">${b}</b><span>${s}</span></div>`).join("");

  const zt=R.zone_trends,top=zt[0],second=zt[1],rest=zt.filter(z=>!z.hot);
  const restMax=Math.max(...rest.map(z=>z.mean.change_pct_points));
  $("t-zones").innerHTML=`Of ${zt.length} PJM zones, two stand apart. ${SHORT[top.zone]||top.zone} went from <strong>${sign(top.mean.growth_before_pct,1)}% a year to ${sign(top.mean.growth_after_pct,1)}%</strong>. ${SHORT[second.zone]||second.zone} went from ${sign(second.mean.growth_before_pct,1)}% a year to <strong>${sign(second.mean.growth_after_pct,1)}%</strong>. No other zone sped up by more than ${fmt(restMax,1)} points.`;

  $("t-share").innerHTML=`Dominion now draws <strong>${fmt(zs.DOM.latest_12m_avg_pct,1)}% of all PJM electricity</strong>, up from ${fmt(zs.DOM.first_year_avg_pct,1)}% in ${R.meta.data_start.slice(0,4)}. A break test dates the change in slope: AEP in ${monthName(zs.AEP.break_test.break_month)} (${pval(zs.AEP.break_test.p_value)}) and Dominion in ${monthName(zs.DOM.break_test.break_month)} (${pval(zs.DOM.break_test.p_value)}).`;

  const reg=R.regions,bas=Object.keys(R.meta.cleaning.balancing_authorities).filter(k=>reg[k]);
  const sig=bas.filter(k=>reg[k].baseload_trend.change_p_value<0.05&&reg[k].baseload_trend.change_pct_points>0).map(k=>reg[k].label.split(" (")[0]);
  $("t-regions").innerHTML=`Baseload growth sped up significantly in <strong>${sig.length} of ${bas.length}</strong> large grid regions${sig.length?": "+listJoin(sig):""}. In the others, the change since 2023 is within what chance would produce.`;

  const pj=R.emissions.PJM,last=pj.by_year.filter(y=>!y.partial_year).slice(-1)[0];
  $("t-mef").innerHTML=`In PJM since 2023, one more megawatt-hour of demand adds <strong>${fmt(h.pjm_marginal_factor,2)} tonnes of CO&#8322;</strong>. The average megawatt-hour carries ${fmt(h.pjm_average_factor,2)}. Before 2023 the marginal rate was ${fmt(pj.change_test.before,2)}; the drop is statistically clear (${pval(pj.change_test.p_value)}), but the marginal megawatt-hour still carries ${fmt(h.marginal_vs_average_pct,0)}% more carbon than the average one.`;

  $("t-calc").innerHTML=`Apply PJM&rsquo;s marginal rate to the demand the two zones added. The answer depends on what counts as extra, so both readings are shown.`;
  const card=(title,desc,t)=>`<div><h3>${title}</h3><p style="font-size:15.5px">${desc}</p>
    <div class="big num">${fmt(t.mt_co2_per_year,1)}<small>Mt CO&#8322; / year</small></div>
    <span class="fine">Range ${fmt(t.mt_co2_range[0],1)} to ${fmt(t.mt_co2_range[1],1)}</span>
    <dl><dt>Extra demand, average</dt><dd class="num">${fmt(t.extra_load_mw/1000,1)} GW</dd>
    <dt>Dominion</dt><dd class="num">${fmt(t.by_zone_mw.DOM)} MW</dd><dt>AEP</dt><dd class="num">${fmt(t.by_zone_mw.AEP)} MW</dd>
    <dt>Energy per year</dt><dd class="num">${fmt(t.extra_twh_per_year,1)} TWh</dd>
    <dt>If the average rate were used</dt><dd class="num">${fmt(t.mt_co2_if_average_factor,1)} Mt</dd></dl></div>`;
  $("calc").innerHTML=card("New since 2023","Demand above what each zone&rsquo;s own pre-2023 trend, adjusted by its comparison zones, would have produced. The stricter reading.",h.since_2023)
    +card("All divergence since 2019&ndash;22","Demand above comparison zones, measured from each zone&rsquo;s 2019&ndash;22 level. Includes Dominion&rsquo;s growth that was already underway.",h.since_baseline);
  $("t-calc-fine").innerHTML=`Averages for ${monthName(h.window[0])} to ${monthName(h.window[1])}. Ranges combine leave-one-out refits of the synthetic control with the 95% interval on the marginal factor (${fmt(h.pjm_marginal_factor_ci[0],3)} to ${fmt(h.pjm_marginal_factor_ci[1],3)} t/MWh).`;

  const ef=R.meta.emission_factors_t_per_mwh;
  $("m-data").innerHTML=`EIA Form 930: hourly demand and generation by fuel for ${bas.length} balancing authorities and hourly demand for ${R.meta.zones_used.length} PJM zones, ${R.meta.data_start} through ${R.meta.data_end} UTC. Values at or below zero and spikes beyond 2.5 times the surrounding week&rsquo;s median are removed; gaps of up to six hours are interpolated; months with under 90% coverage are dropped. CO&#8322; is estimated from generation using EIA&rsquo;s 2023 national factors: coal ${ef.coal}, gas ${ef.gas}, petroleum ${ef.oil} t/MWh.`;
  $("m-donors").textContent=`With ${aep.n_donors} comparison zones, the smallest possible placebo p-value is ${(1/(aep.n_donors+1)).toFixed(3)}.`;
  const sb=[...document.querySelectorAll(".hero .legend span")][0];if(sb)sb.textContent=`Built from ${Object.keys(aep.weights).length} other zones that tracked it within ${fmt(aep.rmspe_pre_pct,1)}% before 2023.`;
  $("t-break").innerHTML=`ChatGPT launched in November 2022. The estimated breaks arrive ${monthsBetween("2022-11",zs.AEP.break_test.break_month)} and ${monthsBetween("2022-11",zs.DOM.break_test.break_month)} months later. Large data centers take a year or more to build and energize, so a lag of that order is what a construction-led surge would look like.`;
  $("r-run").textContent=R.meta.generated_utc+" UTC";
  $("f-updated").textContent=`Results generated ${R.meta.generated_utc} UTC. Latest grid hour in the data: ${R.meta.data_end} UTC.`;

  $("tbl-zones").innerHTML="<tr><th>Zone</th><th>Growth 2019–22, %/yr</th><th>Growth 2023 on, %/yr</th><th>Change, points</th><th>p-value</th><th>Recent average, MW</th></tr>"+zt.map(z=>`<tr><td>${ZONE_NAMES[z.zone]||z.zone}</td><td class="num">${sign(z.mean.growth_before_pct,2)}</td><td class="num">${sign(z.mean.growth_after_pct,2)}</td><td class="num">${sign(z.mean.change_pct_points,2)}</td><td class="num">${z.mean.change_p_value<0.001?"<0.001":z.mean.change_p_value.toFixed(3)}</td><td class="num">${fmt(z.latest_12m_mean_mw)}</td></tr>`).join("");
  $("tbl-mef").innerHTML="<tr><th>Region</th><th>Marginal 2019–22</th><th>Marginal 2023 on</th><th>Change p-value</th><th>Average, latest full year</th></tr>"+Object.entries(R.emissions).filter(([,v])=>v.change_test).map(([k,v])=>{const c=v.change_test,l=v.by_year.filter(y=>!y.partial_year).slice(-1)[0];return `<tr><td>${v.label}</td><td class="num">${fmt(c.before,3)}</td><td class="num">${fmt(c.after,3)}</td><td class="num">${c.p_value<0.001?"<0.001":c.p_value.toFixed(3)}</td><td class="num">${l?fmt(l.average_intensity,3):"n/a"}</td></tr>`;}).join("");
}

/* ---------- chart: zones ---------- */
function drawZones(){
  const narrow=($("c-zones").clientWidth||600)<520,zname=z=>narrow?(ZONE_NAMES[z]||z).split(" (")[0]:(ZONE_NAMES[z]||z);
  const zt=R.zone_trends,row=30,m={t:8,r:narrow?44:60,b:30,l:narrow?168:190};
  const {svg,W,H}=frame($("c-zones"),m.t+m.b+row*zt.length);
  const vals=zt.map(z=>z.mean.change_pct_points),lo=Math.min(0,...vals),hi=Math.max(...vals);
  const x=lin(lo,hi,m.l,W-m.r);
  for(const t of ticks(lo,hi,5)){S("line",{x1:x(t),x2:x(t),y1:m.t,y2:H-m.b,class:"grid"},svg);T(svg,x(t),H-m.b+18,sign(t,0),{"text-anchor":"middle"});}
  zt.forEach((z,i)=>{
    const y=m.t+i*row,v=z.mean.change_pct_points,x0=x(Math.min(0,v)),w=Math.max(1,Math.abs(x(v)-x(0)));
    T(svg,m.l-10,y+row/2+4,zname(z.zone),{"text-anchor":"end",class:z.hot?"lab":""});
    S("rect",{x:x0,y:y+6,width:w,height:row-12,rx:2,fill:z.hot?css("--hot"):css("--neutral")},svg);
    T(svg,x(Math.max(0,v))+7,y+row/2+4,sign(v,1),{class:z.hot?"lab":""});
    const hit=S("rect",{x:0,y:y,width:W,height:row,fill:"transparent"},svg);
    const html=`<b>${ZONE_NAMES[z.zone]||z.zone}</b><br>2019–22: ${sign(z.mean.growth_before_pct,2)}% a year<br>2023 on: ${sign(z.mean.growth_after_pct,2)}% a year<br><em>Change ${sign(v,2)} points, ${pval(z.mean.change_p_value)}</em>`;
    hit.addEventListener("pointermove",ev=>showTip(html,ev));hit.addEventListener("pointerleave",hideTip);
  });
  S("line",{x1:x(0),x2:x(0),y1:m.t,y2:H-m.b,stroke:css("--zero")},svg);
}

/* ---------- chart: synthetic control ---------- */
function drawSCM(){
  const zones=Object.keys(R.synthetic_control);
  pressGroup($("scm-zone"),zones.map(z=>[z,ZONE_NAMES[z]]),state.scmZone,k=>{state.scmZone=k;drawSCM();drawTwinDetail();});
  pressGroup($("scm-kind"),[["levels","Against comparison zones"],["acceleration","Beyond its own earlier trend"]],state.scmKind,k=>{state.scmKind=k;drawSCM();drawTwinDetail();});
  const both=R.synthetic_control[state.scmZone],s=both[state.scmKind]||both.levels,name=SHORT[state.scmZone];
  $("scm-title").textContent=`${name} demand: gap to its synthetic twin`;
  $("scm-sub").textContent=state.scmKind==="levels"?"Percent above or below the weighted mix of comparison zones, monthly.":"Percent, after removing each zone’s own 2019–22 trend. Asks only whether growth sped up.";
  const m={t:14,r:16,b:34,l:50},{svg,W,H}=frame($("c-scm"),Math.max(300,Math.min(440,($("c-scm").clientWidth||600)*0.6)));
  const n=s.months.length,all=s.gap_pct.concat(s.placebo_band_pct.low,s.placebo_band_pct.high).filter(v=>v!=null);
  const lo=Math.min(-5,...all),hi=Math.max(5,...all),pad=(hi-lo)*0.06;
  const x=lin(0,n-1,m.l,W-m.r),y=lin(lo-pad,hi+pad,H-m.b,m.t);
  yAxis(svg,y,ticks(lo,hi,6),m.l,W-m.r,v=>sign(v,0)+"%");yearAxis(svg,s.months,x,H-m.b);
  const up=s.placebo_band_pct.high.map((v,i)=>[x(i),y(v)]),dn=s.placebo_band_pct.low.map((v,i)=>[x(i),y(v)]).reverse();
  S("path",{d:path(up)+path(dn).replace("M","L")+"Z",fill:css("--band")},svg);
  S("line",{x1:m.l,x2:W-m.r,y1:y(0),y2:y(0),stroke:css("--zero")},svg);
  const t0=s.months.indexOf(s.treatment_start);
  if(t0>0){S("line",{x1:x(t0),x2:x(t0),y1:m.t,y2:H-m.b,stroke:"#8a8a8a","stroke-dasharray":"3 4"},svg);T(svg,x(t0)-8,m.t+12,"Fitted on these months",{"text-anchor":"end"});T(svg,x(t0)+8,m.t+12,"Compared from here");}
  S("path",{d:path(s.gap_pct.map((v,i)=>[x(i),y(v)])),fill:"none",stroke:css("--hot"),"stroke-width":2,"stroke-linejoin":"round"},svg);
  const dot=S("circle",{r:4.5,fill:css("--hot"),stroke:css("--bg"),"stroke-width":2,opacity:0},svg);
  hoverLayer(svg,m.l,W-m.r,m.t,H-m.b,n,i=>x(i),i=>{dot.setAttribute("cx",x(i));dot.setAttribute("cy",y(s.gap_pct[i]));dot.setAttribute("opacity",1);return `<b>${monthName(s.months[i])}</b><br>Gap: ${sign(s.gap_pct[i],1)}%<br><em>Placebo zones: ${sign(s.placebo_band_pct.low[i],1)}% to ${sign(s.placebo_band_pct.high[i],1)}%</em>`;});
  svg.addEventListener("pointerleave",()=>dot.setAttribute("opacity",0));
  const w=Object.entries(s.weights).map(([z,v])=>`${ZONE_NAMES[z]||z} ${fmt(v*100)}%`).join(", ");
  $("scm-stats").innerHTML=[
    [sign(s.recent_gap_pct,1)+"%","gap, "+monthName(s.recent_window[0])+" to "+monthName(s.recent_window[1])],
    [fmt(s.recent_gap_mw)+" MW","average extra demand (leave-one-out: "+fmt(Math.min(...s.recent_gap_mw_leave_one_out))+" to "+fmt(Math.max(...s.recent_gap_mw_leave_one_out))+")"],
    [s.rank,"rank among all zones by post/pre error ratio (p = "+s.placebo_p_value.toFixed(3)+")"],
    [fmt(s.rmspe_pre_pct,1)+"%","typical miss before 2023; smaller means a closer twin"]
  ].map(([b,t])=>`<div><b class="num">${b}</b><span>${t}</span></div>`).join("")+`<div style="grid-column:1/-1"><span>Twin built from: ${w}.</span></div>`;

  const aep=R.synthetic_control.AEP.levels,dom=R.synthetic_control.DOM.levels,domA=R.synthetic_control.DOM.acceleration;
  $("t-scm").innerHTML=`AEP tracked its twin within ${fmt(aep.rmspe_pre_pct,1)}% for four years, then rose <strong>${fmt(aep.recent_gap_pct,0)}% above it: ${fmt(aep.recent_gap_mw/1000,1)} gigawatts</strong>, on average. That ranks ${aep.rank} zones. Dominion sits ${fmt(dom.recent_gap_pct,0)}% above its twin${dom.placebo_in_time&&dom.placebo_in_time.gap_pct>3?", but it was pulling away well before 2023":""}.`;
  const pit=dom.placebo_in_time,pitA=aep.placebo_in_time;
  $("t-scm-fine").innerHTML=`Two honest caveats on Dominion. No mix of zones grew as fast as it did even before 2023, so its twin misses by ${fmt(dom.rmspe_pre_pct,1)}% in the fitting period`+(pit?`, and a placebo test that pretends the build-out began in ${monthName(pit.fake_start)} still finds a ${fmt(pit.gap_pct,0)}% gap`:"")+`. Measured only as speed-up beyond its own earlier trend, Dominion&rsquo;s gap is ${sign(domA?domA.recent_gap_pct:null,1)}% (${domA?fmt(domA.recent_gap_mw):"n/a"} MW, rank ${domA?domA.rank:"n/a"}): suggestive, not conclusive.`+(pitA?` The same placebo date finds ${sign(pitA.gap_pct,1)}% for AEP, as it should.`:"");
}

/* ---------- chart: share ---------- */
function drawShare(){
  const zs=R.zone_share,keys=Object.keys(zs),months=zs[keys[0]].months,n=months.length;
  const colors={DOM:css("--hot"),AEP:css("--cool")};
  const m={t:14,r:92,b:34,l:46},{svg,W,H}=frame($("c-share"),Math.max(300,Math.min(440,($("c-share").clientWidth||600)*0.6)));
  const all=keys.flatMap(k=>zs[k].share_12m_pct).filter(v=>v!=null),lo=Math.floor(Math.min(...all)),hi=Math.ceil(Math.max(...all));
  const first=zs[keys[0]].share_12m_pct.findIndex(v=>v!=null);
  const x=lin(first,n-1,m.l,W-m.r),y=lin(lo,hi,H-m.b,m.t);
  yAxis(svg,y,ticks(lo,hi,5),m.l,W-m.r,v=>v+"%");
  months.forEach((mo,i)=>{if(i>=first&&mo.endsWith("-01")){S("line",{x1:x(i),x2:x(i),y1:H-m.b,y2:H-m.b+5,class:"axis-line"},svg);T(svg,x(i),H-m.b+20,mo.slice(0,4),{"text-anchor":"middle"});}});
  const ends=[];
  keys.forEach(k=>{const a=zs[k].share_12m_pct;
    S("path",{d:path(a.map((v,i)=>i<first?null:[x(i),y(v)])),fill:"none",stroke:colors[k]||"#999","stroke-width":2},svg);
    const bi=months.indexOf(zs[k].break_test&&zs[k].break_test.break_month);
    if(bi>=first&&a[bi]!=null){S("circle",{cx:x(bi),cy:y(a[bi]),r:6,fill:css("--bg"),stroke:colors[k],"stroke-width":2},svg);}
    let li=n-1;while(li>0&&a[li]==null)li--;ends.push({k,y:y(a[li]),v:a[li]});});
  ends.sort((p,q)=>p.y-q.y);for(let i=1;i<ends.length;i++)if(ends[i].y-ends[i-1].y<30)ends[i].y=ends[i-1].y+30;
  ends.forEach(e=>{T(svg,W-m.r+10,e.y,SHORT[e.k]||e.k,{class:"lab"});T(svg,W-m.r+10,e.y+15,fmt(e.v,1)+"%");});
  hoverLayer(svg,m.l,W-m.r,m.t,H-m.b,n-first,i=>x(i+first),i=>{const j=i+first;return `<b>12 months to ${monthName(months[j])}</b><br>`+keys.map(k=>`${SHORT[k]||k}: ${fmt(zs[k].share_12m_pct[j],2)}%`+(zs[k].break_test&&zs[k].break_test.break_month===months[j]?" <em>(estimated break)</em>":"")).join("<br>");});
}

/* ---------- chart: regions dumbbell ---------- */
function drawRegions(){
  const reg=R.regions,keys=Object.keys(R.meta.cleaning.balancing_authorities).filter(k=>reg[k]).sort((a,b)=>reg[b].baseload_trend.growth_after_pct-reg[a].baseload_trend.growth_after_pct);
  const row=38,m={t:10,r:30,b:30,l:($("c-regions").clientWidth||600)<520?172:200};
  const {svg,W,H}=frame($("c-regions"),m.t+m.b+row*keys.length);
  const vals=keys.flatMap(k=>[reg[k].baseload_trend.growth_before_pct,reg[k].baseload_trend.growth_after_pct]);
  const lo=Math.min(0,...vals)-0.4,hi=Math.max(...vals)+0.4,x=lin(lo,hi,m.l,W-m.r);
  for(const t of ticks(lo,hi,6)){S("line",{x1:x(t),x2:x(t),y1:m.t,y2:H-m.b,class:"grid"},svg);T(svg,x(t),H-m.b+18,sign(t,0)+"%",{"text-anchor":"middle"});}
  S("line",{x1:x(0),x2:x(0),y1:m.t,y2:H-m.b,stroke:css("--zero")},svg);
  keys.forEach((k,i)=>{const t=reg[k].baseload_trend,y=m.t+i*row+row/2,sig=t.change_p_value<0.05;
    T(svg,m.l-12,y+4,reg[k].label,{"text-anchor":"end",class:sig?"lab":""});
    S("line",{x1:x(t.growth_before_pct),x2:x(t.growth_after_pct),y1:y,y2:y,stroke:sig?"#8a8a8a":"#3d3d3d","stroke-width":2},svg);
    S("circle",{cx:x(t.growth_before_pct),cy:y,r:6,fill:sig?css("--cool"):css("--bg"),stroke:css("--cool"),"stroke-width":2},svg);
    S("circle",{cx:x(t.growth_after_pct),cy:y,r:6,fill:sig?css("--hot"):css("--bg"),stroke:css("--hot"),"stroke-width":2},svg);
    const hit=S("rect",{x:0,y:y-row/2,width:W,height:row,fill:"transparent"},svg);
    const html=`<b>${reg[k].label}</b><br>2019–22: ${sign(t.growth_before_pct,2)}% a year <em>(${sign(t.growth_before_ci[0],1)} to ${sign(t.growth_before_ci[1],1)})</em><br>2023 on: ${sign(t.growth_after_pct,2)}% a year <em>(${sign(t.growth_after_ci[0],1)} to ${sign(t.growth_after_ci[1],1)})</em><br><em>Change ${pval(t.change_p_value)}${sig?"":", not significant"}</em>`;
    hit.addEventListener("pointermove",ev=>showTip(html,ev));hit.addEventListener("pointerleave",hideTip);});
}

/* ---------- chart: marginal vs average ---------- */
function drawMEF(){
  const em=R.emissions,keys=Object.keys(em);if(!em[state.mefRegion])state.mefRegion=keys[0];
  pressGroup($("mef-region"),keys.map(k=>[k,em[k].label.split(" (")[0]]),state.mefRegion,k=>{state.mefRegion=k;drawMEF();drawCarbonDetail();});
  const e=em[state.mefRegion],ys=e.by_year;$("mef-title").textContent=e.label+": marginal vs. average carbon intensity";
  const m={t:14,r:20,b:34,l:46},{svg,W,H}=frame($("c-mef"),Math.max(280,Math.min(400,($("c-mef").clientWidth||600)*0.55)));
  const all=ys.flatMap(d=>[d.ci[0],d.ci[1],d.average_intensity]),hi=Math.max(...all)*1.08;
  const x=lin(0,Math.max(1,ys.length-1),m.l+26,W-m.r-26),y=lin(0,hi,H-m.b,m.t);
  yAxis(svg,y,ticks(0,hi,5),m.l,W-m.r,v=>v.toFixed(1));
  ys.forEach((d,i)=>T(svg,x(i),H-m.b+20,d.year+(d.partial_year?"*":""),{"text-anchor":"middle"}));
  S("path",{d:path(ys.map((d,i)=>[x(i),y(d.average_intensity)])),fill:"none",stroke:css("--cool"),"stroke-width":2},svg);
  S("path",{d:path(ys.map((d,i)=>[x(i),y(d.mef)])),fill:"none",stroke:css("--hot"),"stroke-width":2},svg);
  ys.forEach((d,i)=>{S("line",{x1:x(i),x2:x(i),y1:y(d.ci[0]),y2:y(d.ci[1]),stroke:css("--hot"),"stroke-width":2},svg);
    S("circle",{cx:x(i),cy:y(d.average_intensity),r:4.5,fill:css("--cool"),stroke:css("--bg"),"stroke-width":2},svg);
    S("circle",{cx:x(i),cy:y(d.mef),r:4.5,fill:css("--hot"),stroke:css("--bg"),"stroke-width":2},svg);});
  if(ys.some(d=>d.partial_year))T(svg,W-m.r,m.t+2,"* year to date",{"text-anchor":"end"});
  hoverLayer(svg,m.l,W-m.r,m.t,H-m.b,ys.length,i=>x(i),i=>{const d=ys[i];return `<b>${e.label.split(" (")[0]}, ${d.year}${d.partial_year?" to date":""}</b><br>Marginal: ${fmt(d.mef,3)} t/MWh <em>(${fmt(d.ci[0],3)} to ${fmt(d.ci[1],3)})</em><br>Average: ${fmt(d.average_intensity,3)} t/MWh<br><em>${fmt(d.n_hours)} hours</em>`;});

  /* response bar, PJM */
  const mix=em.PJM&&em.PJM.marginal_mix_after;const host=$("c-mix");if(!mix){host.innerHTML="";return;}
  const parts=[["gas","Gas","--f-gas"],["coal","Coal","--f-coal"],["hydro","Hydro and pumped storage","--f-hydro"],["other","Other plants","--f-other"],["imports","Imports","--neutral"]].map(([k,l,c])=>({k,l,c:css(c),v:Math.max(0,mix[k]||0)})).filter(p=>p.v>0.005);
  const tot=parts.reduce((a,p)=>a+p.v,0);const f=frame(host,92);let px=0;const bw=f.W;
  parts.forEach((p,i)=>{const w=p.v/tot*bw;S("rect",{x:px+(i?1:0),y:0,width:Math.max(1,w-(i?2:1)),height:40,rx:2,fill:p.c},f.svg);
    if(w>46){T(f.svg,px+6,60,fmt(p.v/tot*100)+"%",{class:"lab"});T(f.svg,px+6,77,w>110?p.l:p.l.split(" ")[0]);}
    const hit=S("rect",{x:px,y:0,width:w,height:80,fill:"transparent"},f.svg);const html=`<b>${p.l}</b><br>${fmt(p.v/tot*100,1)}% of the response to one extra MWh of PJM demand`;
    hit.addEventListener("pointermove",ev=>showTip(html,ev));hit.addEventListener("pointerleave",hideTip);px+=w;});
}

/* ---------- chart: live week ---------- */
function drawLive(){
  const L=R.latest_week_pjm,host=$("c-live");if(!L){host.innerHTML="<p>No recent hourly data in this run.</p>";return;}
  const n=L.hours_utc.length,fuels=FUELS.filter(f=>L[f[0]]);
  const m={t:14,r:16,b:36,l:52},{svg,W,H}=frame(host,Math.max(300,Math.min(440,(host.clientWidth||600)*0.6)));
  const tot=L.hours_utc.map((_,i)=>fuels.reduce((a,f)=>a+(L[f[0]][i]||0),0)),hi=Math.max(...tot)*1.05;
  const x=lin(0,n-1,m.l,W-m.r),y=lin(0,hi,H-m.b,m.t);
  yAxis(svg,y,ticks(0,hi,5),m.l,W-m.r,v=>fmt(v/1000)+" GW");
  const et=s=>new Date(s.replace(" ","T")+":00Z");const dfmt=new Intl.DateTimeFormat("en-US",{timeZone:"America/New_York",weekday:"short",month:"short",day:"numeric"});
  const tfmt=new Intl.DateTimeFormat("en-US",{timeZone:"America/New_York",weekday:"short",month:"short",day:"numeric",hour:"numeric"});
  let lastDay="";L.hours_utc.forEach((h,i)=>{const d=dfmt.format(et(h));if(d!==lastDay){if(lastDay&&x(i)<W-m.r-40){S("line",{x1:x(i),x2:x(i),y1:H-m.b,y2:H-m.b+5,class:"axis-line"},svg);T(svg,x(i),H-m.b+20,d.split(", ")[1]||d);}lastDay=d;}});
  const base=new Array(n).fill(0);
  fuels.forEach(f=>{const top=base.map((b,i)=>b+(L[f[0]][i]||0));
    S("path",{d:path(top.map((v,i)=>[x(i),y(v)]))+path(base.map((v,i)=>[x(i),y(v)]).reverse()).replace("M","L")+"Z",fill:css(f[2]),stroke:css("--bg"),"stroke-width":1},svg);
    for(let i=0;i<n;i++)base[i]=top[i];});
  hoverLayer(svg,m.l,W-m.r,m.t,H-m.b,n,i=>x(i),i=>`<b>${tfmt.format(et(L.hours_utc[i]))} ET</b><br>`+fuels.slice().reverse().map(f=>`${f[1]}: ${fmt((L[f[0]][i]||0)/1000,1)} GW`).join("<br>")+`<br><em>Carbon intensity ${fmt(L.intensity[i],3)} t/MWh</em>`);
  $("live-legend").innerHTML=fuels.map(f=>`<span><i class="sq" style="background:${css(f[2])}"></i>${f[1]}</span>`).join("");
  const iv=L.intensity.filter(v=>v!=null),avg=iv.reduce((a,b)=>a+b,0)/iv.length,share=k=>100*L[k].reduce((a,b)=>a+(b||0),0)/tot.reduce((a,b)=>a+b,0);
  $("live-sub").textContent=`${tfmt.format(et(L.hours_utc[0]))} to ${tfmt.format(et(L.hours_utc[n-1]))}, Eastern time.`;
  $("t-live").innerHTML=`Over the most recent week of data, gas supplied <strong>${fmt(share("gas"))}%</strong> of PJM&rsquo;s generation, nuclear ${fmt(share("nuclear"))}% and coal ${fmt(share("coal"))}%. Average carbon intensity was <strong>${fmt(avg,2)} t/MWh</strong>, ranging from ${fmt(Math.min(...iv),2)} to ${fmt(Math.max(...iv),2)} across hours.`;
}


/* ---------- generic pieces for the detail pages ---------- */
function fmtBy(v,f){if(v==null)return "n/a";if(f==="mon")return monthName(v);if(f==="p")return pval(v);if(f==="raw")return String(v);
  if(f[0]==="a")return fmt(Math.abs(v),+f.slice(1)||0);if(f[0]==="s")return sign(v,+f.slice(1)||0);if(f.startsWith("gw"))return fmt(v/1000,+f.slice(2)||0);if(f[0]==="m")return fmt(v/1e6,+f.slice(1)||0);return fmt(v,+f||0);}
function resolveVals(){document.querySelectorAll("[data-v]").forEach(e=>{const [p,f="0"]=e.dataset.v.split("|");const v=p.split(".").reduce((a,k)=>a==null?a:a[k],R);e.textContent=fmtBy(v,f);});}
function table(id,head,rows){if(!has(id))return;$(id).innerHTML="<thead><tr>"+head.map(h=>`<th>${h}</th>`).join("")+"</tr></thead><tbody>"+rows.map(r=>"<tr>"+r.map((c,i)=>`<td${i?' class="num"':""}>${c}</td>`).join("")+"</tr>").join("")+"</tbody>";}
const pcell=p=>p==null?"n/a":p<0.001?"<0.001":p.toFixed(3);
const ci=(a,d=1)=>a?`${sign(a[0],d)} to ${sign(a[1],d)}`:"n/a";

function lineChart(id,o){
  if(!has(id))return;const host=$(id),n=o.labels.length;
  const m={t:16,r:o.endLabels?104:18,b:34,l:o.left||50},{svg,W,H}=frame(host,Math.max(280,Math.min(o.height||420,(host.clientWidth||600)*0.58)));
  let first=n,last=0;o.series.forEach(s=>s.values.forEach((v,i)=>{if(v!=null){first=Math.min(first,i);last=Math.max(last,i);}}));if(first>last)return;
  const all=o.series.flatMap(s=>s.values).filter(v=>v!=null);let lo=o.ymin!=null?o.ymin:Math.min(...all),hi=Math.max(...all);const pad=(hi-lo)*0.07||1;if(o.ymin==null)lo-=pad;hi+=pad;
  const x=lin(first,Math.max(first+1,last),m.l,W-m.r),y=lin(lo,hi,H-m.b,m.t),yf=o.yfmt||(v=>fmt(v,0));
  yAxis(svg,y,ticks(lo,hi,5),m.l,W-m.r,yf);
  if(o.months)o.labels.forEach((mo,i)=>{if(i>=first&&mo.endsWith("-01")){S("line",{x1:x(i),x2:x(i),y1:H-m.b,y2:H-m.b+5,class:"axis-line"},svg);T(svg,x(i),H-m.b+20,mo.slice(0,4),{"text-anchor":"middle"});}});
  else{const step=Math.ceil((last-first+1)/Math.max(2,Math.floor((W-m.l-m.r)/70)));for(let i=first;i<=last;i+=step)T(svg,x(i),H-m.b+20,o.xfmt?o.xfmt(o.labels[i]):o.labels[i],{"text-anchor":"middle"});}
  if(o.vline!=null&&o.vline>=first){S("line",{x1:x(o.vline),x2:x(o.vline),y1:m.t,y2:H-m.b,stroke:"#8a8a8a","stroke-dasharray":"3 4"},svg);if(o.vlabel)T(svg,x(o.vline)+8,m.t+12,o.vlabel);}
  if(o.hline!=null)S("line",{x1:m.l,x2:W-m.r,y1:y(o.hline),y2:y(o.hline),stroke:css("--zero")},svg);
  const ends=[];
  o.series.forEach(s=>{S("path",{d:path(s.values.map((v,i)=>v==null?null:[x(i),y(v)])),fill:"none",stroke:s.color,"stroke-width":s.width||2,"stroke-linejoin":"round","stroke-dasharray":s.dash||""},svg);
    if(o.dots)s.values.forEach((v,i)=>{if(v!=null)S("circle",{cx:x(i),cy:y(v),r:4,fill:s.color,stroke:css("--bg"),"stroke-width":2},svg);});
    if(o.endLabels&&s.label!==false){let li=last;while(li>first&&s.values[li]==null)li--;ends.push({s,y:y(s.values[li]),v:s.values[li]});}});
  ends.sort((a,b)=>a.y-b.y);for(let i=1;i<ends.length;i++)if(ends[i].y-ends[i-1].y<30)ends[i].y=ends[i-1].y+30;
  ends.forEach(e=>{T(svg,W-m.r+10,e.y,e.s.name,{class:"lab"});T(svg,W-m.r+10,e.y+15,yf(e.v));});
  hoverLayer(svg,m.l,W-m.r,m.t,H-m.b,last-first+1,i=>x(i+first),i=>{const j=i+first;return `<b>${o.tipTitle?o.tipTitle(o.labels[j]):o.labels[j]}</b><br>`+o.series.filter(s=>s.tip!==false&&s.values[j]!=null).map(s=>`${s.name}: ${yf(s.values[j])}`).join("<br>");});
}
function barsH(id,rows,o){
  if(!has(id))return;o=o||{};const host=$(id),narrow=(host.clientWidth||600)<520,row=30,m={t:8,r:64,b:28,l:narrow?150:200};
  const {svg,W,H}=frame(host,m.t+m.b+row*rows.length),vals=rows.map(r=>r.value),lo=Math.min(0,...vals),hi=Math.max(...vals,0.0001),x=lin(lo,hi,m.l,W-m.r),f=o.fmt||(v=>fmt(v,1));
  for(const t of ticks(lo,hi,5)){S("line",{x1:x(t),x2:x(t),y1:m.t,y2:H-m.b,class:"grid"},svg);T(svg,x(t),H-m.b+18,f(t),{"text-anchor":"middle"});}
  rows.forEach((r,i)=>{const y=m.t+i*row,w=Math.max(1,Math.abs(x(r.value)-x(0)));
    T(svg,m.l-10,y+row/2+4,narrow?r.label.split(" (")[0]:r.label,{"text-anchor":"end",class:r.hot?"lab":""});
    S("rect",{x:x(Math.min(0,r.value)),y:y+6,width:w,height:row-12,rx:2,fill:r.hot?css("--hot"):css("--neutral")},svg);
    T(svg,x(Math.max(0,r.value))+7,y+row/2+4,f(r.value),{class:r.hot?"lab":""});
    if(r.tip){const hit=S("rect",{x:0,y:y,width:W,height:row,fill:"transparent"},svg);hit.addEventListener("pointermove",ev=>showTip(r.tip,ev));hit.addEventListener("pointerleave",hideTip);}});
  S("line",{x1:x(0),x2:x(0),y1:m.t,y2:H-m.b,stroke:css("--zero")},svg);
}
function stackedBars(id,labels,parts){ /* parts:[{name,color,values}] in percent; one bar per label */
  if(!has(id))return;const host=$(id),m={t:10,r:10,b:30,l:44},{svg,W,H}=frame(host,Math.max(260,Math.min(380,(host.clientWidth||600)*0.5)));
  const y=lin(0,100,H-m.b,m.t),bw=(W-m.l-m.r)/labels.length;yAxis(svg,y,[0,25,50,75,100],m.l,W-m.r,v=>v+"%");
  labels.forEach((lab,i)=>{let acc=0;const tot=parts.reduce((a,p)=>a+Math.max(0,p.values[i]||0),0)||1;T(svg,m.l+bw*(i+.5),H-m.b+20,lab,{"text-anchor":"middle"});
    parts.forEach(p=>{const v=Math.max(0,p.values[i]||0)/tot*100;if(v<=0)return;const y1=y(acc+v),h=y(acc)-y1;S("rect",{x:m.l+bw*i+bw*.14,y:y1+1,width:bw*.72,height:Math.max(0,h-2),rx:2,fill:p.color},svg);acc+=v;});
    const hit=S("rect",{x:m.l+bw*i,y:m.t,width:bw,height:H-m.b-m.t,fill:"transparent"},svg);const html=`<b>${lab}</b><br>`+parts.slice().reverse().filter(p=>(p.values[i]||0)>0.05).map(p=>`${p.name}: ${fmt(Math.max(0,p.values[i])/tot*100,1)}%`).join("<br>");
    hit.addEventListener("pointermove",ev=>showTip(html,ev));hit.addEventListener("pointerleave",hideTip);});
}
function legend(id,items){if(has(id))$(id).innerHTML=items.map(([n,c,sq])=>`<span><i${sq?' class="sq"':""} style="background:${c}"></i>${n}</span>`).join("");}

/* ---------- detail pages ---------- */
function drawZoneDetail(){
  const reg=R.regions,mo=R.meta.months,keys=["DOM_ZONE","AEP_ZONE","PJM_REST"].filter(k=>reg[k]),col={DOM_ZONE:css("--hot"),AEP_ZONE:css("--cool"),PJM_REST:css("--ink-3")},nm={DOM_ZONE:"Dominion",AEP_ZONE:"AEP",PJM_REST:"Rest of PJM"};
  lineChart("c-zone-index",{labels:mo,months:true,endLabels:true,hline:100,vline:mo.indexOf(R.meta.treatment_start),vlabel:"January 2023",series:keys.map(k=>({name:nm[k],color:col[k],values:reg[k].mean_index})),yfmt:v=>fmt(v,0),tipTitle:m=>"12 months to "+monthName(m)});
  lineChart("c-zone-base",{labels:mo,months:true,endLabels:true,hline:100,vline:mo.indexOf(R.meta.treatment_start),series:keys.map(k=>({name:nm[k],color:col[k],values:reg[k].baseload_index})),yfmt:v=>fmt(v,0),tipTitle:m=>"12 months to "+monthName(m)});
  const lf=R.load_factor,yrs=lf.PJM_REST.years;
  lineChart("c-loadfactor",{labels:yrs.map(String),dots:true,endLabels:true,height:340,series:keys.filter(k=>lf[k]).map(k=>({name:nm[k],color:col[k],values:lf[k].load_factor_pct})),yfmt:v=>fmt(v,1)+"%"});
  table("tbl-zones-base",["Zone","Baseload growth 2019–22, %/yr","Baseload growth 2023 on, %/yr","Change, points","p-value"],R.zone_trends.slice().sort((a,b)=>b.baseload.change_pct_points-a.baseload.change_pct_points).map(z=>[ZONE_NAMES[z.zone]||z.zone,sign(z.baseload.growth_before_pct,2),sign(z.baseload.growth_after_pct,2),sign(z.baseload.change_pct_points,2),pcell(z.baseload.change_p_value)]));
}
function drawTwinDetail(){
  const sc=R.synthetic_control,s=(sc[state.scmZone]||{})[state.scmKind]||sc[state.scmZone].levels,name=SHORT[state.scmZone];
  lineChart("c-twin-lines",{labels:s.months,months:true,endLabels:true,vline:s.months.indexOf(s.treatment_start),vlabel:"Compared from here",series:[{name:name,color:css("--hot"),values:roll12(s.actual_index)},{name:"Synthetic",color:css("--cool"),values:roll12(s.synthetic_index)}],yfmt:v=>fmt(v,1),tipTitle:m=>"12 months to "+monthName(m)});
  const rows=Object.entries(s.placebo_ratios).map(([z,v])=>({label:ZONE_NAMES[z]||z,value:v,tip:`<b>${ZONE_NAMES[z]||z}</b><br>Placebo zone: its error after 2023 is ${fmt(v,1)} times its error before`}));
  rows.push({label:ZONE_NAMES[state.scmZone],value:s.rmspe_ratio,hot:true,tip:`<b>${ZONE_NAMES[state.scmZone]}</b><br>The zone under study: ${fmt(s.rmspe_ratio,1)} times`});rows.sort((a,b)=>b.value-a.value);
  barsH("c-placebo",rows,{fmt:v=>fmt(v,1)+"×"});
  table("tbl-weights",["Comparison zone","Weight"],Object.entries(s.weights).map(([z,v])=>[ZONE_NAMES[z]||z,fmt(v*100,1)+"%"]));
  const out=[];for(const z of Object.keys(sc))for(const k of ["levels","acceleration"]){const f=sc[z][k];if(!f)continue;out.push([`${SHORT[z]}, ${k==="levels"?"against comparison zones":"beyond own earlier trend"}`,sign(f.recent_gap_pct,1)+"%",fmt(f.recent_gap_mw),fmt(Math.min(...f.recent_gap_mw_leave_one_out))+" to "+fmt(Math.max(...f.recent_gap_mw_leave_one_out)),fmt(f.rmspe_pre_pct,2)+"%",fmt(f.rmspe_ratio,1)+"×",f.rank,f.placebo_p_value.toFixed(3)]);}
  for(const z of Object.keys(sc)){const p=sc[z].levels.placebo_in_time;if(p)out.push([`${SHORT[z]}, placebo start ${monthName(p.fake_start)} (pre-2023 data only)`,sign(p.gap_pct,1)+"%","","","","",p.rank,p.p_value.toFixed(3)]);}
  table("tbl-robust",["Specification","Gap","Extra MW","Leave-one-out MW","Pre-period error","Post/pre ratio","Rank","p-value"],out);
}
function drawTimingDetail(){
  const zs=R.zone_share;table("tbl-break",["Zone","Share in "+R.meta.data_start.slice(0,4),"Share, latest 12 months","Estimated break","Slope before, pts/yr","Slope after, pts/yr","Sup-F","p-value"],Object.keys(zs).map(k=>{const b=zs[k].break_test||{};return [ZONE_NAMES[k],fmt(zs[k].first_year_avg_pct,2)+"%",fmt(zs[k].latest_12m_avg_pct,2)+"%",b.break_month?monthName(b.break_month):"n/a",sign(b.slope_before_per_year,2),sign(b.slope_after_per_year,2),fmt(b.sup_f,1),pcell(b.p_value)];}));
  const k0=Object.keys(zs)[0];lineChart("c-share-raw",{labels:zs[k0].months,months:true,endLabels:true,series:Object.keys(zs).map(k=>({name:SHORT[k],color:k==="DOM"?css("--hot"):css("--cool"),values:zs[k].share_pct,width:1.5})),yfmt:v=>fmt(v,1)+"%",tipTitle:monthName});
}
function drawRegionDetail(){
  const reg=R.regions,mo=R.meta.months,keys=Object.keys(R.meta.cleaning.balancing_authorities).filter(k=>reg[k]);
  const sig=keys.filter(k=>reg[k].baseload_trend.change_p_value<0.05).sort((a,b)=>reg[b].baseload_trend.change_pct_points-reg[a].baseload_trend.change_pct_points).slice(0,3),pal=[css("--hot"),css("--cool"),css("--f-nuclear")];
  lineChart("c-region-index",{labels:mo,months:true,endLabels:true,hline:100,vline:mo.indexOf(R.meta.treatment_start),vlabel:"January 2023",series:keys.filter(k=>!sig.includes(k)).map(k=>({name:reg[k].label.split(" (")[0],color:css("--neutral"),values:reg[k].baseload_index,width:1.3,label:false})).concat(sig.map((k,i)=>({name:reg[k].label.split(" (")[0],color:pal[i],values:reg[k].baseload_index,width:2.4}))),yfmt:v=>fmt(v,0),tipTitle:m=>"12 months to "+monthName(m)});
  const row=(k,t)=>[sign(t.growth_before_pct,2),ci(t.growth_before_ci),sign(t.growth_after_pct,2),ci(t.growth_after_ci),sign(t.change_pct_points,2),pcell(t.change_p_value)];
  const head=["Region","2019–22, %/yr","95% interval","2023 on, %/yr","95% interval","Change, points","p-value"];
  table("tbl-regions-base",head,keys.map(k=>[reg[k].label].concat(row(k,reg[k].baseload_trend))));
  table("tbl-regions-mean",head.concat(["Recent average, GW"]),keys.map(k=>[reg[k].label].concat(row(k,reg[k].mean_trend),[fmt(reg[k].latest_12m_mean_mw/1000,1)])));
}
function drawCarbonDetail(){
  const e=R.emissions[state.mefRegion];if(!e)return;const short=e.label.split(" (")[0];
  document.querySelectorAll("[data-region-name]").forEach(n=>n.textContent=short);
  table("tbl-mef-year",["Year","Marginal, t/MWh","95% interval","Average, t/MWh","Marginal vs. average","Hours used"],e.by_year.map(d=>[d.year+(d.partial_year?" to date":""),fmt(d.mef,3),fmt(d.ci[0],3)+" to "+fmt(d.ci[1],3),fmt(d.average_intensity,3),sign(100*(d.mef/d.average_intensity-1),0)+"%",fmt(d.n_hours)]));
  const g=e.generation_mix;stackedBars("c-genmix",g.years.map(String),FUELS.filter(f=>g[f[0]]).map(f=>({name:f[1],color:css(f[2]),values:g[f[0]]})));
  legend("genmix-legend",FUELS.filter(f=>g[f[0]]).map(f=>[f[1],css(f[2]),true]));
  const parts=[["gas","Gas","--f-gas"],["coal","Coal","--f-coal"],["hydro","Hydro and pumped storage","--f-hydro"],["nuclear","Nuclear","--f-nuclear"],["other","Other plants","--f-other"],["imports","Imports","--neutral"]],b=e.marginal_mix_before,a=e.marginal_mix_after;
  if(b&&a){stackedBars("c-mix-compare",["2019–22","2023 on"],parts.map(p=>({name:p[1],color:css(p[2]),values:[100*(b[p[0]]||0),100*(a[p[0]]||0)]})));legend("mixc-legend",parts.map(p=>[p[1],css(p[2]),true]));
    table("tbl-mix",["Source","Share of response, 2019–22","Share of response, 2023 on"],parts.map(p=>[p[1],fmt(100*(b[p[0]]||0),1)+"%",fmt(100*(a[p[0]]||0),1)+"%"]));}
}
function drawLiveDetail(){
  const L=R.latest_week_pjm;if(!L||!has("c-intensity"))return;const tf=new Intl.DateTimeFormat("en-US",{timeZone:"America/New_York",weekday:"short",hour:"numeric"}),df=new Intl.DateTimeFormat("en-US",{timeZone:"America/New_York",month:"short",day:"numeric"}),d=s=>new Date(s.replace(" ","T")+":00Z");
  lineChart("c-intensity",{labels:L.hours_utc,height:320,ymin:0,series:[{name:"Carbon intensity",color:css("--hot"),values:L.intensity}],yfmt:v=>fmt(v,2),xfmt:h=>df.format(d(h)),tipTitle:h=>tf.format(d(h))+" ET"});
  lineChart("c-demand",{labels:L.hours_utc,height:320,series:[{name:"Demand",color:css("--cool"),values:L.demand_mw}],yfmt:v=>fmt(v/1000,0)+" GW",xfmt:h=>df.format(d(h)),tipTitle:h=>tf.format(d(h))+" ET"});
}

/* ---------- navigation and start-up ---------- */
const PAGES=[["index.html","Overview"],["zones.html","Zones"],["twin.html","Twin test"],["timing.html","Timing"],["regions.html","Regions"],["carbon.html","Carbon"],["live.html","Live grid"],["report.html","Report"]];
function buildNav(){
  const here=(location.pathname.split("/").pop()||"index.html"),nav=document.createElement("nav");nav.className="nav";nav.setAttribute("aria-label","Pages");
  nav.innerHTML=`<a class="mark" href="index.html">Grid<span>/</span>Data Centers</a><button class="menu" aria-expanded="false" aria-controls="navlist">Menu</button><ul id="navlist">`+PAGES.map(([h,l])=>`<li><a href="${h}"${h===here?' aria-current="page"':""}>${l}</a></li>`).join("")+`<li><a href="https://github.com/sahiljangra12/grid-data-centers">Code</a></li></ul>`;
  document.body.prepend(nav);const b=nav.querySelector(".menu");b.addEventListener("click",()=>{const o=nav.classList.toggle("open");b.setAttribute("aria-expanded",o);});
  const i=PAGES.findIndex(p=>p[0]===here),pn=document.querySelector(".prevnext");
  if(pn&&i>=0){const a=PAGES[i-1],c=PAGES[i+1];pn.innerHTML=(a?`<a href="${a[0]}"><small>Previous</small>${a[1]}</a>`:"<span></span>")+(c?`<a class="next" href="${c[0]}"><small>Next</small>${c[1]}</a>`:"<span></span>");}
}
function drawAll(){
  if(has("heroArt"))drawHero();if(has("c-zones"))drawZones();if(has("c-scm"))drawSCM();if(has("c-share"))drawShare();if(has("c-regions"))drawRegions();if(has("c-mef"))drawMEF();if(has("c-live"))drawLive();
  drawZoneDetail();if(has("c-twin-lines")||has("tbl-robust"))drawTwinDetail();drawTimingDetail();drawRegionDetail();drawCarbonDetail();drawLiveDetail();
}
if(new URLSearchParams(location.search).has("print"))document.documentElement.classList.add("light");
buildNav();
fetch("data/results.json",{cache:"no-cache"}).then(r=>{if(!r.ok)throw new Error("HTTP "+r.status);return r.json();}).then(j=>{
  R=j;R.zt=Object.fromEntries(R.zone_trends.map(z=>[z.zone,z]));
  const bas=Object.keys(R.meta.cleaning.balancing_authorities).filter(k=>R.regions[k]);
  R.d={n_zones:R.zone_trends.length,n_regions:bas.length,n_sig:bas.filter(k=>R.regions[k].baseload_trend.change_p_value<0.05&&R.regions[k].baseload_trend.change_pct_points>0).length,
    min_p:1/(R.synthetic_control.AEP.levels.n_donors+1),rest_max:Math.max(...R.zone_trends.filter(z=>!z.hot).map(z=>z.mean.change_pct_points)),n_donors:R.synthetic_control.AEP.levels.n_donors};
  fillText();resolveVals();drawAll();document.documentElement.classList.add("ready");
  let w=innerWidth,timer;addEventListener("resize",()=>{if(innerWidth===w)return;w=innerWidth;clearTimeout(timer);timer=setTimeout(drawAll,180);});
  if(document.fonts&&document.fonts.ready)document.fonts.ready.then(drawAll);
}).catch(err=>{console.error(err);const m=document.querySelector("main");if(m)m.innerHTML='<section class="block"><h2>The results file did not load</h2><p style="margin-top:20px">This site reads <code>data/results.json</code>, which the analysis pipeline writes. Reload the page to try again.</p></section>';});
