import { entryReady, resolveEntryId } from './pzp-card-utils.js';
/* Local PZP schedule editor. All controller access remains inside HA. */
class PzpScheduleCard extends HTMLElement {
  setConfig(config) {
    if (!config.config_entry_id && !config.entity) throw new Error('Zadejte entity nebo config_entry_id integrace PZP.');
    this.config = config;
    this.program = config.program || 'R046';
    if(!this.shadowRoot)this.attachShadow({mode:'open'});
    this.shadowRoot.innerHTML = `<style>
      :host{display:block}ha-card{padding:20px}.top{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
      h2{font-size:20px;margin:0 0 14px}select,button{font:inherit;color:var(--primary-text-color);border:1px solid var(--divider-color);border-radius:9px;background:var(--card-background-color);padding:9px 12px;cursor:pointer}
      select{flex:1;min-width:180px}button:disabled{opacity:.5;cursor:wait}.nav{display:flex;justify-content:space-between;align-items:center;margin:16px 0;gap:8px}.caption{text-align:center;font-weight:600}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
      .slot{display:flex;flex-direction:column;gap:4px;min-height:58px}.slot[aria-pressed=true]{background:var(--primary-color);color:var(--text-primary-color,#fff);border-color:var(--primary-color)}
      .small{font-size:12px;opacity:.8}.note{font-size:13px;line-height:1.5;color:var(--secondary-text-color);margin-top:14px}.status{font-size:14px;min-height:20px;margin-top:12px}.error{color:var(--error-color,#db4437)}
      @media(min-width:650px){.grid{grid-template-columns:repeat(6,1fr)}}
    </style><ha-card><h2>Časové programy čerpadla</h2><div class="top"><select aria-label="Časový program"></select><button class="refresh" title="Načíst z čerpadla">Obnovit</button></div>
      <div class="nav"><button data-action="previous_day" aria-label="Předchozí den">‹ Den</button><span class="caption day">—</span><button data-action="next_day" aria-label="Následující den">Den ›</button></div>
      <div class="nav"><button data-action="previous_time" aria-label="Předchozí časový úsek">‹ Čas</button><span class="caption hours">—</span><button data-action="next_time" aria-label="Následující časový úsek">Čas ›</button></div>
      <div class="grid"></div><details style="margin-top:18px"><summary>Hromadné úpravy dne</summary><p class="note">Načte se všech 96 čtvrthodin zvoleného dne. Kopie zůstává pouze v této kartě; lze ji vložit do jiného dne nebo programu.</p><div class="top bulk"></div></details><div class="status" role="status"></div><div class="note">Barevný interval znamená aktivní funkci vybraného programu. Kliknutím změníš jednu čtvrthodinu. Časy se řídí hodinami čerpadla a program běží i bez HA.</div></ha-card>`;
    const names = {R046:'Útlum topení',M146:'Útlum směšovače 1',O039:'Komfortní teplota TUV',C003:'Blokování kompresoru'};
    const select = this.shadowRoot.querySelector('select');
    for(const [value,name] of Object.entries(names)){const option=document.createElement('option');option.value=value;option.textContent=name;select.append(option)}
    select.value=this.program;
    select.addEventListener('change',()=>{this.program=select.value;this.state=null;this.run('view')});
    this.shadowRoot.querySelector('.refresh').addEventListener('click',()=>this.run('view'));
    for(const button of this.shadowRoot.querySelectorAll('[data-action]')) button.addEventListener('click',()=>this.run(button.dataset.action));
    for(const [action,label]of [['copy','Kopírovat den'],['paste','Vložit den'],['fill','Zapnout celý den'],['clear','Vypnout celý den']]){const b=document.createElement('button');b.textContent=label;b.onclick=()=>this.bulk(action);this.shadowRoot.querySelector('.bulk').append(b)}
    this.loaded=false;
    if(this._hass) this.run('view');
  }
  set hass(hass){this._hass=hass;if(this.config&&!this.loaded&&!this.busy&&entryReady(this.config,hass))this.run('view')}
  getCardSize(){return 6}
  async bulk(action){
    if(this.busy||!this.state?.available)return;
    if(action==='paste'&&!this.clipboard){this.shadowRoot.querySelector('.status').textContent='Nejprve zkopírujte den.';return}
    if(action!=='copy'&&!confirm(`Změnit všech 96 intervalů dne ${this.state.day} v programu ${this.program}?`))return;
    await this.run('day_view');if(!this.state?.day_slots)return;
    if(action==='copy'){this.clipboard=[...this.state.day_slots];this.shadowRoot.querySelector('.status').textContent='Celý den byl zkopírován.';return}
    const desired=action==='paste'?[...this.clipboard]:Array(96).fill(action==='fill');
    await this.run('day_set',desired);
  }
  async run(action, slot) {
    if(this.busy||!this._hass)return;
    if(!entryReady(this.config,this._hass)){this.shadowRoot.querySelector('.status').textContent='Entita integrace zatím není načtená.';return}
    this.busy=true;this.loaded=true;
    const status=this.shadowRoot.querySelector('.status');status.className='status';status.textContent=action==='set'?'Ukládám a ověřuji změnu…':'Načítám z čerpadla…';
    for(const el of this.shadowRoot.querySelectorAll('button,select'))el.disabled=true;
    const data={config_entry_id:resolveEntryId(this.config,this._hass),program:this.program,action};
    if(action==='day_view'||action==='day_set'){
      Object.assign(data,{day:this.state.day,start:this.state.start});
      if(action==='day_set')Object.assign(data,{day_slots:slot,expected_day_slots:[...this.state.day_slots]});
      status.textContent=action==='day_view'?'Načítám všech 96 intervalů dne…':'Ukládám celý den a ověřuji výsledek. Může to trvat několik minut…';
    }
    if(action==='set'){
      if(!this.state){this.busy=false;return}
      Object.assign(data,{slot,value:!this.state.slots[slot],day:this.state.day,start:this.state.start,expected_slots:[...this.state.slots]});
    }
    try {
      const result=await this._hass.callWS({type:'call_service',domain:'pzp_web',service:'schedule',service_data:data,return_response:true});
      this.state=result.response;this.renderState();
      status.textContent=['set','day_set'].includes(action)?'Změna ověřena v čerpadle.':'';
    }catch(error){status.className='status error';status.textContent=error.message||'Spojení se nezdařilo. Obnovte zobrazení.';this.state=null;this.shadowRoot.querySelector('.grid').replaceChildren()}
    finally{this.busy=false;for(const el of this.shadowRoot.querySelectorAll('button,select'))el.disabled=el.classList.contains('slot')&&!this.state?.available}
  }
  renderState(){
    const s=this.state;if(!s||!Array.isArray(s.slots)||s.slots.length!==12)throw new Error('Neplatná odpověď čerpadla.');
    this.shadowRoot.querySelector('.day').textContent=s.day;
    const [hour,minute]=s.start.split(':').map(Number);const start=hour*60+minute;
    const time=n=>String(Math.floor((n%1440)/60)).padStart(2,'0')+':'+String(n%60).padStart(2,'0');
    this.shadowRoot.querySelector('.hours').textContent=s.start+' – '+time(start+180);
    const grid=this.shadowRoot.querySelector('.grid');grid.replaceChildren();
    s.slots.forEach((active,i)=>{const b=document.createElement('button');b.className='slot';b.setAttribute('aria-pressed',String(active));b.disabled=!s.available;
      const label=document.createElement('span');label.textContent=time(start+i*15);const detail=document.createElement('span');detail.className='small';detail.textContent=active?'Zapnuto':'Vypnuto';
      b.append(label,detail);b.addEventListener('click',()=>this.run('set',i));grid.append(b)});
  }
}
customElements.define('pzp-schedule-card',PzpScheduleCard);
window.customCards=window.customCards||[];
window.customCards.push({type:'pzp-schedule-card',name:'Časové programy PZP',description:'Časové programy uložené v regulátoru PZP.'});
