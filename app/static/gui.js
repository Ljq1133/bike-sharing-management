// helper for API calls with token
async function http(path, opts={}){
  const token = document.getElementById('token').value;
  opts.headers = opts.headers || {};
  if(token) opts.headers['Authorization'] = 'Bearer '+token;
  const res = await fetch(path, opts);
  if(!res.ok) throw await res.json();
  return res.json();
}

// map + marker state
let map, markers = [];
function initMap(){
  map = L.map('map').setView([31.23,121.47], 13);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom:19}).addTo(map);
}

function clearMarkers(){
  for(const m of markers) map.removeLayer(m);
  markers = [];
}

function addBikeMarker(b){
  const cls = b.status==='available' ? 'green' : (b.status==='maintenance' ? 'orange' : 'red');
  const icon = L.divIcon({className:'', html:`<div class="marker ${cls}"><span class="pulse"></span><span class="dot"></span></div>`, iconSize:[26,26], iconAnchor:[13,13]});
  const marker = L.marker([b.lat, b.lng], {icon}).addTo(map);
  const me = sessionStorage.getItem('bike_me') ? JSON.parse(sessionStorage.getItem('bike_me')) : null;
  let actionHtml = '';
  if(me && me.is_maintainer){
    // For maintainers: delete is allowed (server will handle any constraints); maintenance toggle disabled when bike is in use
    const maintDisabled = b.status === 'in_use' ? 'disabled' : '';
    actionHtml = `<button onclick="deleteFromPopup(${b.id})" class='btn danger'>删除</button> <button ${maintDisabled} onclick="toggleMaintFromPopup(${b.id},'${b.status}')" class='btn'>维护</button>`;
  } else {
    // For users: only allow rent when available and user has no ongoing rental
    const hasOngoing = sessionStorage.getItem('has_ongoing_rental') === '1';
    if(hasOngoing){
      actionHtml = `<button class='btn' disabled>已拥有租赁</button>`;
    } else if(b.status === 'available'){
      actionHtml = `<button onclick="rentFromPopup(${b.id})" class='btn primary'>租赁</button>`;
    } else {
      actionHtml = `<button class='btn' disabled>不可租赁</button>`;
    }
  }
  const html = `<div style="min-width:180px"><b>单车 #${b.id}</b><div class="muted">状态: ${b.status} · 评分: ${(b.rating||0).toFixed(2)} · 使用次数: ${(b.usage_count||0)}</div><div style="margin-top:8px">${actionHtml}</div></div>`;
  marker.bindPopup(html);
  markers.push(marker);
}

// Center map on a bike and show nearby bikes by setting manual coords and triggering locate
window.centerOnBike = async (bikeId) => {
  try{
    const bikes = await http('/api/bikes');
    const b = bikes.find(x=> x.id === bikeId);
    if(!b){ alert('未找到该单车'); return; }
    // set manual inputs so locate uses this point
    try{ document.getElementById('manualLat').value = b.lat; document.getElementById('manualLng').value = b.lng; }catch(e){}
    // ensure manual mode and show manual coords input (dispatch change event so listener updates UI)
    try{
      const modeSel = document.getElementById('modeSelect');
      if(modeSel){ modeSel.value = 'manual'; modeSel.dispatchEvent(new Event('change')); }
      const manualContainer = document.getElementById('manualCoordsContainer'); if(manualContainer) manualContainer.style.display = 'block';
      // scroll sidebar to top so manual coords and list are visible
      try{ const sb = document.querySelector('.sidebar'); if(sb) sb.scrollTo({top:0, behavior:'smooth'}); }catch(e){}
    }catch(e){}
    try{ document.getElementById('locate').click(); }catch(e){ map.setView([b.lat, b.lng], 13); }
  }catch(e){ alert('定位失败: '+JSON.stringify(e)); }
}

window.rentFromPopup = async (bikeId)=>{
  try{
    await http('/api/rentals',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({bike_id:bikeId})});
    alert('租赁成功');
    try{ await fetchMyRentals(); }catch(e){}
    try{ document.getElementById('locate').click(); }catch(e){}
  }catch(e){ alert(JSON.stringify(e)); }
}

window.deleteFromPopup = async (bikeId)=>{
  try{
    await http(`/api/bikes/${bikeId}`,{method:'DELETE'});
    alert('删除成功');
    // refresh list/markers
    document.getElementById('locate').click();
  }catch(e){ alert(JSON.stringify(e)); }
}

window.toggleMaintFromPopup = async (bikeId, status)=>{
  const me = sessionStorage.getItem('bike_me') ? JSON.parse(sessionStorage.getItem('bike_me')) : null;
  if(!me || !me.is_maintainer){ alert('仅维护人员可执行此操作'); return; }
  // Do not allow setting maintenance while bike is rented
  if(status === 'in_use'){
    alert('被租赁的单车不能切换到维护状态');
    return;
  }
  const newStatus = status==='maintenance' ? 'available' : 'maintenance';
  try{
    await http(`/api/bikes/${bikeId}/status`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:newStatus})});
    alert('修改成功');
    try{ document.getElementById('locate').click(); }catch(e){}
    try{ fetchMyRentals(); }catch(e){}
  }catch(e){ alert(JSON.stringify(e)); }
}

function showApp(){
  document.getElementById('loginOverlay').style.display = 'none';
  document.getElementById('app').style.display = 'block';
  if(!map) initMap();
  const t = sessionStorage.getItem('bike_token'); if(t) document.getElementById('token').value = t;
  if(document.getElementById('token').value) { fetchMeAndUpdate(); fetchMyRentals(); }
}

// distance helper (km)
function haversineKm(lat1, lon1, lat2, lon2){
  const toRad = v => v * Math.PI / 180;
  const R = 6371; // km
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a = Math.sin(dLat/2) * Math.sin(dLat/2) + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon/2) * Math.sin(dLon/2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  return R * c;
}

function showLoginOverlay(){
  // restore initial login content
  const o = document.getElementById('loginOverlay');
  o.innerHTML = `
    <div class="login-card">
      <h2>登录</h2>
      <input id="overlay_username" placeholder="用户名">
      <input id="overlay_password" type="password" placeholder="密码">
      <div class="row">
        <button id="overlayLogin" class="btn primary">登录</button>
        <button id="showRegister" class="btn">去注册</button>
      </div>
      <div style="margin-top:8px;color:var(--muted);font-size:13px">未注册？点击“去注册”在弹窗中完成注册。</div>
    </div>`;
  // bind
  document.getElementById('overlayLogin').onclick = async ()=>{
    const u = document.getElementById('overlay_username').value;
    const p = document.getElementById('overlay_password').value;
    const data = new URLSearchParams(); data.append('username',u); data.append('password',p);
    try{
      const r = await fetch('/api/auth/login',{method:'POST',body:data});
      const j = await r.json();
      if(!r.ok){ throw j; }
      document.getElementById('token').value = j.access_token; sessionStorage.setItem('bike_token', j.access_token);
      showApp();
      alert('登录成功');
    }catch(e){ alert('登录失败: '+ (e && e.detail ? e.detail : JSON.stringify(e))); }
  };
  document.getElementById('showRegister').onclick = ()=>{ showRegisterOverlay(); };
}

function showRegisterOverlay(){
  const o = document.getElementById('loginOverlay');
  o.innerHTML = `
    <div class="login-card">
      <h2>注册</h2>
      <input id="overlay_reg_username" placeholder="用户名">
      <input id="overlay_reg_password" type="password" placeholder="密码">
      <label style="display:flex;align-items:center;gap:8px;margin:6px 0"><input type="checkbox" id="overlay_reg_is_maintainer"> 我是维护人员</label>
      <input id="overlay_reg_invite" placeholder="邀请码（维护人员）" />
      <div class="row">
        <button id="overlayRegister" class="btn primary">注册</button>
        <button id="overlayBack" class="btn">返回登录</button>
      </div>
    </div>`;
  document.getElementById('overlayBack').onclick = ()=>{ showLoginOverlay(); };
  document.getElementById('overlayRegister').onclick = async ()=>{
    const u = document.getElementById('overlay_reg_username').value;
    const p = document.getElementById('overlay_reg_password').value;
    const isMaint = document.getElementById('overlay_reg_is_maintainer').checked;
    const invite = document.getElementById('overlay_reg_invite').value;
    if(!u){ alert('用户名不能为空'); return; }
    if(!p || p.length<=8 || !(/[A-Za-z]/.test(p) && /[0-9]/.test(p))){ alert('密码必须超过8位并包含字母和数字'); return; }
    try{
      const body = {username:u,password:p,is_maintainer:isMaint}; if(invite) body.invite_code = invite;
      const res = await fetch('/api/users',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      if(!res.ok){ const err = await res.json(); throw err; }
      alert('注册成功，请登录');
      showLoginOverlay();
    }catch(e){ alert(JSON.stringify(e)); }
  };
}

window.addEventListener('load', ()=>{
  // show overlay; init token if present
  const t = sessionStorage.getItem('bike_token'); if(t) document.getElementById('token').value = t;
  showLoginOverlay();
});

async function fetchMeAndUpdate(){
  try{
    const me = await http('/api/me');
    sessionStorage.setItem('bike_me', JSON.stringify(me));
    const info = document.getElementById('meInfo'); if(info) info.innerText = `已登录: ${me.username} (${me.is_maintainer? '维护人员':'普通用户'})`;
    // toggle maintainer-only UI
    const mPanel = document.getElementById('maintainerControls'); if(mPanel) mPanel.style.display = me.is_maintainer ? 'block' : 'none';
    // hide sidebar auth/login UI after successful login
    const authEl = document.querySelector('.auth'); if(authEl) authEl.style.display = 'none';
      // update my rentals list after we have the user
      try{ fetchMyRentals(); }catch(e){ console.warn('fetchMyRentals call failed', e); }
    return me;
  }catch(e){
    sessionStorage.removeItem('bike_me');
    const info = document.getElementById('meInfo'); if(info) info.innerText = '';
    // show sidebar auth when not logged in
    const authEl = document.querySelector('.auth'); if(authEl) authEl.style.display = 'block';
    const container = document.getElementById('myRentals'); if(container) container.innerHTML = '';
    return null;
  }
}

async function fetchMyRentals(){
  try{
    const me = sessionStorage.getItem('bike_me') ? JSON.parse(sessionStorage.getItem('bike_me')) : null;
    const container = document.getElementById('myRentals');
    const header = document.getElementById('rentalsHeader');
    if(!container) return;
    container.innerHTML = '';
    if(me && me.is_maintainer){
      // show maintenance records for maintainers
      if(header) header.innerText = '维修记录';
      const list = await http('/api/maintenances');
      if(!list || list.length===0){ container.innerHTML = '<div class="muted">暂无维修记录</div>'; return; }
      for(const m of list){
        const el = document.createElement('div'); el.className='bike-card';
        const txt = `<div><b>维护 #${m.id}</b><div class="muted">单车:${m.bike_id} 维护人:${m.maintainer_id||'-'}<br/>开始:${m.start_time||'-'} 结束:${m.end_time||'-'}</div></div>`;
        el.innerHTML = txt;
        container.appendChild(el);
      }
      return;
    } else {
      if(header) header.innerText = '我的租赁';
      const list = await http('/api/rentals/me');
      // mark whether user has any ongoing rental
      const hasOngoing = list && list.some(r=> r.status === 'ongoing');
      try{ sessionStorage.setItem('has_ongoing_rental', hasOngoing ? '1' : '0'); }catch(e){}
      if(!list || list.length===0){ container.innerHTML = '<div class="muted">暂无租赁</div>'; return; }
      for(const r of list){
        const el = document.createElement('div'); el.className='bike-card';
        const txt = `<div><b>租赁 #${r.id}</b><div class="muted">单车:${r.bike_id} 状态:${r.status} ${r.rating!=null? '· 评分:'+r.rating : ''}</div></div>`;
        el.innerHTML = txt;
        if(r.status==='ongoing'){
          const btn = document.createElement('button'); btn.className='btn primary'; btn.innerText='归还'; btn.onclick=async ()=>{
            try{
              // prompt for rating 0-5
              let rating = null;
              try{
                const inp = prompt('给此单车评分 0-5（可留空）');
                if(inp !== null && inp !== ''){
                  const rv = parseInt(inp);
                  if(isNaN(rv) || rv<0 || rv>5) { alert('评分必须为0-5的整数'); return; }
                  rating = rv;
                }
              }catch(e){}
              await http(`/api/rentals/${r.id}/return`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({rating: rating})});
              alert('归还成功');
              try{ await fetchMyRentals(); }catch(e){ console.warn('fetchMyRentals after return failed', e); }
              try{ sessionStorage.setItem('has_ongoing_rental','0'); }catch(e){}
              try{ document.getElementById('locate').click(); }catch(e){}
            }catch(e){ alert(JSON.stringify(e)); }
          };
          el.appendChild(btn);
        }
        container.appendChild(el);
      }
    }
  }catch(e){ console.warn('fetchMyRentals failed', e); }
}

window.addEventListener('load', ()=>{ if(document.getElementById('token').value) fetchMeAndUpdate(); });

// show/hide manual coords when mode changes
window.addEventListener('load', ()=>{
  const modeSel = document.getElementById('modeSelect');
  const manualContainer = document.getElementById('manualCoordsContainer');
  if(modeSel && manualContainer){
    const update = ()=>{ manualContainer.style.display = (modeSel.value === 'manual') ? 'block' : 'none'; };
    modeSel.addEventListener('change', update);
    update();
  }
});

document.getElementById('locate').onclick = async ()=>{
  // Determine selected mode: manual / geolocate / top_rated
    const modeSel = document.getElementById('modeSelect');
    const mode = modeSel ? modeSel.value : 'manual';
  // Fetch bikes early so we can sort/display and use first bike as center when coords are missing
  let bikes = [];
  try{ bikes = await http('/api/bikes'); }catch(e){ bikes = []; }

  // pre-sort for non-distance modes so bikes[0] matches displayed first
  if(mode === 'top_rated'){
    bikes.sort((a,b)=> (b.rating||0) - (a.rating||0));
  } else if(mode === 'top_used'){
    bikes.sort((a,b)=> (b.usage_count||0) - (a.usage_count||0));
  }

  // show/hide manual coords when mode changes (handled at top-level)
  // Use manual inputs if provided, otherwise use first bike or current map center.
  const latInput = document.getElementById('manualLat').value;
  const lngInput = document.getElementById('manualLng').value;
  let lat, lng;
  if(mode === 'geolocate'){
    // try browser geolocation (promise wrapper)
    try{
      const pos = await new Promise((resolve, reject)=> navigator.geolocation.getCurrentPosition(resolve, reject, {timeout:10000}));
      lat = pos.coords.latitude; lng = pos.coords.longitude;
    }catch(e){
      // fallback to manual/map center
      if(latInput && lngInput){ lat = parseFloat(latInput); lng = parseFloat(lngInput); }
      else if(bikes && bikes.length>0){ lat = bikes[0].lat; lng = bikes[0].lng; }
      else if(map){ const center = map.getCenter(); lat = center.lat; lng = center.lng; }
      else { lat = 31.23; lng = 121.47; }
    }
  } else {
    if(latInput && lngInput){ lat = parseFloat(latInput); lng = parseFloat(lngInput); }
    else if(bikes && bikes.length>0){ lat = bikes[0].lat; lng = bikes[0].lng; }
    else if(map){ const center = map.getCenter(); lat = center.lat; lng = center.lng; }
    else { lat = 31.23; lng = 121.47; }
  }
  map.setView([lat,lng], 13);
  try{
    // bikes already fetched above; fallback if request failed earlier
    if(!bikes || bikes.length===0){ try{ bikes = await http('/api/bikes'); }catch(e){ bikes = []; } }
    const container = document.getElementById('bikes'); container.innerHTML = '';
    clearMarkers();
    // if backend returns empty, create demo markers nearby for a nicer demo
    if(!bikes || bikes.length===0){
      bikes = [];
      for(let i=0;i<6;i++){
        const offsetLat = (Math.random()-0.5)*0.01; const offsetLng = (Math.random()-0.5)*0.01;
        bikes.push({id:1000+i, lat: lat+offsetLat, lng: lng+offsetLng, status: ['available','in_use','maintenance'][Math.floor(Math.random()*3)], rating: Math.random()*5});
      }
      container.innerHTML = '<div class="muted">展示演示车辆（后端无数据）</div>';
    }

    // Sorting according to mode (distance-based sorts require lat/lng)
    if(mode === 'top_rated' || mode === 'top_used'){
      // already pre-sorted above; nothing to do here
    } else {
      // compute distance from chosen lat/lng and sort ascending
      for(const b of bikes){ b._dist_km = haversineKm(lat, lng, b.lat||0, b.lng||0); }
      bikes.sort((a,b)=> (a._dist_km||0) - (b._dist_km||0));
    }

    for(const b of bikes){
      addBikeMarker(b);
      const card = document.createElement('div'); card.className='bike-card';
      let infoLine = `${(b.lat||0).toFixed(5)}, ${(b.lng||0).toFixed(5)} · 评分: ${(b.rating||0).toFixed(2)} · 使用次数: ${(b.usage_count||0)}`;
      if(mode !== 'top_rated' && mode !== 'top_used' && b._dist_km!=null){ infoLine += ` · 距离: ${b._dist_km.toFixed(2)} km`; }
      card.innerHTML = `<div><b>单车 #${b.id}</b><div class="muted">${infoLine}</div></div><div><span class='badge ${b.status}'>${b.status}</span></div>`;
      const row = document.createElement('div'); row.style.marginTop='8px';
      const locateBtn = document.createElement('button'); locateBtn.className='btn'; locateBtn.innerText='定位'; locateBtn.onclick = ()=>{ try{ document.getElementById('manualLat').value = b.lat; document.getElementById('manualLng').value = b.lng; const modeSel = document.getElementById('modeSelect'); if(modeSel){ modeSel.value='manual'; modeSel.dispatchEvent(new Event('change')); } const manualContainer = document.getElementById('manualCoordsContainer'); if(manualContainer) manualContainer.style.display='block'; try{ const sb = document.querySelector('.sidebar'); if(sb) sb.scrollTo({top:0, behavior:'smooth'}); }catch(e){} document.getElementById('locate').click(); }catch(e){ map.setView([b.lat,b.lng],13); } };
      row.appendChild(locateBtn);
      const me = sessionStorage.getItem('bike_me') ? JSON.parse(sessionStorage.getItem('bike_me')) : null;
      if(me && me.is_maintainer){
          const delBtn = document.createElement('button'); delBtn.className='btn danger'; delBtn.innerText='删除'; delBtn.onclick=async ()=>{ try{ await http(`/api/bikes/${b.id}`,{method:'DELETE'}); alert('删除成功'); document.getElementById('locate').click(); }catch(e){ alert(JSON.stringify(e)); } };
        row.appendChild(delBtn);
        const maintBtn = document.createElement('button'); maintBtn.className='btn';
        if(b.status === 'in_use'){
          maintBtn.innerText = '无法维护(使用中)'; maintBtn.disabled = true;
        } else {
          maintBtn.innerText='维护切换'; maintBtn.onclick=async ()=>{ 
            try{
              await http(`/api/bikes/${b.id}/status`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status: b.status==='maintenance'?'available':'maintenance'})});
              alert('修改成功');
              try{ document.getElementById('locate').click(); }catch(e){}
              try{ fetchMyRentals(); }catch(e){}
            }catch(e){ alert(JSON.stringify(e)); }
          };
        }
        row.appendChild(maintBtn);
      } else {
        const hasOngoing = sessionStorage.getItem('has_ongoing_rental') === '1';
        const rentBtn = document.createElement('button'); rentBtn.className='btn primary';
        if(hasOngoing){ rentBtn.innerText='请先归还'; rentBtn.disabled = true; }
        else { rentBtn.innerText='租赁'; rentBtn.onclick=async ()=>{ try{ await http('/api/rentals',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({bike_id:b.id})}); alert('租赁成功'); try{ fetchMyRentals(); }catch(e){} try{ document.getElementById('locate').click(); }catch(e){} }catch(e){ alert(JSON.stringify(e)); } }; }
        row.appendChild(rentBtn);
      }
      card.appendChild(row);
      container.appendChild(card);
    }
  }catch(e){ alert('请求失败: '+JSON.stringify(e)); }
}

// add bike (maintainer)
document.getElementById('addBike').onclick = async ()=>{
  const lat = parseFloat(document.getElementById('newLat').value);
  const lng = parseFloat(document.getElementById('newLng').value);
  if(Number.isNaN(lat) || Number.isNaN(lng)){ alert('请输入有效的经纬度'); return; }
  try{
    await http('/api/bikes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({lat, lng})});
    alert('添加成功');
    // refresh nearby view (try to re-run locate)
    document.getElementById('locate').click();
  }catch(e){ alert(JSON.stringify(e)); }
}
