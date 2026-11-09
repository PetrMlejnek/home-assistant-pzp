"""Exercise the server authorization boundary without installing HA locally."""
import importlib.util
from pathlib import Path
import sys,types,unittest
from unittest.mock import patch
class Forbidden(Exception):
    def __init__(self,reason=None):super().__init__(reason)
web=types.SimpleNamespace(HTTPForbidden=Forbidden,HTTPNotFound=type('NotFound',(Exception,),{}),
                          json_response=lambda value,status=200:types.SimpleNamespace(status=status,headers={}))

base=Path(__file__).parents[1]/'custom_components/pzp_web'
client_spec=importlib.util.spec_from_file_location('pzp_access_test.client',base/'client.py')
client=importlib.util.module_from_spec(client_spec);client_spec.loader.exec_module(client)
fake_http=types.ModuleType('homeassistant.components.http')
fake_http.HomeAssistantView=type('HomeAssistantView',(),{'json':staticmethod(lambda value,status_code=200:web.json_response(value,status=status_code))})
fake_aiohttp=types.ModuleType('aiohttp');fake_aiohttp.web=web
with patch.dict(sys.modules,{'pzp_access_test':types.ModuleType('pzp_access_test'),'pzp_access_test.client':client,'homeassistant.components.http':fake_http,'aiohttp':fake_aiohttp}):
    spec=importlib.util.spec_from_file_location('pzp_access_test.admin',base/'admin.py');admin=importlib.util.module_from_spec(spec);spec.loader.exec_module(admin)

class Request(dict):
    query={}

def immediate(coroutine):
    try:coroutine.send(None)
    except StopIteration as result:return result.value
    raise AssertionError('Unauthorized requests must not await device or body access')

class AccessTests(unittest.TestCase):
    def setUp(self):
        self.lookups=[]
        def entry(key):
            self.lookups.append(key);return types.SimpleNamespace(domain='pzp_web')
        self.hass=types.SimpleNamespace(config_entries=types.SimpleNamespace(async_get_entry=entry),data={})
        self.view=admin.PzpAdminView(self.hass)
    def test_anonymous_read_denied_before_entry_lookup(self):
        with self.assertRaises(web.HTTPForbidden):immediate(self.view.get(Request(),'test'))
        self.assertEqual(self.lookups,[])
    def test_non_admin_read_denied_before_device_access(self):
        with self.assertRaises(web.HTTPForbidden):immediate(self.view.get(Request(hass_user=types.SimpleNamespace(is_admin=False)),'test'))
        self.assertEqual(self.lookups,[])
    def test_non_admin_write_denied_before_body_read(self):
        with self.assertRaises(web.HTTPForbidden):immediate(self.view.post(Request(hass_user=types.SimpleNamespace(is_admin=False)),'test'))
        self.assertEqual(self.lookups,[])
    def test_admin_unavailable_result_is_noncacheable(self):
        response=immediate(self.view.get(Request(hass_user=types.SimpleNamespace(is_admin=True)),'test'))
        self.assertEqual(response.status,503);self.assertEqual(response.headers['Cache-Control'],'no-store')

if __name__=='__main__':unittest.main()
