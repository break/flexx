"""
Test the main use of the event loop.
"""

from flexx.util.testing import run_tests_if_main, skipif, skip, raises
from flexx.event.both_tester import run_in_both

from flexx import event
from flexx.event._dict import isidentifier

loop = event.loop


class Foo(event.Component):
    
    def __init__(self):
        super().__init__()
        self.r = []
        print('init')
    
    @event.reaction('!foo')
    def on_foo(self, *events):
        self.r.append(len(events))
        print(len(events))


## Tests for both

@run_in_both()
def test_calllater():
    """
    xx
    called later
    called later
    """
    def x():
        print('called later')
    loop.call_soon(x)
    loop.call_soon(x)
    print('xx')
    loop.iter()


@run_in_both(Foo)
def test_iter():
    """
    init
    -
    1
    init
    -
    2
    """
    foo = Foo()
    foo.emit('foo', {})
    print('-')
    loop.iter()
    
    foo = Foo()
    foo.emit('foo', {})
    foo.emit('foo', {})
    print('-')
    loop.iter()


@run_in_both()
def test_iter_fail():
    """
    1
    ok
    1
    ? AttributeError
    """
    # Failing func call
    res = []
    def fail():
        print('1')
        raise AttributeError('xx')
    
    try:
        fail()
        print('bad')
    except AttributeError:
        print('ok')
    
    # When handled by the loop, error is printed, but no fail
    loop.call_soon(fail)
    loop.iter()


@run_in_both(Foo)
def test_context():
    """
    init
    1
    init
    2
    """
    foo = Foo()
    with loop:
        foo.emit('foo', {})
    
    foo = Foo()
    with loop:
        foo.emit('foo', {})
        foo.emit('foo', {})
    
    assert not loop.is_processing_actions()


@run_in_both(Foo)
def test_loop_reset():
    """
    init
    -
    1
    """
    foo = Foo()
    foo.emit('foo', {})
    foo.emit('foo', {})
    foo.emit('foo', {})
    
    loop.reset()
    loop.iter()
    print('-')
    
    foo.emit('foo', {})
    foo.emit('foo', {})
    loop.reset()
    foo.emit('foo', {})
    loop.iter()

    
@run_in_both(Foo)
def test_loop_cannot_call_iter():
    """
    ? Cannot call
    """
    def callback():
        try:
            loop.iter()
        except RuntimeError as err:
            print(err)
    
    loop.call_soon(callback)
    loop.iter()


## Tests for only Python


def test_loop_asyncio():
    import asyncio
    
    aio_loop = asyncio.new_event_loop()
    loop.integrate(aio_loop, reset=False)
    
    res = []
    def callback():
        res.append(1)
    
    loop.call_soon(callback)
    aio_loop.stop()
    aio_loop.run_forever()
    
    assert len(res) == 1
    
    # Now run wrong loop
    aio_loop = asyncio.new_event_loop()
    # loop.integrate(aio_loop, reset=False)  -> dont do this (yet)
    
    loop.call_soon(callback)
    aio_loop.stop()
    aio_loop.run_forever()
    
    assert len(res) == 1
    
    loop.integrate(aio_loop, reset=False)  # but do it now
    aio_loop.stop()
    aio_loop.run_forever()
    
    aio_loop.stop()
    aio_loop.run_forever()
    
    assert len(res) == 2


def xx_disabled_test_integrate():
    
    res = []
    def calllater(f):
        res.append(f)
    
    ori = event.loop._call_soon_func
    
    foo = Foo()
    event.loop.integrate(calllater)
    foo.emit('foo', {})
    foo.emit('foo', {})
    assert len(res) == 1 and res[0].__name__ == 'iter'
    
    with raises(ValueError):
        event.loop.integrate('not a callable')
    
    event.loop._call_soon_func = ori


run_tests_if_main()
