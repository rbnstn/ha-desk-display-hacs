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
    this.loadDoorbell();
  }
  set hass(value) {
    const previous = this._hass;
    this._hass = value;
    if (this.isConnected && !this.loaded) this.load();
    for (const picker of this.shadowRoot?.querySelectorAll?.('ha-entity-picker') ?? []) picker.hass = value;
    if (this.isConnected && this.loaded && this.layout && previous &&
        this.layout.widgets.some(widget => {
          return [widget.entity_id,widget.value?.fallback_entity_id,widget.visible_when?.entity_id,...(widget.rules??[]).map(r=>r.when.entity_id)].filter(Boolean).some(entity=>{
            const before=previous.states?.[entity],after=value.states?.[entity];
            return before?.state!==after?.state || before?.attributes?.unit_of_measurement!==after?.attributes?.unit_of_measurement;
          });
        })) this.schedulePreview(true);
  }
  connectedCallback() {
    if (this._hass && !this.loaded) this.load();
    if (this.loaded) this.startVideoPreview();
  }
  disconnectedCallback() {
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
      this.draw();
      if (this.layout) this.preview();
      this.startVideoPreview();
    } catch (error) {
      this.loaded = false;
      this.shadowRoot.textContent = `Desk Display konnte nicht geladen werden: ${error.message ?? error}`;
    }
  }
  startVideoPreview() {
    if (this.videoPreviewTimer) return;
    this.videoPreviewTimer = setInterval(() => {
      if (this.isConnected && (this.overlayPreview || this.layout?.widgets.some(w => ['media','clock'].includes(w.kind))) && !this.previewTimer) this.preview(true);
      if (this.isConnected) this.refreshDoorbellStatus();
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
    this.doorbell = structuredClone(this.devices[this.selected]?.doorbell ??
      {enabled:false,entity_id:'',camera:'',open_entity_id:'',duration:30,preload:false});
    this.doorbell.preload ??= false;
    this.doorbell.post_open_duration ??= 45;
    this.doorbell.door_state_entity_id ??= '';
    this.overlayPreview = false;
    this.savedSnapshot=this.editState();
    this.history=[this.savedSnapshot];this.historyIndex=0;
    this.selection=new Set([0]);
  }
  recordEdit() {
    const state=this.editState();
    if (!this.history || state===this.history[this.historyIndex]) return;
    this.history.splice(this.historyIndex+1);this.history.push(state);
    if (this.history.length>40) this.history.shift();
    this.historyIndex=this.history.length-1;
  }
  undoEdit(direction=-1) {
    this.recordEdit();
    const target=this.historyIndex+direction;
    if (target<0 || target>=this.history.length) return;
    this.historyIndex=target;
    const state=JSON.parse(this.history[target]);
    this.layout=state.layout;this.doorbell=state.doorbell;
    this.widgetIndex=Math.min(this.widgetIndex,Math.max(0,this.layout.widgets.length-1));
    this.selection=new Set([this.widgetIndex]);this.draw();this.preview();
  }
  selectedWidgets() {
    const indices=this.selection?.has(this.widgetIndex) ? this.selection : new Set([this.widgetIndex]);
    return this.layout.widgets.filter((w,i)=>indices.has(i));
  }
  moveSelection(dx,dy) {
    const widgets=this.selectedWidgets();if (!widgets.length) return;
    dx=Math.max(-Math.min(...widgets.map(w=>w.x)),Math.min(dx,480-Math.max(...widgets.map(w=>w.x+w.width))));
    dy=Math.max(-Math.min(...widgets.map(w=>w.y)),Math.min(dy,320-Math.max(...widgets.map(w=>w.y+w.height))));
    for (const w of widgets) {w.x+=dx;w.y+=dy;}
  }
  snapPosition(widget,x,y) {
    if (!this.snapEnabled) return [x,y];
    const selected=this.selectedWidgets(),others=this.layout.widgets.filter(w=>!selected.includes(w));
    const snap=(value,size,bound,axis)=>{
      const lines=[0,bound/2,bound,...others.flatMap(w=>[w[axis],w[axis]+w[axis==='x'?'width':'height']/2,w[axis]+w[axis==='x'?'width':'height']])];
      const offsets=[0,size/2,size];let best=Math.round(value/8)*8,distance=Math.abs(best-value);
      for (const line of lines) for (const offset of offsets) if (Math.abs(line-offset-value)<distance) {best=line-offset;distance=Math.abs(best-value);}
      return Math.max(0,Math.min(bound-size,distance<=4?Math.round(best):value));
    };
    return [snap(x,widget.width,480,'x'),snap(y,widget.height,320,'y')];
  }
  groupSelection(remove=false) {
    const widgets=this.selectedWidgets();
    const group='g'+Date.now().toString(36);
    for (const w of widgets) {if(remove) delete w.group;else w.group=group;}
    this.recordEdit();this.draw();this.schedulePreview();
  }
  arrangeSelection(axis,distribute=false) {
    const widgets=this.selectedWidgets().sort((a,b)=>a[axis]-b[axis]);
    if(widgets.length<2)return;
    const size=axis==='x'?'width':'height';
    if(distribute && widgets.length>2) {
      const first=widgets[0][axis],last=widgets.at(-1)[axis]+widgets.at(-1)[size];
      const gap=(last-first-widgets.reduce((sum,w)=>sum+w[size],0))/(widgets.length-1);
      let cursor=first;for(const w of widgets){w[axis]=Math.round(cursor);cursor+=w[size]+gap;}
    } else {for(const w of widgets)w[axis]=widgets[0][axis];}
    this.recordEdit();this.draw();this.schedulePreview();
  }
  editState(layout=this.layout,doorbell=this.doorbell) {
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
      const text=`${index+1}. ${this.widgetLabel(widget)}`;
      if (select?.options[index]) select.options[index].textContent=text;
      const button=this.shadowRoot?.querySelector?.(`.element-strip button[data-index="${index}"]`);
      if (button) button.textContent=text;
    }
  }
  widgetLabel(widget) {
    return widget.text || widget.entity_id || ({image:'Bild / Logo',clock:'Uhrzeit',media:'Video',sensor:'HA-Wert',button:'Button',switch:'Switch',text:'Text'})[widget.kind];
  }
  wrapFields(parent,start,key,title,open=false) {
    const group=this.element('details',{class:'editor-group'});
    group.open=this.groupsOpen[key] ?? open;
    group.append(this.element('summary',{},title));
    const body=this.element('div',{class:'group-body'});
    body.append(...Array.from(parent.childNodes).slice(start));
    group.append(body);parent.append(group);
    group.ontoggle=()=>this.groupsOpen[key]=group.open;
  }
  conditionFields(parent,condition) {
    const picker=this.element('ha-entity-picker');picker.hass=this._hass;picker.label='Bedingungs-Entität';picker.value=condition.entity_id;
    picker.addEventListener('value-changed',event=>{condition.entity_id=event.detail.value??'';this.schedulePreview();});parent.append(picker);
    const select=this.element('select',{'aria-label':'Vergleich'});
    for(const [value,text] of [['eq','Ist gleich'],['ne','Ist ungleich'],['gt','Größer als'],['gte','Mindestens'],['lt','Kleiner als'],['lte','Höchstens'],['missing','Nicht verfügbar']])select.append(this.element('option',{value},text));
    select.value=condition.op;select.onchange=()=>{condition.op=select.value;this.schedulePreview();};parent.append(select);
    this.field(parent,'Vergleichswert (originaler HA-Zustand)',condition.value,value=>condition.value=value);
  }
  switchInspectorTab(tab) {
    if (!['element','display','doorbell'].includes(tab)) return;
    this.inspectorTab=tab;
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
    if (this.overlayPreview || !selected || selected.kind === 'media' || this.layout.widgets.length >= 8) return;
    const copy = structuredClone(selected);
    copy.x = Math.min(480-copy.width, copy.x+12);
    copy.y = Math.min(320-copy.height, copy.y+12);
    this.layout.widgets.splice(this.widgetIndex+1, 0, copy);
    ++this.widgetIndex;
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
    const savedLayout = structuredClone(this.layout);
    const savedDoorbell = structuredClone(this.doorbell);
    this.saving=true; this.status('Wird gespeichert und übertragen …');
    try {
      const result = await this._hass.callWS({type:'desk_display/save',entry_id:this.devices[deviceIndex].id,layout:savedLayout,doorbell:savedDoorbell});
      this.devices[deviceIndex].layout = savedLayout;
      this.devices[deviceIndex].doorbell = savedDoorbell;
      if (deviceIndex===this.selected) this.savedSnapshot=this.editState(savedLayout,savedDoorbell);
      const resultPreview = await this._hass.callWS({type:'desk_display/preview',layout:savedLayout,doorbell:savedDoorbell,overlay:this.overlayPreview});
      if (deviceIndex===this.selected && this.editState()===this.editState(savedLayout,savedDoorbell)) {
        this.previewImage = `data:image/png;base64,${resultPreview.png}`;
        this.shadowRoot.querySelector('.stage img').src = this.previewImage;
      }
      if (deviceIndex===this.selected) this.status(result.sent ? 'Gespeichert und vom Display bestätigt.' : 'Gespeichert. Display offline oder Übertragung fehlgeschlagen; HA versucht es erneut.');
    } catch (error) { if (deviceIndex===this.selected) this.status(`Fehler: ${error.message ?? error}`); }
    finally { this.saving=false;this.updateSaveState(); }
  }
  draw() {
    this.recordEdit();
    this.previewResize?.disconnect();
    this.shadowRoot.replaceChildren();
    this.shadowRoot.append(this.element('style', {}, `
      :host{display:block;color:var(--primary-text-color,#172033);font:15px system-ui}
      *{box-sizing:border-box}[hidden]{display:none!important}
      main{padding:16px;max-width:1500px;margin:auto;height:calc(100dvh - 56px);min-height:380px;display:flex;flex-direction:column;gap:12px;overflow:hidden}
      .workspace-header{display:flex;gap:24px;align-items:center;flex:none}.workspace-header h1{font-size:22px;margin:0;white-space:nowrap}
      .workspace-header select{min-width:0;flex:1;margin:0}
      h1{font-size:26px;margin:0 0 8px}p{line-height:1.5;color:var(--secondary-text-color,#64748b)}
      .columns{display:grid;grid-template-columns:minmax(0,1fr) 380px;gap:16px;flex:1;min-height:0}
      .canvas{min-width:0;min-height:0;display:flex;flex-direction:column;gap:10px}
      .preview-well{flex:1;min-height:0;display:flex;align-items:center;justify-content:center}
      .toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:6px;flex:none}.toolbar button{margin:0}
      #save-layout{margin-left:auto}.save-state{font-size:12px;white-space:nowrap;color:var(--secondary-text-color,#64748b)}
      .save-state[data-dirty=true]{color:#d97706}
      .inspector{display:flex;flex-direction:column;min-height:0;padding:0;overflow:hidden}
      .inspector-tabs{display:flex;padding:12px;gap:4px;border-bottom:1px solid var(--divider-color,#ddd);flex:none}
      .inspector-tabs button{flex:1;background:transparent;color:inherit;margin:0;border-radius:10px}
      .inspector-tabs button[aria-selected=true]{background:#6750a4;color:white}
      .inspector-scroll{overflow:auto;min-height:0;padding:16px;overscroll-behavior:contain;scrollbar-gutter:stable}
      .editor-group{border-top:1px solid var(--divider-color,#ddd);margin-top:12px}
      summary{cursor:pointer;font-weight:600;padding:12px 0}.group-body{padding-bottom:6px}
      .element-strip{display:flex;gap:6px;overflow:auto;flex:none;padding-bottom:2px}
      .element-strip button{white-space:nowrap;font-size:12px;margin:0;background:var(--secondary-background-color,#e7e0ec);color:inherit;padding:7px 10px}
      .element-strip button[aria-pressed=true]{background:#6750a4;color:white}
      section{background:var(--card-background-color,#fff);border:1px solid var(--divider-color,#ddd);border-radius:20px;padding:20px}
      label{display:block;margin:12px 0}input,select,button{font:inherit;border:1px solid #94a3b8;border-radius:6px;padding:9px}
      input[type=checkbox]{width:auto;margin-right:8px}
      input,select{width:100%;background:var(--card-background-color,#fff);color:inherit;margin-top:5px}
      button{cursor:pointer;background:#2563eb;color:#fff;border:0;margin:5px 8px 5px 0}
      button.secondary{background:#475569}button:disabled{opacity:.5;cursor:wait}
      .stage{position:relative;width:100%;aspect-ratio:3/2;background:#101827;border-radius:8px;overflow:hidden;touch-action:none}
      .stage img{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
      .hit{position:absolute;border:1px dashed #94a3b8;cursor:move;background:transparent;padding:0;margin:0;touch-action:none}
      .hit.active{border:2px solid #57d9b0}.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
      .resize{position:absolute;right:0;bottom:0;z-index:3;width:18px;height:18px;background:#57d9b0;border:2px solid white;cursor:nwse-resize}
      #status{min-height:20px;margin:0;font-size:13px}small{display:block;margin-top:8px;color:var(--secondary-text-color,#64748b)}
      .canvas small{font-size:12px;margin:0}
      @media(max-width:800px){main{padding:10px;gap:8px}.workspace-header{gap:10px}.workspace-header h1{font-size:18px}
        .columns{grid-template-columns:minmax(0,1fr);grid-template-rows:minmax(180px,40%) minmax(0,1fr);gap:10px}
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
      this.selected = Number(deviceSelect.value); this.widgetIndex = 0;
      this.layout = structuredClone(this.devices[this.selected].layout); this.loadDoorbell(); this.draw(); this.preview();
    };
    header.append(deviceSelect);
    const bellSection=this.element('div',{'data-pane':'doorbell',role:'tabpanel'});
    const bellSettings=this.element('details');
    bellSettings.open=true;
    bellSettings.ontoggle=()=>this.bellSettingsOpen=bellSettings.open;
    bellSettings.append(this.element('summary',{},'Klingel-Overlay (optional)'));
    const enabled=this.element('input',{type:'checkbox','aria-label':'Klingel-Overlay aktivieren'});
    enabled.checked=!!this.doorbell.enabled;
    enabled.onchange=()=>{this.doorbell.enabled=enabled.checked;this.status('Klingel-Overlay geändert. Zum Übertragen speichern.');};
    const enabledLabel=this.element('label');enabledLabel.append(enabled,document.createTextNode('Klingel-Overlay aktivieren'));
    bellSettings.append(enabledLabel,this.element('small',{},'Beim Klingeln legt sich Kamera und Türöffner über die normale Anzeige. Wiederholtes Klingeln verlängert die Zeit. Die Tür öffnet nur durch Antippen.'));
    for (const [key,label,domains] of [
      ['entity_id','Klingel-Auslöser',['binary_sensor','event','input_button']],
      ['camera','Overlay-Kamera',['camera']],
      ['open_entity_id','Türöffner / Nuki-Schloss',['button','input_button','script','lock']],
      ['door_state_entity_id','Türkontakt (optional)',['binary_sensor']]]) {
      const picker=this.element('ha-entity-picker');picker.hass=this._hass;
      picker.label=label;picker.includeDomains=domains;picker.value=this.doorbell[key];
      picker.addEventListener('value-changed',event=>{this.doorbell[key]=event.detail.value ?? '';this.schedulePreview();});
      bellSettings.append(picker);
    }
    bellSettings.append(this.element('small',{},'Bei einem Schloss wird die Aktion „Tür öffnen“ ausgeführt. Das Schloss muss diese Aktion ohne PIN unterstützen; sonst ein HA-Skript verwenden.'));
    const preload=this.element('input',{type:'checkbox','aria-label':'Overlay-Kamera vorbereiten'});
    preload.checked=!!this.doorbell.preload;
    preload.onchange=()=>{this.doorbell.preload=preload.checked;this.status('Kameravorbereitung geändert. Zum Übertragen speichern.');};
    const preloadLabel=this.element('label');
    preloadLabel.append(preload,document.createTextNode('Overlay-Kamera vorbereiten'));
    bellSettings.append(preloadLabel,this.element('small',{},'Hält auf dem HA-Rechner ein aktuelles Kamerabild bereit, damit es beim Klingeln schneller erscheint. Zusätzliche Kamera-Verbindung und HA-Rechenlast; das Display bleibt bei höchstens 1 FPS. Nach dem Speichern kurz auf den Kamerastart warten.'));
    bellSettings.append(this.element('small',{id:'doorbell-ready',role:'status'},'Kamerabereitschaft wird geprüft …'));
    this.field(bellSettings,'Automatisch schließen nach (Sekunden)',this.doorbell.duration,
      value=>this.doorbell.duration=Number(value),{type:'number',min:5,max:300,step:1});
    this.field(bellSettings,'Nach Türaktion mindestens weiter anzeigen (Sekunden)',this.doorbell.post_open_duration,
      value=>this.doorbell.post_open_duration=Number(value),{type:'number',min:5,max:300,step:1});
    bellSettings.append(this.element('small',{},'Der Türknopf zeigt Verarbeitung, ausgeführten Befehl oder Fehler. Nur ein Türkontakt (Ein = offen) bestätigt die physisch offene Tür; entriegelt beschreibt den Schlosszustand. Die Ansicht bleibt nach der Aktion standardmäßig noch 45 Sekunden offen.'));
    const overlayPreview=this.element('button',{class:'secondary'},this.overlayPreview?'Normale Vorschau':'Overlay-Vorschau');
    overlayPreview.onclick=()=>{this.overlayPreview=!this.overlayPreview;this.draw();this.preview();};
    const test=this.element('button',{class:'secondary'},'Overlay am Display testen');
    const close=this.element('button',{class:'secondary'},'Overlay am Display schließen');
    const testOverlay=async active=>{
      try {
        const result=await this._hass.callWS({type:'desk_display/doorbell_test',entry_id:this.devices[this.selected].id,active});
        this.status(result.sent?'Overlay-Ansicht vom Display bestätigt.':'Ansicht geändert. Display offline oder Übertragung fehlgeschlagen.');
      } catch(error) {this.status(`Overlay: ${error.message ?? error}`);}
    };
    test.onclick=()=>testOverlay(true);close.onclick=()=>testOverlay(false);
    bellSettings.append(overlayPreview,test,close,this.element('small',{},'Vor dem Gerätetest aktivieren und speichern. Die Vorschau öffnet keine Tür. Binary-Sensoren lösen beim Wechsel Aus → Ein aus; Ereignis-Entitäten bei einem neuen Zeitstempel.'));
    bellSection.append(bellSettings);
    const columns = this.element('div', {class: 'columns'});
    const canvasSection = this.element('section',{class:'canvas'});
    const well=this.element('div',{class:'preview-well'});
    const stage = this.element('div', {class: 'stage', 'aria-label': 'Displayvorschau'});
    const image = this.element('img', {alt: 'Vorschau der Anzeige'});
    if (this.previewImage) image.src = this.previewImage;
    stage.append(image);well.append(stage);canvasSection.append(well);
    const elementStrip=this.element('div',{class:'element-strip','aria-label':'Elemente'});
    this.layout.widgets.forEach((widget,index)=>{
      const choose=this.element('button',{'aria-pressed':String(index===this.widgetIndex),'data-index':index},`${index+1}. ${this.widgetLabel(widget)}`);
      choose.disabled=this.overlayPreview;choose.onclick=event=>this.selectWidget(index,event.ctrlKey||event.metaKey);elementStrip.append(choose);
    });
    canvasSection.append(elementStrip);
    canvasSection.append(this.element('small', {class:'canvas-meta'}, this.overlayPreview ?
      'Overlay-Vorschau · Zum Bearbeiten der normalen Elemente auf „Normale Vorschau“ wechseln.' :
      '480 × 320 Pixel · Ziehen oder Pfeiltasten; Shift = 10 Pixel. Größe am grünen Griff ändern.'));
    const add = this.element('button', {}, 'Element hinzufügen');
    add.disabled = this.overlayPreview || this.layout.widgets.length >= 8;
    add.onclick = () => {
      this.layout.widgets.push({kind:'text',text:'Neuer Text',entity_id:'',x:24,y:180,width:300,height:48,size:24,color:'#ffffff'});
      if (this.layout.theme === 'material_light') this.layout.widgets.at(-1).color='#1d1b20';
      this.widgetIndex = this.layout.widgets.length - 1; this.draw(); this.preview();
    };
    const save = this.element('button', {id:'save-layout'}, 'Speichern & übertragen');
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
      if(!(event.ctrlKey||event.metaKey) || !['z','y'].includes(event.key.toLowerCase()))return;
      if(['INPUT','TEXTAREA'].includes(event.target.tagName))return;
      event.preventDefault();this.undoEdit(event.key.toLowerCase()==='y'||event.shiftKey?1:-1);
    };
    toolbar.append(add,remove,this.element('span',{id:'save-state',class:'save-state',role:'status'}),save);
    canvasSection.append(toolbar, this.element('div', {id:'status',role:'status'}));
    if (!this.devices[this.selected].touch) canvasSection.append(this.element('small', {},
      'Für Touch-Buttons und Switches bitte Display-Firmware 0.2.0 installieren. Text und HA-Werte funktionieren weiterhin.'));
    const settings = this.element('div');
    const themeLabel = this.element('label',{},'Display-Design');
    const theme = this.element('select',{'aria-label':'Display-Design'});
    for (const [value,label] of [['classic','Klassisch'],['material_dark','Material · Dunkel'],['material_light','Material · Hell']])
      theme.append(this.element('option',{value},label));
    theme.value = this.layout.theme ?? 'classic';
    theme.onchange = () => this.applyTheme(theme.value);
    themeLabel.append(theme); settings.append(themeLabel,this.element('small',{},'Designwechsel setzt Hintergrund und Textfarben. Positionen, Größen und Entitäten bleiben erhalten.'));
    this.field(settings, 'Hintergrund', this.layout.background, value => this.layout.background = value, {type:'color'});
    const debugLabel = this.element('label');
    const debug = this.element('input', {type:'checkbox','aria-label':'CPU und FPS anzeigen'});
    debug.checked = !!this.layout.debug;
    debug.onchange = () => {this.layout.debug = debug.checked; this.status('Debug-Anzeige geändert. Zum Übertragen speichern.');};
    debugLabel.append(debug,document.createTextNode('CPU und FPS anzeigen'));
    settings.append(debugLabel,this.element('small', {},
      'Debug-Anzeige unten rechts auf dem Gerät. CPU ≈ gemittelte Auslastung beider Kerne; FPS = abgeschlossene HA-Bildupdates pro Sekunde.'));
    if (!this.devices[this.selected].debug_overlay) settings.append(this.element('small', {},
      'Debug-Anzeige und schnellere Bildupdates benötigen Display-Firmware 0.3.0.'));
    const displayPanel=this.element('div',{'data-pane':'display',role:'tabpanel'});
    displayPanel.append(...settings.childNodes);settings.append(displayPanel);
    const widgetPanel=this.element('div',{'data-pane':'element',role:'tabpanel'});
    const widgetSelect = this.element('select', {'aria-label':'Element auswählen'});
    this.layout.widgets.forEach((widget,index) => widgetSelect.append(this.element('option',{value:index},`${index+1}. ${this.widgetLabel(widget)}`)));
    widgetSelect.value = this.widgetIndex;
    widgetSelect.onchange = () => this.selectWidget(Number(widgetSelect.value));
    widgetPanel.append(this.element('label',{},'Ausgewähltes Element'),widgetSelect);
    const widget = this.layout.widgets[this.widgetIndex];
    if (widget) {
      const arrangeStart=settings.childNodes.length;
      const duplicate=this.element('button',{class:'secondary'},'Duplizieren');
      duplicate.disabled=widget.kind==='media' || this.layout.widgets.length>=8;
      duplicate.onclick=()=>this.duplicateSelected();
      const backward=this.element('button',{class:'secondary'},'Eine Ebene zurück');
      backward.disabled=this.widgetIndex===0;backward.onclick=()=>this.moveSelectedLayer(-1);
      const forward=this.element('button',{class:'secondary'},'Eine Ebene nach vorn');
      forward.disabled=this.widgetIndex===this.layout.widgets.length-1;forward.onclick=()=>this.moveSelectedLayer(1);
      settings.append(duplicate,backward,forward);
      const snap=this.element('input',{type:'checkbox'});snap.checked=!!this.snapEnabled;
      snap.onchange=()=>{this.snapEnabled=snap.checked;};
      const snapLabel=this.element('label');snapLabel.append(snap,document.createTextNode('8-Pixel-Raster und Kanten einrasten'));settings.append(snapLabel);
      settings.append(this.element('small',{},'Strg/Klick wählt mehrere Elemente. Gruppen werden gemeinsam verschoben.'));
      for(const [label,action] of [['Gruppieren',()=>this.groupSelection()],['Gruppe auflösen',()=>this.groupSelection(true)],['Links gemeinsam ausrichten',()=>this.arrangeSelection('x')],['Oben gemeinsam ausrichten',()=>this.arrangeSelection('y')],['Horizontal verteilen',()=>this.arrangeSelection('x',true)],['Vertikal verteilen',()=>this.arrangeSelection('y',true)]]) {
        const button=this.element('button',{class:'secondary'},label);button.onclick=action;settings.append(button);
      }
      const alignment=this.element('select',{'aria-label':'Am Display ausrichten'});
      alignment.append(this.element('option',{value:''},'Am Display ausrichten …'));
      for (const [value,label] of [['left','Links'],['center','Horizontal mittig'],['right','Rechts'],['top','Oben'],['middle','Vertikal mittig'],['bottom','Unten']])
        alignment.append(this.element('option',{value},label));
      alignment.onchange=()=>this.alignSelected(alignment.value);
      settings.append(alignment,this.element('small',{},'Ausrichtung bezieht sich auf das ganze Display. Die oberste Ebene bestimmt auch das Touch-Ziel. Maximal acht Elemente und ein Videofeld.'));
      this.wrapFields(settings,arrangeStart,'arrange','Anordnen');
      const contentStart=settings.childNodes.length;
      const ruleStart=settings.childNodes.length;
      const visible=this.element('input',{type:'checkbox','aria-label':'Sichtbarkeitsbedingung'});visible.checked=!!widget.visible_when;
      visible.onchange=()=>{if(visible.checked)widget.visible_when={entity_id:widget.entity_id,op:'eq',value:'on'};else delete widget.visible_when;this.draw();this.schedulePreview();};
      const visibleLabel=this.element('label');visibleLabel.append(visible,document.createTextNode('Nur bei erfüllter Bedingung anzeigen'));settings.append(visibleLabel);
      if(widget.visible_when)this.conditionFields(settings,widget.visible_when);
      for(const [i,rule] of (widget.rules??[]).entries()) {
        const box=this.element('details');box.open=true;box.append(this.element('summary',{},`Farbregel ${i+1}`));
        this.conditionFields(box,rule.when);this.field(box,'Textfarbe',rule.color,v=>rule.color=v,{type:'color'});this.field(box,'Symbol / Präfix (optional)',rule.symbol,v=>rule.symbol=v,{maxlength:4});
        const remove=this.element('button',{class:'secondary'},'Regel entfernen');remove.onclick=()=>{widget.rules.splice(i,1);this.draw();this.schedulePreview();};box.append(remove);settings.append(box);
      }
      const addRule=this.element('button',{class:'secondary'},'Farbregel hinzufügen');addRule.disabled=(widget.rules?.length??0)>=4;
      addRule.onclick=()=>{(widget.rules??=[]).push({when:{entity_id:widget.entity_id,op:'gt',value:'0'},color:'#57d9b0',symbol:''});this.draw();this.schedulePreview();};settings.append(addRule,this.element('small',{},'Erste passende Farbregel gewinnt. Vergleiche verwenden den HA-Rohwert vor Umrechnung. Nicht verfügbare Werte erfüllen nur „Nicht verfügbar“.'));
      this.wrapFields(settings,ruleStart,'rules','Farben & Sichtbarkeit');
      const kind = this.element('select', {'aria-label':'Elementtyp'});
      for (const [value,label] of [['text','Text'],['sensor','HA-Wert'],['button','Button'],['switch','Switch'],['media','Video / Livestream'],['image','Bild / Logo'],['clock','Uhrzeit / Datum']]) {
        kind.append(this.element('option',{value},label));
      }
      kind.value = widget.kind;
      kind.onchange = () => {
        widget.kind = kind.value;
        if (widget.text==='Neuer Text') widget.text=({image:'Bild / Logo',clock:'Uhrzeit',media:'Video',sensor:'HA-Wert',button:'Button',switch:'Switch',text:'Neuer Text'})[widget.kind];
        if (widget.kind!=='sensor') delete widget.value;
        if (widget.kind!=='clock') delete widget.clock_format;
        if (widget.kind!=='image') {delete widget.image;delete widget.fit;}
        if (['text','image','clock'].includes(widget.kind)) widget.entity_id='';
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
        this.draw(); this.schedulePreview();
      };
      settings.append(kind);
      this.field(settings, 'Beschriftung', widget.text, value => widget.text = value, {maxlength:80});
      if (widget.kind === 'image') {
        const upload=this.element('input',{type:'file',accept:'image/png,image/jpeg,image/webp','aria-label':'Bild oder Logo hochladen'});
        upload.onchange=()=>this.uploadPicture(upload.files[0],widget);
        const fit=this.element('select',{'aria-label':'Bildanpassung'});
        fit.append(this.element('option',{value:'contain'},'Vollständig anzeigen'),this.element('option',{value:'cover'},'Feld füllen / zuschneiden'));
        fit.value=widget.fit ?? 'contain';fit.onchange=()=>{widget.fit=fit.value;this.schedulePreview();};
        settings.append(upload,fit,this.element('small',{},'PNG, JPEG oder WebP; wird vor dem Speichern verkleinert. Transparente Logos werden unterstützt.'));
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
        if (widget.kind !== 'sensor') settings.append(this.element('small', {}, widget.kind === 'button'
          ? 'Tippen am Display drückt den HA-Button oder startet das ausgewählte Skript. Die Vorschau löst keine Aktion aus.'
          : 'Tippen am Display schaltet die Entität um. Der angezeigte Zustand kommt aus Home Assistant.'));
      }
      this.wrapFields(settings,contentStart,'content','Inhalt & Daten',true);
      const positionStart=settings.childNodes.length;
      for (const fields of [[['x','X',0,479],['y','Y',0,319]],[['width','Breite',1,480],['height','Höhe',1,320]]]) {
        const row = this.element('div',{class:'row'});
        for (const [key,title,min,max] of fields) this.field(row,title,widget[key],value=>{widget[key]=Number(value);this.refreshHits();},{type:'number',min,max,step:1,'data-field':key});
        settings.append(row);
      }
      this.wrapFields(settings,positionStart,'position','Position & Größe');
      const appearanceStart=settings.childNodes.length;
      this.field(settings,'Schriftgröße',widget.size,value=>widget.size=Number(value),{type:'number',min:12,max:64,step:1});
      this.field(settings,'Textfarbe',widget.color,value=>widget.color=value,{type:'color'});
      if (this.layout.theme?.startsWith('material_')) {
        const style = widget.style ??= {};
        const surface = this.element('input',{type:'checkbox','aria-label':'Kartenfläche anzeigen'});
        surface.checked = style.surface ?? !['text','image'].includes(widget.kind);
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
        if (!['media','image','sensor'].includes(widget.kind)) settings.append(align);
      }
      this.wrapFields(settings,appearanceStart,'appearance','Aussehen');
    }
    widgetPanel.append(...Array.from(settings.childNodes).filter(node=>node!==displayPanel));
    if (this.overlayPreview) widgetPanel.replaceChildren(this.element('h2',{},'Overlay-Vorschau'),
      this.element('p',{},'Zum Bearbeiten deiner normalen Elemente im Reiter Klingel auf „Normale Vorschau“ wechseln.'));
    settings.append(widgetPanel,bellSection);
    const inspector=this.element('section',{class:'inspector'});
    const tabs=this.element('div',{class:'inspector-tabs',role:'tablist','aria-label':'Einstellungen'});
    for (const [key,title] of [['element','Element'],['display','Display'],['doorbell','Klingel']]) {
      const tab=this.element('button',{'data-tab':key,role:'tab','aria-controls':'pane-'+key},title);
      tab.onclick=()=>this.switchInspectorTab(key);tabs.append(tab);
      settings.querySelector('[data-pane='+key+']').id='pane-'+key;
    }
    const scroll=this.element('div',{class:'inspector-scroll'});scroll.append(settings);
    inspector.append(tabs,scroll);
    columns.append(canvasSection,inspector);main.append(columns);this.refreshHits();
    this.switchInspectorTab(this.inspectorTab);
    this.updateSaveState();
    if (typeof ResizeObserver!=='undefined') {
      this.previewResize=new ResizeObserver(entries=>{
        const {width,height}=entries[0].contentRect;
        stage.style.width=Math.max(1,Math.floor(Math.min(width,height*1.5)))+'px';
      });
      this.previewResize.observe(well);
    }
  }
  refreshHits() {
    const stage = this.shadowRoot.querySelector('.stage');
    stage.querySelectorAll('.hit').forEach(element=>element.remove());
    if (this.overlayPreview) return;
    this.layout.widgets.forEach((widget,index)=>{
      const hit = this.element('button',{class:`hit ${this.selection?.has(index)?'active':''}`,'aria-label':`Element ${index+1}: ${widget.text}`});
      const position = () => Object.assign(hit.style,{left:`${widget.x/4.8}%`,top:`${widget.y/3.2}%`,width:`${widget.width/4.8}%`,height:`${widget.height/3.2}%`});
      position();
      hit.onkeydown=event=>{
        const moves={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]};
        if (!moves[event.key]) return;
        event.preventDefault();
        if (index!==this.widgetIndex) {this.selectWidget(index);return;}
        this.nudgeSelected(...moves[event.key],event.shiftKey?10:1);position();
        this.shadowRoot.querySelector('[data-field=x]').value=widget.x;
        this.shadowRoot.querySelector('[data-field=y]').value=widget.y;
        this.schedulePreview();
      };
      hit.onpointerdown = event => {
        if(event.ctrlKey||event.metaKey){this.selectWidget(index,true);return;}
        if (index!==this.widgetIndex) {this.selectWidget(index);return;}
        event.preventDefault();hit.setPointerCapture(event.pointerId);
        const rect = stage.getBoundingClientRect();
        const start = {x:event.clientX,y:event.clientY,wx:widget.x,wy:widget.y};
        hit.onpointermove = move => {
          const [x,y]=this.snapPosition(widget,Math.round(start.wx+(move.clientX-start.x)*480/rect.width),Math.round(start.wy+(move.clientY-start.y)*320/rect.height));
          this.moveSelection(x-widget.x,y-widget.y);
          position();
          for(const [i,w] of this.layout.widgets.entries()) {const target=stage.querySelectorAll('.hit')[i];if(target){target.style.left=`${w.x/4.8}%`;target.style.top=`${w.y/3.2}%`;}}
          this.shadowRoot.querySelector('[data-field=x]').value=widget.x;
          this.shadowRoot.querySelector('[data-field=y]').value=widget.y;
        };
        const end=()=>{hit.onpointermove=null;hit.onpointerup=null;hit.onpointercancel=null;this.schedulePreview();};
        hit.onpointerup=end;hit.onpointercancel=end;
      };
      if (index===this.widgetIndex) {
        const grip=this.element('span',{class:'resize','aria-label':`Größe von Element ${index+1} ändern`});
        grip.onpointerdown=event => {
          event.stopPropagation(); event.preventDefault(); grip.setPointerCapture(event.pointerId);
          const rect=stage.getBoundingClientRect();
          const start={x:event.clientX,y:event.clientY,width:widget.width,height:widget.height};
          grip.onpointermove=move => {
            widget.width=Math.max(1,Math.min(480-widget.x,Math.round(start.width+(move.clientX-start.x)*480/rect.width)));
            widget.height=Math.max(1,Math.min(320-widget.y,Math.round(start.height+(move.clientY-start.y)*320/rect.height)));
            position();
            this.shadowRoot.querySelector('[data-field=width]').value=widget.width;
            this.shadowRoot.querySelector('[data-field=height]').value=widget.height;
          };
          const end=()=>{grip.onpointermove=null;grip.onpointerup=null;grip.onpointercancel=null;this.schedulePreview();};
          grip.onpointerup=end;grip.onpointercancel=end;
        };
        hit.append(grip);
      }
      stage.append(hit);
    });
  }
  schedulePreview(quiet = false) {
    if(!quiet)this.recordEdit();
    this.updateSaveState();
    // State changes must not postpone a pending user edit or overwrite save feedback.
    if (quiet && this.previewTimer) return;
    clearTimeout(this.previewTimer);
    this.previewTimer=setTimeout(()=>{this.previewTimer=null;this.preview(quiet);},250);
  }
  async preview(quiet = false) {
    const sequence=++this.previewSequence;
    try {
      const result=await this._hass.callWS({type:'desk_display/preview',layout:this.layout,doorbell:this.doorbell,overlay:this.overlayPreview});
      if(sequence!==this.previewSequence)return;
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
  }
}
if (!customElements.get('desk-display-panel')) customElements.define('desk-display-panel',DeskDisplayPanel);
