// ui/src/bitPanel.js — BIT v0.1 drawer INSIDE spatial map (not a free panel).
// Wired to #bitDrawer inside mapPanel .map-wrap. No ensurePanel.
let _token="", _log=()=>{}, _busy=false;
const BULAN=["Januari","Februari","Maret","April","Mei","Juni","Juli","Agustus","September","Oktober","November","Desember"];
const esc = s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmtKg = kg=>{ const v=Number(kg)||0; if(Math.abs(v)>=1e6) return (v/1e6).toFixed(1)+"M"; if(Math.abs(v)>=1e3) return (v/1e3).toFixed(1)+"k"; return String(Math.round(v)); };
const fmtPct = p=> p==null?"\u2014":Number(p).toFixed(1)+"%";
const kpiCard=(label,value,sub)=>`<div><div style="font-size:10px;color:var(--text-dim);letter-spacing:.06em">${esc(label)}</div><div style="font-size:14px;font-weight:600">${esc(value)}</div><div style="font-size:10px;color:var(--text-dim)">${esc(sub||"")}</div></div>`;
function renderBar(k){
  const _isYa = String(k.sampai_dengan||"ya").toLowerCase()==="ya";
  const _ytdOn = !!document.getElementById("bitYTD")?.checked;
  const _rencanaVal = k.rencana_main_kg!=null ? k.rencana_main_kg : (_isYa ? (k.rencana_ytd_kg||0) : (k.rencana_kg||0));
  const _actualVal = k.actual_main_kg!=null ? k.actual_main_kg : (_isYa ? (k.actual_kg||0) : (k.actual_period_kg||0));
  const max=Math.max(k.target_expected_kg||0,_rencanaVal||0,_actualVal||0,1);
  const _suf = _ytdOn ? " YTD" : "";
  const row=(label,val,color,pct)=>{
    const w=Math.max(4,100*val/max);
    const pctHtml = pct ? `<span style="font-size:11px;min-width:52px;text-align:right;color:var(--text-dim)">${esc(pct)}</span>` : `<span style="min-width:52px"></span>`;
    return `<div style="display:flex;align-items:center;gap:8px;margin:4px 0"><span style="width:110px;font-size:11px">${esc(label)}</span><div style="flex:1;height:14px;background:rgba(255,255,255,.08);border-radius:7px;overflow:hidden"><div style="width:${w.toFixed(1)}%;height:100%;background:${color}"></div></div><span style="font-size:11px;min-width:88px;text-align:right">${fmtKg(val)} kg</span>${pctHtml}</div>`;
  };
  const _rencanaPct = k.plan_coverage_pct!=null ? fmtPct(k.plan_coverage_pct) : "";
  const _realisasiPct = k.achievement_pct!=null ? fmtPct(k.achievement_pct) : "";
  const _kekuranganKg = k.current_gap_kg!=null ? fmtKg(k.current_gap_kg) : "\u2014";
  const _kekuranganPct = k.achievement_pct!=null ? fmtPct(Math.max(0, 100 - k.achievement_pct)) : "";
  return `<div style="font-size:11px;font-weight:600;margin-bottom:4px">Target`+_suf+` vs Rencana`+_suf+` vs Realisasi`+_suf+`</div>`
    +row("Target"+_suf,k.target_expected_kg,"#3B82F6","")
    +row("Rencana"+_suf,_rencanaVal||0,"#FACC15",_rencanaPct)
    +row("Realisasi"+_suf,_actualVal,"#22C55E",_realisasiPct)
    +`<div style="display:flex;justify-content:space-between;align-items:center;margin-top:6px;font-size:11px;border-top:1px solid rgba(255,255,255,.08);padding-top:6px"><span>Kekurangan</span><span style="display:flex;gap:12px;align-items:center"><span style="color:${(k.current_gap_kg||0)>0?'#EF4444':'#22C55E'}">${_kekuranganKg} kg</span><span style="min-width:52px;text-align:right">${esc(_kekuranganPct)}</span></span></div>`;
}
function renderTable(rows){
  const wrap=document.getElementById("bitTableWrap"), tbl=document.getElementById("bitTable");
  if(!wrap||!tbl) return;
  if(!rows||!rows.length){ wrap.style.display="none"; tbl.innerHTML=""; return; }
  wrap.style.display="block";
  const hdr=`<tr><th>BKPH</th><th>TPG</th><th>Nama</th><th>JAB</th><th style="text-align:right">Target</th><th style="text-align:right">Rencana</th><th style="text-align:right">Capaian</th></tr>`;
  const body=rows.map(r=>`<tr><td>${esc(r.bkph||"")}</td><td>${esc(r.tpg||"")}</td><td>${esc(r.nama||"")}</td><td style="text-align:center">${esc(r.kode_jab||"")}</td><td style="text-align:right">${fmtKg(r.target_ro_nps_kg)}</td><td style="text-align:right">${fmtKg(r.merencanakan_kg)}</td><td style="text-align:right">${fmtPct(r.gap_pct)}</td></tr>`).join("");
  tbl.innerHTML=hdr+body;
}
function renderDiagnostic(d){
  const el=document.getElementById("bitDiagnostic"); if(!el) return;
  if(!d||!d.aktivitas){ el.innerHTML="<div style=\"color:var(--text-dim);font-size:11px\">Belum ada data telusur.</div>"; return; }
  // el visibility via tab pane
  const a=d.aktivitas, diag=d.diagnostic;
  const jenisRows=(a.per_jenis||[]).map(j=>`<tr><td>${esc(j.label)}</td><td style="color:var(--text-dim);font-size:10px">${esc(j.arti||"")}</td><td style="text-align:right">${j.count}</td><td style="text-align:right">${j.pohon?String(j.pohon):"\u2014"}</td></tr>`).join("");
  const pemChips=(a.per_pembaharuan||[]).filter(x=>x.dim!=null).map(x=>`<span style="display:inline-block;padding:2px 6px;border:1px solid var(--neon-border);border-radius:99px;font-size:10px;margin:2px">${esc(x.label||("Pem "+x.dim))}: <b>${x.count}</b></span>`).join("") || '<span style="color:var(--text-dim)">\u2014</span>';
  const chain=(diag?.chain||[]).map(c=>{
    if(c.stage==="Target") return `<div><b>Target</b> ${fmtKg(c.kg)} <span style="color:var(--text-dim)">${esc(c.note||"")}</span></div>`;
    if(c.stage==="Rencana") return `<div><b>Rencana</b> ${fmtKg(c.kg)} <span style="color:var(--text-dim)">${c.pct_of_target!=null?fmtPct(c.pct_of_target)+" dari target":""} ${c.gap!=null?"\u00b7 kekurangan "+fmtKg(c.gap):""}</span></div>`;
    if(c.stage==="Aktivitas") return `<div><b>Aktivitas</b> ${c.count} baris \u00b7 ${c.n_penyadap} penyadap \u00b7 ${c.n_petak} petak <span style="color:var(--text-dim)">\u00b7 hasil/kegiatan ${c.yield_per_aktivitas_kg!=null?fmtKg(c.yield_per_aktivitas_kg):"\u2014"}</span></div>`;
    if(c.stage==="Penerimaan") return `<div><b>Penerimaan</b> ${fmtKg(c.kg)} <span style="color:var(--text-dim)">${c.pct_of_target!=null?fmtPct(c.pct_of_target)+" dari target":""} ${c.pct_of_rencana!=null?"\u00b7 "+fmtPct(c.pct_of_rencana)+" dari rencana":""} ${c.yield_per_pohon_kg!=null?"\u00b7 "+c.yield_per_pohon_kg+" kg/pohon":""}</span></div>`;
    return "";
  }).join("");
  const q=diag?.q_proxy||{};
  el.innerHTML=
    `<div style="font-size:11px;font-weight:600;margin-bottom:4px">TELUSUR RANTAI \u2014 Target \u2192 Rencana \u2192 Aktivitas (Jenis \u00d7 Pohon) \u2192 Penerimaan</div>`
    +`<div style="font-size:11px;line-height:1.5;margin-bottom:6px">${chain}</div>`
    +`<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:6px"><span class="bit-chip">Pohon (cakupan): <b>${a.pohon_scope}</b> (${a.luas_scope_ha} ha)</span><span class="bit-chip">Petak aktif: <b>${a.n_petak_aktiv}</b></span><span class="bit-chip">Pohon dikerjakan: <b>${a.pohon_tersentuh_total||"\u2014 (belum diisi)"}</b></span></div>`
    +`<div style="max-height:140px;overflow:auto;border:1px solid var(--neon-border);border-radius:6px;margin-bottom:6px"><table class="bit-table"><tr><th>Jenis Kegiatan</th><th>Keterangan</th><th style="text-align:right">Kegiatan</th><th style="text-align:right">Pohon</th></tr>${jenisRows}</table></div>`
    +`<div style="font-size:10px;color:var(--text-dim);margin-bottom:4px">Tahap pembaharuan: ${pemChips}</div>`
    +`<div style="font-size:10px;color:var(--text-dim)">Faktor produksi Q=N\u00d7A\u00d7F\u00d7Y: N=${q.N_pohon_scope} A=${q.A_jenis_unik} F=${q.F_n_aktivitas} Y=${q.Y_yield_per_aktivitas!=null?q.Y_yield_per_aktivitas:"\u2014"} \u2014 ${esc(q.Y_note||q.formula||"")}</div>`;
}
function renderHypothesis(h){
  const el=document.getElementById('bitHypothesis'); if(!el) return;
  if(!h||!h.hypotheses){ el.innerHTML='<div style="color:var(--text-dim);font-size:11px">Belum ada uji dugaan.</div>'; return; }
  // via tab pane
  const color=s=> s==='Didukung'?'#22C55E': s==='Tidak didukung'?'#EF4444': s==='Belum teruji'?'#FACC15':'#94A3B8';
  const badge=s=> `<span style="display:inline-block;padding:1px 6px;border-radius:99px;font-size:10px;font-weight:600;color:#0f172a;background:`+color(s)+`">`+s+`</span>`;
  const rows=(h.hypotheses_sorted||h.hypotheses).map(x=>{
    const d=x.delta_pct!=null? (x.delta_pct>0?'+'+x.delta_pct: String(x.delta_pct))+'%': '\u2014';
    return `<div style="display:flex;gap:8px;align-items:flex-start;padding:6px;border:1px solid var(--neon-border);border-radius:6px;background:rgba(255,255,255,.03);margin-bottom:6px"><div style="min-width:28px;font-weight:700">`+x.id+`</div><div style="flex:1"><div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap"><b>`+esc(x.label)+`</b> `+badge(x.status)+` <span style="font-size:10px;color:var(--text-dim)">`+d+` `+(x.cur!=null?String(x.cur):'')+(x.prev!=null?' \u2192 '+x.prev:'')+`</span></div><div style="font-size:11px;margin-top:2px">`+esc(x.evidence||'')+`</div><div style="font-size:10px;color:var(--text-dim);margin-top:2px">Akan gugur jika: `+esc(x.kondisi_gugur||'')+`</div></div></div>`;
  }).join('');
  const cmp=h.meta&&h.meta.comparison? `<div style="font-size:10px;color:var(--text-dim);margin-bottom:4px">Dibanding periode: `+esc(h.meta.comparison)+`</div>` : '';
  el.innerHTML='<div style="font-size:11px;font-weight:600;margin-bottom:4px">UJI HIPOTESIS PENYEBAB (H1\u2013H4)</div>'+cmp+rows;
}
function renderRekomendasi(data){
  const el=document.getElementById('bitRekomendasi'); if(!el) return;
  if(!data||!data.rekomendasi){ el.innerHTML='<div style="color:var(--text-dim);font-size:11px">Belum ada rekomendasi.</div>'; return; }
  const rows=data.rekomendasi_sorted||data.rekomendasi||[];
  if(!rows.length){ el.innerHTML='<div style="color:var(--text-dim);font-size:11px">Tidak ada rekomendasi — pantau periode depan.</div>'; return; }
  const prioLabel=p=> p===1?'Prioritas 1 — Utama':p===2?'Prioritas 2':'Prioritas 3 — Catatan data';
  const biayaColor=b=> b==='Rendah'?'#22C55E':b==='Sedang'?'#FACC15':b==='Tinggi'?'#EF4444':'#94A3B8';
  const cards=rows.map(r=>{
    const prioCls='reko-prio'+(r.prioritas||3);
    const manfaat=r.manfaat_kg!=null? fmtKg(r.manfaat_kg)+' kg'+(r.manfaat_pct!=null?' ('+fmtPct(r.manfaat_pct)+' dari target)':'') : '— (perbaiki data dulu)';
    return '<div class="reko-card '+prioCls+'"><div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap"><b>'+esc(r.id)+'</b><span style="background:'+biayaColor(r.biaya)+';color:#0f172a;padding:1px 6px;border-radius:99px;font-size:10px">'+esc(r.biaya||'—')+'</span><span style="font-size:10px;color:var(--text-dim)">'+esc(prioLabel(r.prioritas))+'</span></div><div style="margin-top:4px"><b>Masalah:</b> '+esc(r.masalah||'')+'</div><div><b>Faktor:</b> '+esc(r.faktor||'')+'</div><div style="color:#7dd3fc"><b>Tindakan:</b> '+esc(r.tindakan||'')+'</div><div><b>Manfaat:</b> '+esc(manfaat)+' <span style="color:var(--text-dim);font-size:10px">— '+esc(r.asumsi||'')+'</span></div><div style="font-size:10px;color:var(--text-dim)">Sumber daya: '+esc(r.sumber_daya||'')+' · Verifikasi: '+esc(r.verifikasi||'')+'</div></div>';
  }).join('');
  const lim=data.limitations&&data.limitations.length? '<div style="font-size:10px;color:#FACC15;margin-top:6px">⚠ '+esc(data.limitations.join(" · "))+'</div>':'';
  el.innerHTML='<div style="font-size:11px;font-weight:600;margin-bottom:4px">REKOMENDASI — prioritas dari H1–H4 + sebaran</div>'+cards+lim;
}
function renderKasus(data){
  const el=document.getElementById('bitKasus'); if(!el) return;
  if(!data){ el.innerHTML='<div style="color:var(--text-dim);font-size:11px">Memuat kasus...</div>'; return; }
  const rows=data.rows||[];
  const total=data.total||0, closed=data.closed_n||0, false_n=data.false_n||0, rate=data.false_rate_pct;
  let head='<div style="font-size:11px;font-weight:600;margin-bottom:4px">KASUS INVESTIGASI — '+total+' kasus '+ (rate!=null ? '(salah simpul '+rate+'% dari '+closed+' tertutup)':'') +'</div>';
  let metrics='<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:6px"><span class="bit-chip">Total '+total+'</span><span class="bit-chip">Tertutup '+closed+'</span><span class="bit-chip" style="'+(rate!=null&&rate>10?'color:#EF4444':'')+'">Salah simpul '+false_n+' ('+(rate!=null?rate+'%':'—')+')</span></div>';
  let form='<div style="border:1px solid var(--neon-border);border-radius:6px;padding:6px;margin-bottom:8px;background:rgba(255,255,255,.03)"><div style="font-size:11px;font-weight:600;margin-bottom:4px">Rekam kasus baru dari periode ini</div><textarea id="bitGejala" placeholder="Gejala: mis. Produksi Feb Penuh Ya turun vs Jan, kesenjangan 191 ton..." style="width:100%;min-height:56px;background:rgba(0,0,0,.2);border:1px solid var(--neon-border);border-radius:6px;color:var(--text);padding:6px;font-size:11px"></textarea><div style="display:flex;gap:6px;margin-top:6px"><input id="bitPertanyaan" placeholder="Pertanyaan (opsional)" style="flex:1;background:rgba(0,0,0,.2);border:1px solid var(--neon-border);border-radius:6px;color:var(--text);padding:5px;font-size:11px"><select id="bitKepastian" style="background:rgba(0,0,0,.3);border:1px solid var(--neon-border);border-radius:6px;color:var(--text);padding:4px;font-size:11px"><option>Belum teruji</option><option>Didukung</option><option>Tidak didukung</option><option>Terkonfirmasi</option></select><button id="bitSimpanKasus" class="spatial-btn" style="padding:4px 10px">Simpan</button></div><div id="bitKasusMsg" style="font-size:10px;color:var(--text-dim);margin-top:4px"></div></div>';
  let list='';
  if(!rows.length){
    list='<div style="color:var(--text-dim);font-size:11px;padding:8px;text-align:center">Belum ada kasus — simpan gejala periode ini untuk ukur salah simpul.</div>';
  } else {
    list=rows.slice(0,12).map(r=>{
      const statusColor=r.status==='open'?'#FACC15':r.status==='verified'?'#22C55E':'#94A3B8';
      const kepColor=r.kepastian==='Didukung'?'#22C55E':r.kepastian==='Tidak didukung'?'#EF4444':r.kepastian==='Terkonfirmasi'?'#3B82F6':'#FACC15';
      const outcome=r.hasil&&r.hasil.outcome? r.hasil.outcome : 'belum';
      return '<div style="border:1px solid var(--neon-border);border-radius:6px;padding:6px;margin-bottom:6px;background:rgba(255,255,255,.02)"><div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap"><b style="font-size:11px">'+esc(r.id)+'</b><span style="background:'+statusColor+';color:#0f172a;padding:1px 6px;border-radius:99px;font-size:10px;font-weight:600">'+esc(r.status)+'</span><span style="background:'+kepColor+';color:#0f172a;padding:1px 6px;border-radius:99px;font-size:10px">'+esc(r.kepastian)+'</span><span style="font-size:10px;color:var(--text-dim)">'+esc(r.created_at?r.created_at.slice(0,10):'')+' · '+esc(outcome)+'</span></div><div style="font-size:11px;margin-top:4px">'+esc(r.gejala||'')+'</div>'+(r.kesimpulan?'<div style="font-size:10px;color:var(--text-dim);margin-top:2px">Simpulan: '+esc(r.kesimpulan)+'</div>':'')+(r.keputusan?'<div style="font-size:10px;color:#7dd3fc">Putusan: '+esc(r.keputusan)+'</div>':'')+'</div>';
    }).join('');
    if(rows.length>12) list+='<div style="font-size:10px;color:var(--text-dim)">Menampilkan 12 dari '+total+' kasus.</div>';
  }
  el.innerHTML=head+metrics+form+list;
  // wire simpan
  const btn=el.querySelector("#bitSimpanKasus");
  if(btn) btn.onclick=async ()=>{
    const gejalaEl=el.querySelector("#bitGejala"), tanyaEl=el.querySelector("#bitPertanyaan"), kepEl=el.querySelector("#bitKepastian"), msgEl=el.querySelector("#bitKasusMsg");
    const gejala=(gejalaEl.value||"").trim();
    if(gejala.length<5){ if(msgEl) msgEl.textContent="Gejala minimal 5 karakter."; return; }
    if(msgEl) msgEl.textContent="Menyimpan...";
    btn.disabled=true;
    try{
      const tahun=parseInt(document.getElementById("bitTahun")?.value||"2026"), bulan=parseInt(document.getElementById("bitBulan")?.value||"2"), periode=parseInt(document.getElementById("bitPeriode")?.value||"0"), sampai_dengan=(document.getElementById("bitSampai")?.value||"ya");
      const token=document.querySelector('meta[name="ana-token"]')?.content||_token||"";
      let did=""; try{ did=localStorage.getItem("ana_device_id")||"";}catch(_){}
      const payload={gejala, pertanyaan:(tanyaEl.value||"").trim(), kepastian:(kepEl.value||"Belum teruji"), periode:{tahun,bulan,periode,sampai_dengan}};
      const r=await fetch("/api/bit/cases",{method:"POST",headers:{"X-Ana-Token":token,"Content-Type":"application/json","X-Ana-Device":did},body:JSON.stringify({action:"create", payload})});
      const j=await r.json();
      if(!r.ok||!j.ok) throw new Error(j.error||r.status);
      if(msgEl) msgEl.textContent="Tersimpan "+j.case.id;
      gejalaEl.value=""; tanyaEl.value="";
      await refreshKasus();
    }catch(e){ if(msgEl) msgEl.textContent="Gagal: "+(e.message||e); }
    finally{ btn.disabled=false; }
  };
}
async function refreshKasus(){
  const el=document.getElementById('bitKasus'); if(!el) return;
  el.innerHTML='<div style="color:var(--text-dim);font-size:11px;padding:8px">Memuat kasus...</div>';
  try{
    const token=document.querySelector('meta[name="ana-token"]')?.content||_token||"";
    let did=""; try{ did=localStorage.getItem("ana_device_id")||"";}catch(_){}
    const r=await fetch("/api/bit/cases",{method:"POST",headers:{"X-Ana-Token":token,"Content-Type":"application/json","X-Ana-Device":did},body:JSON.stringify({action:"list", limit:20})});
    const j=await r.json();
    if(!r.ok||!j.ok) throw new Error(j.error||r.status);
    renderKasus(j);
  }catch(e){ el.innerHTML='<div style="color:#EF4444;font-size:11px">Gagal muat kasus: '+esc(e.message||e)+'</div>'; }
}
function renderAnalisis(data){
  const el=document.getElementById('bitAnalisis'); if(!el) return;
  if(!data||!data.tren){ el.innerHTML='<div style="color:var(--text-dim);font-size:11px">Belum ada analisis.</div>'; return; }
  const tren=data.tren||[];
  const dist=data.distribusi||{}, anom=data.anomali||[], sens=data.sensitivitas_sorted||data.sensitivitas||[], strat=data.stratified||[];
  let trenHtml='<div style="font-size:11px;font-weight:600;margin-bottom:4px">TREN — 6 periode terakhir</div><div style="max-height:120px;overflow:auto;border:1px solid var(--neon-border);border-radius:6px"><table class="bit-table"><tr><th>Periode</th><th style="text-align:right">Target</th><th style="text-align:right">Realisasi</th><th style="text-align:right">Capaian</th><th style="text-align:right">Tumbuh</th></tr>'+tren.slice(-6).map(t=>'<tr><td>'+esc(t.label||'')+'</td><td style="text-align:right">'+fmtKg(t.target||0)+'</td><td style="text-align:right">'+fmtKg(t.actual||0)+'</td><td style="text-align:right">'+fmtPct(t.achievement)+'</td><td style="text-align:right;color:'+((t.growth_pct||0)>0?'#22C55E':'#EF4444')+'">'+(t.growth_pct!=null?fmtPct(t.growth_pct):'—')+'</td></tr>').join('')+'</table></div>';
  let distHtml='';
  if(dist.achievement) distHtml+='<div class="ana-card"><b>Distribusi Capaian</b> · mean '+fmtPct(dist.achievement.mean)+' median '+fmtPct(dist.achievement.median)+' sd '+fmtPct(dist.achievement.stdev)+' ['+dist.achievement.min+'–'+dist.achievement.max+'%] · <b>'+(dist.konsentrasi?dist.konsentrasi.klasifikasi:'')+'</b> pangsa top2 '+fmtPct(dist.konsentrasi?dist.konsentrasi.top2_share_pct:null)+'</div>';
  if(dist.gap) distHtml+='<div class="ana-card"><b>Kesenjangan</b> · mean '+fmtKg(dist.gap.mean)+' max '+fmtKg(dist.gap.max)+' sd '+fmtKg(dist.gap.stdev)+'</div>';
  let anomHtml='<div style="font-size:11px;font-weight:600;margin:6px 0 4px">ANOMALI</div>'+(anom.length? anom.map(a=>'<div class="ana-card" style="border-color:'+(a.jenis==='tidak ada'?'#22C55E':'#EF4444')+'"><b>'+esc(a.jenis||'')+'</b> '+esc(a.nama||a.label||a.catatan||'')+' '+ (a.achievement!=null?' capaian '+fmtPct(a.achievement):'') + (a.gap!=null?' gap '+fmtKg(a.gap):'') +'</div>').join('') : '<div class="ana-card">Tidak ada anomali.</div>');
  let sensHtml='<div style="font-size:11px;font-weight:600;margin:6px 0 4px">SENSITIVITAS — +10% tiap faktor</div><div style="border:1px solid var(--neon-border);border-radius:6px"><table class="bit-table"><tr><th>Faktor</th><th>Perubahan</th><th style="text-align:right">Dampak</th></tr>'+sens.map(s=>'<tr><td>'+esc(s.faktor||'')+'</td><td>'+esc(s.perubahan||'')+'</td><td style="text-align:right">'+fmtKg(s.dampak_kg||0)+' <span style="color:var(--text-dim);font-size:10px">'+esc(s.keterangan||'')+'</span></td></tr>').join('')+'</table></div>';
  let stratHtml='<div style="font-size:11px;font-weight:600;margin:6px 0 4px">STRATIFIED — kelompok sebanding</div>'+strat.map(s=>'<div class="ana-card">'+esc(s.kelompok||s.catatan||'')+' '+(s.selisih!=null?' selisih '+fmtPct(s.selisih):'')+'<br><span style="color:var(--text-dim);font-size:10px">'+esc(s.catatan||'')+'</span></div>').join('');
  el.innerHTML=trenHtml+distHtml+anomHtml+sensHtml+stratHtml;
}
function renderSebaran(h){
  const el=document.getElementById('bitSebaran'); if(!el) return;
  if(!h||!h.rows){ el.innerHTML='<div style="color:var(--text-dim);font-size:11px">Belum ada sebaran.</div>'; return; }
  const level=(h.level||'').replace('kode_','').toUpperCase();
  const rows=h.rows||[];
  if(!rows.length){ el.innerHTML='<div style="color:var(--text-dim);font-size:11px">Tidak ada data untuk sebaran '+level+'.</div>'; return; }
  const hdr='<tr><th>'+level+'</th><th style="text-align:right">Target</th><th style="text-align:right">Rencana</th><th style="text-align:right">Realisasi</th><th style="text-align:right">Capaian</th><th style="text-align:right">Kesenjangan</th><th style="text-align:right">Pangsa Kesenjangan</th></tr>';
  const body=rows.slice(0,12).map(r=>'<tr><td>'+esc(r.nama||r.kode)+'</td><td style="text-align:right">'+fmtKg(r.target_expected)+'</td><td style="text-align:right">'+fmtKg(r.rencana_kg)+'</td><td style="text-align:right">'+fmtKg(r.actual_kg)+'</td><td style="text-align:right">'+fmtPct(r.achievement_pct)+'</td><td style="text-align:right;color:'+(r.gap_kg>0?'#EF4444':'#22C55E')+'">'+fmtKg(r.gap_kg)+'</td><td style="text-align:right">'+fmtPct(r.share_gap_pct)+'</td></tr>').join('');
  const more=rows.length>12?'<div style="font-size:10px;color:var(--text-dim);margin-top:4px">Menampilkan 12 dari '+rows.length+' wilayah — fokus pada kesenjangan terbesar.</div>':'';
  const topPetak=(h.top_petak||[]).length? '<div style="margin-top:8px"><div style="font-size:11px;font-weight:600;margin-bottom:4px">Petak dengan aktivitas terbanyak</div><div style="max-height:120px;overflow:auto;border:1px solid var(--neon-border);border-radius:6px"><table class="bit-table"><tr><th>Petak</th><th>Evapot</th><th style="text-align:right">Kegiatan</th><th>Pembaharuan</th></tr>'+h.top_petak.slice(0,8).map(p=>'<tr><td>'+esc(p.nomor_petak||p.kode_evapot||'')+'</td><td style="font-size:10px">'+esc(p.kode_evapot||'')+'</td><td style="text-align:right">'+(p.jumlah_aktivitas||p.jumlah||'')+'</td><td style="font-size:10px">P1:'+(p.pem1||0)+' P2:'+(p.pem2||0)+' P3:'+(p.pem3||0)+'</td></tr>').join('')+'</table></div></div>' : '';
  const meta=h.meta&&h.meta.period_bounds? '<div style="font-size:10px;color:var(--text-dim);margin-bottom:4px">Sebaran '+level+' · '+h.meta.period_bounds.join(' s/d ')+' · s/d='+esc(h.meta.sampai_dengan||'')+'</div>' : '';
  el.innerHTML='<div style="font-size:11px;font-weight:600;margin-bottom:4px">SEBARAN KESENJANGAN — per '+level+'</div>'+meta+'<div style="max-height:220px;overflow:auto;border:1px solid var(--neon-border);border-radius:6px"><table class="bit-table">'+hdr+body+'</table></div>'+more+topPetak;
}

async function fetchAndRender(){
  if(_busy) return; _busy=true;
  const btn=document.getElementById("bitRefresh"); if(btn){ btn.disabled=true; btn.textContent="…"; }
  // YTD: selalu reset ke tahun/bulan/periode saat ini (default YTD)
  try{
    const ytdEl=document.getElementById("bitYTD");
    if(ytdEl?.checked) _applyYTD();
  }catch(_){}
  try{
    const tahun=parseInt(document.getElementById("bitTahun")?.value||"2026");
    const bulan=parseInt(document.getElementById("bitBulan")?.value||"4");
    const periode=parseInt(document.getElementById("bitPeriode")?.value||"2");
    const breakdown=!!document.getElementById("bitBreakdown")?.checked;
    let sampai_dengan=(document.getElementById("bitSampai")?.value||"ya").trim().toLowerCase();
    if(!["ya","tidak"].includes(sampai_dengan)) sampai_dengan="ya";
    const token=_token||document.querySelector('meta[name="ana-token"]')?.content||"";
    let did=""; try{ did=localStorage.getItem("ana_device_id")||"";}catch(_){}
    const payload={tahun, bulan, periode, sampai_dengan, include_breakdown: breakdown};
    let r,j;
    // hypothesis single call (kpi+aktivitas+Q+H1-H4) — fallback diagnostic -> target_gap
    try{
      r=await fetch("/api/bit/hypothesis",{method:"POST",headers:{"X-Ana-Token":token,"Content-Type":"application/json","X-Ana-Device":did},credentials:"same-origin",body:JSON.stringify(payload)});
      j=await r.json().catch(()=>({ok:false,error:"bad json"}));
      if(!r.ok || j.ok===false) throw new Error(j.error||("HTTP "+r.status));
    }catch(_e1){
      try{
        r=await fetch("/api/bit/diagnostic",{method:"POST",headers:{"X-Ana-Token":token,"Content-Type":"application/json","X-Ana-Device":did},credentials:"same-origin",body:JSON.stringify(payload)});
        j=await r.json().catch(()=>({ok:false,error:"bad json"}));
        if(!r.ok || j.ok===false) throw new Error(j.error||("HTTP "+r.status));
      }catch(_e2){
        r=await fetch("/api/bit/target_gap",{method:"POST",headers:{"X-Ana-Token":token,"Content-Type":"application/json","X-Ana-Device":did},credentials:"same-origin",body:JSON.stringify(payload)});
        j=await r.json().catch(()=>({ok:false,error:"bad json"}));
      }
    }
    const kpiEl=document.getElementById("bitKpis"), barEl=document.getElementById("bitBar"), metaEl=document.getElementById("bitMeta"), evEl=document.getElementById("bitEvidence");
    if(!r.ok||j.ok===false){ if(metaEl) metaEl.textContent="Error: "+(j.error||("HTTP "+r.status)); if(kpiEl) kpiEl.innerHTML=""; if(barEl) barEl.innerHTML=""; renderTable([]); return; }
    const k=j.kpi||{};
    const _isYa = String(k.sampai_dengan||"ya").toLowerCase()==="ya";
    const _rencanaMain = k.rencana_main_kg!=null ? k.rencana_main_kg : (_isYa ? k.rencana_ytd_kg : k.rencana_kg);
    const _actualMain = k.actual_main_kg!=null ? k.actual_main_kg : (_isYa ? k.actual_kg : k.actual_period_kg);
    const _rentang = (k.period_bounds||[]).join(" s/d ");
    const _ytdOn2 = !!document.getElementById("bitYTD")?.checked;
    const _ytdSuf = _ytdOn2 ? " YTD" : "";
    const _labelSuf = (_ytdSuf + (_isYa ? " (kumulatif)" : " (periode)")) || (_ytdSuf || "");
    // bila YTD on, label jadi "Target YTD (kumulatif)" else "Target (periode)"
    if(kpiEl) kpiEl.innerHTML=kpiCard("Target"+_labelSuf,fmtKg(k.target_expected_kg)+" kg",`${k.target_pct}% \u00d7 ${fmtKg(k.target_total_kg)} \u00b7 ${_rentang}`)+kpiCard("Rencana"+_labelSuf,fmtKg(_rencanaMain)+" kg",`${k.n_rencana||0} rencana`+(_isYa ? ` \u00b7 periode ${fmtKg(k.rencana_kg)}` : ``))+kpiCard("Realisasi"+_labelSuf,fmtKg(_actualMain)+" kg",`capaian ${fmtPct(k.achievement_pct)} \u00b7 ${_rentang}`)+kpiCard("Cakupan Rencana",fmtPct(k.plan_coverage_pct),`kekurangan ${fmtKg(k.plan_gap_kg)}`)+kpiCard("Selisih Pelaksanaan",fmtKg(k.execution_gap_kg)+" kg",_isYa ? `kumulatif Jan s/d periode` : `hanya periode`)+kpiCard("Kekurangan vs Target",fmtKg(k.current_gap_kg)+" kg",k.current_gap_kg>0?"kurang (belum capai target)":"surplus (melebihi target)");
    if(barEl) barEl.innerHTML=renderBar(k);
    const _modeLabel = String(k.sampai_dengan||"ya").toLowerCase()==="ya" ? "Ya (kumulatif Jan s/d periode)" : "Tidak (periode saja)";
    if(metaEl) metaEl.textContent=`Mode ${k.sampai_dengan==="ya"?"Ya":"Tidak"} \u00b7 ${_modeLabel} \u00b7 Rentang hitung ${k.period_bounds?.join(" s/d ")} \u00b7 Kumulatif ${k.ytd_bounds?.join(" s/d ")} \u00b7 ${j.meta?.rule_version||""} ${j.cached?"(cached)":""}`;
    if(evEl) evEl.innerHTML=(j.evidence||[]).map(e=>`\u2022 ${esc(e.statement)} <span style="color:var(--text-dim)">[${esc(e.source)}]</span>`).join("<br>")+(j.limitations?.length?`<br><span style="color:#FACC15">\u26a0 ${esc(j.limitations.join(" \u00b7 "))}</span>`:"");
    renderTable(j.breakdown||[]);
    try{ renderDiagnostic(j); }catch(_){}
    try{ renderHypothesis(j); }catch(_){}
    try{ const _tab = document.querySelector('.bit-tab.active')?.dataset.tab; if(_tab==="kasus") refreshKasus(); }catch(_){}
    // sebaran parallel (global DIVRE..TPG)
    try{ renderRekomendasi({rekomendasi:[]}); }catch(_){}
    // rekomendasi parallel
    try{
      const r3=await fetch("/api/bit/rekomendasi",{method:"POST",headers:{"X-Ana-Token":token,"Content-Type":"application/json","X-Ana-Device":did},credentials:"same-origin",body:JSON.stringify(payload)});
      const j3=await r3.json().catch(()=>null);
      if(r3.ok && j3 && j3.ok!==false) { try{ renderRekomendasi(j3); }catch(_){} }
    }catch(_){}
    try{ const ra=await fetch("/api/bit/analisis",{method:"POST",headers:{"X-Ana-Token":token,"Content-Type":"application/json","X-Ana-Device":did},credentials:"same-origin",body:JSON.stringify(payload)}); const ja=await ra.json().catch(()=>null); if(ra.ok && ja && ja.ok!==false) try{ renderAnalisis(ja); }catch(_){} }catch(_){}
    try{
      const r2=await fetch("/api/bit/sebaran",{method:"POST",headers:{"X-Ana-Token":token,"Content-Type":"application/json","X-Ana-Device":did},credentials:"same-origin",body:JSON.stringify(payload)});
      const j2=await r2.json().catch(()=>null);
      if(r2.ok && j2 && j2.ok!==false) { try{ renderSebaran(j2); }catch(_){} }
    }catch(_){}
    try{ _log(`BIT ${tahun}-${bulan} P${periode} s/d=${sampai_dengan} target ${fmtKg(k.target_expected_kg)} rencana ${fmtKg(k.rencana_ytd_kg)} actual ${fmtKg(k.actual_kg)} ach ${fmtPct(k.achievement_pct)}`);}catch(_){}
  }catch(e){ const m=document.getElementById("bitMeta"); if(m) m.textContent="Fetch gagal: "+(e.message||e); }
  finally{ _busy=false; const b=document.getElementById("bitRefresh"); if(b){ b.disabled=false; b.textContent="Tampilkan"; } }
}
export function initBitPanel(opts={}){
  _token=opts.token||document.querySelector('meta[name="ana-token"]')?.content||"";
  _log=opts.log||(()=>{});
  // persist per-user (localStorage, like panel layout but inside map)
  const BIT_KEY="ana_bit_drawer_v1";
  const _saveBit=()=>{
    try{
      const r=document.getElementById("bitDrawer");
      if(!r) return;
      const s={ collapsed: r.classList.contains("collapsed") };
      ["left","top","width","maxHeight"].forEach(k=>{ const v=r.style[k]; if(v) s[k]=v; });
      try{ s.ytd = !!document.getElementById("bitYTD")?.checked; }catch(_){}
      localStorage.setItem(BIT_KEY, JSON.stringify(s));
    }catch(_){}
  };
  const _loadBit=()=>{
    try{
      const raw=localStorage.getItem(BIT_KEY);
      if(!raw) return null;
      const j=JSON.parse(raw); return (j&&typeof j==="object")?j:null;
    }catch(_){ return null; }
  };
  const _applyBit=(drawer)=>{
    const s=_loadBit(); if(!s) return;
    // clamp inside wrap
    try{
      const wrap=drawer.parentElement;
      const pr=wrap?wrap.getBoundingClientRect():null;
      if(s.left) drawer.style.left=s.left;
      if(s.top) drawer.style.top=s.top;
      if(s.width) drawer.style.width=s.width;
      if(s.maxHeight) { drawer.style.maxHeight=s.maxHeight; drawer.style.height="auto"; }
      if(s.left||s.top){ drawer.style.right="auto"; drawer.style.transform="none"; }
      if(s.collapsed===false) drawer.classList.remove("collapsed");
      else if(s.collapsed===true) drawer.classList.add("collapsed");
      try{
        const ytdEl=document.getElementById("bitYTD");
        if(ytdEl && typeof s.ytd==="boolean") ytdEl.checked=s.ytd;
        if(ytdEl?.checked) _applyYTD(); else _releaseYTD();
      }catch(_){}
      // clamp after apply
      if(pr){
        const r=drawer.getBoundingClientRect();
        if(r.right>pr.right) drawer.style.left=Math.max(0, pr.width - r.width - 8)+"px";
        if(r.bottom>pr.bottom) drawer.style.maxHeight=Math.max(180, pr.height - (r.top-pr.top) - 8)+"px";
      }
    }catch(_){}
  };
  const _applyYTD=()=>{
    const ytdEl=document.getElementById("bitYTD");
    if(!ytdEl||!ytdEl.checked) return;
    const now=new Date(); const y=now.getFullYear(), m=now.getMonth()+1, d=now.getDate();
    const per = d<=15 ? "1" : "2";
    const th=document.getElementById("bitTahun"), bh=document.getElementById("bitBulan"), ph=document.getElementById("bitPeriode"), sh=document.getElementById("bitSampai");
    if(th) th.value=String(y);
    if(bh) bh.value=String(m);
    if(ph) ph.value=per;
    if(sh) sh.value="ya";
    [th,bh,ph,sh].forEach(el=>{ if(el) el.disabled=true; });
  };
  const _releaseYTD=()=>{
    ["bitTahun","bitBulan","bitPeriode","bitSampai"].forEach(id=>{ const el=document.getElementById(id); if(el) el.disabled=false; });
  };
  // drawer lives inside mapPanel — wait until mapPanel exists
  let tries=0;
  const tryBind=()=>{
    const drawer=document.getElementById("bitDrawer");
    if(!drawer){
      if(tries++<20) setTimeout(tryBind, 400);
      else console.warn("[BIT] #bitDrawer not found — mapPanel belum siap");
      return;
    }
    // restore persisted pos/size (default: top 8px centered via CSS — no save yet)
    _applyBit(drawer);
    // default YTD aktif bila belum ada simpanan (first load) -> reset ke hari ini
    try{
      const raw=localStorage.getItem(BIT_KEY);
      if(!raw){
        const ytdEl=document.getElementById("bitYTD"); if(ytdEl) ytdEl.checked=true;
        _applyYTD();
      } else {
        // sudah di _applyBit, tapi pastikan today jika YTD
        const ytdEl=document.getElementById("bitYTD"); if(ytdEl?.checked) _applyYTD();
      }
    }catch(_){ try{ _applyYTD(); }catch(_){} }
    // populate bulan
    const sel=document.getElementById("bitBulan");
    if(sel && !sel.options.length){
      BULAN.forEach((b,i)=>{ const o=document.createElement("option"); o.value=String(i+1); o.textContent=b; if(i+1===4) o.selected=true; sel.appendChild(o); });
    }
    let _dragMoved=false;
    const headEl = drawer.querySelector("#bitToggle");
    headEl?.addEventListener("click", (e)=>{ if(_dragMoved) return; drawer.classList.toggle("collapsed"); _saveBit(); });
    drawer.querySelector("#bitRefresh")?.addEventListener("click", fetchAndRender);
    // tabs
    const tabs=drawer.querySelectorAll(".bit-tab");
    const panes={ringkasan:drawer.querySelector("#bitTabRingkasan"),analisis:drawer.querySelector("#bitTabAnalisis"),sebaran:drawer.querySelector("#bitTabSebaran"),telusur:drawer.querySelector("#bitTabTelusur"),hipotesis:drawer.querySelector("#bitTabHipotesis"),rekomendasi:drawer.querySelector("#bitTabRekomendasi"),kasus:drawer.querySelector("#bitTabKasus")};
    const activate=(name)=>{
      tabs.forEach(b=>{ const on=b.dataset.tab===name; b.classList.toggle("active",on); b.setAttribute("aria-selected", on?"true":"false"); });
      Object.entries(panes).forEach(([k,el])=>{ if(el) el.classList.toggle("active", k===name); });
      try{ const s2=JSON.parse(localStorage.getItem("ana_bit_drawer_v1")||"{}"); s2.tab=name; localStorage.setItem("ana_bit_drawer_v1", JSON.stringify(s2)); }catch(_){}
    };
    tabs.forEach(b=> b.addEventListener("click", ()=> { activate(b.dataset.tab); if(b.dataset.tab==="kasus") refreshKasus(); }) );
    try{ const _st=JSON.parse(localStorage.getItem("ana_bit_drawer_v1")||"{}"); if(_st.tab && panes[_st.tab]) activate(_st.tab); }catch(_){}
    drawer.querySelector("#bitYTD")?.addEventListener("change", ()=>{
      const ytdEl=document.getElementById("bitYTD");
      if(ytdEl?.checked){ _applyYTD(); } else { _releaseYTD(); }
      _saveBit(); fetchAndRender();
    });
    // --- drag via head (clamped inside .map-wrap) ---
    const wrapEl = drawer.parentElement;
    if(headEl && wrapEl){
      let sx=0, sy=0, ox=0, oy=0, dragging=false;
      const onPointerMove=(e)=>{
        if(!dragging) return;
        const dx=e.clientX - sx, dy=e.clientY - sy;
        if(Math.abs(dx)>2 || Math.abs(dy)>2) _dragMoved=true;
        const pr=wrapEl.getBoundingClientRect(), rw=drawer.getBoundingClientRect();
        let nx=Math.min(Math.max(0, ox+dx), pr.width - rw.width);
        let ny=Math.min(Math.max(0, oy+dy), pr.height - rw.height);
        drawer.style.left = nx+"px";
        drawer.style.top = ny+"px";
      };
      const onPointerUp=()=>{
        if(dragging){ dragging=false; drawer.classList.remove("dragging"); _saveBit(); setTimeout(()=>_dragMoved=false,200); }
        removeEventListener("pointermove", onPointerMove);
        removeEventListener("pointerup", onPointerUp);
      };
      headEl.addEventListener("pointerdown", (e)=>{
        if(e.button!==0) return;
        e.preventDefault();
        const r=drawer.getBoundingClientRect(), pr=wrapEl.getBoundingClientRect();
        // switch from centered transform to absolute left/top on first drag
        if(getComputedStyle(drawer).transform!=="none"){
          drawer.style.left = (r.left - pr.left)+"px";
          drawer.style.top = (r.top - pr.top)+"px";
          drawer.style.right = "auto";
          drawer.style.transform = "none";
        }
        const curR=drawer.getBoundingClientRect();
        sx=e.clientX; sy=e.clientY;
        ox=curR.left - pr.left; oy=curR.top - pr.top;
        dragging=true; _dragMoved=false; drawer.classList.add("dragging");
        addEventListener("pointermove", onPointerMove);
        addEventListener("pointerup", onPointerUp);
      });
      headEl.addEventListener("touchstart", (e)=>{
        const t=e.touches[0]; if(!t) return;
        const r=drawer.getBoundingClientRect(), pr=wrapEl.getBoundingClientRect();
        if(getComputedStyle(drawer).transform!=="none"){
          drawer.style.left = (r.left - pr.left)+"px";
          drawer.style.top = (r.top - pr.top)+"px";
          drawer.style.right="auto"; drawer.style.transform="none";
        }
        const curR=drawer.getBoundingClientRect();
        sx=t.clientX; sy=t.clientY; ox=curR.left-pr.left; oy=curR.top-pr.top;
        dragging=true; _dragMoved=false; drawer.classList.add("dragging");
      }, {passive:false});
      headEl.addEventListener("touchmove", (e)=>{
        const t=e.touches[0]; if(!t) return;
        if(!dragging) return; e.preventDefault();
        const dx=t.clientX - sx, dy=t.clientY - sy;
        if(Math.abs(dx)>2||Math.abs(dy)>2) _dragMoved=true;
        const pr=wrapEl.getBoundingClientRect(), rw=drawer.getBoundingClientRect();
        let nx=Math.min(Math.max(0, ox+dx), pr.width - rw.width);
        let ny=Math.min(Math.max(0, oy+dy), pr.height - rw.height);
        drawer.style.left=nx+"px"; drawer.style.top=ny+"px";
      }, {passive:false});
      headEl.addEventListener("touchend", ()=>{ dragging=false; drawer.classList.remove("dragging"); _saveBit(); setTimeout(()=>_dragMoved=false,200); });
    }
    // --- resize via 8 handles (n/s/e/w + corners) ---
    const handles = drawer.querySelectorAll(".bit-handle");
    if(handles.length){
      let sx2=0, sy2=0, sw2=0, sh2=0, sl2=0, st2=0, dir="", resizing=false;
      const ensureAbs=()=>{
        const r=drawer.getBoundingClientRect(), pr=wrapEl.getBoundingClientRect();
        if(getComputedStyle(drawer).transform!=="none"){
          drawer.style.left=(r.left-pr.left)+"px";
          drawer.style.top=(r.top-pr.top)+"px";
          drawer.style.right="auto";
          drawer.style.transform="none";
        }
      };
      const onResMove=(e)=>{
        if(!resizing) return;
        const dx=e.clientX - sx2, dy=e.clientY - sy2;
        const pr=wrapEl.getBoundingClientRect();
        const minW=320, minH=180;
        if(dir.includes("e")){
          const maxW=pr.width - sl2 - 8;
          drawer.style.width=Math.min(Math.max(minW, sw2+dx), Math.min(900, maxW))+"px";
        }
        if(dir.includes("w")){
          const newW=Math.min(Math.max(minW, sw2-dx), sl2+sw2-8);
          const newL=Math.max(0, Math.min(sl2+dx, sl2+sw2-minW));
          if(newW>=minW){ drawer.style.width=newW+"px"; drawer.style.left=newL+"px"; }
        }
        if(dir.includes("s")){
          const maxH2=pr.height - st2 - 8;
          drawer.style.maxHeight=Math.min(Math.max(minH, sh2+dy), Math.min(700, maxH2))+"px";
          drawer.style.height="auto";
        }
        if(dir.includes("n")){
          const newH=Math.min(Math.max(minH, sh2-dy), st2+sh2-8);
          const newT=Math.max(0, Math.min(st2+dy, st2+sh2-minH));
          if(newH>=minH){ drawer.style.maxHeight=newH+"px"; drawer.style.top=newT+"px"; }
        }
      };
      const onResUp=()=>{
        resizing=false; drawer.classList.remove("dragging"); _saveBit();
        removeEventListener("pointermove", onResMove); removeEventListener("pointerup", onResUp);
      };
      handles.forEach(h=>{
        h.addEventListener("pointerdown", (e)=>{
          e.preventDefault(); e.stopPropagation();
          ensureAbs();
          const r=drawer.getBoundingClientRect(), pr=wrapEl.getBoundingClientRect();
          sx2=e.clientX; sy2=e.clientY;
          sw2=r.width; sh2=r.height;
          sl2=r.left-pr.left; st2=r.top-pr.top;
          dir=h.dataset.dir||"se";
          resizing=true; drawer.classList.add("dragging");
          addEventListener("pointermove", onResMove);
          addEventListener("pointerup", onResUp);
        });
        // touch fallback
        h.addEventListener("touchstart", (e)=>{
          const t=e.touches[0]; if(!t) return; e.preventDefault();
          ensureAbs();
          const r=drawer.getBoundingClientRect(), pr=wrapEl.getBoundingClientRect();
          sx2=t.clientX; sy2=t.clientY; sw2=r.width; sh2=r.height;
          sl2=r.left-pr.left; st2=r.top-pr.top;
          dir=h.dataset.dir||"se"; resizing=true; drawer.classList.add("dragging");
        }, {passive:false});
        h.addEventListener("touchmove", (e)=>{
          const t=e.touches[0]; if(!t) return; if(!resizing) return; e.preventDefault();
          onResMove({clientX:t.clientX, clientY:t.clientY});
        }, {passive:false});
        h.addEventListener("touchend", onResUp);
      });
    }
    // auto-open on first load so user sees it
    // keep collapsed by default — user clicks to open
    setTimeout(fetchAndRender, 900);
  };
  tryBind();
  return { fetchAndRender };
}
