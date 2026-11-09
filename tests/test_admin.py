import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT=Path(__file__).parents[1]
spec=importlib.util.spec_from_file_location('pzp_admin_client',ROOT/'custom_components/pzp_web/client.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class AdminFake(m.PzpClient):
    def __init__(self):
        super().__init__('192.0.2.10','test','test-only')
        self.pages={};self.posts=[];self.lost=False
        for c in self.admin_catalog.values():
            r=ET.Element('PAGE');ET.SubElement(r,'ACCESS',UCID=c['version'])
            for name in c['symbols']:ET.SubElement(r,'INPUT',NAME=name,VALUE='0')
            self.pages[c['page']]=r
    def _read_page(self,path):return self.pages[path]
    def values(self,section):return self.pages[self.admin_catalog[section]['page']].findall('INPUT')
    def _post_command(self,path,symbol,value):
        self.posts.append((path,symbol,value))
        for i in self.pages[path].findall('INPUT'):
            if i.get('NAME')==symbol:i.set('VALUE',str(value))
        if self.lost:raise m.PzpError('lost')
    def _request(self,path,data=None,**kw):
        from urllib.parse import parse_qs
        self.posts.append((path,data))
        values=parse_qs(data.decode(),keep_blank_values=True)
        for i in self.pages[path].findall('INPUT'):
            if i.get('NAME') in values:i.set('VALUE',values[i.get('NAME')][0])
        if self.lost:raise m.PzpError('lost')
        return self.base+path,'<PAGE/>'


class AdminTests(unittest.TestCase):
    def setUp(self):
        self.c=AdminFake();p=patch.object(m.time,'sleep');p.start();self.addCleanup(p.stop)
    def test_read_only_never_posts(self):
        for key in self.c.admin_catalog:self.c.admin_view(key)
        self.assertEqual(self.c.posts,[])
    def test_secret_never_in_result(self):
        for section,index in [('credentials',1),('credentials',2),('weather',5),('email',9),('faults',9)]:
            self.c.values(section)[index].set('VALUE','private-test-secret')
            result=json.dumps(self.c.admin_view(section))
            self.assertNotIn('private-test-secret',result)
    def test_reject_unknown_token_before_write(self):
        with self.assertRaises(m.PzpError):self.c.admin_action({'section':'clock','token':'bad','action':'set','field':'dst','value':True})
        self.assertEqual(self.c.posts,[])
    def test_boolean_lost_reply_is_read_back_and_not_replayed(self):
        s=self.c.admin_view('clock');self.c.lost=True
        r=self.c.admin_action({'section':'clock','token':s['token'],'action':'set','field':'dst','value':True})
        self.assertTrue(next(f for f in r['fields'] if f['key']=='dst')['value'])
        self.assertEqual(len(self.c.posts),1)
        with self.assertRaises(m.PzpError):self.c.admin_action({'section':'clock','token':s['token'],'action':'set','field':'dst','value':True})
        self.assertEqual(len(self.c.posts),1)
    def test_stale_value_rejected(self):
        s=self.c.admin_view('clock');self.c.values('clock')[4].set('VALUE','1')
        with self.assertRaises(m.PzpError):self.c.admin_action({'section':'clock','token':s['token'],'action':'set','field':'dst','value':True})
        self.assertEqual(self.c.posts,[])
    def test_unsupported_firmware_read_and_write_closed(self):
        self.c.pages['/PAGE34.XML'].find('ACCESS').set('UCID','unknown')
        with self.assertRaises(m.UnsupportedFirmware):self.c.admin_view('clock')
        self.assertEqual(self.c.posts,[])
    def test_hidden_editor_cannot_open(self):
        s=self.c.admin_view('room2')
        with self.assertRaises(m.PzpError):self.c.admin_action({'section':'room2','token':s['token'],'action':'open','field':'RM220'})
        self.assertEqual(self.c.posts,[])
    def test_form_encodes_special_characters_once_and_readbacks(self):
        s=self.c.admin_view('weather');value='a&b=č % +'
        r=self.c.admin_action({'section':'weather','token':s['token'],'action':'form','changes':{'city':value}})
        self.assertEqual(next(f for f in r['fields'] if f['key']=='city')['value'],value)
        self.assertEqual(len(self.c.posts),1)
        self.assertIn(b'__T704AB271_BOOL_i=1',self.c.posts[0][1])
    def test_unknown_field_cannot_write_arbitrary_symbol(self):
        s=self.c.admin_view('weather')
        with self.assertRaises(m.PzpError):self.c.admin_action({'section':'weather','token':s['token'],'action':'form','changes':{'WR50000':'1'}})
        self.assertEqual(self.c.posts,[])
    def test_oversized_utf8_value_rejected(self):
        s=self.c.admin_view('weather')
        with self.assertRaises(ValueError):self.c.admin_action({'section':'weather','token':s['token'],'action':'form','changes':{'city':'č'*21}})
        self.assertEqual(self.c.posts,[])
    def test_pulse_lost_reply_never_retried(self):
        s=self.c.admin_view('remote');self.c.lost=True
        with self.assertRaises(m.WriteUncertain):self.c.admin_action({'section':'remote','token':s['token'],'action':'pulse','field':'reset'})
        self.assertEqual(len(self.c.posts),1)

    def prepare_editor(self):
        cfg=self.c.admin_catalog['room1'];f=next(x for x in cfg['fields'] if x['key']=='RM100')
        self.c.values('room1')[f['visible']].set('VALUE','1')
        r=ET.Element('PAGE');ET.SubElement(r,'ACCESS',UCID=f['editor_version'])
        for i,name in enumerate(f['editor_symbols']):ET.SubElement(r,'INPUT',NAME=name,VALUE='RM100: CIB' if i==1 else '0')
        self.c.pages[f['editor']]=r
        s=self.c.admin_view('room1');return self.c.admin_action({'section':'room1','token':s['token'],'action':'open','field':'RM100'})

    def test_editor_lost_key_reply_never_sends_commit(self):
        s=self.prepare_editor();self.c.lost=True
        with self.assertRaises(m.WriteUncertain):self.c.admin_action({'section':'room1','token':s['token'],'action':'key','field':'RM100','key':1})
        self.assertEqual([p[2] for p in self.c.posts],[99,1])

    def test_editor_changed_by_another_browser_never_commits(self):
        s=self.prepare_editor();self.c.pages['/PAGE372.XML'].findall('INPUT')[0].set('VALUE','ABCD')
        with self.assertRaises(m.PzpError):self.c.admin_action({'section':'room1','token':s['token'],'action':'commit','field':'RM100'})
        self.assertEqual([p[2] for p in self.c.posts],[99])

    def test_editor_cannot_smuggle_enter_as_key(self):
        s=self.prepare_editor()
        with self.assertRaises(ValueError):self.c.admin_action({'section':'room1','token':s['token'],'action':'key','field':'RM100','key':14})
        self.assertEqual([p[2] for p in self.c.posts],[99])

    def test_cib_address_bytes_in_native_display_order(self):
        nodes=self.c.values('room1')
        for i,v in [(16,'C'),(17,'6'),(18,'4'),(19,'3')]:nodes[i].set('VALUE',v)
        s=self.c.admin_view('room1')
        self.assertEqual(next(f for f in s['fields'] if f['key']=='RM100')['value'],'346C')

    def test_clock_can_open_after_natural_minute_tick(self):
        cfg=self.c.admin_catalog['clock'];f=next(x for x in cfg['fields'] if x['key']=='clock')
        r=ET.Element('PAGE');ET.SubElement(r,'ACCESS',UCID=f['editor_version'])
        for i,name in enumerate(f['editor_symbols']):ET.SubElement(r,'INPUT',NAME=name,VALUE='Datum a čas' if i==1 else '1')
        self.c.pages[f['editor']]=r
        self.c.values('clock')[0].set('VALUE','12:30');s=self.c.admin_view('clock')
        self.c.values('clock')[0].set('VALUE','12:31')
        result=self.c.admin_action({'section':'clock','token':s['token'],'action':'open','field':'clock'})
        self.assertEqual(result['editor'],'clock')
        self.assertEqual([p[2] for p in self.c.posts],[99])


class DayFake(m.PzpClient):
    def __init__(self):
        super().__init__('192.0.2.10','test','test-only');self.day='Pondělí';self.hour=0;self.bits=[False]*96;self.posts=[];self.lost=False
    def _schedule_state(self,code):
        return {'program':code,'day':self.day,'start':f'{self.hour:02}:00','available':True,'name':'Test',
                'slots':self.bits[self.hour*4:self.hour*4+12],'_symbols':[str(self.hour*4+i) for i in range(12)]}
    def _post_command(self,path,symbol,value):
        self.posts.append((symbol,value))
        if symbol==m.SCHEDULES['R046']['command']:
            if value==3:self.hour=max(0,self.hour-1)
            if value==4:self.hour=min(21,self.hour+1)
        else:
            self.bits[int(symbol)]=bool(value)
            if self.lost:raise m.PzpError('lost')


class DayTests(unittest.TestCase):
    def test_full_day_read_is_navigation_only_and_restores_view(self):
        c=DayFake();c.hour=4;r=c.schedule({'program':'R046','action':'day_view','day':c.day,'start':'04:00'})
        self.assertEqual(r['day_slots'],[False]*96);self.assertEqual(c.hour,4)
        self.assertTrue(all(s==m.SCHEDULES['R046']['command'] and v in (3,4) for s,v in c.posts))
    def test_day_stale_snapshot_has_no_settings_writes(self):
        c=DayFake();c.bits[95]=True
        with self.assertRaises(m.PzpError):c.schedule({'program':'R046','action':'day_set','day':c.day,'start':'00:00','day_slots':[True]*96,'expected_day_slots':[False]*96})
        self.assertTrue(all(s==m.SCHEDULES['R046']['command'] and v in (3,4) for s,v in c.posts))
    def test_day_writes_exactly_changed_slots_and_verifies_all(self):
        c=DayFake();desired=[i in (0,20,95) for i in range(96)]
        r=c.schedule({'program':'R046','action':'day_set','day':c.day,'start':'00:00','day_slots':desired,'expected_day_slots':[False]*96})
        self.assertEqual(r['day_slots'],desired)
        self.assertEqual(len([s for s,v in c.posts if s!=m.SCHEDULES['R046']['command']]),3)
    def test_day_lost_write_never_replayed(self):
        c=DayFake();c.lost=True
        with self.assertRaises(m.WriteUncertain):c.schedule({'program':'R046','action':'day_set','day':c.day,'start':'00:00','day_slots':[True]*96,'expected_day_slots':[False]*96})
        self.assertEqual(len([s for s,v in c.posts if s!=m.SCHEDULES['R046']['command']]),1)


if __name__=='__main__':unittest.main()
