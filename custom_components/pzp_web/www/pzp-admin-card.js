import { entryReady, resolveEntryId } from './pzp-card-utils.js';
/* Administrator-only local settings. Secrets are write-only and never HA entities. */
class PzpAdminCard extends HTMLElement {
  setConfig(config) {
    if(!config.config_entry_id && !config.entity)throw new Error('Zadejte entity nebo config_entry_id.');
    this.config=config;this.attachShadowIfNeeded();this.loaded=false;
    this.shadowRoot.innerHTML=`<style>
      :host{display:block}ha-card{padding:22px}h2{margin:0 0 16px;font-size:22px}h3{margin:20px 0 10px;font-size:18px}.top,.buttons,.keys{display:flex;gap:9px;flex-wrap:wrap;align-items:center}
      input,select,button{box-sizing:border-box;font:inherit;color:var(--primary-text-color);background:var(--card-background-color);border:1px solid var(--divider-color);border-radius:9px;padding:10px}button{cursor:pointer}button:disabled{opacity:.45;cursor:default}select{flex:1;min-width:180px}input{width:100%;max-width:420px}input[type=checkbox]{width:22px;height:22px}.row{padding:13px 0;border-bottom:1px solid var(--divider-color);display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap}.row label{flex:1;min-width:180px}.value{font-weight:600;overflow-wrap:anywhere}.hint,.note{color:var(--secondary-text-color);font-size:13px;line-height:1.55}.note{margin:14px 0}.unavailable{opacity:.55}.status{margin:12px 0;line-height:1.5}.error{color:var(--error-color,#db4437)}details{margin-top:20px}summary{cursor:pointer;font-weight:600}.keys{margin:18px 0}.keys button{min-width:52px}.prepared{font-size:22px;line-height:1.8;word-break:break-word}.primary{background:var(--primary-color);color:var(--text-primary-color,#fff)}.forms{margin-top:16px}
    </style><ha-card><h2>Nastavení čerpadla</h2><div class="top"><select aria-label="Oblast nastavení"></select><button class="refresh">Načíst</button></div><div class="status" role="status"></div><div class="content"></div>
    <details class="recovery"><summary>Obnovit připojení HA</summary><p class="note">Tento formulář mění připojení webové integrace HA. Nemění síť čerpadla ani adresu existujícího Modbusu. Prázdné jméno či heslo ponechá uložený údaj.</p><div class="recovery-fields"></div><button class="connect">Ověřit a uložit připojení</button></details></ha-card>`;
    this.shadowRoot.querySelector('select').onchange=()=>this.load();
    this.shadowRoot.querySelector('.refresh').onclick=()=>this.load();
    const container=this.shadowRoot.querySelector('.recovery-fields');
    for(const [key,label,type]of [['host','Adresa pro připojení HA','text'],['username','Přihlašovací jméno','text'],['password','Heslo','password']]){
      const row=document.createElement('div');row.className='row';const lab=document.createElement('label');lab.textContent=label;const input=document.createElement('input');input.type=type;input.dataset.recovery=key;input.autocomplete='off';input.setAttribute('aria-label',label);row.append(lab,input);container.append(row);
    }
    this.shadowRoot.querySelector('.connect').onclick=async()=>{
      const data={action:'connection'};for(const input of container.querySelectorAll('input')){if(input.value)data[input.dataset.recovery]=input.value;if(input.type==='password')input.value=''}
      await this.perform(data,false);this.loaded=false;await this.initialize();
    };
    if(entryReady(this.config,this._hass))this.initialize();
  }
  attachShadowIfNeeded(){if(!this.shadowRoot)this.attachShadow({mode:'open'})}
  set hass(hass){this._hass=hass;if(this.config&&!this.loaded&&!this.busy&&entryReady(this.config,hass))this.initialize()}
  getCardSize(){return 9}
  async api(method,data,section){
    try{return await this._hass.callApi(method,`pzp_web/${encodeURIComponent(resolveEntryId(this.config,this._hass))}/admin${section?'?section='+encodeURIComponent(section):''}`,data)}
    catch(error){throw new Error(error.body?.error||error.body?.message||error.message||'Připojení selhalo. Obnovte zobrazení.')}
  }
  status(text,error=false){const el=this.shadowRoot.querySelector('.status');el.className='status'+(error?' error':'');el.textContent=text}
  lock(value){this.busy=value;for(const el of this.shadowRoot.querySelectorAll('button,input,select'))el.disabled=value||el.dataset.unavailable==='true'}
  async initialize(){
    if(this.busy||!this._hass)return;this.loaded=true;
    if(!this._hass.user?.is_admin){this.shadowRoot.querySelector('ha-card').textContent='Nastavení čerpadla je dostupné pouze správci HA.';return}
    this.lock(true);
    try{const r=await this.api('GET');const sel=this.shadowRoot.querySelector('select');sel.replaceChildren();for(const s of r.sections){const o=document.createElement('option');o.value=s.key;o.textContent=s.name;sel.append(o)}this.shadowRoot.querySelector('[data-recovery=host]').value=r.host;this.status('')}
    catch(e){this.status(e.message,true)}finally{this.lock(false)}
    if(this.shadowRoot.querySelector('select').value)await this.load();
  }
  async load(){
    if(this.busy)return;const section=this.shadowRoot.querySelector('select').value;if(!section)return;
    this.state=null;this.shadowRoot.querySelector('.content').replaceChildren();this.lock(true);this.status('Načítám skutečné nastavení z čerpadla…');
    try{this.state=await this.api('GET',undefined,section);this.render();this.status('')}catch(e){this.status(e.message,true)}finally{this.lock(false)}
  }
  async perform(data,withToken=true){
    if(this.busy)return;this.lock(true);this.status('Provádím příkaz a načítám výsledek…');
    try{const request=withToken?{section:this.state.section,token:this.state.token,...data}:data;const result=await this.api('POST',request);if(result.section){this.state=result;this.render()}this.status(result.message||(result.editor?'Hodnota je připravená v editoru. Uloží se až tlačítkem Potvrdit.':'Načten aktuální stav čerpadla.'))}
    catch(e){this.state=null;this.shadowRoot.querySelector('.content').replaceChildren();this.status(e.message+' Pro další práci stiskněte Načíst.',true)}finally{this.lock(false)}
  }
  button(label,handler,parent,unavailable=false){const b=document.createElement('button');b.textContent=label;b.onclick=handler;b.dataset.unavailable=String(unavailable);b.disabled=unavailable;parent.append(b);return b}
  render(){
    const container=this.shadowRoot.querySelector('.content');container.replaceChildren();const s=this.state;
    if(s.editor){
      const h=document.createElement('h3');h.textContent=s.name;container.append(h);const value=document.createElement('div');value.className='prepared';
      value.textContent=s.secret?'•••• (chráněná hodnota)':s.values.map(v=>(v.label?v.label+': ':'')+v.value).join(' · ');container.append(value);
      const keys=document.createElement('div');keys.className='keys';for(const [key,label]of Object.entries(s.keys))this.button(label,()=>this.perform({action:'key',field:s.editor,key:Number(key)}),keys);container.append(keys);
      const b=document.createElement('div');b.className='buttons';this.button('Potvrdit v čerpadle',()=>{if(confirm('Uložit připravenou hodnotu do čerpadla?'))this.perform({action:'commit',field:s.editor})},b).className='primary';this.button('Zavřít bez potvrzení',()=>this.load(),b);container.append(b);return;
    }
    if(s.note){const note=document.createElement('p');note.className='note';note.textContent=s.note;container.append(note)}
    const inputs=[];
    for(const f of s.fields){
      const row=document.createElement('div');row.className='row'+(!f.available?' unavailable':'');const label=document.createElement('label');label.textContent=f.label;row.append(label);
      const text=document.createElement('span');text.className='value';text.textContent=f.secret?(f.value?'Nastaveno':'Nenastaveno'):(typeof f.value==='boolean'?(f.value?'Ano':'Ne'):String(f.value??''));
      if(f.kind==='form'){
        const input=document.createElement('input');input.type=f.secret?'password':'text';input.autocomplete='off';input.maxLength=f.max;input.setAttribute('aria-label',f.label);input.value=f.secret?'':String(f.value??'');input.placeholder=f.secret?(f.value?'Nastaveno · prázdné ponechá beze změny':'Nová hodnota'):'';input.dataset.unavailable=String(!f.available);input.disabled=!f.available;row.append(input);inputs.push({f,input,original:input.value});
      }else if(f.kind==='bool'){
        const input=document.createElement('input');input.type='checkbox';input.checked=f.value;input.setAttribute('aria-label',f.label);input.dataset.unavailable=String(!f.available);input.disabled=!f.available;input.onchange=()=>{if(confirm(`Změnit „${f.label}“ na ${input.checked?'Ano':'Ne'}?`))this.perform({action:'set',field:f.key,value:input.checked});else input.checked=f.value};row.append(input);
      }else if(f.kind==='choice'){
        const sel=document.createElement('select');sel.setAttribute('aria-label',f.label);for(const name of Object.keys(f.options)){const option=document.createElement('option');option.value=name;option.textContent=name;sel.append(option)}sel.value=f.value;sel.onchange=()=>{if(confirm(`Změnit „${f.label}“ na ${sel.value}?`))this.perform({action:'set',field:f.key,value:sel.value});else sel.value=f.value};row.append(sel);
      }else if(f.kind==='editor'){row.append(text);this.button('Upravit',()=>this.perform({action:'open',field:f.key}),row,!f.available)}
      else if(f.kind==='pulse'||f.kind==='cycle'){if(f.kind==='cycle')row.append(text);this.button(f.kind==='cycle'?'Přepnout':'Provést',()=>{if(confirm(f.confirm||`Provést „${f.label}“?`))this.perform({action:f.kind,field:f.key})},row,!f.available)}
      else row.append(text);
      if(!f.available){const hint=document.createElement('span');hint.className='hint';hint.textContent='Regulátor nyní nenabízí';row.append(hint)}container.append(row);
    }
    if(inputs.length){const buttons=document.createElement('div');buttons.className='forms';this.button('Uložit změněná pole',()=>{
      const changes={};for(const {f,input,original}of inputs)if(f.available&&input.value!==original)changes[f.key]=input.value;
      if(!Object.keys(changes).length){this.status('Žádné pole nebylo změněno.');return}
      if(!confirm(s.confirm||'Uložit změněná pole do čerpadla?'))return;
      for(const {f,input}of inputs)if(f.secret)input.value='';this.perform({action:'form',changes});
    },buttons).className='primary';container.append(buttons)}
  }
}
customElements.define('pzp-admin-card',PzpAdminCard);
window.customCards=window.customCards||[];window.customCards.push({type:'pzp-admin-card',name:'Nastavení PZP',description:'Úplná uživatelská nastavení regulátoru pro správce HA.'});
