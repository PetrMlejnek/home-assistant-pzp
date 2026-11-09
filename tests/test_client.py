import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

path = Path(__file__).parents[1] / "custom_components/pzp_web/client.py"
spec = importlib.util.spec_from_file_location("pzp_client", path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class FakeClient(m.PzpClient):
    def __init__(self, *, lost_reply=False, apply_write=True, offline=False):
        super().__init__("192.0.2.10", "test", "not-a-real-password")
        self.season = "Léto"
        self.posts = 0
        self.reads = 0
        self.lost_reply = lost_reply
        self.apply_write = apply_write
        self.offline = offline

    def read_state(self):
        self.reads += 1
        if self.offline:
            raise m.PzpError("offline")
        return {"season": self.season, "period_mode": "Ruční", "season_visible": True}

    def _request(self, path, data=None, **kwargs):
        assert path == "/PAGE40.XML"
        assert data == b"__TC9AFA189_SINT_d%3D99"
        self.posts += 1
        if self.apply_write:
            self.season = "Topná sezóna" if self.season == "Léto" else "Léto"
        if self.lost_reply:
            raise m.PzpError("reply lost")
        return self.base + path, "<PAGE/>"


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.sleep_patch = patch.object(m.time, "sleep")
        self.sleep_patch.start()
        self.addCleanup(self.sleep_patch.stop)

    def test_same_value_never_writes(self):
        c = FakeClient()
        self.assertEqual(c.set_season("Léto")["season"], "Léto")
        self.assertEqual(c.posts, 0)

    def test_lost_reply_applied_once_is_confirmed_by_read(self):
        c = FakeClient(lost_reply=True)
        self.assertEqual(c.set_season("Topná sezóna")["season"], "Topná sezóna")
        self.assertEqual(c.posts, 1)

    def test_lost_reply_unapplied_is_never_retried(self):
        c = FakeClient(lost_reply=True, apply_write=False)
        with self.assertRaises(m.WriteUncertain):
            c.set_season("Topná sezóna")
        self.assertEqual(c.posts, 1)

    def test_offline_rejects_before_any_write(self):
        c = FakeClient(offline=True)
        with self.assertRaises(m.PzpError):
            c.set_season("Topná sezóna")
        self.assertEqual(c.posts, 0)
        c.offline = False
        self.assertEqual(c.read_state()["season"], "Léto")
        self.assertEqual(c.posts, 0)

    def test_bad_option_never_writes(self):
        c = FakeClient()
        with self.assertRaises(ValueError):
            c.set_season("invalid")
        self.assertEqual(c.posts, 0)

    def test_unknown_page_version_fails_closed(self):
        root = ET.fromstring('<PAGE><ACCESS UCID="unknown"/></PAGE>')
        with self.assertRaises(m.UnsupportedFirmware):
            m.PzpClient.parse_season_page(root)

    def test_expected_page_mapping(self):
        values = ["1", "1", "Volba období", "Režim změny období", "Ruční", "Léto",
                  "1", "Vytápění v letním období", "Ne", "0", "Chlazení", "Ne"]
        root = ET.Element("PAGE")
        ET.SubElement(root, "ACCESS", UCID=m.EXPECTED_PAGE_VERSION)
        for value in values:
            ET.SubElement(root, "INPUT", VALUE=value)
        state = m.PzpClient.parse_season_page(root)
        self.assertEqual(state["season"], "Léto")
        self.assertEqual(state["period_mode"], "Ruční")
        self.assertTrue(state["season_visible"])

    def test_redirect_cannot_send_auth_to_another_host(self):
        handler = m.LocalRedirects("192.0.2.10")
        with self.assertRaises(m.PzpError):
            handler.redirect_request(None, None, 302, "", {}, "http://example.com/")


class FakeNumericClient(m.PzpClient):
    def __init__(self, *, fail_key=None, wrong_buffer=False, unavailable=False):
        super().__init__('192.0.2.10','test','not-a-real-password')
        self.catalog={'R043': {'kind':'numeric','decimals':1,'code':'R043','page':'/main',
                              'editor':'/editor','command':'cmd'}}
        self.value='-8.0'
        self.buffer=''
        self.commands=[]
        self.fail_key=fail_key
        self.wrong_buffer=wrong_buffer
        self.unavailable=unavailable

    def _read_page(self, path):
        return None

    def _parameter_value(self, cfg, root):
        return {'value':self.value,'available':not self.unavailable}

    def _editor_value(self, cfg):
        if self.wrong_buffer and self.buffer=='12.3':return '123.0'
        return self.buffer

    def _post_command(self, page, symbol, key):
        self.commands.append(key)
        if key==99:self.buffer=self.value
        elif key==13:self.buffer=''
        elif key==14:self.value=self.buffer
        elif key==10:self.buffer+='-'
        elif key==11:self.buffer+='.'
        else:self.buffer+=str(key)
        if key==self.fail_key:raise m.PzpError('reply lost')


class NumericTests(unittest.TestCase):
    def setUp(self):
        p=patch.object(m.time,'sleep');p.start();self.addCleanup(p.stop)

    def test_typing_failure_never_commits_or_replays(self):
        c=FakeNumericClient(fail_key=2)
        with self.assertRaises(m.PzpError):c.set_numeric('R043','12.3')
        self.assertNotIn(14,c.commands)
        self.assertEqual(c.commands.count(2),1)
        self.assertEqual(c.value,'-8.0')

    def test_wrong_prepared_value_never_commits(self):
        c=FakeNumericClient(wrong_buffer=True)
        with self.assertRaises(m.PzpError):c.set_numeric('R043','12.3')
        self.assertNotIn(14,c.commands)
        self.assertEqual(c.value,'-8.0')

    def test_commit_reply_lost_verifies_without_replay(self):
        c=FakeNumericClient(fail_key=14)
        self.assertEqual(c.set_numeric('R043','12.3'),'12.3')
        self.assertEqual(c.commands.count(14),1)

    def test_same_value_never_opens_editor(self):
        c=FakeNumericClient()
        self.assertEqual(c.set_numeric('R043','-8,0'),'-8.0')
        self.assertEqual(c.commands,[])

    def test_hidden_parameter_cannot_be_written(self):
        c=FakeNumericClient(unavailable=True)
        with self.assertRaises(m.PzpError):c.set_numeric('R043','12.3')
        self.assertEqual(c.commands,[])

    def test_invalid_values_fail_before_any_command(self):
        for value in ['nan','Infinity','1e2','1.23','1;anything','1234567890']:
            c=FakeNumericClient()
            with self.assertRaises(ValueError):c.set_numeric('R043',value)
            self.assertEqual(c.commands,[])

    def test_signed_decimal_sequence_and_one_confirmation(self):
        c=FakeNumericClient()
        self.assertEqual(c.set_numeric('R043','-9.5'),'-9.5')
        self.assertEqual(c.commands,[99,13,10,9,11,5,14])


class FakeScheduleClient(m.PzpClient):
    def __init__(self, *, lost_write=False, bad_readback=False):
        super().__init__('192.0.2.10','test','not-a-real-password')
        self.state={'program':'R046','name':'Útlum topení','available':True,'day':'Pondělí',
                    'start':'00:00','slots':[False]*12,'_symbols':['slot'+str(i) for i in range(12)]}
        self.posts=[]
        self.lost_write=lost_write
        self.bad_readback=bad_readback

    def _schedule_state(self, code):
        return {**self.state,'slots':list(self.state['slots'])}

    def _post_command(self,page,symbol,value):
        self.posts.append((symbol,value))
        if symbol.startswith('slot'):
            if not self.bad_readback:self.state['slots'][int(symbol[4:])]=bool(value)
            if self.lost_write:raise m.PzpError('reply lost')


class ScheduleTests(unittest.TestCase):
    def request(self, **extra):
        return {'program':'R046','action':'set','slot':0,'value':True,
                'day':'Pondělí','start':'00:00','expected_slots':[False]*12,**extra}

    def test_stale_view_does_not_write_another_day(self):
        c=FakeScheduleClient()
        with self.assertRaises(m.PzpError):c.schedule(self.request(day='Úterý'))
        self.assertEqual(c.posts,[])

    def test_changed_slots_abort_without_overwriting(self):
        c=FakeScheduleClient();c.state['slots'][11]=True
        with self.assertRaises(m.PzpError):c.schedule(self.request())
        self.assertEqual(c.posts,[])

    def test_lost_reply_never_replays_or_commits(self):
        c=FakeScheduleClient(lost_write=True)
        with self.assertRaises(m.WriteUncertain):c.schedule(self.request())
        self.assertEqual(c.posts,[('slot0',1)])

    def test_invalid_readback_never_commits(self):
        c=FakeScheduleClient(bad_readback=True)
        with self.assertRaises(m.WriteUncertain):c.schedule(self.request())
        self.assertEqual(c.posts,[('slot0',1)])

    def test_success_writes_only_one_slot_and_confirms(self):
        c=FakeScheduleClient();result=c.schedule(self.request())
        self.assertEqual(result['slots'],[True]+[False]*11)
        self.assertEqual(c.posts,[('slot0',1),(m.SCHEDULES['R046']['command'],5)])
        self.assertNotIn('_symbols',result)

    def test_identical_requested_slot_is_read_only(self):
        c=FakeScheduleClient();c.schedule(self.request(value=False))
        self.assertEqual(c.posts,[])

    def test_initial_view_never_posts(self):
        c=FakeScheduleClient();c.schedule({'program':'R046'})
        self.assertEqual(c.posts,[])


class HistoryTests(unittest.TestCase):
    def test_unknown_firmware_prevents_navigation(self):
        c=m.PzpClient('192.0.2.10','test','not-a-real-password')
        with patch.object(c,'_read_page',return_value=ET.fromstring('<PAGE><ACCESS UCID="unknown"/></PAGE>')),patch.object(c,'_post_command') as post:
            with self.assertRaises(m.UnsupportedFirmware):c.history({'action':'newest'})
            post.assert_not_called()

    def test_view_has_no_navigation_or_plant_commands(self):
        c=m.PzpClient('192.0.2.10','test','not-a-real-password')
        with patch.object(c,'_history_detail',return_value={'description':'event'}),patch.object(c,'_post_command') as post:
            self.assertEqual(c.history({'action':'view'}),{'description':'event'})
            post.assert_not_called()

    def test_missing_next_record_does_not_navigate(self):
        c=m.PzpClient('192.0.2.10','test','not-a-real-password')
        with patch.object(c,'_history_detail',return_value={'has_older':False}),patch.object(c,'_post_command') as post:
            c.history({'action':'older'})
            post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
