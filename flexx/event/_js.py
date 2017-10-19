"""
Implementation of flexx.event in JS via PyScript.
"""

import sys
import json

from flexx.pyscript import JSString, py2js as py2js_
from flexx.pyscript.parser2 import get_class_definition

from flexx.event._action import ActionDescriptor, Action
from flexx.event._reaction import ReactionDescriptor, Reaction
from flexx.event._property import Property
from flexx.event._emitter import Emitter
from flexx.event._component import Component


Object = Date = console = setTimeout = undefined = None  # fool pyflake

reprs = json.dumps


def py2js(*args, **kwargs):
    kwargs['inline_stdlib'] = False
    kwargs['docstrings'] = False
    return py2js_(*args, **kwargs)


class ComponentJS:
    """ An implementation of the Component class in PyScript. It has
    some boilerplate code to create actions, reactions, emitters and
    properties, but otherwise shares most of the code with the Python
    classes by transpiling their methods via PyScript. This helps ensure
    that the Python and JS implementation of this event system have the
    same API and behavior.
    
    The Python version of this class has a ``JSCODE`` attribute that
    contains the auto-generated JavaScript for this class.
    """
    
    _REACTION_COUNT = 0
    _IS_COMPONENT = True
    
    def __init__(self, init_handlers=True):
        
        # Init some internal variables
        self.__handlers = {}  # reactions connecting to this component
        self.__props_being_set = {}
        self.__props_ever_set = {}
        self.__pending_events = {}
        
        # Create properties
        for name in self.__properties__:
            self.__handlers.setdefault(name, [])
            self['_' + name + '_value'] = None  # need *something*
        for name in self.__properties__:
            func = self['_' + name + '_func']
            creator = self['__create_' + func.emitter_type]
            self.__create_Property(name)
            if func.default is not undefined:
                self._set_prop(name, func.default, True)
        
        # Create emitters
        for name in self.__emitters__:
            self.__handlers.setdefault(name, [])
            func = self[name]
            self.__create_Emitter(func, name)
        
        # Init handlers and properties now, or later?
        if init_handlers:
            self._init_handlers()
    
    def __init_handlers(self):
        # Create (and connect) handlers
        for name in self.__reactions__:
            func = self[name]
            self[name] = self.__create_Handler(func, name, func._connection_strings)
    
    def __connect(self, *connection_strings):
        # The JS version (no decorator functionality)
        
        if len(connection_strings) < 2:
            raise RuntimeError('connect() (js) needs a function and one or ' +
                               'more connection strings.')
        
        # Get callable
        if callable(connection_strings[0]):
            func = connection_strings[0]
            connection_strings = connection_strings[1:]
        elif callable(connection_strings[-1]):
            func = connection_strings[-1]
            connection_strings = connection_strings[:-1]
        else:
            raise TypeError('connect() decorator requires a callable.')
        
        # Verify connection strings
        for s in connection_strings:
            if not (isinstance(s, str) and len(s)):
                raise ValueError('Connection string must be nonempty strings.')
        
        # Get function name (Flexx sets __name__ on methods)
        name = func.__name__ or func.name or 'anonymous'
        name = name.split(' ')[-1].split('flx_')[-1]
        return self.__create_Handler(func, name, connection_strings)
    
    def __create_Property(self, name):
        private_name = '_' + name + '_value'
        def getter():
            return self[private_name]
        def setter(x):
            self._set_prop(name, x)
        opts = {'enumerable': True, 'configurable': True,  # i.e. overloadable
                'get': getter, 'set': setter}
        Object.defineProperty(self, name, opts)
    
    def __create_Readonly(self, name):
        private_name = '_' + name + '_value'
        def getter():
            return self[private_name]
        def setter(x):
            raise AttributeError('Readonly %s is not settable' % name)
        opts = {'enumerable': True, 'configurable': True,  # i.e. overloadable
                'get': getter, 'set': setter}
        Object.defineProperty(self, name, opts)
    
    def __create_Emitter(self, emitter_func, name):
        # Keep a ref to the emitter func, which is a class attribute. The object
        # attribute with the same name will be overwritten with the property below.
        # Because the class attribute is the underlying function, super() works.
        def func(*args):  # this func should return None, so super() works correct
            ev = emitter_func.apply(self, args)
            if ev is not None:
                self.emit(name, ev)
        def getter():
            return func
        def setter(x):
            raise AttributeError('Emitter %s is not settable' % name)
        opts = {'enumerable': True, 'configurable': True,  # i.e. overloadable
                'get': getter, 'set': setter}
        Object.defineProperty(self, name, opts)
    
    def __create_Handler(self, handler_func, name, connection_strings):
        # Keep ref to the handler function, see comment in create_Emitter().
        
        # Create function that becomes our "handler object"
        def handler(*events):
            return handler_func.apply(self, events)
        
        # Attach methods to the function object (this gets replaced)
        HANDLER_METHODS_HOOK  # noqa
        
        # Init handler
        that = self
        Component.prototype._REACTION_COUNT += 1
        handler._name = name
        handler._id = 'h' + str(Component.prototype._REACTION_COUNT)
        handler._ob1 = lambda : that  # no weakref in JS
        handler._init(connection_strings, self)
        
        return handler


class Loop:
    
    def __init__(self):
        self._pending_calls = []
        self._scheduled = False
    
    def call_later(self, func):
        """ Call the given function in the next iteration of the "event loop".
        """
        self._pending_calls.append(func)
        if not self._scheduled:
            self._scheduled = True
            setTimeout(self.iter, 0)
    
    def iter(self):
        """ Do one event loop iteration; process all pending function calls.
        """
        self._scheduled = False
        while len(self._pending_calls):
            func = self._pending_calls.pop(0)
            try:
                func()
            except Exception as err:
                console.log(err)


def get_Component_js():
    """ Get the final code for the JavaScript version of the Component class.
    """
    # Start with our special JS version
    jscode = py2js(ComponentJS, 'Component')
    # Add the Reaction methods
    code = '\n'
    for name, val in sorted(Reaction.__dict__.items()):
        if not name.startswith('__') and callable(val):
            code += py2js(val, 'reaction.' + name, indent=1)[4:]
            code += '\n'
        
    jscode = jscode.replace('HANDLER_METHODS_HOOK', code)
    # Add the methods from the Python Component class
    code = '\n'
    for name, val in sorted(Component.__dict__.items()):
        if name.startswith(('__', '_Component__')) or not callable(val):
            continue
        code += py2js(val, 'Component.prototype.' + name)
        code += '\n'
    jscode += code
    # Almost done
    jscode = jscode.replace('new Dict()', '{}').replace('new Dict(', '_pyfunc_dict(')
    jscode = jscode.replace('Component.prototype', '$Component')
    jscode = jscode.replace('}\n', '}\nvar $Component = Component.prototype;\n', 1)
    return jscode


JS_Loop = py2js(Loop, 'Loop') + '\nvar loop = new Loop();\n'
JS_Component = get_Component_js()
JS = JS_Loop + JS_Component


def create_js_component_class(cls, cls_name, base_class='Component.prototype'):
    """ Create the JS equivalent of a subclass of the Component class.
    
    Given a Python class with actions, properties, emitters and reactions,
    this creates the code for the JS version of the class. It also supports
    class constants that are int/float/str, or a tuple/list thereof.
    The given class does not have to be a subclass of Component.
    
    This more or less does what ComponentMeta does, but for JS.
    """
    
    assert cls_name != 'Component'  # we need this special class above instead
    
    # Collect meta information of all code pieces that we collect
    meta = {'vars_unknown': set(), 'vars_global': set(), 'std_functions': set(),
            'std_methods': set(), 'linenr': 1e9}
    def py2js_local(*args, **kwargs):
        code = py2js(*args, **kwargs)
        for key in meta:
            if key == 'linenr':
                meta[key] = min(meta[key], code.meta[key])
            else:
                meta[key].update(code.meta[key])
        return code
    
    total_code = []
    funcs_code = []  # functions and emitters go below class constants
    const_code = []
    err = ('Objects on JS Component classes can only be int, float, str, '
           'or a list/tuple thereof. Not %s -> %r.')
    
    total_code.append('\n'.join(get_class_definition(cls_name, base_class)).rstrip())
    prefix = '' if cls_name.count('.') else 'var '
    total_code[0] = prefix + total_code[0]
    prototype_prefix = '$' + cls_name.split('.')[-1] + '.'
    total_code.append('var %s = %s.prototype;' % (prototype_prefix[:-1], cls_name))
    # Functions to ignore
    OK_MAGICS = ('__actions__', '__properties__', '__emitters__',
                 '__reactions__', '__local_properties__')
    
    # Process class items in original order or sorted by name if we cant
    class_items = cls.__dict__.items()
    if sys.version_info < (3, 6):
        class_items = sorted(class_items)
    
    for name, val in class_items:
        name = name.replace('_JS__', '_%s__' % cls_name.split('.')[-1])  # fix __ mangling
        if isinstance(val, ActionDescriptor):
            # Set underlying function as class attribute. This is overwritten
            # by the instance, but this way super() works.
            funcname = name
            # Add function def
            code = py2js_local(val._func, prototype_prefix + funcname)
            code = code.replace('super()', base_class)  # fix super
            funcs_code.append(code.rstrip())
            # Mark to not bind the func
            funcs_code.append(prototype_prefix + funcname + '.nobind = true;')
            funcs_code.append('')
        elif isinstance(val, ReactionDescriptor):
            funcname = name  # funcname is simply name, so that super() works
            # Add function def
            code = py2js_local(val._func, prototype_prefix + funcname)
            code = code.replace('super()', base_class)  # fix super
            funcs_code.append(code.rstrip())
            # Mark to not bind the func
            funcs_code.append(prototype_prefix + funcname + '.nobind = true;')
            # Add connection strings, but not for implicit reactions
            if val._connection_strings:
                funcs_code.append(prototype_prefix + funcname +
                                  '._connection_strings = ' +
                                  reprs(val._connection_strings))
            funcs_code.append('')
        elif isinstance(val, Emitter):
            funcname = name
            # Add function def
            code = py2js_local(val._func, prototype_prefix + funcname)
            code = code.replace('super()', base_class)  # fix super
            funcs_code.append(code.rstrip())
            # Mark to not bind the func
            funcs_code.append(prototype_prefix + funcname + '.nobind = true;')
            funcs_code.append('')
        elif isinstance(val, Property):
            # Mutator and validator functions are picked up as normal functions.
            # Set default value on class.
            default_val = json.dumps(val._default)
            t = '%s_%s_value = %s;'
            const_code.append(t % (prototype_prefix, name, default_val))
        elif callable(val):
            # Functions, including methods attached by the meta class
            code = py2js_local(val, prototype_prefix + name)
            code = code.replace('super()', base_class)  # fix super
            funcs_code.append(code.rstrip())
            funcs_code.append('')
        elif name in OK_MAGICS:
            const_code.append(prototype_prefix + name + ' = ' + reprs(val))
        elif name.startswith('__'):
            pass  # we create our own __emitters__, etc.
        else:
            try:
                serialized = json.dumps(val)
            except Exception as err:  # pragma: no cover
                raise ValueError('Attributes on JS Component class must be '
                                 'JSON compatible.\n%s' % str(err))
            const_code.append(prototype_prefix + name + ' = ' + serialized)
    
    if const_code:
        total_code.append('')
        total_code.extend(const_code)
    if funcs_code:
        total_code.append('')
        total_code.extend(funcs_code)
    total_code.append('')
    
    # Return string with meta info (similar to what py2js returns)
    js = JSString('\n'.join(total_code))
    js.meta = meta
    return js


if __name__ == '__main__':
    
    # Testing ...
    from flexx import event
    
    class Foo(Component):
        
        foo = event.StringProp('asd', settable=True)
        
        @event.action
        def do_bar(self, v=0):
            print(v)
        
        @event.reaction
        def react2foo(self):
            print(self.foo)
    
    print('-' * 80)
    # print(JS_Loop)
    print('-' * 80)
    print(JS_Component)
    print('-' * 80)
    print(len(JS), 'bytes in total')
    print('-' * 80)
    # print(create_js_component_class(Foo, 'Foo'))
