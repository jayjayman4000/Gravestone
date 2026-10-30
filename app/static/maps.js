'use strict';
(() => {
  if (window.GravestoneMapsLoaded) return;
  window.GravestoneMapsLoaded = true;
  const element = (tag, text, attrs={}) => {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    for (const [key,value] of Object.entries(attrs)) node.setAttribute(key,value);
    return node;
  };
  async function api(path, options) {
    const response = await fetch(path, options);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `Map request failed (${response.status})`);
    return data;
  }
  const post = (path, data) => api(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  async function init() {
    let root = document.getElementById('map-pack-manager');
    if (!root) {
      const dialog = document.querySelector('#map-tools .drawer-body');
      if (!dialog) return;
      root = element('section',null,{id:'map-pack-manager'});dialog.prepend(root);
    }
    root.replaceChildren();
    root.append(element('h3','Offline U.S. county map packs'));
    root.append(element('p','Choose only the counties you need. TIGER/Line 2025 · U.S. Census Bureau. Roads/highways and named paths are reference data, NOT computed routes or current passability. Dashed mapped-water lines do not imply drinking-water safety. No elevation data installed.'));
    const status = element('p','Loading local catalog…',{id:'map-pack-status',role:'status','aria-live':'polite'});
    root.append(status);
    const states = element('select',null,{id:'map-state'}), counties = element('select',null,{id:'map-county'});
    const label = (text,input) => {const node=element('label',text);node.append(input);return node;};
    root.append(label('State / territory ',states),label('County / equivalent (2025 coverage) ',counties));
    const roads=element('input',null,{type:'checkbox',id:'download-roads'});roads.checked=true;
    const water=element('input',null,{type:'checkbox',id:'download-water'});
    root.append(label(' Download roads / highways ',roads),label(' Download linear water ',water));
    const preparation=element('input',null,{type:'checkbox',id:'map-online-preparation'});
    root.append(label(' ONLINE PREPARATION: I explicitly permit this selected Census download. This does not enable the operating-system network. ',preparation));
    const download=element('button','Download selected county layers',{type:'button',id:'map-download'});
    download.disabled=true;preparation.addEventListener('change',()=>{download.disabled=!preparation.checked;});
    root.append(download);
    root.append(element('p','Per layer: ZIP ≤64 MiB; expanded ≤256 MiB; converted ≤96 MiB. Original ZIPs are retained. At least 512 MiB free space plus conversion headroom is required. Exact download size is unknown until the publisher responds; a large county may be refused. No automatic downloads.'));
    const importLayer=element('select',null,{id:'map-import-layer'});
    for (const layer of ['roads','water']) importLayer.append(element('option',layer,{value:layer}));
    const file=element('input',null,{type:'file',accept:'.zip,application/zip',id:'map-import-file'});
    const importButton=element('button','Import selected official Census ZIP (offline)',{type:'button',id:'map-import'});
    root.append(element('h4','Import pack without internet'),element('p','On a connected computer, download the original 2025 county ROADS or LINEARWATER ZIP from www2.census.gov. Select its matching state/county and layer here, choose that ZIP, then Import. Imports are user-supplied bytes, not authenticated publisher downloads.'),label('Import layer ',importLayer),label('Original Census ZIP ',file),importButton);
    const layerBox=element('fieldset');layerBox.append(element('legend','Displayed map layers'));
    for (const [key,title] of [['roads','Roads / highways'],['water','Mapped linear water (dashed)'],['labels','Source names / labels']]) {
      const input=element('input',null,{type:'checkbox',id:'map-layer-'+key});input.checked=true;
      input.addEventListener('change',()=>{if(window.gravestoneAtlas){window.gravestoneAtlas.layers[key]=input.checked;window.gravestoneAtlas.schedule();}});
      layerBox.append(label(title+' ',input));
    }
    const topo=element('input',null,{type:'checkbox',id:'map-layer-topo',disabled:'disabled'});
    layerBox.append(label('Topo / elevation — Not installed / unavailable ',topo));root.append(layerBox);
    const installed=element('div',null,{id:'map-installed'});root.append(element('h4','Installed packs (local storage)'),installed);
    let catalog, packs=[];
    async function show(regionId) {
      const selected=packs.filter(pack=>pack.region_id===regionId);
      if (!window.gravestoneAtlas) throw new Error('Map canvas is not available yet. Try View again.');
      status.textContent='Loading installed county geometry from local storage…';
      const local=[];
      for (const pack of selected) {
        const geo=await api('/api/maps/data?id='+encodeURIComponent(pack.id)+'&layer='+pack.layer);
        // Sort once, not on every redraw; highways paint over smaller roads.
        geo.features.sort((a,b)=>Number(['S1100','S1200'].includes(a.properties.mtfcc))-Number(['S1100','S1200'].includes(b.properties.mtfcc)));
        local.push({...pack,features:geo.features});
      }
      window.gravestoneAtlas.setPacks(local);
      const text=selected.map(p=>`${p.name}, ${p.state} · ${p.layer} · ${p.features.toLocaleString()} features · Census 2025`).join(' / ');
      status.textContent=text+' · local/offline reference; not routing.';
      document.getElementById('world-map').setAttribute('aria-label',text+'; roads and mapped water reference, not computed routing');
    }
    async function refresh() {
      packs=(await api('/api/maps/installed')).packs;
      installed.replaceChildren();
      if (!packs.length) installed.append(element('p','No county packs installed. Only the separate country-outline overview is available.'));
      for (const pack of packs) {
        const row=element('section');
        row.append(element('p',`${pack.name}, ${pack.state} · ${pack.layer} · ${pack.year} · ${((pack.original_bytes+pack.data_bytes)/1048576).toFixed(1)} MiB · ${pack.features.toLocaleString()} features`));
        const view=element('button','View county',{type:'button'});
        view.addEventListener('click',()=>show(pack.region_id).catch(error=>{status.textContent=error.message;}));
        const remove=element('button','Remove '+pack.layer,{type:'button'});
        remove.addEventListener('click',async()=>{
          if(!confirm(`Remove ${pack.name} ${pack.layer} from local storage?`)) return;
          try {await post('/api/maps/remove',{id:pack.id});await refresh();window.gravestoneAtlas?.setPacks([],false);status.textContent='Pack removed.';} catch(error){status.textContent=error.message;}
        });
        const provenance=element('details');provenance.append(element('summary','Source / byte integrity'),element('p',`${pack.publisher}. ${pack.rights} ${pack.source_url} · Original SHA-256: ${pack.sha256} · Retrieved/imported: ${pack.retrieved_at}. ${pack.imported?'User-supplied import; publisher origin not authenticated.':''}`));
        row.append(view,remove,provenance);installed.append(row);
      }
    }
    download.addEventListener('click',async()=>{
      if(!preparation.checked) return;
      download.disabled=true;
      try {
        const layers=[...(roads.checked?['roads']:[]),...(water.checked?['water']:[])];
        const job=await post('/api/maps/download',{region_id:counties.value,layers,online_preparation:true});
        for (;;) {
          const progress=await api('/api/maps/jobs/'+job.id);
          status.textContent=`${progress.state}: county ${progress.region_id} ${progress.layer||''}. Only selected layers are requested.`;
          if(progress.state==='complete'){await refresh();await show(progress.region_id);break;}
          if(progress.state==='error'){await refresh();throw new Error(progress.error+' Installed layers, if any, are listed below.');}
          await new Promise(resolve=>setTimeout(resolve,700));
        }
      } catch(error){status.textContent=error.message;} finally{download.disabled=!preparation.checked;}
    });
    importButton.addEventListener('click',async()=>{
      importButton.disabled=true;
      try {
        if(!file.files.length) throw new Error('Choose the original county Census ZIP first.');
        const selected=file.files[0];
        if(selected.size>64*1048576) throw new Error('ZIP exceeds 64 MiB.');
        status.textContent='Validating and importing selected local ZIP…';
        await api(`/api/maps/import?region_id=${encodeURIComponent(counties.value)}&layer=${importLayer.value}`,{method:'POST',headers:{'Content-Type':'application/zip'},body:selected});
        await refresh();await show(counties.value);
      } catch(error){status.textContent=error.message;} finally{importButton.disabled=false;}
    });
    try {
      catalog=await api('/api/maps/catalog');
      for(const state of [...new Set(catalog.regions.map(r=>r.state))].sort()) states.append(element('option',state,{value:state}));
      const updateCounties=()=>{counties.replaceChildren();for(const region of catalog.regions.filter(r=>r.state===states.value)) counties.append(element('option',region.name+' ['+region.id+']',{value:region.id}));};
      states.addEventListener('change',updateCounties);updateCounties();
      await refresh();status.textContent=`Local 2025 catalog: ${catalog.regions.length.toLocaleString()} counties/equivalents, ${states.options.length} state/territory codes. No online request made. Select a county or view an installed pack.`;
      const first=packs[0];
      if(first){if(window.gravestoneAtlas) await show(first.region_id);else document.addEventListener('gravestone:map-ready',()=>show(first.region_id).catch(error=>{status.textContent=error.message;}),{once:true});}
    }catch(error){status.textContent='Map catalog/storage unavailable: '+error.message;download.disabled=true;}
  }
  init();
})();
