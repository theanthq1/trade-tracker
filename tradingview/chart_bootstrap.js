(async function () {
  const $ = id => document.getElementById(id), money = v => v == null ? '—' : `$${Number(v).toFixed(2)}`;
  const message = $('message'), app = $('app'), canvas = $('chart'), wrap = $('chart-wrap'), tooltip = $('tooltip');
  const showError = text => { message.textContent = text; message.hidden = false; app.hidden = true; };
  try {
    const context = await fetch('/udf/context').then(r => r.json());
    if (!context.ticker || !context.trade_date) throw Error('The selected trade is missing its ticker or trade date.');
    const q = new URLSearchParams({symbol:context.ticker,resolution:'1',from:String(context.from_seconds),to:String(context.to_seconds)});
    const history = await fetch(`/udf/history?${q}`).then(r => r.json());
    if (history.s !== 'ok' || !history.t?.length) throw Error(history.errmsg || 'No local one-minute candles were found for this trade date.');
    const allBars = history.t.map((time,i) => ({time,open:+history.o[i],high:+history.h[i],low:+history.l[i],close:+history.c[i],volume:+(history.v?.[i]||0)}));
    const sessionStart = context.from_seconds, sessionEnd = context.to_seconds;
    let revealed = 0, playing = false, timer = null, hover = null;
    let sim = {entry:null, exit:null, side:null, pending:null};
    const ctx = canvas.getContext('2d');

    // This is the chart series update boundary: forward replay reveals exactly one bar
    // and calls update(), analogous to a chart library candle-series update method.
    const candleSeries = { data: [], update(bar) { this.data.push(bar); draw(); }, setData(data) { this.data = data.slice(); draw(); } };
    const currentBar = () => candleSeries.data[candleSeries.data.length - 1] || null;
    const revealedAt = () => currentBar()?.time ?? sessionStart;
    const fmtTime = ts => new Date(ts * 1000).toLocaleTimeString([], {hour:'numeric',minute:'2-digit',second:'2-digit'});
    const fmtHold = seconds => { if (seconds == null) return '—'; const m = Math.floor(seconds / 60), s = seconds % 60; return `${m}m ${s}s`; };
    const num = id => Math.max(0, Number($(id).value) || 0);
    $('symbol').textContent = context.ticker; $('date').textContent = `${context.trade_date} · 9:30–10:30 America/New_York`;
    $('candle-count').textContent = `0 / ${allBars.length}`; $('replay-time').textContent = fmtTime(sessionStart); app.hidden = false; message.hidden = true;

    function executionFor(side) {
      if ($('execution').value === 'close') return {price:currentBar().close, time:currentBar().time};
      sim.pending = {side}; $('sim-status').textContent = `Pending simulated ${side} at next candle open`; return null;
    }
    function execute(side, bar, price) {
      const slippage = num('slippage'), adjusted = side === 'buy' ? price + slippage : price - slippage, qty = Math.max(1, num('quantity'));
      if (side === 'buy') { if (sim.entry) return; sim.entry = {price:adjusted,time:bar.time,qty}; sim.side = 'long'; }
      else { if (!sim.entry || sim.exit) return; sim.exit = {price:adjusted,time:bar.time}; sim.pending = null; }
      updateSimulation(); draw();
    }
    function order(side) {
      const bar = currentBar(); if (!bar) { $('sim-status').textContent = 'Reveal a candle before placing an order'; return; }
      if ($('execution').value === 'next_open') { sim.pending = {side}; $('sim-status').textContent = `Pending simulated ${side} at next candle open`; return; }
      const fill = executionFor(side); if (fill) execute(side, bar, fill.price);
    }
    function next() {
      if (revealed >= allBars.length) { stop(); return; }
      const bar = allBars[revealed]; revealed += 1; candleSeries.update(bar);
      if (sim.pending) execute(sim.pending.side, bar, bar.open);
      updateStats(); updateSimulation();
      if (revealed >= allBars.length) stop();
    }
    function previous() { stop(); if (!revealed) return; revealed -= 1; candleSeries.setData(allBars.slice(0, revealed)); if (sim.pending) sim.pending = null; const t = revealedAt(); if (sim.entry && sim.entry.time > t) sim = {entry:null,exit:null,side:null,pending:null}; else if (sim.exit && sim.exit.time > t) sim.exit = null; updateStats(); updateSimulation(); }
    function reset() { stop(); revealed = 0; sim = {entry:null,exit:null,side:null,pending:null}; candleSeries.setData([]); updateStats(); updateSimulation(); }
    function play() { if (playing || revealed >= allBars.length) return; playing = true; tick(); }
    function stop() { playing = false; if (timer) { clearTimeout(timer); timer = null; } }
    function tick() { if (!playing) return; next(); if (playing) timer = setTimeout(tick, 1000 / Number($('speed').value)); }
    function updateStats() { const bar = currentBar(); $('replay-time').textContent = bar ? fmtTime(bar.time) : fmtTime(sessionStart); $('current-price').textContent = money(bar?.close); $('candle-count').textContent = `${revealed} / ${allBars.length}`; }
    function updateSimulation() {
      $('sim-entry').textContent = sim.entry ? money(sim.entry.price) : '—'; $('sim-exit').textContent = sim.exit ? money(sim.exit.price) : '—';
      const pnl = sim.entry && sim.exit ? (sim.exit.price - sim.entry.price) * sim.entry.qty - num('commission') * 2 : null;
      const basis = sim.entry ? sim.entry.price * sim.entry.qty : null, ret = pnl != null && basis ? pnl / basis * 100 : null;
      $('sim-return').textContent = ret == null ? '—' : `${ret >= 0 ? '+' : ''}${ret.toFixed(2)}%`; $('sim-pnl').textContent = pnl == null ? '—' : `${pnl >= 0 ? '+' : '-'}${money(Math.abs(pnl))}`;
      $('sim-holding').textContent = sim.entry && sim.exit ? fmtHold(sim.exit.time - sim.entry.time) : '—';
      if (!sim.entry) $('sim-status').textContent = sim.pending ? `Pending simulated ${sim.pending.side} at next candle open` : 'No simulated position'; else if (!sim.exit) $('sim-status').textContent = 'Simulated position open'; else $('sim-status').textContent = 'Simulated position closed';
    }
    function dims() { return {w:canvas.clientWidth,h:canvas.clientHeight,l:58,r:74,t:18,b:38,v:Math.max(38,canvas.clientHeight*.16)}; }
    function draw() {
      const d=dims(), {w,h,l,r,t,b,v}=d; ctx.clearRect(0,0,w,h); const data=candleSeries.data; if(!data.length){ctx.fillStyle='#8b98a9';ctx.fillText('Press Next candle or Play to begin the replay.',l,t+24);return;}
      const hi=Math.max(...data.map(x=>x.high)), lo=Math.min(...data.map(x=>x.low)), pad=(hi-lo||1)*.1, topPrice=hi+pad, botPrice=lo-pad, plotBottom=h-b-v, pxTime=x=>l+((x-sessionStart)/(sessionEnd-sessionStart))*(w-l-r), py=p=>t+(topPrice-p)/(topPrice-botPrice)*(plotBottom-t);
      ctx.strokeStyle='#2a3442';ctx.fillStyle='#8b98a9';ctx.font='11px sans-serif'; for(let i=0;i<=5;i++){let y=t+(plotBottom-t)*i/5;ctx.beginPath();ctx.moveTo(l,y);ctx.lineTo(w-r,y);ctx.stroke();ctx.fillText(money(topPrice-(topPrice-botPrice)*i/5),w-r+8,y+4)}
      for(let hour=9;hour<=10;hour++){const ts=sessionStart+(hour-9)*3600+ (hour===9?0:0), x=pxTime(ts);ctx.beginPath();ctx.moveTo(x,t);ctx.lineTo(x,h-b);ctx.stroke();ctx.fillText(`${hour}:30`,x-14,h-15)}
      const cw=Math.max(3,Math.min(14,(w-l-r)/Math.max(allBars.length,1)*.7)), mv=Math.max(...data.map(x=>x.volume),1); data.forEach(bar=>{const x=pxTime(bar.time), color=bar.close>=bar.open?'#39d09b':'#ff6b78';ctx.strokeStyle=color;ctx.fillStyle=color;ctx.beginPath();ctx.moveTo(x,py(bar.high));ctx.lineTo(x,py(bar.low));ctx.stroke();ctx.fillRect(x-cw/2,py(Math.max(bar.open,bar.close)),cw,Math.max(1,py(Math.min(bar.open,bar.close))-py(Math.max(bar.open,bar.close))));ctx.globalAlpha=.22;ctx.fillRect(x-cw/2,plotBottom+(h-b-plotBottom)*(1-bar.volume/mv),cw,(h-b-plotBottom)*bar.volume/mv);ctx.globalAlpha=1});
      const marker=(timestamp,price,color,label)=>{if(!timestamp||price==null)return;const x=pxTime(new Date(timestamp).getTime()/1000), y=py(+price);if(x<l||x>w-r)return;ctx.fillStyle=color;ctx.beginPath();ctx.arc(x,y,5,0,Math.PI*2);ctx.fill();ctx.fillText(label,x+8,y-7)};
      if(new Date(context.entry_timestamp||0).getTime()/1000<=revealedAt()) marker(context.entry_timestamp,context.entry_price,'#61a8ff','Actual entry'); if(new Date(context.exit_timestamp||0).getTime()/1000<=revealedAt()) marker(context.exit_timestamp,context.exit_price,'#61a8ff','Actual exit');
      if(sim.entry) marker(new Date(sim.entry.time*1000).toISOString(),sim.entry.price,'#ffbd66','Sim entry'); if(sim.exit) marker(new Date(sim.exit.time*1000).toISOString(),sim.exit.price,'#ffbd66','Sim exit');
      ctx.fillStyle='#8b98a9';ctx.fillText('VOLUME',l,plotBottom+16); if(hover){ctx.strokeStyle='rgba(237,243,250,.4)';ctx.setLineDash([3,4]);ctx.beginPath();ctx.moveTo(hover.x,t);ctx.lineTo(hover.x,h-b);ctx.stroke();ctx.setLineDash([])}
    }
    function resize(){const s=devicePixelRatio||1;canvas.width=canvas.clientWidth*s;canvas.height=canvas.clientHeight*s;ctx.setTransform(s,0,0,s,0,0);draw()}
    canvas.addEventListener('pointermove',e=>{const rect=canvas.getBoundingClientRect();hover={x:e.clientX-rect.left};tooltip.style.display='none';draw()}); canvas.addEventListener('pointerleave',()=>{hover=null;draw()});
    $('play').onclick=play; $('pause').onclick=stop; $('next').onclick=next; $('previous').onclick=previous; $('reset').onclick=reset; $('buy').onclick=()=>order('buy'); $('sell').onclick=()=>order('sell'); $('speed').onchange=()=>{if(playing){stop();play()}}; window.onresize=resize;
    updateStats(); updateSimulation(); resize();
  } catch (error) { showError(error.message || 'Unable to load the trade replay.'); }
})();
