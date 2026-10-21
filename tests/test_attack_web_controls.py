"""HTML constraints must accept the editor's displayed, derived decimal values."""
from html.parser import HTMLParser
from pathlib import Path
import math
import unittest

class Controls(HTMLParser):
    def __init__(self):
        super().__init__();self.inputs={}
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='input' and 'id' in attrs:self.inputs[attrs['id']]=attrs

class DecimalControlTests(unittest.TestCase):
    def setUp(self):
        parser=Controls();parser.feed((Path(__file__).resolve().parents[1]/'tools/attack_web/index.html').read_text(encoding='utf-8'));self.inputs=parser.inputs
    def assert_representable(self,identity,value):
        attrs=self.inputs[identity]
        self.assertGreaterEqual(value,float(attrs['min']))
        self.assertLessEqual(value,float(attrs['max']))
        if attrs.get('step')!='any':
            units=(value-float(attrs['min']))/float(attrs['step'])
            self.assertTrue(math.isclose(units,round(units),abs_tol=1e-7),(identity,value,attrs['step']))
    def test_derived_and_imported_decimals_can_be_saved(self):
        for name,value in [('interval',round(1.5/1.4,2)),('speed',1.33),('radius',23.5),('direction',12.34),('range',1.07),('spacing',20.15)]:
            with self.subTest(control=name):
                self.assert_representable(name,value)
                self.assert_representable(name+'Number',value)
    def test_integer_count_and_guidance_tenths_stay_constrained(self):
        self.assertEqual(self.inputs['countNumber']['step'],'1')
        self.assertEqual(self.inputs['trackingNumber']['step'],'0.1')
        self.assert_representable('groupDelay',.25)
        self.assert_representable('groupDelayNumber',.25)
