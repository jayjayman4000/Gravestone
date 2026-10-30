'use strict';
(() => {
  const clamp = (value, low, high) => Math.min(high, Math.max(low, value));
  function projectPoint(lon, lat, view, width, height) {
    const scale = Math.min(width / 360, height / 180) * view.zoom;
    return [width / 2 + (lon - view.lon) * scale, height / 2 - (lat - view.lat) * scale];
  }
  function changeView(view, lon, lat, factor) {
    return {...view, lon: clamp(view.lon + lon, -180, 180), lat: clamp(view.lat + lat, -90, 90), zoom: clamp(view.zoom * factor, 1, view.maxZoom || 16)};
  }
  function fitBounds(bbox, width, height) {
    width = Math.max(1,width); height = Math.max(1,height);
    const [west,south,east,north] = bbox;
    const scale = Math.min(width / 360, height / 180);
    const zoom = Math.min(width / Math.max(.001,east-west), height / Math.max(.001,north-south)) * .8 / scale;
    return {lon:(west+east)/2, lat:(south+north)/2, zoom:clamp(zoom,1,131072), maxZoom:131072};
  }
  function parseCoordinates(latitude, longitude) {
    if (!latitude.trim() || !longitude.trim()) throw new Error('Enter both latitude and longitude.');
    const lat = Number(latitude), lon = Number(longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) {
      throw new Error('Latitude must be −90 to 90; longitude must be −180 to 180.');
    }
    return {lat, lon};
  }
  function rings(geometry) {
    if (!geometry) return [];
    if (geometry.type === 'Polygon') return geometry.coordinates;
    if (geometry.type === 'MultiPolygon') return geometry.coordinates.flat();
    return [];
  }
  function labelFits(box, placed) {
    const [x,y,w,h] = box;
    return placed.every(([px,py,pw,ph]) => x > px+pw+4 || x+w+4 < px || y > py+ph+4 || y+h+4 < py);
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {projectPoint, changeView, parseCoordinates, rings, labelFits, fitBounds};
    return;
  }
  class Atlas {
    constructor(canvas, features) {
      this.canvas = canvas;
      this.ctx = canvas.getContext('2d');
      if (!this.ctx) throw new Error('Canvas rendering is unavailable in this browser.');
      this.features = features;
      this.view = {lon:0, lat:0, zoom:1, maxZoom:131072};
      this.packs = [];
      this.layers = {roads:true,water:true,labels:true};
      new MutationObserver(() => this.schedule()).observe(document.documentElement, {attributes:true,attributeFilter:['data-theme']});
      this.marker = null;
      this.drag = null;
      this.frame = null;
      canvas.addEventListener('pointerdown', event => {
        if (event.button !== 0) return;
        this.drag = {x:event.clientX, y:event.clientY};
        canvas.setPointerCapture(event.pointerId);
        canvas.focus();
      });
      canvas.addEventListener('pointermove', event => {
        if (!this.drag) return;
        const scale = Math.min(this.width / 360, this.height / 180) * this.view.zoom;
        this.view = changeView(this.view, -(event.clientX-this.drag.x) / scale, (event.clientY-this.drag.y) / scale, 1);
        this.drag = {x:event.clientX, y:event.clientY};
        this.schedule();
      });
      for (const name of ['pointerup', 'pointercancel', 'lostpointercapture']) canvas.addEventListener(name, () => {this.drag = null;});
      canvas.addEventListener('wheel', event => {
        event.preventDefault();
        this.zoom(event.deltaY < 0 ? 1.2 : 1/1.2);
      }, {passive:false});
      canvas.addEventListener('keydown', event => {
        const step = 15 / this.view.zoom;
        const moves = {ArrowLeft:[-step,0], ArrowRight:[step,0], ArrowUp:[0,step], ArrowDown:[0,-step]};
        if (moves[event.key]) {
          event.preventDefault();
          this.view = changeView(this.view, ...moves[event.key], 1);
          this.schedule();
        } else if (['+', '=', '-'].includes(event.key)) {
          event.preventDefault(); this.zoom(event.key === '-' ? 1/1.5 : 1.5);
        } else if (event.key === 'Home') { event.preventDefault(); this.reset(); }
      });
      new ResizeObserver(() => this.resize()).observe(canvas);
      this.resize();
    }
    resize() {
      const rect = this.canvas.getBoundingClientRect();
      this.width = rect.width;
      this.height = rect.height;
      if (this.pendingBounds && this.width > 0 && this.height > 0) {
        this.view = fitBounds(this.pendingBounds,this.width,this.height);this.pendingBounds=null;
      }
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      this.canvas.width = Math.round(this.width * dpr);
      this.canvas.height = Math.round(this.height * dpr);
      this.ctx.setTransform(dpr,0,0,dpr,0,0);
      this.schedule();
    }
    schedule() {
      if (this.frame !== null) return;
      this.frame = requestAnimationFrame(() => {this.frame = null; this.draw();});
    }
    zoom(factor) { this.view = changeView(this.view, 0, 0, factor); this.schedule(); }
    reset() { this.view = {lon:0, lat:0, zoom:1,maxZoom:131072}; this.marker = null; this.schedule(); }
    setPacks(packs, fit=true) {
      this.packs = packs;
      if (fit && packs.length) {
        if (this.width > 0 && this.height > 0) this.view = fitBounds(packs[0].bbox,this.width,this.height);
        else this.pendingBounds = packs[0].bbox;
      }
      this.schedule();
    }
    draw() {
      const ctx = this.ctx;
      const point = (lon, lat) => projectPoint(lon,lat,this.view,this.width,this.height);
      const styles = getComputedStyle(document.documentElement);
      const color = name => styles.getPropertyValue('--map-' + name).trim() || styles.getPropertyValue('--text').trim() || '#888';
      ctx.fillStyle = color('bg');
      ctx.fillRect(0,0,this.width,this.height);
      ctx.strokeStyle = color('grid');
      ctx.lineWidth = .7;
      ctx.beginPath();
      for (let lon=-180; lon<=180; lon+=30) {ctx.moveTo(...point(lon,-90));ctx.lineTo(...point(lon,90));}
      for (let lat=-90; lat<=90; lat+=30) {ctx.moveTo(...point(-180,lat));ctx.lineTo(...point(180,lat));}
      ctx.stroke();
      ctx.strokeStyle = color('line');
      ctx.lineWidth = 1;
      const labelBoxes = [];
      for (const feature of this.features) {
        ctx.beginPath();
        for (const ring of rings(feature.geometry)) {
          let previous = null;
          for (const coordinate of ring) {
            const [lon,lat] = coordinate;
            if (!Number.isFinite(lon) || !Number.isFinite(lat)) continue;
            const xy = point(lon,lat);
            if (!previous || Math.abs(lon-previous[0]) > 180) ctx.moveTo(...xy);
            else ctx.lineTo(...xy);
            previous = coordinate;
          }
        }
        ctx.stroke();
        if (this.view.zoom >= 3) {
          const ring = rings(feature.geometry)[0];
          if (!ring || !ring.length) continue;
          const xs = ring.map(p => p[0]), ys = ring.map(p => p[1]);
          const low = Math.min(...xs), high = Math.max(...xs);
          if (high-low > 180) continue;
          const [x,y] = point((low+high)/2,(Math.min(...ys)+Math.max(...ys))/2);
          const name = feature.properties && (feature.properties.name || feature.properties.iso_a3);
          if (name && x > 20 && y > 20 && x < this.width-20 && y < this.height-20) {
            ctx.font = '11px system-ui';
            const width = ctx.measureText(String(name)).width;
            const box = [x-width/2,y-10,width,13];
            if (box[0] < 4 || box[0]+width > this.width-4 || !labelFits(box,labelBoxes)) continue;
            labelBoxes.push(box);
            ctx.textAlign='center'; ctx.fillStyle=color('label'); ctx.fillText(String(name),x,y);
          }
        }
      }
      for (const pack of this.packs) {
        if (!this.layers[pack.layer]) continue;
        // Draw minor paths first; primary/secondary highways remain distinguishable.
        const ranked = pack.features;
        for (const feature of ranked) {
          const major = ['S1100','S1200'].includes(feature.properties.mtfcc);
          ctx.strokeStyle = color(pack.layer === 'water' ? 'water' : 'road');
          ctx.lineWidth = pack.layer === 'water' ? 1.1 : major ? 2.5 : .8;
          ctx.globalAlpha = pack.layer === 'water' ? .75 : major ? 1 : .55;
          ctx.setLineDash(pack.layer === 'water' ? [5,3] : []);
          ctx.beginPath();
          let anchor = null;
          for (const line of feature.geometry.coordinates) {
            let previous = null;
            for (const coordinate of line) {
              const xy = point(...coordinate);
              if (!previous || Math.abs(coordinate[0]-previous[0]) > 180) ctx.moveTo(...xy);
              else ctx.lineTo(...xy);
              if (xy[0]>8 && xy[0]<this.width-8 && xy[1]>16 && xy[1]<this.height-8) anchor = xy;
              previous = coordinate;
            }
          }
          ctx.stroke();
          const name = feature.properties.name;
          if (this.layers.labels && name && anchor && (major || this.view.zoom > 1000)) {
            ctx.font = '11px system-ui';
            const width = ctx.measureText(name).width;
            const box = [anchor[0]-width/2,anchor[1]-10,width,13];
            if (labelFits(box,labelBoxes)) {
              labelBoxes.push(box); ctx.globalAlpha=1; ctx.textAlign='center';
              ctx.lineWidth=3; ctx.strokeStyle=color('bg');ctx.strokeText(name,...anchor);
              ctx.fillStyle=color('label');ctx.fillText(name,...anchor);
            }
          }
        }
      }
      ctx.globalAlpha=1;ctx.setLineDash([]);
      if (this.marker) {
        const [x,y] = point(this.marker.lon,this.marker.lat);
        ctx.strokeStyle=color('marker');ctx.lineWidth=2;ctx.beginPath();ctx.arc(x,y,5,0,Math.PI*2);
        ctx.moveTo(x-12,y);ctx.lineTo(x+12,y);ctx.moveTo(x,y-12);ctx.lineTo(x,y+12);ctx.stroke();
      }
      document.getElementById('map-status').textContent = `Center ${this.view.lat.toFixed(4)}°, ${this.view.lon.toFixed(4)}° · ${this.view.zoom.toFixed(1)}× · ${this.packs.length ? this.packs.map(p => p.name + ' ' + p.layer + ' (2025)').join(' · ') : 'country overview; no regional detail displayed'} · reference, not routing`;
    }
  }
  async function loadMap() {
    const get = id => document.getElementById(id);
    try {
      const library = await libraryReady;
      const url = library && library.map && contentURL(library.map.file);
      if (!url) throw new Error('No reference map is installed.');
      const response = await fetch(url);
      if (!response.ok) throw new Error('Reference map file is unavailable.');
      const geo = await response.json();
      if (geo.type !== 'FeatureCollection' || !Array.isArray(geo.features)) throw new Error('Reference map is not a GeoJSON FeatureCollection.');
      const features = geo.features.filter(f => f.geometry && ['Polygon','MultiPolygon'].includes(f.geometry.type));
      if (!features.length) throw new Error('No country polygons are available.');
      const atlas = new Atlas(get('world-map'), features);
      window.gravestoneAtlas = atlas;
      document.dispatchEvent(new Event('gravestone:map-ready'));
      get('map-source').textContent = [library.map.publisher, library.map.rights].filter(Boolean).join(' · ') || 'Map provenance not supplied.';
      const names = features.map(f => f.properties && (f.properties.name || f.properties.iso_a3)).filter(Boolean).sort();
      get('map-countries').textContent = names.length ? names.join(' · ') : 'Country names are not supplied in this map.';
      for (const id of ['zoom-in','zoom-out','map-reset','map-center']) get(id).disabled = false;
      get('zoom-in').addEventListener('click', () => atlas.zoom(1.5));
      get('zoom-out').addEventListener('click', () => atlas.zoom(1/1.5));
      get('map-reset').addEventListener('click', () => atlas.reset());
      get('map-center-form').addEventListener('submit', event => {
        event.preventDefault();
        try {
          const coordinates = parseCoordinates(get('latitude').value,get('longitude').value);
          atlas.marker = coordinates;
          atlas.view = {...coordinates,zoom:Math.max(3,atlas.view.zoom),maxZoom:131072};
          get('coordinate-status').textContent = 'Entered reference point only; not a GPS fix. Coordinates are not saved.';
          atlas.schedule();
        } catch (error) {get('coordinate-status').textContent = error.message;}
      });
    } catch (error) {
      get('map-status').textContent = error.message;
      get('map-status').classList.add('error');
    }
  }
  loadMap();
  if (!document.querySelector('script[src="/static/maps.js"]')) {
    const script = document.createElement('script');script.src='/static/maps.js';document.head.append(script);
  }
})();
