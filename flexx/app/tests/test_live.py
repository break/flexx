""" Test a live app connection.
"""

import os
import sys
from flexx import app, event, webruntime

from flexx.util.testing import run_tests_if_main, raises, skip


ON_TRAVIS = os.getenv('TRAVIS', '') == 'true'
ON_PYPY = '__pypy__' in sys.builtin_module_names


def runner(cls):
    t = app.launch(cls, 'firefox')
    t.test_init()
    app.call_later(5, app.stop)
    app.run()
    if not (ON_TRAVIS and ON_PYPY):  # has intermittent fails on pypy3
        t.test_check()


class ModelA(app.Model):
    
    @event.prop
    def foo1(self, v=0):
        return float(v+1)
    
    @event.prop
    def foo2(self, v=0):
        return float(v+1)

    @event.prop
    def result(self, v=''):
        if v:
            app.stop()
        return str(v)
    
    def test_init(self):
        self.call_js('set_result()')
    
    def test_check(self):
        assert self.foo1 == 1
        assert self.foo2 == 1
        #
        assert self.bar1 == 1
        assert self.bar2 == 1
        #
        assert self.result == '1 1 - 1 1'
        print('A ok')
    
    class JS:
        
        @event.prop
        def bar1(self, v=0):
            return int(v+1)
        
        @event.prop
        def bar2(self, v=0):
            return int(v+1)
        
        def set_result(self):
            self.result = ' '.join([self.foo1, self.foo2, '-',
                                    self.bar1, self.bar2])

class ModelB(ModelA):
    
    @event.prop
    def foo2(self, v=0):
        return int(v+2)
    
    @event.prop
    def foo3(self, v=0):
        return int(v+2)
    
    def test_check(self):
        assert self.foo1 == 1
        assert self.foo2 == 2
        assert self.foo3 == 2
        #
        assert self.bar1 == 1
        assert self.bar2 == 2
        assert self.bar3 == 2
        #
        assert self.result == '1 2 2 - 1 2 2'
        print('B ok')
    
    class JS:
        
        @event.prop
        def bar2(self, v=0):
            return int(v+2)
        
        @event.prop
        def bar3(self, v=0):
            return int(v+2)
        
        def set_result(self):
            self.result = ' '.join([self.foo1, self.foo2, self.foo3, '-',
                                    self.bar1, self.bar2, self.bar3])


class ModelC(ModelB):
    # Test properties and proxy properties, no duplicates etc.
    
    def test_check(self):
        py_result = ' '.join(self.__properties__) + ' - ' + ' '.join(self.__proxy_properties__)
        js_result = self.result
        assert py_result == 'bar1 bar2 bar3 foo1 foo2 foo3 result - bar1 bar2 bar3'
        assert js_result == 'bar1 bar2 bar3 foo1 foo2 foo3 result - foo1 foo2 foo3 result'
        print('C ok')
    
    class JS:
        
        @event.prop
        def bar2(self, v=0):
            return int(v+2)
        
        @event.prop
        def bar3(self, v=0):
            return int(v+2)
        
        def set_result(self):
            self.result = ' '.join(self.__properties__) + ' - ' + ' '.join(self.__proxy_properties__)

##


def test_generated_javascript():
    # Test that there are no diplicate funcs etc.
    
    codeA, codeB = ModelA.JS.CODE, ModelB.JS.CODE
    
    assert codeA.count('_foo1_func = function') == 1
    assert codeA.count('_foo2_func = function') == 1
    assert codeA.count('_foo3_func = function') == 0
    assert codeA.count('_bar1_func = function') == 1
    assert codeA.count('_bar2_func = function') == 1
    assert codeA.count('_bar3_func = function') == 0
    
    assert codeB.count('_foo1_func = function') == 0
    assert codeB.count('_foo2_func = function') == 0  # proxy needs no new func
    assert codeB.count('_foo3_func = function') == 1
    assert codeB.count('_bar1_func = function') == 0
    assert codeB.count('_bar2_func = function') == 1  # but real prop does
    assert codeB.count('_bar3_func = function') == 1


def test_apps():
    
    if not webruntime.has_firefox():
        skip('This live test needs firefox.')
    
    runner(ModelA)
    runner(ModelB)
    runner(ModelC)


test_generated_javascript()
runner(ModelC)
# test_apps()
# run_tests_if_main()
#if __name__ == '__main__':
#    test_apps()
