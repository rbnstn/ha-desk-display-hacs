// Native web component: no build step or external frontend dependencies.
export class DeskDisplayPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode: 'open'});
    this.devices = [];
    this.selected = 0;
    this.widgetIndex = 0;
    this.previewSequence = 0;
  }
  set hass(value) {
    const previous = this._hass;
    this._hass = value;
    if (this.isConnected && !this.loaded) this.load();
    const picker = this.shadowRoot?.querySelector('ha-entity-picker');
    if (picker) picker.hass = value;
    if (this.isConnected && this.loaded && this.layout && previous &&
        this.layout.widgets.some(widget => {
          if (widget.kind === 'text') return false;
          const before = previous.states?.[widget.entity_id];
          const after = value.states?.[widget.entity_id];
          return before?.state !== after?.state ||
            before?.attributes?.unit_of_measurement !== after?.attributes?.unit_of_measurement;
        })) this.schedulePreview(true);
  }
  connectedCallback() {
    if (this._hass && !this.loaded) this.load();
  }
  disconnectedCallback() {
    clearTimeout(this.previewTimer);
    this.previewTimer = null;
    ++this.previewSequence;
  }
  async load() {
    this.loaded = true;
    try {
      this.devices = await this._hass.callWS({type: 'desk_display/list'});
      this.layout = structuredClone(this.devices[this.selected]?.layout);
      this.draw();
      if (this.layout) this.preview();
    } catch (error) {
      this.loaded = false;
      this.shadowRoot.textContent = `Desk Display konnte nicht geladen werden: ${error.message ?? error}`;
    }
  }
  element(tag, attributes = {}, text) {
    const element = document.createElement(tag);
    for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
    if (text !== undefined) element.textContent = text;
    return element;
  }
  status(message) {
    this.shadowRoot.querySelector('#status').textContent = message;
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
    this.layout.widgets.splice(this.widgetIndex, 1);
    this.widgetIndex = Math.max(0, Math.min(this.widgetIndex, this.layout.widgets.length - 1));
    this.draw();
    this.preview();
  }
  draw() {
    this.shadowRoot.replaceChildren();
    this.shadowRoot.append(this.element('style', {}, `
      :host{display:block;color:var(--primary-text-color,#172033);font:15px system-ui}
      *{box-sizing:border-box}main{padding:28px;max-width:1100px;margin:auto}
      h1{font-size:26px;margin:0 0 8px}p{line-height:1.5;color:var(--secondary-text-color,#64748b)}
      .columns{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:24px;margin-top:24px}
      section{background:var(--card-background-color,#fff);border:1px solid var(--divider-color,#ddd);border-radius:12px;padding:20px}
      label{display:block;margin:12px 0}input,select,button{font:inherit;border:1px solid #94a3b8;border-radius:6px;padding:9px}
      input[type=checkbox]{width:auto;margin-right:8px}
      input,select{width:100%;background:var(--card-background-color,#fff);color:inherit;margin-top:5px}
      button{cursor:pointer;background:#2563eb;color:#fff;border:0;margin:5px 8px 5px 0}
      button.secondary{background:#475569}button:disabled{opacity:.5;cursor:wait}
      .stage{position:relative;width:100%;aspect-ratio:3/2;background:#101827;border-radius:8px;overflow:hidden;touch-action:none}
      .stage img{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
      .hit{position:absolute;border:1px dashed #94a3b8;cursor:move;background:transparent;padding:0;margin:0;touch-action:none}
      .hit.active{border:2px solid #57d9b0}.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
      #status{min-height:24px;margin-top:16px}small{display:block;margin-top:8px;color:var(--secondary-text-color,#64748b)}
      @media(max-width:850px){.columns{grid-template-columns:1fr}main{padding:16px}}
    `));
    const main = this.element('main');
    main.append(this.element('h1', {}, 'Desk Display'),
      this.element('p', {}, 'Platziere Texte, HA-Werte, Buttons und Switches auf deinem E32R35T.'));
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
      this.layout = structuredClone(this.devices[this.selected].layout); this.draw(); this.preview();
    };
    main.append(deviceSelect);
    const columns = this.element('div', {class: 'columns'});
    const canvasSection = this.element('section');
    const stage = this.element('div', {class: 'stage', 'aria-label': 'Displayvorschau'});
    const image = this.element('img', {alt: 'Vorschau der Anzeige'});
    if (this.previewImage) image.src = this.previewImage;
    stage.append(image); canvasSection.append(stage);
    canvasSection.append(this.element('small', {}, '480 × 320 Pixel · Elemente ziehen oder Position rechts eingeben. Später eingefügte Elemente liegen oben.'));
    const add = this.element('button', {}, 'Element hinzufügen');
    add.disabled = this.layout.widgets.length >= 8;
    add.onclick = () => {
      this.layout.widgets.push({kind:'text',text:'Neuer Text',entity_id:'',x:24,y:180,width:300,height:48,size:24,color:'#ffffff'});
      this.widgetIndex = this.layout.widgets.length - 1; this.draw(); this.preview();
    };
    const save = this.element('button', {}, 'Speichern & übertragen');
    save.onclick = async () => {
      clearTimeout(this.previewTimer);
      this.previewTimer = null;
      ++this.previewSequence;
      const deviceIndex = this.selected;
      const savedLayout = structuredClone(this.layout);
      save.disabled = true; this.status('Wird gespeichert und übertragen …');
      try {
        const result = await this._hass.callWS({type:'desk_display/save',entry_id:this.devices[deviceIndex].id,layout:savedLayout});
        this.devices[deviceIndex].layout = savedLayout;
        const resultPreview = await this._hass.callWS({type:'desk_display/preview',layout:savedLayout});
        this.previewImage = `data:image/png;base64,${resultPreview.png}`;
        if (deviceIndex === this.selected) this.shadowRoot.querySelector('.stage img').src = this.previewImage;
        this.status(result.sent ? 'Gespeichert und vom Display bestätigt.' : 'Gespeichert. Display offline oder Übertragung fehlgeschlagen; HA versucht es erneut.');
      } catch (error) { this.status(`Fehler: ${error.message ?? error}`); }
      finally { save.disabled = false; }
    };
    const remove = this.element('button', {class:'secondary'}, 'Element entfernen');
    remove.disabled = !this.layout.widgets.length;
    remove.onclick = () => this.removeSelected();
    canvasSection.append(add, remove, save, this.element('div', {id:'status',role:'status'}));
    if (!this.devices[this.selected].touch) canvasSection.append(this.element('small', {},
      'Für Touch-Buttons und Switches bitte Display-Firmware 0.2.0 installieren. Text und HA-Werte funktionieren weiterhin.'));
    const settings = this.element('section');
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
    const widgetSelect = this.element('select', {'aria-label':'Element auswählen'});
    this.layout.widgets.forEach((widget,index) => widgetSelect.append(this.element('option',{value:index},`${index+1}. ${widget.text || widget.entity_id}`)));
    widgetSelect.value = this.widgetIndex;
    widgetSelect.onchange = () => {this.widgetIndex = Number(widgetSelect.value); this.draw();};
    settings.append(widgetSelect);
    const widget = this.layout.widgets[this.widgetIndex];
    if (widget) {
      const kind = this.element('select', {'aria-label':'Elementtyp'});
      for (const [value,label] of [['text','Text'],['sensor','HA-Wert'],['button','Button'],['switch','Switch']]) {
        kind.append(this.element('option',{value},label));
      }
      kind.value = widget.kind;
      kind.onchange = () => {
        widget.kind = kind.value;
        const domain = widget.entity_id.split('.')[0];
        if ((widget.kind === 'button' && !['button','input_button','script'].includes(domain)) ||
            (widget.kind === 'switch' && !['switch','input_boolean'].includes(domain))) widget.entity_id = '';
        this.draw(); this.schedulePreview();
      };
      settings.append(kind);
      this.field(settings, 'Beschriftung', widget.text, value => widget.text = value, {maxlength:80});
      if (widget.kind !== 'text') {
        const picker = this.element('ha-entity-picker');
        picker.hass = this._hass; picker.value = widget.entity_id; picker.label = 'HA-Entität';
        if (widget.kind === 'button') picker.includeDomains = ['button','input_button','script'];
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
        if (widget.kind !== 'sensor') settings.append(this.element('small', {}, widget.kind === 'button'
          ? 'Tippen am Display drückt den HA-Button oder startet das ausgewählte Skript. Die Vorschau löst keine Aktion aus.'
          : 'Tippen am Display schaltet die Entität um. Der angezeigte Zustand kommt aus Home Assistant.'));
      }
      for (const fields of [[['x','X',0,479],['y','Y',0,319]],[['width','Breite',1,480],['height','Höhe',1,320]]]) {
        const row = this.element('div',{class:'row'});
        for (const [key,title,min,max] of fields) this.field(row,title,widget[key],value=>{widget[key]=Number(value);this.refreshHits();},{type:'number',min,max,step:1,'data-field':key});
        settings.append(row);
      }
      this.field(settings,'Schriftgröße',widget.size,value=>widget.size=Number(value),{type:'number',min:12,max:64,step:1});
      this.field(settings,'Textfarbe',widget.color,value=>widget.color=value,{type:'color'});
    }
    columns.append(canvasSection,settings);main.append(columns);this.refreshHits();
  }
  refreshHits() {
    const stage = this.shadowRoot.querySelector('.stage');
    stage.querySelectorAll('.hit').forEach(element=>element.remove());
    this.layout.widgets.forEach((widget,index)=>{
      const hit = this.element('button',{class:`hit ${index===this.widgetIndex?'active':''}`,'aria-label':`Element ${index+1}: ${widget.text}`});
      const position = () => Object.assign(hit.style,{left:`${widget.x/4.8}%`,top:`${widget.y/3.2}%`,width:`${widget.width/4.8}%`,height:`${widget.height/3.2}%`});
      position();
      hit.onpointerdown = event => {
        if (index!==this.widgetIndex) {this.widgetIndex=index;this.draw();return;}
        event.preventDefault();hit.setPointerCapture(event.pointerId);
        const rect = stage.getBoundingClientRect();
        const start = {x:event.clientX,y:event.clientY,wx:widget.x,wy:widget.y};
        hit.onpointermove = move => {
          widget.x=Math.max(0,Math.min(480-widget.width,Math.round(start.wx+(move.clientX-start.x)*480/rect.width)));
          widget.y=Math.max(0,Math.min(320-widget.height,Math.round(start.wy+(move.clientY-start.y)*320/rect.height)));
          position();
          this.shadowRoot.querySelector('[data-field=x]').value=widget.x;
          this.shadowRoot.querySelector('[data-field=y]').value=widget.y;
        };
        const end=()=>{hit.onpointermove=null;hit.onpointerup=null;hit.onpointercancel=null;this.schedulePreview();};
        hit.onpointerup=end;hit.onpointercancel=end;
      };
      stage.append(hit);
    });
  }
  schedulePreview(quiet = false) {
    // State changes must not postpone a pending user edit or overwrite save feedback.
    if (quiet && this.previewTimer) return;
    clearTimeout(this.previewTimer);
    this.previewTimer=setTimeout(()=>{this.previewTimer=null;this.preview(quiet);},250);
  }
  async preview(quiet = false) {
    const sequence=++this.previewSequence;
    try {
      const result=await this._hass.callWS({type:'desk_display/preview',layout:this.layout});
      if(sequence!==this.previewSequence)return;
      this.previewImage=`data:image/png;base64,${result.png}`;
      this.shadowRoot.querySelector('.stage img').src=this.previewImage;
      if (!quiet) this.status('Vorschau aktualisiert. Zum Übertragen speichern.');
    } catch(error) {if(sequence===this.previewSequence && !quiet)this.status(`Vorschau: ${error.message ?? error}`);}
  }
}
if (!customElements.get('desk-display-panel')) customElements.define('desk-display-panel',DeskDisplayPanel);
