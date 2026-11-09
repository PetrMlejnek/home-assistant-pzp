import { entryReady, resolveEntryId } from './pzp-card-utils.js';
/* Read the controller's event history without changing its operation. */
class PzpHistoryCard extends HTMLElement {
  setConfig(config){
    if(!config.config_entry_id && !config.entity)throw new Error('Zadejte entity nebo config_entry_id integrace PZP.');
    this.config=config;if(!this.shadowRoot)this.attachShadow({mode:'open'});
    this.shadowRoot.innerHTML=`<style>
      ha-card{display:block;padding:20px}h2{margin:0 0 16px;font-size:20px}.nav{display:flex;gap:8px;flex-wrap:wrap}button{font:inherit;background:var(--card-background-color);color:var(--primary-text-color);border:1px solid var(--divider-color);padding:10px;border-radius:8px;cursor:pointer}button:disabled{opacity:.4;cursor:default}h3{font-size:18px;margin-bottom:8px}.meta,.note{font-size:13px;color:var(--secondary-text-color)}table{width:100%;border-collapse:collapse;margin:16px 0}td{padding:7px;border-bottom:1px solid var(--divider-color)}td:last-child{text-align:right}.status{margin-top:12px;font-size:14px}.error{color:var(--error-color)}
      </style><ha-card><h2>Historie událostí čerpadla</h2><div class="nav"><button data-action="newest">Nejnovější</button><button data-action="newer">‹ Novější</button><button data-action="older">Starší ›</button></div><h3 class="description">—</h3><div class="meta"></div><table aria-label="Teploty při události"></table><div class="status" role="status"></div><p class="note">Záznamy uložené přímo v regulátoru, včetně hodnot čidel v okamžiku události. Označení Bxx odpovídá původnímu webu. Prohlížení nemění nastavení čerpadla.</p></ha-card>`;
    for(const b of this.shadowRoot.querySelectorAll('[data-action]'))b.addEventListener('click',()=>this.run(b.dataset.action));
    this.loaded=false;if(entryReady(this.config,this._hass))this.run('newest');
  }
  set hass(hass){this._hass=hass;if(this.config&&!this.loaded&&!this.busy&&entryReady(this.config,hass))this.run('newest')}
  getCardSize(){return 6}
  async run(action){
    if(this.busy||!this._hass)return;this.busy=true;this.loaded=true;
    const status=this.shadowRoot.querySelector('.status');status.className='status';status.textContent='Načítám historii z čerpadla…';
    for(const b of this.shadowRoot.querySelectorAll('button'))b.disabled=true;
    try{
      const result=await this._hass.callWS({type:'call_service',domain:'pzp_web',service:'history',service_data:{config_entry_id:resolveEntryId(this.config,this._hass),action},return_response:true});
      const s=result.response;this.state=s;
      this.shadowRoot.querySelector('.description').textContent=s.available?s.description:'Žádný záznam';
      this.shadowRoot.querySelector('.meta').textContent=s.available?[s.time,s.alarm?'Porucha':'Událost',s.active?'Vznik':'Ukončení'].join(' · '):'';
      const table=this.shadowRoot.querySelector('table');table.replaceChildren();
      if(s.available)for(const [name,value] of Object.entries(s.temperatures)){const row=document.createElement('tr');for(const text of [name,value+' °C']){const td=document.createElement('td');td.textContent=text;row.append(td)}table.append(row)}
      status.textContent='';
    }catch(error){this.state=null;status.className='status error';status.textContent=error.message||'Spojení se nezdařilo.'}
    finally{this.busy=false;for(const b of this.shadowRoot.querySelectorAll('button'))b.disabled=b.dataset.action!=='newest'&&!this.state?.['has_'+b.dataset.action]}
  }
}
customElements.define('pzp-history-card',PzpHistoryCard);
window.customCards=window.customCards||[];
window.customCards.push({type:'pzp-history-card',name:'Historie PZP',description:'Události uložené v regulátoru.'});
