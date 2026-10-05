// Native web component: no build step or external frontend dependencies.
export class DeskDisplayPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode: 'open'});
    this.devices = [];
    this.selected = 0;
    this.widgetIndex = 0;
    this.previewSequence = 0;
    this.inspectorTab = 'element';
    this.groupsOpen = {};
    try { this.advanced=localStorage.getItem('desk-display-advanced')==='true'; } catch { this.advanced=false; }
    this.visibilityHandler=()=>{if(!document.hidden && this.isConnected){this.preview(true);this.diagnosticsAt=0;}};
    this.loadDoorbell();
  }
  set hass(value) {
    const previous = this._hass;
    this._hass = value;
    if (this.isConnected && !this.loaded) this.load();
    for (const picker of this.shadowRoot?.querySelectorAll?.('ha-entity-picker,ha-icon-picker') ?? []) picker.hass = value;
    if (this.isConnected && this.loaded && this.layout && previous &&
        this.layout.widgets.some(widget => {
          return [widget.entity_id,widget.value?.fallback_entity_id,widget.visible_when?.entity_id,widget.config?.tariff_entity_id,...Object.values(widget.config??{}).filter(v=>typeof v==='string' && /^[a-z_]+\.[a-z0-9_]+$/.test(v)),...(widget.rules??[]).map(r=>r.when.entity_id)].filter(Boolean).some(entity=>{
            const before=previous.states?.[entity],after=value.states?.[entity];
            return before?.state!==after?.state || JSON.stringify(before?.attributes)!==JSON.stringify(after?.attributes);
          });
        })) this.schedulePreview(true);
  }
  connectedCallback() {
    document.addEventListener('visibilitychange',this.visibilityHandler);
    if (this._hass && !this.loaded) this.load();
    if (this.loaded) this.startVideoPreview();
  }
  disconnectedCallback() {
    document.removeEventListener('visibilitychange',this.visibilityHandler);
    this.previewAgain=false;
    this.previewResize?.disconnect();
    clearInterval(this.videoPreviewTimer);
    this.videoPreviewTimer = null;
    clearTimeout(this.previewTimer);
    this.previewTimer = null;
    ++this.previewSequence;
  }
  async load() {
    this.loaded = true;
    try {
      this.devices = await this._hass.callWS({type: 'desk_display/list'});
      this.layout = structuredClone(this.devices[this.selected]?.layout);
      this.loadDoorbell();
      this.recoveryDraft=this.recoverDraft();
      this.draw();
      if (this.layout) this.preview();
      this.startVideoPreview();
    } catch (error) {
      this.loaded = false;
      this.shadowRoot.textContent = `Desk Display konnte nicht geladen werden: ${error.message ?? error}`;
    }
  }


  copyElements() {
    if(this.overlayPreview)return;this.elementClipboard=structuredClone(this.selectedWidgets());this.status('Elemente kopiert. Auf einer Seite mit Strg+V einfügen.');
  }
  pasteElements() {
    if(this.overlayPreview || !this.elementClipboard?.length)return;
    const copied=structuredClone(this.elementClipboard);
    if(this.layout.widgets.length+copied.length>10 || [...this.layout.widgets,...copied].filter(w=>w.kind==='media').length>1){this.status('Einfügen passt nicht: höchstens zehn Elemente und ein Stream.');return;}
    const groups=new Map();for(const w of copied){w.x=Math.min(480-w.width,Math.round((w.x+8)/8)*8);w.y=Math.min(320-w.height,Math.round((w.y+8)/8)*8);w.locked=false;if(w.group){if(!groups.has(w.group))groups.set(w.group,'paste'+Date.now().toString(36)+groups.size);w.group=groups.get(w.group);}}
    const start=this.layout.widgets.length;this.layout.widgets.push(...copied);this.widgetIndex=start;this.selection=new Set(copied.map((_,i)=>start+i));this.draw();this.schedulePreview();
  }
  setZoom(value) {this.zoom=Math.max(1,Math.min(3,value));this.draw();}
  showDistances(stage,widget) {
    stage.querySelectorAll('.measure').forEach(e=>e.remove());
    const distances=[['Links',widget.x,widget.x/2,widget.y],['Oben',widget.y,widget.x,widget.y/2],['Rechts',480-widget.x-widget.width,widget.x+widget.width+(480-widget.x-widget.width)/2,widget.y],['Unten',320-widget.y-widget.height,widget.x,widget.y+widget.height+(320-widget.y-widget.height)/2]];
    for(const other of this.layout.widgets.filter(w=>!this.selectedWidgets().includes(w))) {
      if(other.y<widget.y+widget.height && other.y+other.height>widget.y){const gap=other.x>=widget.x+widget.width?other.x-widget.x-widget.width:widget.x>=other.x+other.width?widget.x-other.x-other.width:-1;if(gap>=0)distances.push(['Abstand',gap,Math.min(widget.x+widget.width,other.x+other.width)+gap/2,widget.y+widget.height/2]);}
      if(other.x<widget.x+widget.width && other.x+other.width>widget.x){const gap=other.y>=widget.y+widget.height?other.y-widget.y-widget.height:widget.y>=other.y+other.height?widget.y-other.y-other.height:-1;if(gap>=0)distances.push(['Abstand',gap,widget.x+widget.width/2,Math.min(widget.y+widget.height,other.y+other.height)+gap/2]);}
    }
    for(const [label,pixels,x,y] of distances.slice(0,8)){const badge=this.element('span',{class:'measure'},`${label}: ${pixels} px`);Object.assign(badge.style,{left:`${Math.max(0,Math.min(420,x))/4.8}%`,top:`${Math.max(0,Math.min(300,y))/3.2}%`});stage.append(badge);}
  }
  draftKey() {
    const id=this.devices[this.selected]?.id;
    return id&&!this.isOverlayDesigner?`desk-display-draft:${this._hass?.user?.id??'local'}:${id}`:null;
  }
  persistDraft() {
    const key=this.draftKey();if(!key || typeof localStorage==='undefined' || !this.layout)return;
    try {
      if(this.editState()===this.savedSnapshot){localStorage.removeItem(key);return;}
      const draft={version:1,at:Date.now(),base:this.savedSnapshot,state:this.editState()};
      const data=JSON.stringify(draft);if(data.length<1800000)localStorage.setItem(key,data);
    }catch(error){this.draftError=true;}
  }
  recoverDraft() {
    const key=this.draftKey();if(!key || typeof localStorage==='undefined')return null;
    try{const draft=JSON.parse(localStorage.getItem(key));return draft?.version===1 && typeof draft.state==='string' && draft.state!==this.savedSnapshot?draft:null;}catch{return null;}
  }
  async restoreDraft(draft) {
    try {
      const state=JSON.parse(draft.state);
      await this._hass.callWS({type:'desk_display/preview',layout:state.layout,doorbell:state.doorbell,overlay:false});
      this.rootLayout=this.layout=state.layout;this.pageIndex=0;this.doorbell=state.doorbell;this.widgetIndex=0;this.selection=new Set([0]);this.draw();this.preview();
      this.status('Lokaler Entwurf wiederhergestellt. Erst Speichern überträgt ihn.');
    }catch(error){this.status(`Entwurf konnte nicht geladen werden: ${error.message??error}`);}
  }
  inspectLayout() {
    const root=this.documentLayout(),issues=[];
    [root,...(root.pages??[])].forEach((page,pageIndex)=>page.widgets.forEach((w,index)=>{
      const add=(text,error=false)=>issues.push({page:pageIndex,index,text,error});
      if(w.x<0 || w.y<0 || w.x+w.width>480 || w.y+w.height>320)add('Element liegt außerhalb des Displays.',true);
      if(!w.hidden && (root.pages?.length??0)>0 && root.navigation!==false && w.y+w.height>276)add('Element liegt unter der Seitennavigation.');
      if(this._hass?.states && w.entity_id && !this._hass.states[w.entity_id])add('Entität fehlt in Home Assistant.',true);
      if(['sensor','button','switch','progress','gauge','chip','slider','player','weather','countdown','cost'].includes(w.kind) && !w.entity_id)add('Bitte zuerst eine Entität auswählen.',true);
      if(['text','sensor','button','switch'].includes(w.kind) && w.text.length*w.size*.52>w.width-16)add('Beschriftung könnte abgeschnitten werden.');
      if(!w.hidden)for(const other of page.widgets.slice(index+1))if(!other.hidden && Math.min(w.x+w.width,other.x+other.width)>Math.max(w.x,other.x) && Math.min(w.y+w.height,other.y+other.height)>Math.max(w.y,other.y)) {add('Überlappt mit einem weiteren Element. Falls beabsichtigt, ist das in Ordnung.');break;}
    }));return issues;
  }
  async showLayoutIssues() {
    const dialog=this.element('dialog',{class:'add-dialog','aria-label':'Layout prüfen'});dialog.append(this.element('h2',{},'Layout prüfen'));
    let issues=this.inspectLayout();
    try{const measured=await this._hass.callWS({type:'desk_display/inspect',layout:this.documentLayout()});issues=issues.filter(i=>!i.text.includes('Beschriftung könnte'));issues.push(...measured.issues);}catch(error){issues.push({page:0,index:0,text:'Schriftmessung derzeit nicht verfügbar.'});}
    if(!issues.length)dialog.append(this.element('p',{},'Keine Probleme gefunden.'));
    for(const issue of issues){const button=this.element('button',{class:'secondary'},`Seite ${issue.page+1}, Element ${issue.index+1}: ${issue.text}`);button.onclick=()=>{dialog.close();dialog.remove();this.selectPage(issue.page);this.openElementSettings(issue.index);};dialog.append(button);}
    const close=this.element('button',{},'Schließen');close.onclick=()=>{dialog.close();dialog.remove();};dialog.append(close);this.shadowRoot.append(dialog);dialog.showModal();
  }
  async compareDesign() {
    if(!this.savedSnapshot)return;
    const dialog=this.element('dialog',{class:'add-dialog compare-dialog','aria-label':'Design vergleichen'});
    dialog.append(this.element('h2',{},'Gespeichert und Entwurf'));
    const close=this.element('button',{},'Schließen');close.onclick=()=>{dialog.close();dialog.remove();};dialog.append(close);this.shadowRoot.append(dialog);dialog.showModal();
    try {
      const saved=JSON.parse(this.savedSnapshot);
      for(const [title,state] of [['Gespeichert',saved],['Aktueller Entwurf',{layout:this.documentLayout(),doorbell:this.doorbell}]]) {
        const result=await this._hass.callWS({type:'desk_display/preview',layout:state.layout,doorbell:state.doorbell,overlay:this.overlayPreview,page:Math.min(this.pageIndex??0,state.layout.pages?.length??0)});
        dialog.append(this.element('h3',{},title),this.element('img',{alt:title,src:`data:image/png;base64,${result.png}`,style:'width:100%;aspect-ratio:3/2'}));
      }
    }catch(error){dialog.append(this.element('p',{},`Vergleich: ${error.message??error}`));}
  }


  async showRingHistory() {
    const dialog=this.element('dialog',{class:'add-dialog','aria-label':'Klingelverlauf'});dialog.append(this.element('h2',{},'Klingelverlauf'));
    const close=this.element('button',{},'Schließen');close.onclick=()=>{dialog.close();dialog.remove();};dialog.append(close);this.shadowRoot.append(dialog);dialog.showModal();
    try {const result=await this._hass.callWS({type:'desk_display/ringing_history',entry_id:this.devices[this.selected].id});
      if(!result.records?.length)dialog.append(this.element('p',{},'Keine gespeicherten Ereignisse.'));
      for(const record of result.records??[]){const row=this.element('div',{class:'toolbar'});row.append(this.element('span',{},record.label??record.at));if(record.image)row.append(this.element('img',{alt:'Kamerabild beim Klingeln',src:record.image,width:96,height:64}));dialog.append(row);}
      if(result.records?.length){const clear=this.element('button',{class:'secondary'},'Verlauf löschen');clear.onclick=()=>{const confirm=this.element('button',{},'Alle gespeicherten Ereignisse endgültig löschen');confirm.onclick=async()=>{await this._hass.callWS({type:'desk_display/ringing_history',entry_id:this.devices[this.selected].id,clear:true});dialog.close();dialog.remove();this.status('Klingelverlauf gelöscht.');};clear.replaceWith(confirm);};dialog.append(clear);}
    }catch(error){dialog.append(this.element('p',{},`Verlauf: ${error.message??error}`));}
  }

  startVideoPreview() {
    if (this.videoPreviewTimer) return;
    this.videoPreviewTimer = setInterval(() => {
      if (!this.isConnected || document.hidden) return;
      const kinds=this.layout?.widgets.map(w=>w.kind)??[];
      const interval=this.overlayPreview || kinds.includes('media') || kinds.includes('countdown')?1000:kinds.includes('clock')?10000:0;
      if(interval && Date.now()-(this.lastPreviewAt??0)>=interval && !this.previewTimer)this.preview(true);
      if(Date.now()-(this.doorbellStatusAt??0)>=5000){this.doorbellStatusAt=Date.now();this.refreshDoorbellStatus();}
      this.refreshDiagnostics();
    }, 1000);
  }

  async refreshDoorbellStatus() {
    const target=this.shadowRoot.querySelector('#doorbell-ready');
    const device=this.devices[this.selected];
    if (!target || !device || this.doorbellStatusBusy) return;
    if (!this.doorbell.enabled || !this.doorbell.preload) {
      target.textContent='Kameravorbereitung ausgeschaltet. Beim Klingeln muss der Stream erst starten.';
      return;
    }
    const saved=device.doorbell;
    if (!saved?.enabled || !saved.preload || saved.camera!==this.doorbell.camera) {
      target.textContent='Zum Vorbereiten der ausgewählten Kamera speichern.';
      return;
    }
    this.doorbellStatusBusy=true;
    try {
      const result=await this._hass.callWS({type:'desk_display/doorbell_status',entry_id:device.id});
      if (target!==this.shadowRoot.querySelector('#doorbell-ready')) return;
      target.textContent=result.state==='ready' ?
        `Kamera bereit · ${result.mode==='snapshot'?'HA-Kamerabild; Stream startet oder stockt':'Stream'} · vor ${result.age} s empfangen.` :
        result.state==='disabled' ? 'Vorbereitung noch nicht aktiv. Speichern und Verbindung prüfen.' :
        result.message || 'Kamera wird vorbereitet; noch kein aktuelles Bild vorhanden.';
    } catch(error) {target.textContent=`Kamerabereitschaft konnte nicht geprüft werden: ${error.message ?? error}`;}
    finally {this.doorbellStatusBusy=false;}
  }
  async refreshDiagnostics() {
    if(this.diagnosticsBusy || Date.now()-(this.diagnosticsAt??0)<10000 || !this.devices[this.selected])return;
    this.diagnosticsBusy=true;this.diagnosticsAt=Date.now();const device=this.devices[this.selected];
    try {
      const result=await this._hass.callWS({type:'desk_display/diagnostics',entry_id:device.id});
      Object.assign(device,result);
      const diagnostics=this.shadowRoot.querySelector('#diagnostic-details');if(diagnostics)diagnostics.textContent=`WLAN ${result.rssi??'?'} dBm · Speicher ${result.free_heap??'?'} Bytes · Laufzeit ${result.uptime??'?'} s · Neustartgrund ${result.reset_reason??'?'} · Bildaufbau ${result.render_ms??'?'} ms · Übertragung ${result.transfer_ms??'?'} ms / ${result.transfer_bytes??'?'} Bytes · Kameraalter ${result.camera_age??'?'} s`;
      if(device!==this.devices[this.selected])return;
      const target=this.shadowRoot.querySelector('#device-status');
      if(target)target.textContent=`${result.connected?'Verbunden':'Offline'} · Firmware ${result.firmware??'unbekannt'} · letzte Datenbestätigung ${result.age??'?'} s her`;
    }catch(error){const target=this.shadowRoot.querySelector('#device-status');if(target)target.textContent='Verbindungsstatus derzeit nicht verfügbar.';}
    finally{this.diagnosticsBusy=false;}
  }
  supports(minimum) {
    const version=this.devices[this.selected]?.firmware??'';
    const parts=version.split('.').map(Number),required=minimum.split('.').map(Number);
    if(parts.length!==3 || parts.some(v=>!Number.isFinite(v)))return false;
    for(let i=0;i<3;i++){if(parts[i]!==required[i])return parts[i]>required[i];}return true;
  }
  applyCapabilityHints() {
    const requirements=[['Wischen auf freier Fläche','0.8.0'],['Bei Inaktivität','0.9.0'],['Helligkeit bei Inaktivität','0.9.0'],['Nachtmodus','0.6.0'],['Helligkeit (%)','0.6.0'],['Nachthelligkeit','0.6.0'],['Helligkeit beim Klingeln','0.6.0'],['Lange drücken','0.7.0']];
    for(const picker of this.shadowRoot.querySelectorAll('ha-entity-picker')){if(picker.label?.includes('langem Drücken') && !this.supports('0.7.0')){picker.disabled=true;picker.title='Benötigt Firmware 0.7.0';}}
    for(const label of this.shadowRoot.querySelectorAll('label')) {
      const requirement=requirements.find(([text])=>label.textContent.includes(text));
      if(requirement && !this.supports(requirement[1])){for(const input of label.querySelectorAll('input,select'))input.disabled=true;label.title=`Benötigt Firmware ${requirement[1]}`;}
    }
  }
  async fitText() {
    const result=await this._hass.callWS({type:'desk_display/inspect',layout:this.documentLayout()});
    const item=result.sizes.find(i=>i.page===(this.pageIndex??0) && i.index===this.widgetIndex);
    if(!item){this.status('Für dieses Element ist keine automatische Schriftanpassung verfügbar.');return;}
    const widget=this.layout.widgets[this.widgetIndex];widget.size=item.size;
    if(this.documentLayout().design?.size!==undefined)widget.inherit_design=false;
    this.draw();this.schedulePreview();
  }
  chooseTemplate(type) {
    const definitions={energy:[['solar','PV Leistung',['sensor']],['house','Hausverbrauch',['sensor']],['grid','Netzleistung',['sensor']],['battery','Batterieleistung',['sensor']]],status:[['one','Erster Schalter',['switch','input_boolean']],['two','Zweiter Schalter (optional)',['switch','input_boolean']],['three','Dritter Schalter (optional)',['switch','input_boolean']]],camera:[['source','Kamera',['camera']]]};
    const dialog=this.element('dialog',{class:'add-dialog','aria-label':'Vorlage einrichten'}),values={};
    dialog.append(this.element('h2',{},'Entitäten für die Vorlage auswählen'));
    for(const [key,label,domains] of definitions[type]) {
      const picker=this.element('ha-entity-picker');picker.hass=this._hass;picker.label=label;picker.includeDomains=domains;
      const candidates=Object.entries(this._hass.states).filter(([id,state])=>domains.includes(id.split('.')[0]) && (type!=='energy' || ['W','kW'].includes(state.attributes.unit_of_measurement)));
      const hints={solar:/pv|solar|photovoltaik/i,house:/hausverbrauch|house.*consum|load.*power/i,grid:/netz|grid/i,battery:/batter|akku/i};
      const match=type==='energy'?candidates.find(([id,state])=>hints[key].test(id+' '+(state.attributes.friendly_name??''))):candidates.length===1?candidates[0]:null;
      if(match){values[key]=match[0];picker.value=match[0];}
      picker.addEventListener('value-changed',event=>values[key]=event.detail.value??'');dialog.append(picker);
    }
    const error=this.element('p',{role:'status'});dialog.append(error);
    const add=this.element('button',{},'Vorlage hinzufügen');
    add.onclick=()=>{
      const required=type==='energy'?definitions[type].map(d=>d[0]):[definitions[type][0][0]];
      if(required.some(k=>!values[k])){error.textContent='Bitte die benötigten Entitäten auswählen.';return;}
      const widgets=[];const color=this.layout.theme==='material_light'?'#1d1b20':'#e6e0e9';
      const make=(kind,text,entity,x,y,width,height)=>({kind,text,entity_id:entity,x,y,width,height,size:24,color});
      if(type==='energy')widgets.push({...make('energy','Energiefluss','',16,16,448,240),config:{...values}});
      if(type==='camera')widgets.push({...make('media','Kamera','',16,16,this.devices[this.selected].jpeg_regions?448:160,this.devices[this.selected].jpeg_regions?240:120),source:values.source,fps:1});
      if(type==='status')Object.values(values).filter(Boolean).forEach((entity,i)=>widgets.push(make('switch',this._hass.states[entity]?.attributes.friendly_name?.slice(0,80)??entity,entity,16,16+i*68,448,60)));
      if(this.layout.widgets.length+widgets.length>10 || (type==='camera' && this.layout.widgets.some(w=>w.kind==='media'))){error.textContent='Die Vorlage passt nicht auf diese Seite.';return;}
      const group='template'+Date.now().toString(36),index=this.layout.widgets.length;widgets.forEach(w=>w.group=group);this.layout.widgets.push(...widgets);this.widgetIndex=index;this.selection=new Set(widgets.map((_,i)=>index+i));dialog.close();dialog.remove();this.draw();this.schedulePreview();
    };
    const cancel=this.element('button',{class:'secondary'},'Abbrechen');cancel.onclick=()=>{dialog.close();dialog.remove();};dialog.append(add,cancel);this.shadowRoot.append(dialog);dialog.showModal();
  }
  async updateFirmware(file) {
    if(this.updatingFirmware)return;
    if(!file || !file.name.endsWith('.bin') || file.size>1310720){this.status('Passende firmware.bin bis 1,25 MiB auswählen.');return;}
    const deviceId=this.devices[this.selected].id;
    this.updatingFirmware=true;this.status('Firmware wird übertragen. Gerät nicht ausschalten …');
    try {
      const response=await this._hass.fetchWithAuth(`/api/desk_display/${encodeURIComponent(deviceId)}/firmware`,{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:file});
      const result=await response.json();if(!response.ok)throw new Error(result.message??'Update fehlgeschlagen');
      this.status(result.message);this.diagnosticsAt=0;
      const deadline=Date.now()+95000;
      while(this.isConnected && Date.now()<deadline){
        await new Promise(resolve=>setTimeout(resolve,2000));
        const diagnostics=await this._hass.callWS({type:'desk_display/diagnostics',entry_id:deviceId});
        const update=diagnostics.update;
        if(update?.phase==='verified'){this.status(`Update abgeschlossen. Firmware ${update.installed} nach Neustart geprüft.`);await this.load();break;}
        if(update?.phase==='connected_unverified'){this.status(`Display wieder verbunden, Firmware ${update.installed}. Die Datei enthält keine prüfbare Versionskennung.`);break;}
        if(update?.phase==='failed')throw new Error(update.message);
        this.status('Display startet neu. Verbindung und Firmware werden geprüft …');
      }
      if(Date.now()>=deadline)throw new Error('Neustart noch nicht bestätigt. Verbindungsstatus prüfen.');
    }catch(error){this.status('Firmware: '+(error.message??error));}
    finally{this.updatingFirmware=false;}
  }
  async browseMedia(parent, widget, id = null, history = []) {
    let browser = parent.querySelector('.media-browser');
    if (!browser) {browser = this.element('div', {class:'media-browser'}); parent.append(browser);}
    browser.textContent = 'Medien werden geladen …';
    try {
      const item = await this._hass.callWS({type:'desk_display/media_browse',media_content_id:id});
      browser.replaceChildren(this.element('small', {}, item.title));
      if (history.length) {
        const back = this.element('button',{class:'secondary'},'Zurück');
        back.onclick = () => this.browseMedia(parent,widget,history.at(-1),history.slice(0,-1));
        browser.append(back);
      }
      for (const child of item.children ?? []) {
        if (!child.can_expand && !child.can_play) continue;
        const choose = this.element('button',{class:'secondary'}, child.title);
        choose.onclick = () => {
          if (child.can_expand) this.browseMedia(parent,widget,child.media_content_id,[...history,id]);
          else {
            widget.source = child.media_content_id;
            this.draw(); this.schedulePreview();
          }
        };
        browser.append(choose);
      }
      if (!(item.children ?? []).length) browser.append(this.element('small',{},'Keine auswählbaren Videos in diesem Ordner.'));
    } catch(error) {browser.textContent = `Medien: ${error.message ?? error}`;}
  }
  element(tag, attributes = {}, text) {
    const element = document.createElement(tag);
    for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
    if (text !== undefined) element.textContent = text;
    return element;
  }
  loadDoorbell() {
    this.rootLayout=this.layout;this.pageIndex=0;
    this.doorbell = structuredClone(this.devices[this.selected]?.doorbell ??
      {enabled:false,entity_id:'',camera:'',open_entity_id:'',duration:30,preload:false});
    this.doorbell.preload ??= false;
    this.doorbell.post_open_duration ??= 45;
    this.doorbell.door_state_entity_id ??= '';
    this.doorbell.open_enabled ??= true;
    this.doorbell.open_label ??= 'Tuer oeffnen';
    this.overlayPreview = false;
    this.simulation={states:{},door:''};
    this.savedSnapshot=this.editState();
    this.history=[this.savedSnapshot];this.historyIndex=0;
    this.selection=new Set([0]);
  }
  recordEdit() {
    const state=this.editState();
    if (!this.history || state===this.history[this.historyIndex]) return;
    this.history.splice(this.historyIndex+1);this.history.push(state);
    if (this.history.length>40) this.history.shift();
    this.historyIndex=this.history.length-1;this.persistDraft();
  }
  undoEdit(direction=-1) {
    this.recordEdit();
    const target=this.historyIndex+direction;
    if (target<0 || target>=this.history.length) return;
    this.historyIndex=target;
    const state=JSON.parse(this.history[target]);
    this.layout=state.layout;this.doorbell=state.doorbell;
    this.rootLayout=this.layout;this.pageIndex=0;
    this.widgetIndex=Math.min(this.widgetIndex,Math.max(0,this.layout.widgets.length-1));
    this.selection=new Set([this.widgetIndex]);this.draw();this.preview();
  }
  selectedWidgets() {
    const indices=this.selection?.has(this.widgetIndex) ? this.selection : new Set([this.widgetIndex]);
    return this.layout.widgets.filter((w,i)=>indices.has(i));
  }
  moveSelection(dx,dy) {
    const widgets=this.selectedWidgets();if (widgets.some(w=>w.locked))return;if (!widgets.length) return;
    dx=Math.max(-Math.min(...widgets.map(w=>w.x)),Math.min(dx,480-Math.max(...widgets.map(w=>w.x+w.width))));
    dy=Math.max(-Math.min(...widgets.map(w=>w.y)),Math.min(dy,320-Math.max(...widgets.map(w=>w.y+w.height))));
    for (const w of widgets) {w.x+=dx;w.y+=dy;}
  }
  snapPosition(widget,x,y) {
    return [Math.max(0,Math.min(480-widget.width,Math.round(x/8)*8)),Math.max(0,Math.min(320-widget.height,Math.round(y/8)*8))];
  }

  groupSelection(remove=false) {
    const widgets=this.selectedWidgets();
    const group='g'+Date.now().toString(36);
    for (const w of widgets) {if(remove) delete w.group;else w.group=group;}
    this.recordEdit();this.draw();this.schedulePreview();
  }
  showGuides(stage,widget) {
    stage.querySelectorAll('.guide').forEach(line=>line.remove());
    
    this.showDistances(stage,widget);
    const others=this.layout.widgets.filter(w=>!this.selectedWidgets().includes(w));
    for(const [axis,size,bound] of [['x','width',480],['y','height',320]]) {
      const targets=[0,bound/2,bound,...others.flatMap(w=>[w[axis],w[axis]+w[size]/2,w[axis]+w[size]])];
      const edges=[widget[axis],widget[axis]+widget[size]/2,widget[axis]+widget[size]];
      for(const value of new Set(targets.filter(t=>edges.some(e=>Math.abs(e-t)<1)))) {
        const line=this.element('span',{class:`guide ${axis}`});line.style[axis==='x'?'left':'top']=`${value/bound*100}%`;stage.append(line);
      }
    }
  }
  arrangeSelection(axis,distribute=false) {
    const widgets=this.selectedWidgets().sort((a,b)=>a[axis]-b[axis]);
    if(widgets.length<2)return;
    const size=axis==='x'?'width':'height';
    if(distribute && widgets.length>2) {
      const first=widgets[0][axis],last=widgets.at(-1)[axis]+widgets.at(-1)[size];
      const gap=(last-first-widgets.reduce((sum,w)=>sum+w[size],0))/(widgets.length-1);
      let cursor=first;for(const w of widgets){w[axis]=Math.round(cursor);cursor+=w[size]+gap;}
    } else {const anchor=Math.min(widgets[0][axis],(axis==='x'?480:320)-Math.max(...widgets.map(w=>w[size])));for(const w of widgets)w[axis]=anchor;}
    this.recordEdit();this.draw();this.schedulePreview();
  }
  documentLayout() {return this.pageIndex?this.rootLayout:this.layout;}
  editState(layout=this.documentLayout(),doorbell=this.doorbell) {
    return JSON.stringify({layout,doorbell},(key,value)=>
      ['style','value'].includes(key) && value && Object.keys(value).length===0 ? undefined : value);
  }
  updateSaveState() {
    for(const [label,disabled] of [['Rückgängig',!this.historyIndex],['Wiederholen',this.historyIndex>=((this.history?.length??1)-1)]]) {
      const button=this.shadowRoot?.querySelector?.(`button[aria-label="${label}"]`);if(button)button.disabled=disabled||this.overlayPreview;
    }
    const target=this.shadowRoot?.querySelector?.('#save-state');
    if (target) {
      const dirty=this.editState()!==this.savedSnapshot;
      target.textContent=this.saving?'Wird gespeichert …':dirty?'Ungespeicherte Änderungen':'Gespeichert';
      target.dataset.dirty=String(dirty);
    }
    const save=this.shadowRoot?.querySelector?.('#save-layout');
    if (save) save.disabled=!!this.saving;
    const select=this.shadowRoot?.querySelector?.('select[aria-label="Element auswählen"]');
    for (const [index,widget] of (this.layout?.widgets ?? []).entries()) {
      const text=`${widget.locked?'🔒 ':''}${widget.hidden?'◌ ':''}${index+1}. ${this.widgetLabel(widget)}`;
      if (select?.options[index]) select.options[index].textContent=text+(widget.group?` · ${this.groupLabel(widget.group)}`:'');
      const button=this.shadowRoot?.querySelector?.(`.element-strip button[data-index="${index}"]`);
      if (button) {
        button.textContent=text;
        if(widget.group)button.append(this.element('span',{class:'group-badge'},this.groupLabel(widget.group)));
      }
    }
  }
  widgetLabel(widget) {
    return widget.text || widget.entity_id || ({image:'Bild',clock:'Uhrzeit',media:'Video',sensor:'HA-Wert',button:'Button',switch:'Switch',text:'Text'})[widget.kind];
  }
  wrapFields(parent,start,key,title,open=false) {
    const group=this.element('details',{class:'editor-group'});
    group.hidden=!this.advanced && ['globaldesign','simulation','values','rules','arrange'].includes(key);
    group.open=this.groupsOpen[key] ?? open;
    group.append(this.element('summary',{},title));
    const body=this.element('div',{class:'group-body'});
    body.append(...Array.from(parent.childNodes).slice(start));
    group.append(body);parent.append(group);
    group.ontoggle=()=>this.groupsOpen[key]=group.open;
  }
  addWidget(kind) {
    if(this.overlayPreview || this.layout.widgets.length>=10 || !['text','sensor','button','switch','media','image','clock','icon','line','progress','gauge','chip','chart','energy','slider','player','cost','weather','countdown','door_history'].includes(kind))return;
    if(kind==='media' && this.layout.widgets.some(w=>w.kind==='media'))return;
    const names={text:'Neuer Text',sensor:'HA-Wert',button:'Button',switch:'Switch',media:'Video',image:'Bild',clock:'Uhrzeit',icon:'Icon',line:'Trennlinie',progress:'Fortschritt',gauge:'Ringanzeige',chip:'Status',chart:'Verlauf',energy:'Energiefluss',slider:'Slider',player:'Mediensteuerung',cost:'Energiekosten',weather:'Wetter',countdown:'Countdown',door_history:'Klingelverlauf'};
    const sizes={text:[200,48],sensor:[220,48],button:[180,56],switch:[180,56],media:[190,160],image:[120,100],clock:[120,48],icon:[48,48],line:[240,8],progress:[200,64],gauge:[120,120],chip:[160,40],chart:[240,120],energy:[320,200],slider:[240,72],player:[280,144],cost:[220,64],weather:[280,128],countdown:[200,72],door_history:[320,224]};
    let [width,height]=sizes[kind].map(value=>Math.round(value/8)*8);
    if(kind==='media' && !this.devices[this.selected].jpeg_regions){width=160;height=120;}
    const bottom=(this.documentLayout().pages?.length??0) && this.documentLayout().navigation!==false?276:320;
    let position={x:24,y:Math.floor(Math.min(180,bottom-height)/8)*8};
    outer:for(let y=16;y+height<=bottom;y+=8)for(let x=16;x+width<=480;x+=8){
      if(this.layout.widgets.every(w=>x+width<=w.x || x>=w.x+w.width || y+height<=w.y || y>=w.y+w.height)){position={x,y};break outer;}
    }
    const widget={kind,text:names[kind],entity_id:'',...position,width,height,size:24,color:this.layout.theme==='material_light'?'#1d1b20':'#ffffff'};
    if(kind==='clock')widget.clock_format='time';
    if(kind==='media'){widget.source='';widget.fps=1;}
    if(kind==='image')widget.fit='contain';
    if(kind==='icon')widget.icon='mdi:home';
    if(kind==='line')widget.line_width=2;
    this.layout.widgets.push(widget);this.widgetIndex=this.layout.widgets.length-1;this.selection=new Set([this.widgetIndex]);
    this.inspectorTab='element';this.groupsOpen.content=true;
    for(const key of ['arrange','rules','position','appearance'])this.groupsOpen[key]=false;
    this.draw();this.schedulePreview();
    if(kind==='icon')this.updateIcon(widget,'mdi:home');
    this.status('Element hinzugefügt. Inhalt konfigurieren und anschließend speichern.');
  }
  async updateIcon(widget,name) {
    if(!name || !/^[a-z0-9_-]+:[a-z0-9_-]+$/.test(name))return;
    this.iconRequests??=new WeakMap();const token={};this.iconRequests.set(widget,token);
    const icon=this.element('ha-icon');icon.icon=name;icon.hidden=true;this.shadowRoot.append(icon);
    try {
      let svg;
      for(let attempt=0;attempt<40;attempt++) {
        if(this.iconRequests.get(widget)!==token || !this.layout.widgets.includes(widget))return;
        svg=icon.shadowRoot?.querySelector('ha-svg-icon');
        if(svg?.path)break;
        await new Promise(resolve=>setTimeout(resolve,100));
      }
      if(!svg?.path)throw new Error('Icon konnte nicht geladen werden. Bitte erneut auswählen.');
      const box=(svg.viewBox??'0 0 24 24').split(/\s+/).map(Number);
      if(box.length!==4 || !box.every(Number.isFinite) || box[2]<=0 || box[3]<=0)throw new Error('Ungültiges Iconformat');
      const canvas=document.createElement('canvas');canvas.width=128;canvas.height=128;
      const context=canvas.getContext('2d'),scale=128/Math.max(box[2],box[3]);
      context.translate((128-box[2]*scale)/2,(128-box[3]*scale)/2);context.scale(scale,scale);context.translate(-box[0],-box[1]);context.fillStyle='white';
      context.fill(new Path2D(svg.path));
      if(svg.secondaryPath){context.globalAlpha=.5;context.fill(new Path2D(svg.secondaryPath));}
      widget.icon=name;widget.image=canvas.toDataURL('image/png');this.schedulePreview();
    }catch(error){this.status(error.message??String(error));}
    finally{icon.remove();}
  }
  showAddChooser() {
    if(this.overlayPreview || this.layout.widgets.length>=10)return;
    const dialog=this.element('dialog',{class:'add-dialog','aria-labelledby':'add-heading'});
    dialog.append(this.element('h2',{id:'add-heading'},'Was möchtest du hinzufügen?'));
    const grid=this.element('div',{class:'type-grid'});
    const types=[['text','Text','Überschrift oder Beschriftung'],['sensor','HA-Wert','Messwert aus Home Assistant'],['button','Button','HA-Aktion auslösen'],['switch','Switch','Gerät ein- und ausschalten'],['media','Video / Livestream','Kamera oder Medienquelle'],['image','Bild','Eigenes Bild hochladen'],['clock','Uhrzeit / Datum','Zeit aus Home Assistant'],['icon','Icon','Home-Assistant-Icon auswählen'],['line','Trennlinie','Bereiche optisch trennen'],['progress','Fortschritt','Wert als Balken'],['gauge','Ringanzeige','Wert als Ring'],['chip','Status-Chip','Kompakter Gerätestatus'],['chart','Verlauf','Messwerte aus HA-Historie'],['energy','Energiefluss','Solar, Haus, Batterie und Netz'],['slider','Slider','Licht, Lautstärke oder Zahlenwert'],['player','Mediensteuerung','Titel, Cover und Wiedergabe'],['cost','Energiekosten','kWh × Preis oder momentane Kostenrate'],['weather','Wetter','Temperatur, Wetterzeichen und Vorhersage'],['countdown','Timer / Countdown','HA-Timer, Restzeit oder Zieltermin'],['door_history','Klingelverlauf','Letzte Klingelereignisse mit optionalen Bildern']];
    const close=()=>{dialog.close();dialog.remove();this.shadowRoot.querySelector('#add-element')?.focus();};
    for(const [kind,name,description] of types){
      const choice=this.element('button',{class:'type-choice','aria-label':`${name} hinzufügen`});
      choice.append(this.element('strong',{},name),this.element('small',{},description));
      choice.disabled=kind==='media' && this.layout.widgets.some(w=>w.kind==='media');
      if(choice.disabled)choice.append(this.element('small',{},'Bereits ein Videofeld auf dieser Seite'));
      choice.onclick=()=>{close();this.addWidget(kind);};grid.append(choice);
    }
    const cancel=this.element('button',{class:'secondary'},'Abbrechen');cancel.onclick=close;
    dialog.addEventListener('cancel',event=>{event.preventDefault();close();});
    dialog.append(grid,cancel);this.shadowRoot.append(dialog);dialog.showModal();
  }
  conditionSummary(condition) {
    const name=this._hass?.states?.[condition.entity_id]?.attributes?.friendly_name || condition.entity_id || 'Entität auswählen';
    const op={eq:'gleich',ne:'ungleich',gt:'größer als',gte:'mindestens',lt:'kleiner als',lte:'höchstens',missing:'nicht verfügbar'}[condition.op];
    return `Wenn ${name} ${op}${condition.op==='missing'?'':` ${condition.value || '…'}`}`;
  }
  conditionFields(parent,condition,defaultEntity='') {
    const summary=this.element('p',{class:'condition-summary'},this.conditionSummary(condition));
    const update=()=>{summary.textContent=this.conditionSummary(condition);this.schedulePreview();};
    parent.append(summary);
    const picker=this.element('ha-entity-picker');picker.hass=this._hass;picker.label='Andere Entität';picker.value=condition.entity_id;
    if(defaultEntity) {
      const own=this.element('input',{type:'checkbox'});own.checked=condition.entity_id===defaultEntity;picker.hidden=own.checked;
      const label=this.element('label');label.append(own,document.createTextNode('Wert dieses Elements verwenden'));parent.append(label);
      own.onchange=()=>{picker.hidden=own.checked;if(own.checked){condition.entity_id=defaultEntity;picker.value=defaultEntity;}update();};
    }
    picker.addEventListener('value-changed',event=>{condition.entity_id=event.detail.value??'';update();});parent.append(picker);
    const select=this.element('select',{'aria-label':'Vergleich'});
    for(const [value,text] of [['eq','Ist gleich'],['ne','Ist ungleich'],['gt','Größer als'],['gte','Mindestens'],['lt','Kleiner als'],['lte','Höchstens'],['missing','Nicht verfügbar']])select.append(this.element('option',{value},text));
    const label=this.element('label',{},'Wenn der Wert …');label.append(select);parent.append(label);
    const valueBox=this.element('div');parent.append(valueBox);
    this.field(valueBox,'Vergleich mit',condition.value,value=>{condition.value=value;update();});
    valueBox.hidden=condition.op==='missing';
    const hysteresis=this.element('div');parent.append(hysteresis);
    this.field(hysteresis,'Hysterese (Abstand zum Rückschalten)',condition.hysteresis??0,value=>{condition.hysteresis=Number(value);update();},{type:'number',min:0,max:1000000000,step:'any'});
    hysteresis.hidden=!['gt','gte','lt','lte'].includes(condition.op);
    this.field(parent,'Zustand muss so lange bestehen (Sekunden)',condition.delay??0,value=>{condition.delay=Number(value);update();},{type:'number',min:0,max:300});
    select.value=condition.op;select.onchange=()=>{condition.op=select.value;valueBox.hidden=condition.op==='missing';hysteresis.hidden=!['gt','gte','lt','lte'].includes(condition.op);if(hysteresis.hidden)delete condition.hysteresis;update();};
  }
  editDoorbellLayout() {
    const base={background:this.layout.theme==='material_light'?'#fef7ff':'#141218',theme:this.layout.theme??'material_dark',widgets:[
      {kind:'text',text:'Jemand an der Tür',entity_id:'',x:24,y:20,width:432,height:28,size:20,color:'#ffffff',role:'title'},
      {kind:'media',text:'Kamera',entity_id:'',x:24,y:52,width:432,height:this.doorbell.open_enabled?180:240,size:20,color:'#ffffff',source:this.doorbell.camera,fps:1}
    ]};
    if(this.doorbell.open_enabled)base.widgets.push({kind:'button',text:this.doorbell.open_label,entity_id:this.doorbell.open_entity_id,x:24,y:244,width:432,height:48,size:24,color:'#ffffff',role:'door_open'});
    if(!this.doorbell.camera || (this.doorbell.open_enabled && !this.doorbell.open_entity_id)){this.status('Zuerst Kamera und optionalen Türöffner auswählen.');return;}
    const dialog=this.element('dialog',{class:'overlay-designer','aria-label':'Klingel-Layout bearbeiten'});
    const close=this.element('button',{class:'secondary'},'Zurück ohne Übernehmen');close.onclick=()=>{dialog.close();dialog.remove();};dialog.append(close);
    const child=this.element('desk-display-panel');child.isOverlayDesigner=true;child.loaded=true;child.devices=[{...this.devices[this.selected],layout:structuredClone(this.doorbell.layout??base),ota_update:false,backups:[]}];child.layout=child.devices[0].layout;child.loadDoorbell();
    child._hass={states:this._hass.states,callWS:async message=>{
      if(['desk_display/save','desk_display/preview'].includes(message.type)) {
        const camera=message.layout.widgets.find(w=>w.kind==='media'),opener=message.layout.widgets.find(w=>w.role==='door_open');
        const bell={...this.doorbell,layout:message.layout,camera:camera?.source??this.doorbell.camera};
        if(opener){bell.open_label=opener.text;bell.open_entity_id=opener.entity_id;}
        const result=await this._hass.callWS({...message,type:'desk_display/preview',entry_id:this.devices[this.selected]?.id,layout:this.documentLayout(),doorbell:bell,overlay:true,page:this.pageIndex??0});
        if(message.type==='desk_display/preview')return result;
        this.doorbell=structuredClone(bell);dialog.close();dialog.remove();this.draw();this.preview();this.status('Klingel-Layout gespeichert im Entwurf. Zum Display bitte speichern und übertragen.');return {sent:false,backups:[]};
      }
      return this._hass.callWS(message);
    }};
    child.draw();dialog.append(child);this.shadowRoot.append(dialog);dialog.showModal();child.preview();
  }
  openElementSettings(index) {
    this.selectWidget(index);this.groupsOpen.content=true;this.groupsOpen.arrange=false;this.draw();this.switchInspectorTab('element',true);
    this.shadowRoot.querySelector('[data-pane=element] input[maxlength="80"]')?.focus();
  }
  elementMenu(index) {
    this.selectWidget(index);
    const widget=this.layout.widgets[index],dialog=this.element('dialog',{class:'add-dialog','aria-label':'Elementaktionen'});
    dialog.append(this.element('h2',{},this.widgetLabel(widget)));
    const close=()=>{dialog.close();dialog.remove();};
    for(const [label,action] of [['Inhalt bearbeiten',()=>this.openElementSettings(index)],['Duplizieren',()=>this.duplicateSelected()],[widget.locked?'Entsperren':'Position sperren',()=>{widget.locked=!widget.locked;this.draw();this.schedulePreview();}],[widget.hidden?'Einblenden':'Ausblenden',()=>{widget.hidden=!widget.hidden;this.draw();this.schedulePreview();}],['Löschen',()=>this.removeSelected()],['Abbrechen',()=>{}]]) {
      const button=this.element('button',{class:'secondary'},label);button.onclick=()=>{close();action();};dialog.append(button);
    }
    this.shadowRoot.append(dialog);dialog.showModal();
  }
  exportTheme() {
    const root=this.documentLayout(),data={format:'desk-display-theme',version:1,design:root.design??{},theme:root.theme??'material_dark',background:root.background};
    const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const link=this.element('a',{href:url,download:'desk-display-theme.json'});link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  exportDesign(components=false) {
    const data=components?{format:'desk-display-components',version:1,widgets:this.selectedWidgets()}:
      {format:'desk-display-layout',version:1,layout:this.documentLayout(),doorbell:this.doorbell};
    const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
    const link=this.element('a',{href:url,download:components?'desk-display-components.json':'desk-display-layout.json'});
    link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  async importDesign(file) {
    if(!file || file.size>1500000){this.status('Layout-Datei maximal 1,5 MB.');return;}
    try {
      const data=JSON.parse(await file.text());let layout,doorbell;
      if(data.version!==1)throw new Error('Unbekannte Dateiversion.');
      if(data.format==='desk-display-components') {layout=structuredClone(this.documentLayout());const page=this.pageIndex?layout.pages[this.pageIndex-1]:layout;page.widgets.push(...data.widgets);doorbell=this.doorbell;}
      else if(data.format==='desk-display-theme'){layout=structuredClone(this.documentLayout());layout.design=data.design;for(const page of [layout,...(layout.pages??[])]){page.theme=data.theme;page.background=data.background;}doorbell=this.doorbell;}
      else if(data.format==='desk-display-layout'){layout=data.layout;doorbell=data.doorbell;}
      else throw new Error('Keine Desk-Display-Datei.');
      await this._hass.callWS({type:'desk_display/preview',layout,doorbell,overlay:false});
      this.layout=layout;this.doorbell=doorbell;this.widgetIndex=0;this.selection=new Set([0]);
      this.rootLayout=layout;this.pageIndex=0;
      this.draw();this.preview();this.status('Import geprüft. Zum Übertragen speichern.');
    }catch(error){this.status('Import: '+(error.message??error));}
  }
  selectPage(index) {
    const root=this.documentLayout();this.pageIndex=index;this.layout=index?root.pages[index-1]:root;
    this.widgetIndex=0;this.selection=new Set([0]);this.draw();this.preview();
  }
  addPage() {
    const root=this.documentLayout();if((root.pages?.length??0)>=3)return;
    root.page_name??='Übersicht';
    const page={background:this.layout.background,theme:this.layout.theme==='material_light'?'material_light':'material_dark',widgets:[],page_name:`Seite ${(root.pages?.length??0)+2}`};
    (root.pages??=[]).push(page);this.selectPage(root.pages.length);
  }
  addTemplate(type) {
    const states=this._hass?.states??{};
    const make=(kind,text,entity,x,y,width,height,size=24)=>({kind,text,entity_id:entity,x,y,width,height,size,color:this.layout.theme==='material_light'?'#1d1b20':'#e6e0e9'});
    const sensors=Object.keys(states).filter(e=>e.startsWith('sensor.')).sort();let widgets=[];
    if(type==='energy' || type==='status' || type==='camera')return this.chooseTemplate(type);
    if(type==='energy')widgets=sensors.slice(0,3).map((e,i)=>make('sensor',states[e].attributes.friendly_name?.slice(0,80)??e,e,16,16+i*68,448,60));
    if(type==='clock')widgets=[{...make('clock','Uhrzeit','',16,16,448,72,48),clock_format:'time'},{...make('clock','Datum','',16,92,448,40,20),clock_format:'date'}];
    if(type==='status')widgets=Object.keys(states).filter(e=>e.startsWith('switch.')||e.startsWith('input_boolean.')).sort().slice(0,3).map((e,i)=>make('switch',states[e].attributes.friendly_name?.slice(0,80)??e,e,16,16+i*68,448,60));
    if(type==='camera') {const camera=Object.keys(states).find(e=>e.startsWith('camera.'));if(camera)widgets=[{...make('media','','',16,16,448,248),source:camera,fps:1}];}
    if(!widgets.length){this.status('Keine passenden HA-Entitäten gefunden.');return;}
    if(this.layout.widgets.length+widgets.length>10 || (widgets.some(w=>w.kind==='media')&&this.layout.widgets.some(w=>w.kind==='media'))){this.status('Vorlage passt nicht: maximal zehn Elemente und ein Video je Seite.');return;}
    const group='t'+Date.now().toString(36);widgets.forEach(w=>w.group=group);this.layout.widgets.push(...widgets);
    this.widgetIndex=this.layout.widgets.length-widgets.length;this.selection=new Set(widgets.map(w=>this.layout.widgets.indexOf(w)));this.draw();this.schedulePreview();
  }
  switchInspectorTab(tab,activatePreview=false) {
    if (!['element','pages','display','doorbell'].includes(tab)) return;
    this.inspectorTab=tab;
    if(activatePreview && this.overlayPreview!==(tab==='doorbell')) {
      this.overlayPreview=tab==='doorbell';this.draw();this.preview();return;
    }
    for (const panel of this.shadowRoot.querySelectorAll('[data-pane]')) panel.hidden=panel.dataset.pane!==tab;
    for (const button of this.shadowRoot.querySelectorAll('[data-tab]')) button.setAttribute('aria-selected',String(button.dataset.tab===tab));
    const scroll=this.shadowRoot.querySelector('.inspector-scroll');
    if (scroll) scroll.scrollTop=0;
  }
  selectWidget(index,multiple=false) {
    if (!this.layout.widgets[index]) return;
    if (!multiple) this.selection=new Set();
    const group=this.layout.widgets[index].group;
    const members=this.layout.widgets.map((w,i)=>i).filter(i=>i===index || (group && this.layout.widgets[i].group===group));
    const remove=multiple && this.selection.has(index);
    for(const i of members){if(remove)this.selection.delete(i);else this.selection.add(i);}
    this.widgetIndex=index;this.inspectorTab='element';this.draw();
  }
  nudgeSelected(dx,dy,step=1) {
    const widget=this.layout.widgets[this.widgetIndex];
    if (this.overlayPreview || !widget) return;
    this.moveSelection(dx*step,dy*step);
  }
  status(message) {
    this.recordEdit();
    this.shadowRoot.querySelector('#status').textContent = message;
    this.updateSaveState();
  }
  field(parent, title, value, change, options = {}) {
    const label = this.element('label', {}, title);
    const input = this.element('input', {type: options.type ?? 'text', ...options});
    input.value = value;
    input.addEventListener('input', () => { change(input.value); this.schedulePreview(); });
    label.append(input); parent.append(label);
    return input;
  }
  removeSelected() {
    if (!this.layout.widgets[this.widgetIndex]) return;
    const selected=this.selectedWidgets();this.layout.widgets=this.layout.widgets.filter(w=>!selected.includes(w));
    this.widgetIndex = Math.max(0, Math.min(this.widgetIndex, this.layout.widgets.length - 1));
    this.selection=new Set([this.widgetIndex]);
    this.draw();
    this.preview();
  }
  applyTheme(theme) {
    const light = theme === 'material_light';
    this.layout.theme = theme;
    this.layout.background = light ? '#fef7ff' : theme === 'classic' ? '#101827' : '#141218';
    for (const widget of this.layout.widgets) {
      widget.color = widget.kind === 'button' ? '#ffffff' : light ? '#1d1b20' : '#e6e0e9';
    }
    this.draw(); this.schedulePreview();
  }
  duplicateSelected() {
    const selected = this.layout.widgets[this.widgetIndex];
    if (this.overlayPreview || !selected || selected.kind === 'media' || this.layout.widgets.length >= 10) return;
    const copy = structuredClone(selected);
    copy.x = Math.min(480-copy.width, copy.x+12);
    copy.y = Math.min(320-copy.height, copy.y+12);
    this.layout.widgets.splice(this.widgetIndex+1, 0, copy);
    ++this.widgetIndex;this.selection=new Set([this.widgetIndex]);
    this.draw(); this.schedulePreview();
  }
  moveSelectedLayer(direction) {
    if (this.overlayPreview || ![-1,1].includes(direction)) return;
    const widgets = this.layout.widgets;
    const target = this.widgetIndex+direction;
    if (!widgets[this.widgetIndex] || target<0 || target>=widgets.length) return;
    [widgets[this.widgetIndex], widgets[target]] = [widgets[target], widgets[this.widgetIndex]];
    this.widgetIndex=target;
    this.draw(); this.schedulePreview();
  }
  alignSelected(alignment) {
    const widget=this.layout.widgets[this.widgetIndex];
    if (this.overlayPreview || !widget) return;
    const positions={left:['x',0],center:['x',Math.round((480-widget.width)/2)],right:['x',480-widget.width],
      top:['y',0],middle:['y',Math.round((320-widget.height)/2)],bottom:['y',320-widget.height]};
    if (!positions[alignment]) return;
    const [axis,value]=positions[alignment];widget[axis]=value;
    this.draw(); this.schedulePreview();
  }
  async uploadPicture(file, widget) {
    if (!file || file.size>5000000 || !['image/png','image/jpeg','image/webp'].includes(file.type)) {
      this.status('Bitte PNG, JPEG oder WebP bis 5 MB auswählen.');return;
    }
    try {
      const url=URL.createObjectURL(file);
      const image=new Image();
      try {image.src=url;await image.decode();} finally {URL.revokeObjectURL(url);}
      if (image.naturalWidth*image.naturalHeight>20000000) throw new Error('Bild ist zu groß.');
      const canvas=document.createElement('canvas');
      let scale=Math.min(1,480/image.naturalWidth,320/image.naturalHeight),source;
      for (let attempt=0;attempt<5;attempt++) {
        canvas.width=Math.max(1,Math.round(image.naturalWidth*scale));
        canvas.height=Math.max(1,Math.round(image.naturalHeight*scale));
        canvas.getContext('2d').drawImage(image,0,0,canvas.width,canvas.height);
        source=canvas.toDataURL('image/png');
        if (source.length<=133358) break;
        scale*=.75;
      }
      if (source.length>133358) throw new Error('Bild lässt sich nicht ausreichend verkleinern.');
      if (!this.layout.widgets.includes(widget)) return;
      widget.image=source;widget.fit ??= 'contain';
      this.draw();this.schedulePreview();this.status('Bild vorbereitet. Zum Übertragen speichern.');
    } catch(error) {this.status('Bild: '+(error.message ?? error));}
  }
  async saveLayout() {
    if (this.saving || !this.devices[this.selected]) return;
    clearTimeout(this.previewTimer);
    this.previewTimer = null;
    ++this.previewSequence;
    const deviceIndex = this.selected;
    const savedLayout = structuredClone(this.documentLayout());
    const savedPage=this.pageIndex??0;
    const savedSimulation=structuredClone(this.simulation);
    const savedDoorbell = structuredClone(this.doorbell);
    this.saving=true; this.status('Wird gespeichert und übertragen …');
    try {
      const result = await this._hass.callWS({type:'desk_display/save',entry_id:this.devices[deviceIndex].id,layout:savedLayout,doorbell:savedDoorbell,page:savedPage});
      this.devices[deviceIndex].layout = savedLayout;
      this.devices[deviceIndex].doorbell = savedDoorbell;
      this.devices[deviceIndex].backups=result.backups??this.devices[deviceIndex].backups;
      if (deviceIndex===this.selected) this.savedSnapshot=this.editState(savedLayout,savedDoorbell);
      if(deviceIndex===this.selected && savedPage===(this.pageIndex??0) && JSON.stringify(savedSimulation)===JSON.stringify(this.simulation) && this.editState()===this.editState(savedLayout,savedDoorbell))await this.preview(true);
      if (deviceIndex===this.selected) this.status(result.sent ? 'Gespeichert und vom Display bestätigt.' : 'Gespeichert. Display offline oder Übertragung fehlgeschlagen; HA versucht es erneut.');
    } catch (error) { if (deviceIndex===this.selected) this.status(`Fehler: ${error.message ?? error}`); }
    finally { this.saving=false;this.persistDraft();this.updateSaveState(); }
  }
  draw() {
    this.recordEdit();
    this.previewResize?.disconnect();
    this.shadowRoot.replaceChildren();
    this.shadowRoot.append(this.element('style', {}, `
      :host{display:block;color:var(--primary-text-color,#172033);font:15px system-ui}
      *{box-sizing:border-box}[hidden]{display:none!important}
      .overlay-designer{width:calc(100vw - 24px);max-width:1500px;height:calc(100dvh - 24px);padding:0;border-radius:16px;border:1px solid #777}
      main{padding:16px;max-width:1500px;margin:auto;height:calc(100dvh - ${this.isOverlayDesigner?110:56}px);min-height:380px;display:flex;flex-direction:column;gap:12px;overflow:hidden}
      .workspace-header{display:flex;flex-wrap:wrap;gap:8px 24px;align-items:center;flex:none}.workspace-header h1{font-size:22px;margin:0;white-space:nowrap}
      #device-status{flex-basis:100%;font-size:12px;margin:0}
      .workspace-header select{min-width:0;flex:1;margin:0}
      h1{font-size:26px;margin:0 0 8px}p{line-height:1.5;color:var(--secondary-text-color,#64748b)}
      .columns{display:grid;grid-template-columns:minmax(0,1fr) 380px;gap:16px;flex:1;min-height:0}
      .canvas{min-width:0;min-height:0;display:flex;flex-direction:column;gap:10px}
      .preview-well{overflow:auto;align-items:safe center!important;justify-content:safe center!important;flex:1;min-height:0;display:flex;align-items:center;justify-content:center}
      .toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:6px;flex:none}.toolbar button{margin:0}
      #save-layout{margin-left:auto}.save-state{font-size:12px;white-space:nowrap;color:var(--secondary-text-color,#64748b)}
      .save-state[data-dirty=true]{color:#d97706}
      .inspector{display:flex;flex-direction:column;min-height:0;padding:0;overflow:hidden}
      .inspector-tabs{display:flex;padding:12px;gap:4px;border-bottom:1px solid var(--divider-color,#ddd);flex:none}
      .inspector-tabs button{flex:1;background:transparent;color:inherit;margin:0;border-radius:10px}
      .inspector-tabs button[aria-selected=true]{background:#6750a4;color:white}
      .inspector-scroll{overflow:auto;min-height:0;padding:16px;overscroll-behavior:contain;scrollbar-gutter:stable}
      .rule-card{border:1px solid var(--divider-color,#ddd);border-radius:12px;padding:12px;margin:12px 0;background:var(--secondary-background-color,#f3edf7)}
      .condition-summary{font-size:13px;line-height:1.5;margin:8px 0;color:var(--primary-text-color,#1f2937);overflow-wrap:anywhere}
      .rule-result{display:block;margin-top:12px}.rule-card label{margin:10px 0}
      .editor-group{border-top:1px solid var(--divider-color,#ddd);margin-top:12px}
      .add-dialog{box-sizing:border-box;width:min(560px,calc(100vw - 32px));max-height:calc(100dvh - 48px);overflow:auto;border:1px solid var(--divider-color,#ddd);border-radius:20px;padding:20px;background:var(--card-background-color,#fff);color:var(--primary-text-color,#1f2937)}
      .add-dialog::backdrop{background:#0008}.add-dialog h2{margin:0 0 16px;font-size:20px}
      .type-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-bottom:12px}
      .type-choice{text-align:left;margin:0;background:var(--secondary-background-color,#e7e0ec);color:inherit;min-height:76px;border:1px solid var(--divider-color,#ddd)}
      .type-choice small{font-size:12px;line-height:1.4}.type-choice:hover:enabled,.type-choice:focus-visible{outline:2px solid #6750a4}
      summary{cursor:pointer;font-weight:600;padding:12px 0}.group-body{padding-bottom:6px}
      .element-strip{display:flex;gap:6px;overflow:auto;flex:none;padding-bottom:2px}
      .element-strip button{white-space:nowrap;font-size:12px;margin:0;background:var(--secondary-background-color,#e7e0ec);color:inherit;padding:7px 10px}
      .widget-strip{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));grid-template-rows:repeat(2,32px);height:70px;overflow:hidden;box-sizing:border-box}
      .widget-strip button{min-width:0;overflow:hidden;text-overflow:ellipsis;padding:5px;font-size:11px}
      .element-strip button[aria-pressed=true]{background:#6750a4;color:white}
      section{background:var(--card-background-color,#fff);border:1px solid var(--divider-color,#ddd);border-radius:20px;padding:20px}
      label{display:block;margin:12px 0}input,select,button{font:inherit;border:1px solid #94a3b8;border-radius:6px;padding:9px}
      input[type=checkbox]{width:auto;margin-right:8px}
      input,select{width:100%;background:var(--card-background-color,#fff);color:inherit;margin-top:5px}
      button{cursor:pointer;background:#2563eb;color:#fff;border:0;margin:5px 8px 5px 0}
      button.secondary{background:#475569}button:disabled{opacity:.5;cursor:wait}
      .measure{position:absolute;z-index:6;background:#fbbf24;color:#1f2937;padding:2px;font-size:11px;pointer-events:none}.stage{flex:none;position:relative;width:100%;aspect-ratio:3/2;background:#101827;border-radius:8px;overflow:hidden;touch-action:none}
      .stage img{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
      .stage[data-snap=true]:after{content:'';position:absolute;inset:0;pointer-events:none;background-image:linear-gradient(to right,#ffffff18 1px,transparent 1px),linear-gradient(to bottom,#ffffff18 1px,transparent 1px);background-size:1.6667% 2.5%;z-index:1}
      .guide{position:absolute;background:#fbbf24;z-index:4;pointer-events:none}.guide.x{top:0;bottom:0;width:1px}.guide.y{left:0;right:0;height:1px}
      .hit{position:absolute;border:1px dashed #94a3b8;cursor:move;background:transparent;padding:0;margin:0;touch-action:none}
      .hit.active{border:2px solid #57d9b0}.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
      .resize{position:absolute;right:0;bottom:0;z-index:5;width:18px;height:18px;background:#57d9b0;border:2px solid white;cursor:nwse-resize}
      .resize.width{top:50%;bottom:auto;transform:translateY(-50%);width:10px;height:26px;cursor:ew-resize}
      .resize.height{left:50%;right:auto;transform:translateX(-50%);width:26px;height:10px;cursor:ns-resize}
      .group-outline{position:absolute;border:2px dashed #fbbf24;border-radius:5px;pointer-events:none;z-index:2}
      .group-label{position:absolute;left:0;top:0;background:#fbbf24;color:#1f2937;font-size:10px;line-height:14px;padding:0 3px;border-radius:0 0 3px 0}
      .group-badge{margin-left:6px;border-radius:4px;padding:1px 4px;background:#fbbf24;color:#1f2937;font-size:10px}
      #status{min-height:20px;margin:0;font-size:13px}small{display:block;margin-top:8px;color:var(--secondary-text-color,#64748b)}
      .canvas small{font-size:12px;margin:0}
      @media(max-width:800px){main{padding:10px;gap:8px}.workspace-header{gap:10px}.workspace-header h1{font-size:18px}
        .columns{grid-template-columns:minmax(0,1fr);grid-template-rows:minmax(360px,55%) minmax(0,1fr);gap:10px}
        .canvas{padding:10px;gap:6px}.canvas .canvas-meta{display:none}.toolbar button{font-size:12px;padding:8px}
        .element-strip button{padding:5px 8px}.save-state{font-size:11px}.inspector-scroll{padding:12px}}
    `));
    const main = this.element('main');
    const header=this.element('header',{class:'workspace-header'});
    header.append(this.element('h1',{},'Desk Display'));main.append(header);
    this.shadowRoot.append(main);
    if (!this.devices.length) {
      main.append(this.element('section', {}, 'Noch kein Display eingerichtet. Füge Desk Display unter Einstellungen → Geräte & Dienste hinzu.'));
      return;
    }
    const deviceSelect = this.element('select', {'aria-label': 'Display'});
    this.devices.forEach((device, index) => {
      const option = this.element('option', {value: index}, `${device.name} · ${device.host}${device.connected ? '' : ' · offline'}`);
      deviceSelect.append(option);
    });
    deviceSelect.value = this.selected;
    deviceSelect.onchange = () => {
      this.persistDraft();++this.previewSequence;this.pageIndex=0;this.rootLayout=null;this.undoStack=[];this.redoStack=[];
      this.selected = Number(deviceSelect.value); this.widgetIndex = 0;this.diagnosticsAt=0;
      this.layout = structuredClone(this.devices[this.selected].layout); this.loadDoorbell(); this.draw(); this.preview();
    };
    header.append(deviceSelect);
    const advanced=this.element('button',{class:'secondary','aria-pressed':String(this.advanced)},this.advanced?'Erweiterte Ansicht':'Einfache Ansicht');
    advanced.onclick=()=>{this.advanced=!this.advanced;try{localStorage.setItem('desk-display-advanced',String(this.advanced));}catch{}this.draw();};header.append(advanced);
    header.append(this.element('small',{id:'device-status',role:'status'},`${this.devices[this.selected].connected?'Verbunden':'Offline'} · Firmware ${this.devices[this.selected].firmware??'unbekannt'}`));
    if(this.recoveryDraft){const banner=this.element('div',{class:'toolbar'});banner.append(this.element('small',{},this.recoveryDraft.base!==this.savedSnapshot?'Lokaler Entwurf gefunden; das gespeicherte Design hat sich inzwischen geändert.':'Ungespeicherter lokaler Entwurf gefunden.'));const restore=this.element('button',{},'Entwurf wiederherstellen');restore.onclick=()=>{const draft=this.recoveryDraft;this.recoveryDraft=null;this.restoreDraft(draft);};const discard=this.element('button',{class:'secondary'},'Entwurf verwerfen');discard.onclick=()=>{localStorage.removeItem(this.draftKey());this.recoveryDraft=null;this.draw();};banner.append(restore,discard);header.append(banner);}
    const bellSection=this.element('div',{'data-pane':'doorbell',role:'tabpanel'});
    const bellSettings=this.element('div');
    const enabled=this.element('input',{type:'checkbox','aria-label':'Klingel-Overlay aktivieren'});
    enabled.checked=!!this.doorbell.enabled;
    enabled.onchange=()=>{this.doorbell.enabled=enabled.checked;this.status('Klingel-Overlay geändert. Zum Übertragen speichern.');};
    const enabledLabel=this.element('label');enabledLabel.append(enabled,document.createTextNode('Klingel-Overlay aktivieren'));
    bellSettings.append(enabledLabel,this.element('small',{},'Beim Klingeln erscheint die Kamera über der normalen Anzeige. Ein optionaler Türknopf öffnet nur durch Antippen. Wiederholtes Klingeln verlängert die Zeit. Die Vorschau führt keine Türaktion aus.'));
    const openEnabled=this.element('input',{type:'checkbox','aria-label':'Türöffner anzeigen'});openEnabled.checked=this.doorbell.open_enabled;
    openEnabled.onchange=()=>{this.doorbell.open_enabled=openEnabled.checked;this.draw();this.schedulePreview();};
    const openLabel=this.element('label');openLabel.append(openEnabled,document.createTextNode('Türöffner anzeigen'));bellSettings.append(openLabel);
    if(this.doorbell.open_enabled)this.field(bellSettings,'Beschriftung des Türknopfs',this.doorbell.open_label,value=>this.doorbell.open_label=value,{maxlength:80});
    for (const [key,label,domains] of [
      ['entity_id','Klingel-Auslöser',['binary_sensor','event','input_button']],
      ['camera','Overlay-Kamera',['camera']],
      ['open_entity_id','Türöffner / Nuki-Schloss',['button','input_button','script','lock']],
      ['door_state_entity_id','Türkontakt (optional)',['binary_sensor']]]) {
      if(key==='open_entity_id' && !this.doorbell.open_enabled)continue;
      const picker=this.element('ha-entity-picker');picker.hass=this._hass;
      picker.label=label;picker.includeDomains=domains;picker.value=this.doorbell[key];
      picker.addEventListener('value-changed',event=>{this.doorbell[key]=event.detail.value ?? '';this.schedulePreview();});
      bellSettings.append(picker);
    }
    if(this.doorbell.open_enabled)bellSettings.append(this.element('small',{},'Bei einem Schloss wird die Aktion „Tür öffnen“ ausgeführt. Das Schloss muss diese Aktion ohne PIN unterstützen; sonst ein HA-Skript verwenden.'));
    const preload=this.element('input',{type:'checkbox','aria-label':'Overlay-Kamera vorbereiten'});
    preload.checked=!!this.doorbell.preload;
    preload.onchange=()=>{this.doorbell.preload=preload.checked;this.status('Kameravorbereitung geändert. Zum Übertragen speichern.');};
    const preloadLabel=this.element('label');
    preloadLabel.append(preload,document.createTextNode('Overlay-Kamera vorbereiten'));
    bellSettings.append(preloadLabel,this.element('small',{},'Hält auf dem HA-Rechner ein aktuelles Kamerabild bereit, damit es beim Klingeln schneller erscheint. Zusätzliche Kamera-Verbindung und HA-Rechenlast; das Display bleibt bei höchstens 1 FPS. Nach dem Speichern kurz auf den Kamerastart warten.'));
    bellSettings.append(this.element('small',{id:'doorbell-ready',role:'status'},'Kamerabereitschaft wird geprüft …'));
    this.field(bellSettings,'Automatisch schließen nach (Sekunden)',this.doorbell.duration,
      value=>this.doorbell.duration=Number(value),{type:'number',min:5,max:300,step:1});
    if(this.doorbell.open_enabled)this.field(bellSettings,'Nach Türaktion mindestens weiter anzeigen (Sekunden)',this.doorbell.post_open_duration,
      value=>this.doorbell.post_open_duration=Number(value),{type:'number',min:5,max:300,step:1});
    if(this.doorbell.open_enabled)bellSettings.append(this.element('small',{},'Der Türknopf zeigt Verarbeitung, ausgeführten Befehl oder Fehler. Nur ein Türkontakt (Ein = offen) bestätigt die physisch offene Tür; entriegelt beschreibt den Schlosszustand. Die Ansicht bleibt nach der Aktion standardmäßig noch 45 Sekunden offen.'));
    const test=this.element('button',{class:'secondary'},'Overlay am Display testen');
    const close=this.element('button',{class:'secondary'},'Overlay am Display schließen');
    const testOverlay=async active=>{
      try {
        const result=await this._hass.callWS({type:'desk_display/doorbell_test',entry_id:this.devices[this.selected].id,active});
        this.status(result.sent?'Overlay-Ansicht vom Display bestätigt.':'Ansicht geändert. Display offline oder Übertragung fehlgeschlagen.');
      } catch(error) {this.status(`Overlay: ${error.message ?? error}`);}
    };
    test.onclick=()=>testOverlay(true);close.onclick=()=>testOverlay(false);
    bellSettings.append(test,close,this.element('small',{},'Vor dem Gerätetest aktivieren und speichern. Die Vorschau öffnet keine Tür. Binary-Sensoren lösen beim Wechsel Aus → Ein aus; Ereignis-Entitäten bei einem neuen Zeitstempel.'));
    const editBell=this.element('button',{class:'secondary'},'Klingel-Layout bearbeiten');editBell.onclick=()=>this.editDoorbellLayout();bellSettings.append(editBell,this.element('small',{},'Kamera, Titel, Türstatus und zusätzliche Aktionen frei anordnen. Im Layouteditor unter Inhalt die Klingelrolle festlegen. Änderungen werden erst mit Speichern & übertragen aktiv.'));
    const resetBell=this.element('button',{class:'secondary'},'Standard-Klingel-Layout wiederherstellen');resetBell.onclick=()=>{delete this.doorbell.layout;this.draw();this.schedulePreview();};bellSettings.append(resetBell);

    const historyEnabled=this.element('input',{type:'checkbox','aria-label':'Klingelverlauf speichern'});historyEnabled.checked=!!this.doorbell.history_enabled;
    historyEnabled.onchange=()=>{this.doorbell.history_enabled=historyEnabled.checked;this.draw();this.schedulePreview();};const historyLabel=this.element('label');historyLabel.append(historyEnabled,document.createTextNode('Klingelverlauf speichern'));bellSettings.append(historyLabel);
    bellSettings.append(this.element('small',{},'Standardmäßig aus. Speichert bis 20 echte Klingelereignisse lokal in HA. Gerätetests werden nicht erfasst. Ausschalten und Speichern löscht den Verlauf.'));
    if(this.doorbell.history_enabled){this.field(bellSettings,'Aufbewahrung in Tagen',this.doorbell.history_days??7,v=>this.doorbell.history_days=Number(v),{type:'number',min:1,max:30,step:1});const images=this.element('input',{type:'checkbox','aria-label':'Vorschaubilder speichern'});images.checked=!!this.doorbell.history_images;images.onchange=()=>{this.doorbell.history_images=images.checked;this.schedulePreview();};const label=this.element('label');label.append(images,document.createTextNode('Vorschaubilder speichern'));bellSettings.append(label,this.element('small',{},'Nur ein frisches, bereits vorbereitetes Kamerabild wird gespeichert. Ohne solches Bild bleibt nur die Uhrzeit. Ausschalten und Speichern entfernt vorhandene Bilder.'));}
    const historyView=this.element('button',{class:'secondary'},'Klingelverlauf ansehen');historyView.onclick=()=>this.showRingHistory();bellSettings.append(historyView);
    bellSection.append(bellSettings);
    const columns = this.element('div', {class: 'columns'});
    const canvasSection = this.element('section',{class:'canvas'});
    const pageStrip=this.element('div',{class:'element-strip','aria-label':'Seiten'});
    [this.documentLayout(),...(this.documentLayout().pages??[])].forEach((page,index)=>{
      const button=this.element('button',{'aria-pressed':String(index===(this.pageIndex??0))},page.page_name??'Übersicht');button.onclick=()=>this.selectPage(index);pageStrip.append(button);
    });
    const managePages=this.element('button',{class:'secondary'},'Seiten verwalten');managePages.onclick=()=>this.switchInspectorTab('pages',true);pageStrip.append(managePages);canvasSection.append(pageStrip);
    if(this.isOverlayDesigner)pageStrip.hidden=true;
    const well=this.element('div',{class:'preview-well'});
    const stage = this.element('div', {class: 'stage', tabindex: '0', 'aria-label': 'Displayvorschau'});
    stage.dataset.snap='true';
    const image = this.element('img', {alt: 'Vorschau der Anzeige'});
    if (this.previewImage) image.src = this.previewImage;
    stage.append(image);well.append(stage);canvasSection.append(well);
    const elementStrip=this.element('div',{class:'element-strip widget-strip','aria-label':'Elemente'});
    this.layout.widgets.forEach((widget,index)=>{
      const choose=this.element('button',{'aria-pressed':String(this.selection?.has(index)||index===this.widgetIndex),'data-index':index,title:this.widgetLabel(widget)},`${widget.locked?'🔒 ':''}${widget.hidden?'◌ ':''}${index+1}. ${this.widgetLabel(widget)}`);
      if(widget.group)choose.append(this.element('span',{class:'group-badge'},this.groupLabel(widget.group)));
      choose.oncontextmenu=event=>{event.preventDefault();this.elementMenu(index);};choose.ondblclick=()=>this.openElementSettings(index);choose.disabled=this.overlayPreview;choose.onclick=event=>this.selectWidget(index,event.ctrlKey||event.metaKey);elementStrip.append(choose);
    });
    canvasSection.append(elementStrip);
    canvasSection.append(this.element('small', {class:'canvas-meta'}, this.overlayPreview ?
      'Klingelvorschau · Zum Bearbeiten der normalen Anzeige auf „Element“ wechseln.' :
      '480 × 320 Pixel · Ziehen oder Pfeiltasten; Shift = 10 Pixel. Griffe rechts/unten ändern Breite/Höhe, die Ecke beides.'));
    const zoomTools=this.element('div',{class:'toolbar'});for(const [title,value] of [['−',Math.max(1,(this.zoom??1)-.5)],['+',Math.min(3,(this.zoom??1)+.5)],['Gesamtansicht',1]]){const button=this.element('button',{class:'secondary','aria-label':title==='−'?'Verkleinern':title==='+'?'Vergrößern':title},title);button.onclick=()=>this.setZoom(value);zoomTools.append(button);}zoomTools.append(this.element('small',{},`Zoom ${Math.round((this.zoom??1)*100)} %`));canvasSection.append(zoomTools);
    const add = this.element('button', {id:'add-element'}, 'Element hinzufügen');
    add.disabled = this.overlayPreview || this.layout.widgets.length >= 10;
    if(this.layout.widgets.length>=10)add.title='Maximal zehn Elemente pro Seite. Entferne ein Element oder füge eine weitere Seite hinzu.';
    add.onclick = () => this.showAddChooser();
    const save = this.element('button', {id:'save-layout'}, this.isOverlayDesigner?'Klingel-Layout übernehmen':'Speichern & übertragen');
    save.onclick = () => this.saveLayout();
    const remove = this.element('button', {class:'secondary'}, 'Element entfernen');
    remove.disabled = this.overlayPreview || !this.layout.widgets.length;
    remove.onclick = () => this.removeSelected();
    const toolbar=this.element('div',{class:'toolbar'});
    for(const [text,direction] of [['↶',-1],['↷',1]]) {
      const button=this.element('button',{class:'secondary','aria-label':direction<0?'Rückgängig':'Wiederholen'},text);
      button.disabled=this.overlayPreview || (direction<0?this.historyIndex===0:this.historyIndex>=this.history.length-1);
      button.onclick=()=>this.undoEdit(direction);toolbar.append(button);
    }
    main.onkeydown=event=>{
      if(!(event.ctrlKey||event.metaKey) || !['z','y','c','v'].includes(event.key.toLowerCase()))return;
      if(['INPUT','TEXTAREA'].includes(event.target.tagName))return;
      if(event.composedPath().some(e=>['INPUT','TEXTAREA','HA-ENTITY-PICKER'].includes(e.tagName)))return;
      if(event.key.toLowerCase()==='c'){event.preventDefault();this.copyElements();return;}if(event.key.toLowerCase()==='v'){event.preventDefault();this.pasteElements();return;}
      event.preventDefault();this.undoEdit(event.key.toLowerCase()==='y'||event.shiftKey?1:-1);
    };
    const check=this.element('button',{class:'secondary'},'Layout prüfen');check.onclick=()=>this.showLayoutIssues();const compare=this.element('button',{class:'secondary'},'Vergleichen');compare.onclick=()=>this.compareDesign();toolbar.append(check,compare);
    toolbar.append(add,remove,this.element('span',{id:'save-state',class:'save-state',role:'status'}),save);
    canvasSection.append(toolbar, this.element('div', {id:'status',role:'status'}));
    if (!this.devices[this.selected].touch) canvasSection.append(this.element('small', {},
      'Für Touch-Buttons und Switches bitte Display-Firmware 0.2.0 installieren. Text und HA-Werte funktionieren weiterhin.'));
    const settings = this.element('div');
    const themeLabel = this.element('label',{},'Display-Design');
    const theme = this.element('select',{'aria-label':'Display-Design'});
    for (const [value,label] of [['material_dark','Material · Dunkel'],['material_light','Material · Hell']])
      theme.append(this.element('option',{value},label));
    theme.value = this.layout.theme==='material_light'?'material_light':'material_dark';
    theme.onchange = () => this.applyTheme(theme.value);
    themeLabel.append(theme); settings.append(themeLabel,this.element('small',{},'Designwechsel setzt Hintergrund und Textfarben. Positionen, Größen und Entitäten bleiben erhalten.'));
    this.field(settings, 'Hintergrund', this.layout.background, value => this.layout.background = value, {type:'color'});
    const debugLabel = this.element('label');
    const debug = this.element('input', {type:'checkbox','aria-label':'CPU und FPS anzeigen'});
    debug.checked = !!this.documentLayout().debug;
    debug.onchange = () => {this.documentLayout().debug = debug.checked; this.status('Debug-Anzeige geändert. Zum Übertragen speichern.');};
    debugLabel.append(debug,document.createTextNode('CPU und FPS anzeigen'));
    settings.append(debugLabel,this.element('small', {},
      'Debug-Anzeige unten rechts auf dem Gerät. CPU ≈ gemittelte Auslastung beider Kerne; FPS = abgeschlossene HA-Bildupdates pro Sekunde.'));
    if (!this.devices[this.selected].debug_overlay) settings.append(this.element('small', {},
      'Debug-Anzeige und schnellere Bildupdates benötigen Display-Firmware 0.3.0.'));
    const displayPanel=this.element('div',{'data-pane':'display',role:'tabpanel'});
    displayPanel.append(...settings.childNodes);settings.append(displayPanel);
    const designStart=displayPanel.childNodes.length,design=this.documentLayout().design??{};
    const setDesign=(key,value)=>{this.documentLayout().design={...design,...this.documentLayout().design,[key]:value};};
    this.field(displayPanel,'Globale Textfarbe',design.color??'#e6e0e9',v=>setDesign('color',v),{type:'color'});
    this.field(displayPanel,'Globale Schriftgröße',design.size??24,v=>setDesign('size',Number(v)),{type:'number',min:12,max:64});
    this.field(displayPanel,'Globale Kartenfarbe',design.background??'#211f26',v=>setDesign('background',v),{type:'color'});
    this.field(displayPanel,'Globaler Eckenradius',design.radius??16,v=>setDesign('radius',Number(v)),{type:'number',min:0,max:32});
    const themeExport=this.element('button',{class:'secondary'},'Design als Datei exportieren');themeExport.onclick=()=>this.exportTheme();displayPanel.append(themeExport);
    const resetDesign=this.element('button',{class:'secondary'},'Globale Vorgaben entfernen');resetDesign.onclick=()=>{delete this.documentLayout().design;this.draw();this.schedulePreview();};displayPanel.append(resetDesign,this.element('small',{},'Gilt für alle Seiten. Einzelne Elemente können unter Aussehen die Übernahme deaktivieren. Design-Dateien lassen sich unter Sicherungen & Dateien importieren.'));
    this.wrapFields(displayPanel,designStart,'globaldesign','Globales Design');
    const deviceStart=displayPanel.childNodes.length;
    const deviceSettings=this.documentLayout().device??{brightness:100,night_enabled:false,night_start:'22:00',night_end:'07:00',night_brightness:15,ring_brightness:100};
    const setDevice=(key,value)=>{this.documentLayout().device={...deviceSettings,...this.documentLayout().device,[key]:value};};
    this.field(displayPanel,'Helligkeit (%)',deviceSettings.brightness,value=>setDevice('brightness',Number(value)),{type:'number',min:0,max:100});
    const night=this.element('input',{type:'checkbox','aria-label':'Nachtmodus'});night.checked=deviceSettings.night_enabled;night.onchange=()=>{setDevice('night_enabled',night.checked);this.schedulePreview();};
    const nightLabel=this.element('label');nightLabel.append(night,document.createTextNode('Nachtmodus nach HA-Ortszeit'));displayPanel.append(nightLabel);
    for(const [key,label] of [['night_start','Nacht ab'],['night_end','Nacht bis']])this.field(displayPanel,label,deviceSettings[key],value=>setDevice(key,value),{type:'time'});
    for(const [key,label] of [['night_brightness','Nachthelligkeit (%)'],['ring_brightness','Helligkeit beim Klingeln (%)']])this.field(displayPanel,label,deviceSettings[key],value=>setDevice(key,Number(value)),{type:'number',min:0,max:100});
    displayPanel.append(this.element('small',{},'Helligkeit und Nachtmodus benötigen Firmware 0.6.0. Eine HA-Lichtentität erlaubt Automationen; manuelles Schalten über HA beendet den Zeitplan. Beim Klingeln gilt die Klingelhelligkeit, danach wieder der Zeitplan.'));
    this.field(displayPanel,'Bei Inaktivität dimmen nach (0 = aus, Sekunden)',deviceSettings.sleep_after??0,value=>setDevice('sleep_after',Number(value)),{type:'number',min:0,max:3600,step:15});
    this.field(displayPanel,'Helligkeit bei Inaktivität (%)',deviceSettings.sleep_brightness??0,value=>setDevice('sleep_brightness',Number(value)),{type:'number',min:0,max:100});
    displayPanel.append(this.element('small',{},'Ab Firmware 0.9.0. Die erste Berührung weckt nur auf. Klingeln weckt sofort auf.'));
    this.wrapFields(displayPanel,deviceStart,'device','Helligkeit, Nachtmodus & Ruhemodus');
    displayPanel.append(this.element('small',{id:'diagnostic-details',role:'status'},'Diagnose wird geladen …'));
    const firmwareStart=displayPanel.childNodes.length;
    displayPanel.append(this.element('small',{},`Installierte Firmware: ${this.devices[this.selected].firmware??'unbekannt'}`));
    const firmwareFile=this.element('input',{type:'file',accept:'.bin','aria-label':'Firmware-Datei'});displayPanel.append(firmwareFile);
    const flash=this.element('button',{class:'secondary'},'Ausgewählte Firmware installieren');flash.disabled=!this.devices[this.selected].ota_update;flash.onclick=()=>this.updateFirmware(firmwareFile.files[0]);displayPanel.append(flash);
    displayPanel.append(this.element('small',{},'Einmal Firmware 0.6.0 per USB installieren, danach sind Updates hier über WLAN möglich. Die lokal mit deinem bestehenden secrets.h gebaute firmware.bin auswählen (keine bootloader.bin oder partitions.bin). Das Gerät startet nach erfolgreichem Update neu; HA-Schlüssel bleiben im Browser verborgen.'));
    this.wrapFields(displayPanel,firmwareStart,'firmware','Firmware aktualisieren');
    const pagesPanel=this.element('div',{'data-pane':'pages',role:'tabpanel'});
    pagesPanel.append(this.element('h2',{},'Seiten & Wechsel')); 
    this.field(pagesPanel,'Seitenname',this.layout.page_name??'Übersicht',value=>this.layout.page_name=value,{maxlength:20});
    this.field(pagesPanel,'Automatischer Seitenwechsel (0 = aus, Sekunden)',this.documentLayout().rotation??0,value=>this.documentLayout().rotation=Number(value),{type:'number',min:0,max:300});
    const addPage=this.element('button',{class:'secondary'},'Seite hinzufügen');addPage.disabled=(this.documentLayout().pages?.length??0)>=3;addPage.onclick=()=>this.addPage();pagesPanel.append(addPage);
    const removePage=this.element('button',{class:'secondary'},'Diese Seite entfernen');removePage.disabled=!this.pageIndex;
    removePage.onclick=()=>{const root=this.documentLayout(),removed=this.pageIndex;root.pages.splice(removed-1,1);root.page_rules=(root.page_rules??[]).filter(rule=>rule.page!==removed).map(rule=>({...rule,page:rule.page>removed?rule.page-1:rule.page}));this.selectPage(0);};pagesPanel.append(removePage,this.element('small',{},'Bis vier Seiten. Bei mehreren Seiten sind die unteren 44 Pixel für Touch-Navigation und Status reserviert. Wechsel ab 15 Sekunden; Klingel-Overlay pausiert den Wechsel.'));
    pagesPanel.append(this.element('h2',{},'Seiten bei HA-Ereignissen anzeigen'));
    for(const [flag,title] of [['swipe','Wischen auf freier Fläche zum Seitenwechsel (Firmware 0.8.0)'],['navigation','Seitennavigation unten anzeigen']]){const input=this.element('input',{type:'checkbox','aria-label':title});input.checked=this.documentLayout()[flag]??(flag==='navigation');input.onchange=()=>{this.documentLayout()[flag]=input.checked;this.draw();this.schedulePreview();};const label=this.element('label');label.append(input,document.createTextNode(title));pagesPanel.append(label);}
    const rules=this.documentLayout().page_rules??[];
    for(const [index,rule] of rules.entries()) {
      const card=this.element('div',{class:'rule-card'});this.conditionFields(card,rule.when);
      const target=this.element('select',{'aria-label':'Zielseite'});
      [this.documentLayout(),...(this.documentLayout().pages??[])].forEach((page,i)=>target.append(this.element('option',{value:i},page.page_name??'Übersicht')));
      target.value=rule.page;target.onchange=()=>{rule.page=Number(target.value);this.schedulePreview();};card.append(target);
      this.field(card,'Anzeigedauer (Sekunden)',rule.duration,v=>rule.duration=Number(v),{type:'number',min:5,max:300});
      const remove=this.element('button',{class:'secondary'},'Seitenregel entfernen');remove.onclick=()=>{rules.splice(index,1);this.draw();this.schedulePreview();};card.append(remove);pagesPanel.append(card);
    }
    const pageRule=this.element('button',{class:'secondary'},'Seitenregel hinzufügen');pageRule.disabled=rules.length>=8;
    pageRule.onclick=()=>{(this.documentLayout().page_rules??=[]).push({when:{entity_id:'',op:'eq',value:'on'},page:0,duration:30});this.draw();};pagesPanel.append(pageRule,this.element('small',{},'Regel löst beim Wechsel von nicht erfüllt zu erfüllt aus. Danach erscheint wieder die vorherige Seite. HA-Automationen können auch die Aktionen Desk Display: Meldung anzeigen und Seite anzeigen verwenden.'));
    const templatesStart=displayPanel.childNodes.length;
    for(const [type,label] of [['energy','Energieübersicht'],['status','Schalterübersicht'],['clock','Uhrzeit mit Datum'],['camera','Kameraansicht']]){
      const button=this.element('button',{class:'secondary'},label);button.onclick=()=>this.addTemplate(type);displayPanel.append(button);
    }
    displayPanel.append(this.element('small',{},'Vorlagen ergänzen die Seite. Energie, Schalter und Kamera werden zuerst gezielt zugeordnet. Eigene Komponenten unter Sicherungen & Dateien wiederverwenden.'));
    this.wrapFields(displayPanel,templatesStart,'templates','Vorlagen');
    const filesStart=displayPanel.childNodes.length;
    const exportButton=this.element('button',{class:'secondary'},'Layout exportieren');exportButton.onclick=()=>this.exportDesign();displayPanel.append(exportButton);
    const exportComponents=this.element('button',{class:'secondary'},'Auswahl als Komponente exportieren');exportComponents.onclick=()=>this.exportDesign(true);displayPanel.append(exportComponents);
    const importInput=this.element('input',{type:'file',accept:'.json,application/json','aria-label':'Layout oder Komponenten importieren'});importInput.onchange=()=>this.importDesign(importInput.files[0]);displayPanel.append(this.element('label',{},'Layout / Komponenten importieren'),importInput);
    for(const backup of this.devices[this.selected].backups??[]) {
      const button=this.element('button',{class:'secondary'},`Sicherung laden: ${new Date(backup.at).toLocaleString()}`);
      button.onclick=()=>{this.layout=structuredClone(backup.layout);this.rootLayout=this.layout;this.pageIndex=0;this.doorbell=structuredClone(backup.doorbell);this.widgetIndex=0;this.selection=new Set([0]);this.draw();this.preview();this.status('Sicherung geladen. Zum Wiederherstellen speichern.');};displayPanel.append(button);
    }
    displayPanel.append(this.element('small',{},'HA behält die drei vorherigen gespeicherten Layouts. Import und Wiederherstellung ändern zuerst nur den Entwurf. Dateien enthalten keine Geräte- oder WLAN-Schlüssel.'));
    this.wrapFields(displayPanel,filesStart,'files','Sicherungen & Dateien');
    const simulationStart=displayPanel.childNodes.length;
    const simEntity=this.element('ha-entity-picker');simEntity.hass=this._hass;simEntity.label='Entität simulieren';let simId='';
    simEntity.addEventListener('value-changed',event=>simId=event.detail.value??'');displayPanel.append(simEntity);
    let simValue='0';this.field(displayPanel,'Testzustand (z. B. 0, unavailable oder on)',simValue,v=>simValue=v);
    const simulate=this.element('button',{class:'secondary'},'Testzustand hinzufügen');simulate.onclick=()=>{if(simId){this.simulation.states[simId]=simValue;this.draw();this.preview();}};displayPanel.append(simulate);
    for(const [entity,value] of Object.entries(this.simulation.states)){
      const button=this.element('button',{class:'secondary'},`${entity}: ${value} ×`);button.onclick=()=>{delete this.simulation.states[entity];this.draw();this.preview();};displayPanel.append(button);
    }
    const doorSim=this.element('select',{'aria-label':'Türablauf simulieren'});
    for(const [value,label] of [['','Echter Zustand'],['pending','Knopf gedrückt'],['sent','Befehl ausgeführt'],['open','Tür offen'],['closed','Tür geschlossen'],['error','Fehler'],['uncertain','Ergebnis unklar']])doorSim.append(this.element('option',{value},label));
    doorSim.value=this.simulation.door;doorSim.onchange=()=>{this.simulation.door=doorSim.value;this.overlayPreview=!!doorSim.value;this.draw();this.preview();};displayPanel.append(doorSim);
    const resetSim=this.element('button',{class:'secondary'},'Simulation beenden');resetSim.onclick=()=>{this.simulation={states:{},door:''};this.overlayPreview=false;this.draw();this.preview();};displayPanel.append(resetSim,this.element('small',{},'Simulation betrifft nur die Vorschau. Sie wird weder gespeichert noch ans Gerät übertragen und führt keine Türaktion aus.'));
    this.wrapFields(displayPanel,simulationStart,'simulation','Sichere Vorschau-Simulation');
    if(Object.keys(this.simulation.states).length || this.simulation.door)canvasSection.append(this.element('strong',{},'SIMULATION · nur Vorschau'));
    const widgetPanel=this.element('div',{'data-pane':'element',role:'tabpanel'});
    const widget = this.layout.widgets[this.widgetIndex];
    if (widget) {
      const arrangeStart=settings.childNodes.length;
      for(const [flag,title] of [['locked','Position und Größe sperren'],['hidden','Am Display ausblenden']]) {
        const input=this.element('input',{type:'checkbox','aria-label':title});input.checked=!!widget[flag];
        input.onchange=()=>{widget[flag]=input.checked;this.draw();this.schedulePreview();};const label=this.element('label');label.append(input,document.createTextNode(title));settings.append(label);
      }
      const duplicate=this.element('button',{class:'secondary'},'Duplizieren');
      duplicate.disabled=widget.kind==='media' || this.layout.widgets.length>=10;
      duplicate.onclick=()=>this.duplicateSelected();
      const backward=this.element('button',{class:'secondary'},'Eine Ebene zurück');
      backward.disabled=this.widgetIndex===0;backward.onclick=()=>this.moveSelectedLayer(-1);
      const forward=this.element('button',{class:'secondary'},'Eine Ebene nach vorn');
      forward.disabled=this.widgetIndex===this.layout.widgets.length-1;forward.onclick=()=>this.moveSelectedLayer(1);
      settings.append(duplicate,backward,forward);
      settings.append(this.element('small',{},'Strg/Klick wählt mehrere Elemente. Gruppen werden gemeinsam verschoben.'));
      if(widget.group)settings.append(this.element('small',{},`${this.groupLabel(widget.group)} · ${this.layout.widgets.filter(w=>w.group===widget.group).length} Elemente. Gelber Rahmen und gleiche Kennzeichnung zeigen die Zusammengehörigkeit.`));
      for(const [label,action] of [['Gruppieren',()=>this.groupSelection()],['Gruppe auflösen',()=>this.groupSelection(true)]]) {
        const button=this.element('button',{class:'secondary'},label);button.onclick=action;settings.append(button);
      }
      settings.append(this.element('small',{},'Mit Raster und Hilfslinien ausrichten. Die oberste Ebene bestimmt auch das Touch-Ziel. Maximal zehn Elemente und ein Videofeld.'));
      this.wrapFields(settings,arrangeStart,'arrange','Anordnen');
      const contentStart=settings.childNodes.length;

      const kind = this.element('select', {'aria-label':'Elementtyp'});
      for (const [value,label] of [['text','Text'],['sensor','HA-Wert'],['button','Button'],['switch','Switch'],['media','Video / Livestream'],['image','Bild'],['clock','Uhrzeit / Datum'],['icon','Icon'],['line','Trennlinie'],['progress','Fortschritt'],['gauge','Ringanzeige'],['chip','Status-Chip'],['chart','Verlauf'],['energy','Energiefluss'],['slider','Slider'],['player','Mediensteuerung'],['cost','Energiekosten'],['weather','Wetter'],['countdown','Timer / Countdown'],['door_history','Klingelverlauf']]) {
        const option=this.element('option',{value},label);
        option.disabled=value==='media' && this.layout.widgets.some(w=>w!==widget && w.kind==='media');kind.append(option);
      }
      kind.value = widget.kind;
      kind.onchange = () => {
        widget.kind = kind.value;delete widget.config;delete widget.role;
        if (widget.text==='Neuer Text') widget.text=({image:'Bild',clock:'Uhrzeit',media:'Video',sensor:'HA-Wert',button:'Button',switch:'Switch',text:'Neuer Text'})[widget.kind];
        if (widget.kind!=='sensor') delete widget.value;
        if (widget.kind!=='clock') delete widget.clock_format;
        if (!['image','icon','chip'].includes(widget.kind)) {delete widget.image;delete widget.fit;}
        if(!['icon','chip'].includes(widget.kind))delete widget.icon;
        if(widget.kind!=='line')delete widget.line_width;
        if (['text','image','clock','icon','line'].includes(widget.kind)) widget.entity_id='';
        if (widget.kind === 'media') {
          widget.source = widget.entity_id.startsWith('camera.') ? widget.entity_id : (widget.source ?? '');
          widget.width = Math.min(widget.width,160); widget.height = Math.min(Math.max(widget.height,90),120);
          widget.x = Math.min(widget.x,480-widget.width); widget.y = Math.min(widget.y,320-widget.height);
          widget.entity_id = '';
          widget.fps = 1;
        } else {delete widget.source;delete widget.fps;}
        const domain = widget.entity_id.split('.')[0];
        if ((widget.kind === 'button' && !['button','input_button','script','lock'].includes(domain)) ||
            (widget.kind === 'switch' && !['switch','input_boolean'].includes(domain))) widget.entity_id = '';
        this.groupsOpen.content=true;this.draw(); this.schedulePreview();
      };
      const kindLabel=this.element('label',{},'Elementtyp');kindLabel.append(kind);widgetPanel.append(kindLabel);
      if(this.isOverlayDesigner && ['text','button'].includes(widget.kind)) {
        const role=this.element('select',{'aria-label':'Klingelrolle'});for(const [value,label] of [['','Zusätzliches Element'],...(widget.kind==='button'?[['door_open','Türöffner']]:[['title','Titel'],['door_status','Türstatus']])])role.append(this.element('option',{value},label));role.value=widget.role??'';role.onchange=()=>{if(role.value)widget.role=role.value;else delete widget.role;this.schedulePreview();};settings.append(role);
      }
      this.field(settings, 'Beschriftung', widget.text, value => widget.text = value, {maxlength:80});
      if(widget.kind==='energy') {
        const config=widget.config??={};
        for(const [role,label] of [['solar','Solarleistung'],['house','Hausverbrauch'],['battery','Batterieleistung'],['grid','Netzleistung']]) {
          const picker=this.element('ha-entity-picker');picker.hass=this._hass;picker.label=label;picker.value=config[role]??'';picker.addEventListener('value-changed',event=>{config[role]=event.detail.value??'';this.schedulePreview();});settings.append(picker);
        }
        this.field(settings,'Faktor für Werte in Watt',config.factor??1,v=>config.factor=Number(v),{type:'number',step:'any'});
        for(const role of ['grid','battery']){const check=this.element('input',{type:'checkbox'});check.checked=!!config[role+'_invert'];check.onchange=()=>{config[role+'_invert']=check.checked;this.schedulePreview();};const label=this.element('label');label.append(check,document.createTextNode((role==='grid'?'Netz':'Batterie')+'-Vorzeichen umkehren'));settings.append(label);}
        settings.append(this.element('small',{},'Positive Netz-/Batteriewerte fließen zum Haus; negative Werte fließen aus dem Haus.'));
      } else if(['progress','gauge','chip','chart'].includes(widget.kind)) {
        const picker=this.element('ha-entity-picker');picker.hass=this._hass;picker.value=widget.entity_id;picker.label='HA-Entität';picker.addEventListener('value-changed',event=>{widget.entity_id=event.detail.value??'';this.schedulePreview();});settings.append(picker);
        const config=widget.config??={};
        if(widget.kind==='chart') {
          this.field(settings,'Zeitraum (Minuten)',config.minutes??60,v=>config.minutes=Number(v),{type:'number',min:15,max:1440});
          this.field(settings,'Umrechnungsfaktor',config.factor??1,v=>config.factor=Number(v),{type:'number',step:'any'});
          for(const [key,label] of [['min','Minimum (leer = automatisch)'],['max','Maximum (leer = automatisch)'],['threshold','Grenzwert (optional)']])this.field(settings,label,config[key]??'',v=>{if(v==='')delete config[key];else config[key]=Number(v);},{type:'number',step:'any'});
          this.field(settings,'Einheit',config.unit??'',v=>config.unit=v,{maxlength:16});
          settings.append(this.element('small',{},'Verwendet HA-Recorder. Historie wird einmal pro Minute geladen, maximal 120 Punkte.'));
        } else if(widget.kind==='chip') {
          const icon=this.element('ha-icon-picker');icon.hass=this._hass;icon.label='Status-Icon (optional)';icon.value=widget.icon??'';icon.addEventListener('value-changed',event=>{if(event.detail.value)this.updateIcon(widget,event.detail.value);else{delete widget.icon;delete widget.image;this.schedulePreview();}});settings.append(icon);
          for(const [key,label,def] of [['active','Aktiver HA-Zustand','on'],['on_text','Text bei aktiv','Aktiv'],['off_text','Text bei inaktiv','Inaktiv']])this.field(settings,label,config[key]??def,v=>config[key]=v,{maxlength:40});
        } else {
          for(const [key,label,def] of [['min','Minimum',0],['max','Maximum',100]])this.field(settings,label,config[key]??def,v=>config[key]=Number(v),{type:'number'});
          this.field(settings,'Einheit (optional)',config.unit??'',v=>config.unit=v,{maxlength:16});
        }
      } else if(widget.kind==='icon') {
        const picker=this.element('ha-icon-picker');picker.hass=this._hass;picker.label='Home-Assistant-Icon';picker.value=widget.icon??'mdi:home';
        picker.addEventListener('value-changed',event=>this.updateIcon(widget,event.detail.value));settings.append(picker);
        settings.append(this.element('small',{},'Icon auswählen; Größe über die Griffe und Farbe unter Aussehen ändern.'));
      } else if(widget.kind==='line') {
        const direction=this.element('select',{'aria-label':'Richtung der Trennlinie'});
        direction.append(this.element('option',{value:'horizontal'},'Horizontal'),this.element('option',{value:'vertical'},'Vertikal'));
        direction.value=widget.width>=widget.height?'horizontal':'vertical';
        direction.onchange=()=>{[widget.width,widget.height]=[widget.height,widget.width];widget.width=Math.min(widget.width,480-widget.x);widget.height=Math.min(widget.height,320-widget.y);this.draw();this.schedulePreview();};settings.append(direction);
        this.field(settings,'Linienstärke (Pixel)',widget.line_width??2,value=>widget.line_width=Number(value),{type:'number',min:1,max:8});
      } else if (widget.kind === 'image') {
        const upload=this.element('input',{type:'file',accept:'image/png,image/jpeg,image/webp','aria-label':'Bild hochladen'});
        upload.onchange=()=>this.uploadPicture(upload.files[0],widget);
        const fit=this.element('select',{'aria-label':'Bildanpassung'});
        fit.append(this.element('option',{value:'contain'},'Vollständig anzeigen'),this.element('option',{value:'cover'},'Feld füllen / zuschneiden'));
        fit.value=widget.fit ?? 'contain';fit.onchange=()=>{widget.fit=fit.value;this.schedulePreview();};
        settings.append(upload,fit,this.element('small',{},'PNG, JPEG oder WebP; wird vor dem Speichern verkleinert. Transparente Logos werden unterstützt.'));
      } else if(widget.kind==='door_history'){settings.append(this.element('small',{},'Zeigt die letzten vier Klingelereignisse dieses Displays. Speicherung und Bilder im Klingel-Tab ausdrücklich aktivieren.'));
      } else if (widget.kind === 'clock') {
        const format=this.element('select',{'aria-label':'Uhrzeitformat'});
        for (const [value,label] of [['time','Uhrzeit · HH:MM'],['date','Datum · TT.MM.JJJJ'],['datetime','Datum und Uhrzeit']])
          format.append(this.element('option',{value},label));
        format.value=widget.clock_format ?? 'time';format.onchange=()=>{widget.clock_format=format.value;this.schedulePreview();};
        settings.append(format,this.element('small',{},'Verwendet die Zeitzone von Home Assistant. Die Uhrzeit aktualisiert sich innerhalb von etwa zehn Sekunden nach dem Minutenwechsel.'));
      } else if (widget.kind === 'media') {
        const picker = this.element('ha-entity-picker');
        picker.hass = this._hass; picker.includeDomains = ['camera']; picker.label = 'HA-Kamera';
        picker.value = widget.source?.startsWith('camera.') ? widget.source : '';
        picker.addEventListener('value-changed',event => {
          if (event.detail.value) {widget.source = event.detail.value; this.draw(); this.schedulePreview();}
        });
        settings.append(picker);
        this.field(settings,'Kamera / Medienquelle / Video-URL',widget.source ?? '', value => widget.source = value,
          {placeholder:'camera.tuer oder media-source://…',maxlength:2048});
        const browse = this.element('button',{class:'secondary'},'HA-Medien auswählen');
        browse.onclick = () => this.browseMedia(settings,widget);
        settings.append(browse,this.element('small',{},
          'Ein Videofeld bis 480 × 320 Pixel, ohne Ton. Der Stream wird höchstens einmal pro Sekunde aktualisiert. Werte, Buttons und Switches arbeiten unabhängig davon. Größere Bilder benötigen Firmware 0.5.0. Speichern startet den Stream.'));
        widget.fps = 1;
        if (!this.devices[this.selected].jpeg_regions) settings.append(this.element('small',{},
          'Aktuelle Firmware: maximal 160 × 120 Pixel. Für größere Bilder bitte Firmware 0.5.0 flashen.'));
        settings.append(this.element('small',{id:'media-status',role:'status'},'Zum Starten der Quelle speichern.'));
      } else if (widget.kind !== 'text') {
        const picker = this.element('ha-entity-picker');
        picker.hass = this._hass; picker.value = widget.entity_id; picker.label = 'HA-Entität';
        if (widget.kind === 'button') picker.includeDomains = ['button','input_button','script','lock'];
        if(widget.kind==='slider')picker.includeDomains=['light','media_player','number','input_number'];
        if(widget.kind==='weather')picker.includeDomains=['weather'];
        if(widget.kind==='countdown')picker.includeDomains=['timer','sensor','input_datetime'];
        if(widget.kind==='cost')picker.includeDomains=['sensor','input_number'];
        if(widget.kind==='player')picker.includeDomains=['media_player'];
        if (widget.kind === 'switch') picker.includeDomains = ['switch','input_boolean'];
        picker.addEventListener('value-changed', event => {
          if (event.detail.value !== widget.entity_id) {
            widget.entity_id = event.detail.value ?? '';
            const input = settings.querySelector('[data-field=entity_id]');
            if (input) input.value = widget.entity_id;
            this.schedulePreview();
          }
        });
        settings.append(picker);
        // Also works before HA has lazy-loaded its entity picker.
        const placeholder = widget.kind === 'button' ? 'script.tuer_oeffnen' : widget.kind === 'switch' ? 'switch.licht' : 'sensor.pv_leistung';
        this.field(settings, 'Entitäts-ID', widget.entity_id, value => {widget.entity_id = value;picker.value = value;}, {placeholder,'data-field':'entity_id'});
        if (widget.kind==='sensor') {
          const valueStart=settings.childNodes.length;
          settings.append(this.element('small',{},'Beschriftung links, Wert rechts. Zahlenänderungen betreffen nur die Displayanzeige.'));
          const value=widget.value ??= {};
          this.field(settings,'Umrechnungsfaktor',value.factor ?? 1,input=>value.factor=Number(input.replace(',','.')),{type:'text',inputmode:'decimal'});
          this.field(settings,'Eigene Einheit (leer = ohne Einheit)',value.unit ?? '',input=>value.unit=input,{maxlength:16});
          const haUnit=this.element('button',{class:'secondary'},'HA-Einheit verwenden');
          haUnit.onclick=()=>{delete value.unit;this.draw();this.schedulePreview();};
          settings.append(haUnit,this.element('small',{},'Ohne eigene Einheit wird die HA-Einheit übernommen. Beispiel: Faktor 0,001 und Einheit kW für einen Wert in W.'));
          this.field(settings,'Nachkommastellen',value.decimals ?? 2,input=>value.decimals=Number(input),{type:'number',min:0,max:6,step:1});
          const invert=this.element('input',{type:'checkbox','aria-label':'Vorzeichen wechseln'});
          invert.checked=!!value.invert;invert.onchange=()=>{value.invert=invert.checked;this.schedulePreview();};
          const invertLabel=this.element('label');invertLabel.append(invert,document.createTextNode('Vorzeichen wechseln (+ ↔ −)'));settings.append(invertLabel);
          const fallback=this.element('ha-entity-picker');fallback.hass=this._hass;fallback.label='Ersatz-Entität (optional)';fallback.value=value.fallback_entity_id ?? '';
          fallback.addEventListener('value-changed',event=>{value.fallback_entity_id=event.detail.value ?? '';this.schedulePreview();});
          settings.append(fallback);
          const mode=this.element('select',{'aria-label':'Ersatzwert anzeigen'});
          for (const [key,label] of [['both','Bei 0 oder fehlendem Wert'],['missing','Nur bei fehlendem Wert'],['zero','Nur bei 0']])
            mode.append(this.element('option',{value:key},label));
          mode.value=value.fallback_mode ?? 'both';mode.onchange=()=>{value.fallback_mode=mode.value;this.schedulePreview();};
          settings.append(mode,this.element('small',{},'Der ursprüngliche HA-Wert wird geprüft, bevor der Faktor angewendet wird. Der Ersatzwert erhält dieselbe Umrechnung und Einheit.'));
          this.wrapFields(settings,valueStart,'values','Umrechnung & Ersatzwert');
        }
        if(widget.kind==='button') {
          const config=widget.config??={};const hold=this.element('ha-entity-picker');hold.hass=this._hass;hold.label='Aktion bei langem Drücken (optional)';hold.includeDomains=['button','input_button','script','lock'];hold.value=config.hold_entity_id??'';hold.addEventListener('value-changed',event=>{config.hold_entity_id=event.detail.value??'';this.schedulePreview();});settings.append(hold);
          const confirm=this.element('input',{type:'checkbox'});confirm.checked=!!config.confirm;confirm.onchange=()=>{config.confirm=confirm.checked;this.schedulePreview();};const label=this.element('label');label.append(confirm,document.createTextNode('Vor Ausführung durch zweites Tippen bestätigen'));settings.append(label,this.element('small',{},'Langes Drücken (ab 0,7 s) und sofortiges Berührungsfeedback benötigen Firmware 0.7.0.'));
        }
        if(['slider','player'].includes(widget.kind))settings.append(this.element('small',{},'Bedienung erfolgt ausschließlich am Gerät. Slider übernimmt den Bereich der HA-Entität. Mediensteuerung: unten Zurück / Play-Pause / Weiter, darüber Lautstärke.'));
        if (widget.kind !== 'sensor') settings.append(this.element('small', {}, widget.kind === 'button'
          ? 'Tippen am Display drückt den HA-Button oder startet das ausgewählte Skript. Die Vorschau löst keine Aktion aus.'
          : 'Tippen am Display schaltet die Entität um. Der angezeigte Zustand kommt aus Home Assistant.'));
      }

      if(widget.kind==='cost'){
        const config=widget.config??={};this.field(settings,'Preis pro kWh',config.price??.3,v=>config.price=Number(v),{type:'number',min:0,step:.001});
        this.field(settings,'Währung',config.currency??'EUR',v=>config.currency=v,{maxlength:8});
        const mode=this.element('select',{'aria-label':'Kostenberechnung'});for(const [value,text] of [['energy','Energie (Wh/kWh) × Preis'],['power','Leistung (W/kW): Kosten pro Stunde']])mode.append(this.element('option',{value},text));mode.value=config.mode??'energy';mode.onchange=()=>{config.mode=mode.value;this.schedulePreview();};settings.append(mode);
        const tariff=this.element('ha-entity-picker');tariff.hass=this._hass;tariff.label='Preisentität pro kWh (optional)';tariff.value=config.tariff_entity_id??'';tariff.addEventListener('value-changed',e=>{config.tariff_entity_id=e.detail.value??'';this.schedulePreview();});settings.append(tariff,this.element('small',{},'Für Tageskosten einen Tagesenergie-Sensor wählen. Die Kostenrate ist keine aufsummierte Tagesrechnung. Preisentitäten müssen die gewählte Währung pro kWh liefern.'));
        const absolute=this.element('input',{type:'checkbox'});absolute.checked=!!config.absolute;absolute.onchange=()=>{config.absolute=absolute.checked;this.schedulePreview();};const label=this.element('label');label.append(absolute,document.createTextNode('Betrag ohne Vorzeichen verwenden'));settings.append(label);
      }
      if(widget.kind==='weather'){
        const config=widget.config??={};const select=this.element('select',{'aria-label':'Wettervorhersage'});for(const [value,text] of [['none','Nur aktuelles Wetter'],['daily','Täglich'],['hourly','Stündlich'],['twice_daily','Zweimal täglich']])select.append(this.element('option',{value},text));select.value=config.forecast??'daily';select.onchange=()=>{config.forecast=select.value;this.schedulePreview();};settings.append(select,this.element('small',{},'Vorhersage aus der gewählten HA-Wetterintegration. Nicht jeder Anbieter unterstützt jeden Zeitraum.'));
      }
      if(widget.kind==='countdown'){
        const config=widget.config??={};const select=this.element('select',{'aria-label':'Countdown-Quelle'});for(const [value,text] of [['auto','Automatisch: HA-Timer / Sekunden / Termin'],['timestamp','Datum und Uhrzeit'],['seconds','Restzeit in Sekunden'],['minutes','Restzeit in Minuten'],['hours','Restzeit in Stunden']])select.append(this.element('option',{value},text));select.value=config.mode??'auto';select.onchange=()=>{config.mode=select.value;this.schedulePreview();};settings.append(select);
        this.field(settings,'Gesamtdauer für Fortschritt (Sekunden, 0 = automatisch)',config.total??0,v=>config.total=Number(v),{type:'number',min:0,max:31536000,step:1});
        settings.append(this.element('small',{},'HA-Timer berücksichtigen Pause und Endzeit. Zeitangaben ohne Zeitzone verwenden die HA-Zeitzone. Restzeit-Sensoren werden nur angezeigt, nicht gestartet.'));
      }
      if(widget.kind==='sensor'){const config=widget.config??={};const input=this.element('input',{type:'checkbox','aria-label':'Detailansicht beim Antippen'});input.checked=!!config.detail_enabled;input.onchange=()=>{config.detail_enabled=input.checked;this.schedulePreview();};const label=this.element('label');label.append(input,document.createTextNode('Detailansicht beim Antippen'));settings.append(label);this.field(settings,'Detailverlauf (Minuten)',config.detail_minutes??60,v=>config.detail_minutes=Number(v),{type:'number',min:15,max:1440});settings.append(this.element('small',{},'Öffnet den Wert und Recorder-Verlauf für 30 Sekunden. Schließen führt zur aktuellen Seite zurück; Klingeln hat Vorrang.'));}
      this.wrapFields(settings,contentStart,'content','Inhalt & Daten',true);
      const ruleStart=settings.childNodes.length;
      const visible=this.element('input',{type:'checkbox','aria-label':'Sichtbarkeitsbedingung'});visible.checked=!!widget.visible_when;
      visible.onchange=()=>{if(visible.checked)widget.visible_when={entity_id:widget.entity_id,op:'eq',value:'on'};else delete widget.visible_when;this.draw();this.schedulePreview();};
      const visibleLabel=this.element('label');visibleLabel.append(visible,document.createTextNode('Nur bei erfüllter Bedingung anzeigen'));settings.append(visibleLabel);
      if(widget.visible_when)this.conditionFields(settings,widget.visible_when,widget.entity_id);
      for(const [i,rule] of (widget.rules??[]).entries()) {
        const box=this.element('div',{class:'rule-card'});box.append(this.element('strong',{},`Regel ${i+1}`));
        this.conditionFields(box,rule.when,widget.entity_id);box.append(this.element('strong',{class:'rule-result'},'Dann anzeigen mit …'));this.field(box,'Farbe',rule.color,v=>rule.color=v,{type:'color'});this.field(box,'Zeichen vor der Beschriftung (optional)',rule.symbol,v=>rule.symbol=v,{maxlength:4});
        const remove=this.element('button',{class:'secondary'},'Regel entfernen');remove.onclick=()=>{widget.rules.splice(i,1);this.draw();this.schedulePreview();};box.append(remove);settings.append(box);
      }
      const addRule=this.element('button',{class:'secondary'},'Farbregel hinzufügen');addRule.disabled=(widget.rules?.length??0)>=4;
      addRule.onclick=()=>{(widget.rules??=[]).push({when:{entity_id:widget.entity_id,op:'gt',value:'0'},color:'#57d9b0',symbol:''});this.draw();this.schedulePreview();};settings.append(addRule,this.element('small',{},'Regeln werden von oben nach unten geprüft. Die erste passende Regel legt die Farbe fest; ohne Treffer gilt die normale Textfarbe. Verglichen wird der ursprüngliche HA-Wert, z. B. 1000 W vor der Umrechnung in kW.'));
      this.wrapFields(settings,ruleStart,'rules','Farben & Sichtbarkeit');
      const positionStart=settings.childNodes.length;
      for (const fields of [[['x','X',0,479],['y','Y',0,319]],[['width','Breite',1,480],['height','Höhe',1,320]]]) {
        const row = this.element('div',{class:'row'});
        for (const [key,title,min,max] of fields) this.field(row,title,widget[key],value=>{widget[key]=Number(value);this.refreshHits();},{type:'number',min,max,step:1,disabled:!!widget.locked,'data-field':key});
        settings.append(row);
      }
      this.wrapFields(settings,positionStart,'position','Position & Größe');
      const appearanceStart=settings.childNodes.length;
      const inherit=this.element('input',{type:'checkbox'});inherit.checked=widget.inherit_design??true;inherit.onchange=()=>{widget.inherit_design=inherit.checked;this.schedulePreview();};const inheritLabel=this.element('label');inheritLabel.append(inherit,document.createTextNode('Globales Design übernehmen'));settings.append(inheritLabel);
      this.field(settings,'Schriftgröße',widget.size,value=>widget.size=Number(value),{type:'number',min:12,max:64,step:1});
      this.field(settings,'Textfarbe',widget.color,value=>widget.color=value,{type:'color'});
      if (this.layout.theme?.startsWith('material_')) {
        const style = widget.style ??= {};
        const surface = this.element('input',{type:'checkbox','aria-label':'Kartenfläche anzeigen'});
        surface.checked = style.surface ?? !['text','image','icon','line'].includes(widget.kind);
        surface.onchange = () => {style.surface=surface.checked;this.schedulePreview();};
        const surfaceLabel=this.element('label');surfaceLabel.append(surface,document.createTextNode('Kartenfläche anzeigen'));
        if (widget.kind !== 'media') settings.append(surfaceLabel);
        this.field(settings,'Kartenfarbe',style.background ?? (widget.kind==='button'?'#6750a4':this.layout.theme==='material_light'?'#f3edf7':'#211f26'),
          value=>style.background=value,{type:'color'});
        this.field(settings,'Eckenradius',style.radius ?? 16,value=>style.radius=Number(value),{type:'number',min:0,max:32,step:1});
        const align=this.element('select',{'aria-label':'Textausrichtung'});
        for (const [value,label] of [['left','Linksbündig'],['center','Zentriert'],['right','Rechtsbündig']]) align.append(this.element('option',{value},label));
        align.value=style.align ?? (widget.kind==='button'?'center':'left');
        align.onchange=()=>{style.align=align.value;this.schedulePreview();};
        if (!['media','image','sensor','icon','line'].includes(widget.kind)) settings.append(align);
      }
      const fit=this.element('button',{class:'secondary'},'Schrift passend verkleinern');fit.onclick=()=>this.fitText();settings.append(fit);
      this.wrapFields(settings,appearanceStart,'appearance','Aussehen');
    }
    widgetPanel.append(...Array.from(settings.childNodes).filter(node=>node!==displayPanel));
    if (this.overlayPreview) widgetPanel.replaceChildren(this.element('h2',{},'Overlay-Vorschau'),
      this.element('p',{},'Klingelvorschau aktiv. Wähle den Reiter Element, um die normale Anzeige zu bearbeiten.'));
    settings.append(widgetPanel,bellSection,pagesPanel);
    const inspector=this.element('section',{class:'inspector'});
    const tabs=this.element('div',{class:'inspector-tabs',role:'tablist','aria-label':'Einstellungen'});
    for (const [key,title] of [['element','Element'],['pages','Seiten'],['display','Display'],['doorbell','Klingel']]) {
      if(this.isOverlayDesigner && ['pages','doorbell'].includes(key))continue;
      const tab=this.element('button',{'data-tab':key,role:'tab','aria-controls':'pane-'+key},title);
      tab.onclick=()=>this.switchInspectorTab(key,true);tabs.append(tab);
      settings.querySelector('[data-pane='+key+']').id='pane-'+key;
    }
    const scroll=this.element('div',{class:'inspector-scroll'});scroll.append(settings);
    inspector.append(tabs,scroll);
    columns.append(canvasSection,inspector);main.append(columns);this.refreshHits();
    this.switchInspectorTab(this.inspectorTab);
    this.updateSaveState();
    this.applyCapabilityHints();
    if (typeof ResizeObserver!=='undefined') {
      this.previewResize=new ResizeObserver(entries=>{
        const {width,height}=entries[0].contentRect;
        stage.style.width=Math.max(1,Math.floor(Math.min(width,height*1.5)*(this.zoom??1)))+'px';
      });
      this.previewResize.observe(well);
    }
  }
  groupLabel(group) {
    const groups=[...new Set(this.layout.widgets.map(w=>w.group).filter(Boolean))];
    return `Gruppe ${groups.indexOf(group)+1}`;
  }
  refreshGroupBounds(stage) {
    stage.querySelectorAll('.group-outline').forEach(element=>element.remove());
    const groups=[...new Set(this.layout.widgets.map(w=>w.group).filter(Boolean))];
    for(const group of groups) {
      const members=this.layout.widgets.filter(w=>w.group===group);
      const x=Math.min(...members.map(w=>w.x)),y=Math.min(...members.map(w=>w.y));
      const right=Math.max(...members.map(w=>w.x+w.width)),bottom=Math.max(...members.map(w=>w.y+w.height));
      const box=this.element('div',{class:'group-outline','aria-label':`${this.groupLabel(group)}: ${members.length} Elemente`});
      Object.assign(box.style,{left:`${x/4.8}%`,top:`${y/3.2}%`,width:`${(right-x)/4.8}%`,height:`${(bottom-y)/3.2}%`});
      box.append(this.element('span',{class:'group-label'},this.groupLabel(group)));stage.append(box);
    }
  }
  resizeWidget(widget,axis,width,height) {
    if(widget.locked)return;
    if(axis!=='height')widget.width=Math.min(480-widget.x,Math.max(1,Math.round((widget.x+Math.max(8,width))/8)*8-widget.x));
    if(axis!=='width')widget.height=Math.min(320-widget.y,Math.max(1,Math.round((widget.y+Math.max(8,height))/8)*8-widget.y));
  }
  refreshHits() {
    const stage = this.shadowRoot.querySelector('.stage');
    stage.querySelectorAll('.hit').forEach(element=>element.remove());
    if (this.overlayPreview) return;
    this.layout.widgets.forEach((widget,index)=>{
      const hit = this.element('button',{class:`hit ${this.selection?.has(index)?'active':''}`,'aria-label':`Element ${index+1}: ${widget.text}`});
      const position = () => Object.assign(hit.style,{left:`${widget.x/4.8}%`,top:`${widget.y/3.2}%`,width:`${widget.width/4.8}%`,height:`${widget.height/3.2}%`});
      position();
      hit.ondblclick=()=>this.openElementSettings(index);
      hit.oncontextmenu=event=>{event.preventDefault();this.elementMenu(index);};
      hit.onkeydown=event=>{
        if(widget.locked)return;
        const moves={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]};
        if (!moves[event.key]) return;
        event.preventDefault();
        if (index!==this.widgetIndex) {this.selectWidget(index);return;}
        this.nudgeSelected(...moves[event.key],event.shiftKey?10:1);position();
        for(const [i,w] of this.layout.widgets.entries()){const target=stage.querySelectorAll('.hit')[i];if(target){target.style.left=`${w.x/4.8}%`;target.style.top=`${w.y/3.2}%`;}}
        this.shadowRoot.querySelector('[data-field=x]').value=widget.x;
        this.shadowRoot.querySelector('[data-field=y]').value=widget.y;
        this.refreshGroupBounds(stage);
        this.schedulePreview();
      };
      hit.onpointerdown = event => {
        if(widget.locked){this.selectWidget(index);return;}
        if(event.ctrlKey||event.metaKey){this.selectWidget(index,true);return;}
        if (index!==this.widgetIndex) {this.selectWidget(index);return;}
        event.preventDefault();hit.setPointerCapture(event.pointerId);
        const rect = stage.getBoundingClientRect();
        const start = {x:event.clientX,y:event.clientY,wx:widget.x,wy:widget.y};
        hit.onpointermove = move => {
          const [x,y]=this.snapPosition(widget,Math.round(start.wx+(move.clientX-start.x)*480/rect.width),Math.round(start.wy+(move.clientY-start.y)*320/rect.height));
          this.moveSelection(x-widget.x,y-widget.y);
          position();
          this.showGuides(stage,widget);
          for(const [i,w] of this.layout.widgets.entries()) {const target=stage.querySelectorAll('.hit')[i];if(target){target.style.left=`${w.x/4.8}%`;target.style.top=`${w.y/3.2}%`;}}
          this.shadowRoot.querySelector('[data-field=x]').value=widget.x;
          this.shadowRoot.querySelector('[data-field=y]').value=widget.y;
          this.refreshGroupBounds(stage);
        };
        const end=()=>{hit.onpointermove=null;hit.onpointerup=null;hit.onpointercancel=null;stage.querySelectorAll('.guide,.measure').forEach(line=>line.remove());this.schedulePreview();};
        hit.onpointerup=end;hit.onpointercancel=end;
      };
      if (index===this.widgetIndex && !widget.locked) {
        for(const [axis,label] of [['both','Größe'],['width','Breite'],['height','Höhe']]) {
        const grip=this.element('span',{class:`resize ${axis}`,'aria-label':`${label} von Element ${index+1} ändern`});
        grip.onpointerdown=event => {
          event.stopPropagation(); event.preventDefault(); grip.setPointerCapture(event.pointerId);
          const rect=stage.getBoundingClientRect();
          const start={x:event.clientX,y:event.clientY,width:widget.width,height:widget.height};
          grip.onpointermove=move => {
            this.resizeWidget(widget,axis,start.width+(move.clientX-start.x)*480/rect.width,start.height+(move.clientY-start.y)*320/rect.height);
            position();
            this.showDistances(stage,widget);
            this.refreshGroupBounds(stage);
            this.shadowRoot.querySelector('[data-field=width]').value=widget.width;
            this.shadowRoot.querySelector('[data-field=height]').value=widget.height;
          };
          const end=()=>{grip.onpointermove=null;grip.onpointerup=null;grip.onpointercancel=null;this.schedulePreview();};
          grip.onpointerup=end;grip.onpointercancel=end;
        };
        hit.append(grip);
        }
      }
      stage.append(hit);
    });
    this.refreshGroupBounds(stage);
  }
  schedulePreview(quiet = false) {
    if(!quiet){++this.previewSequence;this.recordEdit();}
    this.updateSaveState();
    // State changes must not postpone a pending user edit or overwrite save feedback.
    if (quiet && this.previewTimer) return;
    clearTimeout(this.previewTimer);
    this.previewTimer=setTimeout(()=>{this.previewTimer=null;this.preview(quiet);},250);
  }
  async preview(quiet = false) {
    const sequence=++this.previewSequence;
    if(typeof document!=='undefined' && document.hidden)return;
    if(this.previewBusy){this.previewAgain=true;this.previewAgainQuiet=quiet;return;}
    this.previewBusy=true;this.lastPreviewAt=Date.now();
    const signature=JSON.stringify([this.editState(),this.pageIndex,this.overlayPreview,this.simulation,this.devices[this.selected]?.id]);
    try {
      const result=await this._hass.callWS({type:'desk_display/preview',entry_id:this.devices[this.selected]?.id,layout:this.documentLayout(),doorbell:this.doorbell,overlay:this.overlayPreview,simulation:this.simulation,page:this.pageIndex??0});
      if(sequence!==this.previewSequence || signature!==JSON.stringify([this.editState(),this.pageIndex,this.overlayPreview,this.simulation,this.devices[this.selected]?.id]))return;
      this.previewImage=`data:image/png;base64,${result.png}`;
      this.shadowRoot.querySelector('.stage img').src=this.previewImage;
      const mediaStatus = this.shadowRoot.querySelector('#media-status');
      if (mediaStatus) {
        const item = result.media_status?.find(item => item.index === this.widgetIndex);
        mediaStatus.textContent = item?.message || (item?.state === 'live' ? 'Stream läuft.' :
          item?.state === 'connecting' ? 'Verbindung zur Videoquelle wird aufgebaut …' : 'Zum Starten der Quelle speichern.');
      }
      if (!quiet) this.status(this.editState()!==this.savedSnapshot?'Vorschau aktualisiert. Zum Übertragen speichern.':'Vorschau aktualisiert.');
    } catch(error) {if(sequence===this.previewSequence && !quiet)this.status(`Vorschau: ${error.message ?? error}`);}
    finally {
      this.previewBusy=false;
      if(this.previewAgain && this.isConnected){const nextQuiet=this.previewAgainQuiet;this.previewAgain=false;this.preview(nextQuiet);}
    }
  }
}
if (!customElements.get('desk-display-panel')) customElements.define('desk-display-panel',DeskDisplayPanel);

