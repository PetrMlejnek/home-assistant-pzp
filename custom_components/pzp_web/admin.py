"""Authenticated administrator API; secret values never use HA service events."""
from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from .client import PzpClient, PzpError


class PzpAdminView(HomeAssistantView):
    url = '/api/pzp_web/{entry_id}/admin'
    name = 'api:pzp_web:admin'
    requires_auth = True

    def __init__(self, hass):
        self.hass = hass

    def _entry(self, request, entry_id):
        user=request.get('hass_user')
        if user is None or not user.is_admin:
            raise web.HTTPForbidden(reason='Nastavení je dostupné pouze správci HA.')
        entry=self.hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain!='pzp_web':raise web.HTTPNotFound()
        return entry

    def _response(self, result, status=200):
        response=self.json(result,status_code=status)
        response.headers['Cache-Control']='no-store'
        return response

    async def get(self, request, entry_id):
        self._entry(request,entry_id)
        coordinator=self.hass.data.get('pzp_web',{}).get(entry_id)
        if coordinator is None:return self._response({'error':'Připojení není načtené. Použijte Obnovit připojení HA.'},503)
        section=request.query.get('section')
        if not section:
            return self._response({'sections':[{'key':k,'name':v['name']} for k,v in coordinator.client.admin_catalog.items()],
                                   'host':coordinator.client.host})
        try:
            result=await self.hass.async_add_executor_job(coordinator.client.admin_view,section)
            return self._response(result)
        except (PzpError,ValueError) as err:return self._response({'error':str(err)},400)

    async def post(self, request, entry_id):
        entry=self._entry(request,entry_id)
        if request.content_length and request.content_length>8192:raise web.HTTPRequestEntityTooLarge(max_size=8192,actual_size=request.content_length)
        try:
            data=await request.json()
            if not isinstance(data,dict):raise ValueError('Neplatný požadavek.')
            if data.get('action')=='connection':
                host=data.get('host',entry.data['host'])
                username=data.get('username') or entry.data['username']
                password=data.get('password') or entry.data['password']
                if not all(isinstance(v,str) for v in (host,username,password)):raise ValueError('Neplatné připojení.')
                client=await self.hass.async_add_executor_job(PzpClient,host,username,password)
                await self.hass.async_add_executor_job(client.read_state)
                self.hass.config_entries.async_update_entry(entry,data={**entry.data,'host':host,'username':username,'password':password})
                await self.hass.config_entries.async_reload(entry_id)
                return self._response({'message':'Připojení webové integrace bylo ověřeno a uloženo.'})
            coordinator=self.hass.data.get('pzp_web',{}).get(entry_id)
            if coordinator is None:raise PzpError('Integrace není načtena. Obnovte připojení HA.')
            result=await self.hass.async_add_executor_job(coordinator.client.admin_action,data)
            credentials=result.pop('_credentials',None)
            if credentials:
                self.hass.config_entries.async_update_entry(entry,data={**entry.data,**credentials})
            return self._response(result)
        except (PzpError,ValueError,TypeError) as err:
            # Native and validation errors are deliberately sanitized, without data or secrets.
            message=str(err) if isinstance(err,PzpError) else 'Neplatné údaje nastavení.'
            return self._response({'error':message},400)
