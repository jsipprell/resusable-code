'''Implementation of an 'observer protocol' for python.

This protocol allows objects to use *observable* properties (via an `@observed` decorator).
When a property is observed it has all of its getter, setter and deleteter derivatives call
back any interested parties who have registered handlers (callables) for the observed
object's instance or class (new-style classes only).

In order for this to work, observed objects must all use the `Observable` metaclass. This metaclass
registered the class and any instantiated objects. Instantiated objects are referenced weakly
only, so if the observed object is ever destroyed any registered observation callbacks
are automatically released.

Callbacks happen pseudo-independantly from the property data being returned to the original
requestor, being sent to the observed object's property handler for setting/deletion. Observers
cannot modify the data in any way.

Optionally, observers can be called in a separate thread by indicating this when they register
to observe some class or object.

A metaclass that makes other classes suitable for observation (i.e. the targets of
observation rather than the observers). This should be used in conjuction with the
**@observed** decorator.

Usage:

    from observer import Observable,observed
    class Foo(object):
      __metaclass__ = Observable

      @observed
      def foo(self): return self._foo

      @foo.setter
      def foo(self,value): self._foo = value

      @foo.deleter
      def foo(self): del self._foo

See [add_observer](#add_observer) for the observer (client) side of things.
'''
__all__ = ['Observable','observed','add_observer','remove_all_observers','make_observable']

import sys,weakref,inspect
from types import TypeType,ObjectType,InstanceType,ClassType
from threading import Thread
from inspect import isfunction

_observed_names = dict()
_observed_classes = dict()
_observed_objects = dict()

class ObserverError(Exception): pass

_AnonymousKey = object()

def _hash(self):
  '''Returns the hash of this observable object based on it's object ID. This means the object
  cannot have it's hash and/or equality values based on internal immutable components.

  Observable objects can provide __hash__ methods but these will be replaced by the Observable
  metaclass.
  '''
  if isinstance(self,TypeType):
    return type.__hash__(self)
  else:
    return id(self) ^ 0xa5cf8347

class _Ref(weakref.KeyedRef):
  __slots__ = ('_type','_hash','key')

  def __new__(cls,ob,name,callback=None):
    return super(_Ref,cls).__new__(cls,ob,callback or cls.callback,name)

  def __init__(self,ob,name,callback=None):
    if isinstance(ob,type):
      self._type = TypeType
    elif isinstance(ob,(InstanceType,ClassType)):
      raise ObserverError, 'old-style classes and instances are not supported by the observer protocol'
    else:
      self._type = type(ob)
    self._hash = _hash(ob)
    super(_Ref,self).__init__(ob,callback,name)

  def callback(self):
    global _observed_objects, _observed_classes

    if self._type == TypeType:
      del _observed_classes[self]
    else:
      del _observed_objects[self]

  def __hash__(self):
    return self._hash

  def __eq__(self,other):
    if isinstance(other,weakref.ref):
      #print 'EQ to REF',other
      return self() is other()
    else:
      #print 'EQ to',other
      return self() is other

class _CallbackWrapper(object):
  __slots__ = ('property','type','use_thread','_func','_h')

  def __init__(self,property,type,use_thread,func):
    self.property = property
    self.type = type
    self.use_thread = use_thread
    self._func = func
    self._h = None

  def __call__(self,*args):
    #print 'CALLBACKWRAPPER, args:',repr(args)
    return self._func(*args)

  def __str__(self):
    return self.property

  def __repr__(self):
    return '<Wrapper %r>' % repr(self._func)

  def __hash__(self):
    if self._h is None:
      self._h = hash(self.property) + hash(self._func)
    return self._h

  def __eq__(self,ob):
    if isinstance(ob,_CallbackWrapper):
      return self.property == ob.property and self._func == ob._func
    return self._func == ob

  def clone(self):
    return type(self)(self.property,self.type,self.use_thread,self._func)

def _merge_names(name,dest):
  dest_get = dest['get']
  dest_set = dest['set']
  dest_delete = dest['del']

  if name in _observed_names:
    observersets = _observed_names[name]
    for n,observers in observersets['get'].iteritems():
      dest_get.setdefault(n,set()).update(o.clone() for o in observers)
    for n,observers in observersets['set'].iteritems():
      dest_set.setdefault(n,set()).update(o.clone() for o in observers)
    for n,observers in observersets['del'].iteritems():
      dest_delete.setdefault(n,set()).update(o.clone() for o in observers)

class Observable(type):
  '''See the observer module documentation.'''
  def __new__(cls,name,bases,dct):
    for b in bases:
      if getattr(b,'__hash__',None) is _hash:
        return super(Observable,cls).__new__(cls,name,bases,dct)
    if dct.has_key('__hash__'):
      import warnings
      warnings.warn('Class %r defines __hash__ but this method will be overridden by the Observable metaclass' % name)
      hash_func = dct['__hash__']
      hash_dict = getattr(hash_func,'__dict__',{})
      doc = getattr(hash_func,'__doc__',None)
      module = getattr(hash_func,'__module__',None)
    else:
      hash_dict = _hash.__dict__
      doc = _hash.__doc__
      module = getattr(cls,'__module__',None)
    
    def wrapper(ob):
      return _hash(ob)

    wrapper.__dict__.update(hash_dict)
    wrapper.__name__ = '__hash__'
    if doc:
      wrapper.__doc__ = doc
    if module:
      wrapper.__module__ = module

    dct['__hash__'] = wrapper
    return super(Observable,cls).__new__(cls,name,bases,dct)

  def __init__(cls,name,bases,dct):
    super(Observable,cls).__init__(name,bases,dct)
    if hasattr(cls,'__observed_name__'):
      oname = cls.__observed_name__
      if callable(oname):
        oname = oname()
    else:
      oname = cls.__full_name__
    try:
      wr = _Ref(cls,oname)
    except TypeError:
      wr = cls
    _observed_classes[wr] = observed = {'get':{},'set':{},'del':{}}
    #print 'observable class:',wr()
    _merge_names(oname,observed)
    
    old_init = dct.get('__init__')
    def init(self,*args,**kwargs):
      cls._register(self)
      if old_init:
        old_init(self,*args,**kwargs)
      else:
        super(cls,self).__init__(*args,**kwargs)
    if old_init:
      init.__dict__.update(old_init.__dict__)
      init.__doc__ = old_init.__doc__
      init.__name__ = old_init.__name__
    else:
      init.__name__ = '__init__'
    cls.__init__ = init

  @classmethod
  def _register(cls,ob):
    name = getattr(ob,'__observed_name__',None)
    if name is None:
      name = repr(ob)
    elif callable(name):
      name = name()
    try:
      wr = _Ref(ob,name)
      _observed_objects[wr] = observed = {'get':{},'set':{},'del':{}}
    except TypeError:
      raise ObserverError,'objects of type %r cannot be observed' % cls
    _merge_names(name,observed)
    return ob

  @property
  def __full_name__(cls):
    namespace = getattr(cls,'__module__','')
    if namespace:
      return '.'.join((namespace,cls.__name__))
    return cls.__name__

  @classmethod
  def make_observable(cls,othermeta):
    '''Creates a new metaclass that can used to automatically subclass an existing metaclass
    and thus allow *some* existing metaclass semantics to work while still making classes and
    object observer compatible.

    Note that there is no gaurantee this will operate as expected, it depends on what the subclassed
    metaclasses actually do.

    Usage:

        import observer

        class Foo(object):
          __metaclass__ = observer.make_observable(other_metaclass)

          ...
    '''
    return type(othermeta.__name__,(othermeta,cls),{})
make_observable = Observable.make_observable

def _observe_callback(observed,key,type,name,ob,*args):
  #print type,repr(observed)
  for observer in observed[key][type].itervalues():
      for o in observer:
        property = name or o.property
        if o.use_thread:
          t = Thread(target=o,name='%s_%s_observer' % (property,type),args=(property,ob)+args)
          t.setDaemon(True)
          t.start()
        else:
          #print 'CALLING:',repr(o),'\n  WITH:',repr(property)
          o(property,ob,*args)

def _observe_get(ob,value,name=None):
  _observe_callback(_observed_objects,ob,'get',name,ob,value)
  _observe_callback(_observed_classes,type(ob),'get',name,ob,value)

def _observe_set(ob,new_value,name=None):
  _observe_callback(_observed_objects,ob,'set',name,ob,new_value)
  _observe_callback(_observed_classes,type(ob),'set',name,ob,new_value)

def _observe_delete(ob,name=None):
  _observe_callback(_observed_objects,ob,'del',name,ob)
  _observe_callback(_observed_classes,type(ob),'del',name,ob)

class observed(object):
  '''Creates an observable property. These act just like normal properties, including
  being usable for both getting (singular usage) and optionally setting and deleting
  but they notify any registered observers when get, set or delete happens.
  '''
  def __init__(self,fget=None,fset=None,fdel=None,doc=None):
    self.fget = fget
    self.fset = fset
    self.fdel = fdel
    self.__doc__ = doc or fget.__doc__
    if isfunction(fget):
      self.name = fget.func_name
    else:
      self.name = None

  def __repr__(self):
    return '<observed property %r>' % self.name

  def __call__(self,func):
    self.fget = func
    if self.name is None:
      self.name = func.func_name
    if not self.__doc__:
      self.__doc__ = func.__doc__

  def __get__(self,obj,objtype=None):
    if obj is None:
      return self

    if self.fget is None:
      raise AttributeError, 'unreadable attribute'
    val = self.fget(obj)
    _observe_get(obj,val,self.name)
    return val

  def __set__(self,obj,val):
    if self.fset is None:
      raise AttributeError,"can't set attribute"
    _observe_set(obj,val,self.name)
    self.fset(obj,val)

  def __delete__(self,obj):
    if self.fdel is None:
      raise AttributeError,"can't delete attribute"
    _observe_delete(obj,self.name)

  def setter(self, func):
    self.fset = func
    if self.name is None:
      self.name = func.func_name
    return self

  def deleter(self, func):
    self.fdel = func
    if self.name is None:
      self.name = func.func_name
    return self

def add_observer(ob,property,callback,type='get',name=None,use_thread=False):
  '''Register a function, method or any python callable to be called when a specific
  property in an object is accessed, either via a get, a set or a delete.

  The object registered against (`ob`) can be one of three things:

  1. A string: In this case when any class of this name (including any module namespaces!)
  is created which uses the Observable metaclass, the observer callback will automatically
  be registered for any future instances.

  2. A class: In this case, any future instances of the class (which *must* use the
  Observable metaclass) will generate callbacks for the indicated property and access
  type.

  3. An object: Finally, the callback will be called for indicated property access
  of the given type.

  The `property` argument should be the string name of the attribute in the observed object
  which uses the @observed decorator.

  The `type` argument should be one of _get_,_set_ or _del_ (or _delete_).

  The callback will be called and passed arguments depending on the access `type':

  1. __get__: `callback(property,object,value)`
  2. __set__: `callback(property,object,new-value)`
  3. __del__: `callback(property,object)`

  The attributes passed to the callback are as follows:
  
  * _object_: The object instance whose property is being observed.
  * _property_: The name of the property being observed.
  * _value_: ('get' only) The value of the property as retrieve by calling the property's getter method.
  * _new-value_: ('set' only) The new value that the property's setter function
            will or has been called with (see below for info on call order).

  If the keyword argument `name` is passed to _register_observer_, the observation becomes
  a member in a globally named set. Calling 'remove_all_observers' with this name
  will remove all registered observers (optionally filtered by type) in this set.

  If the keyword argument `use_thread` evaluates to True, callbacks will always be called
  in a separate thread.

  **Callback Order**
  ==================

  Order of observation callbacks is arbitrary and undefined. There is **no guarantee** that
  the original observed object's property methods will have been called either before or after
  the observer (with the exception of _get_ because this MUST be called first in order to
  "get" the observed value); nor is their any gaurantee that an observer callback will be
  called before or after another observer callback. This is true with or without threading
  (via `use_thread`).

  Observer callbacks must not alter the value in any fashion. Their return values are silently
  discarded.
  '''
  if name is None:
    name = _AnonymousKey
  if not callable(callback):
    raise TypeError, 'observer callback must be callable'
  type = type[:3]
  if type not in ('get','set','del'):
    raise TypeError, 'observer callback must be either "get","set" or "del'
  if not isinstance(property,basestring):
    raise TypeError, 'property must be a string'

  wrapper = _CallbackWrapper(property,type,use_thread and True or False,callback)
  observers = None
  if isinstance(ob,basestring):
    observersets = _observed_names.setdefault(ob,{'get':{},'set':{},'del':{}})[type]
    observersets.setdefault(name,set()).add(wrapper)
    # update any Observable classes and objects that match.
    for cls,_observers in _observed_classes.iteritems():
      if isinstance(cls,_Ref):
        key = cls.key
      else:
        key = getattr(cls,'__observed_name__',None)
        if key is None:
          key = cls.__full_name__
        elif callable(key):
          key = key()
      if key == ob:
        _observers[type].setdefault(name,set()).add(wrapper.clone())
    for inst,_observers in _observed_objects.iteritems():
      if inst.key == ob or str(type(inst())) == ob:
        _observers[type].setdefault(name,set()).add(wrapper.clone())
  elif isinstance(ob,TypeType):
    observers = _observed_classes.get(ob)
    if observers is None:
      raise ObserverError,'class %r does not support observation' % ob
  elif isinstance(ob,(ClassType,InstanceType)):
    raise ObserverError,'old-style classes and instances do not support observation (%r)' % ob
  else:
    observers = _observed_objects.get(ob)
    if observers is None:
      raise ObserverError,'object %r does not support observation' % ob

  if observers is not None:
    observers[type].setdefault(name,set()).add(wrapper)

def remove_all_observers(name,type='ALL'):
  '''Removes all observers registered under `name` (the name keyword argument to
  *add_observer()*.  Anonymous observers (those registered without a name) cannot
  be removed.

  To remove only observer of a specific type, pass _get_,_set_, or _del_ in the type
  keyword argument. If `type` is _ALL_ (the default), then all types will be removed.
  '''
  type = type[:3]
  if type not in ('get','set','del','ALL','all'):
    raise ValueError, "'type' keyword argument must be one of 'get','set','del' or 'ALL', not %r" % type

  if type in ('all','ALL'):
    type = None
  for ob,observersets in _observed_names.iteritems():
    for t,observers in observersets.iteritems():
      if type and t != type:
        continue
      if name in observers:
        del observers[name]
  for ob,observersets in _observed_classes.iteritems():
    for t,observers in observersets.iteritems():
      if type and t != type:
        continue
      if name in observers:
        del observers[name]
  for ob,observersets in _observed_objects.iteritems():
    for t,observers in observersets.iteritems():
      if type and t != type:
        continue
      if name in observers:
        del observers[name]

if __name__ == '__main__':
  import gc

  out = sys.stdout.write
  def get_observer(prop,ob,val):
    out('[%s OBSERVED: %s for %s] ' % (ob.name,repr(val),prop))
  def set_observer(prop,ob,val):
    out('[%s OBSERVED: %s = %s] ' % (ob.name,prop,repr(val)))
  def del_observer(prop,ob):
    out('[%s DELETE: %s] ' % (ob.name,prop,))

  add_observer('foobar','baz',get_observer,name='TEST')
  add_observer('foobar','baz',set_observer,'set',name='TEST')
  add_observer('foobar','baz',del_observer,'del',name='TEST')
  add_observer('Cheese','length',get_observer,'get',name='TEST')
  add_observer('Cheese','length',set_observer,'set',name='TEST')

  class foobar(object):
    __metaclass__ = Observable

    def __new__(cls,*args,**kwargs):
      return super(foobar,cls).__new__(cls,*args,**kwargs)

    def __init__(self,val,name='foobar_object'):
      self._baz = val
      self.name = name

    #def __hash__(self):
    #  '''Return hash of baz'''
    #  return hash(self._baz)

    @observed
    def baz(self): return self._baz
    @baz.setter
    def baz(self,value): self._baz = value
    @baz.deleter
    def baz(self): self._baz = None  

  f = foobar(1)
  print 'BAZ',f.baz
  f.baz =10
  print 'BAZ',f.baz
  del f.baz
  print f.baz

  add_observer(foobar,'baz',set_observer,name='TEST')

  class Monkey(foobar):
    def __new__(cls,*args,**kwargs):
      print 'ENW',cls
      return super(Monkey,cls).__new__(cls,*args,**kwargs)

  print '--- Monkey Time'
  m = Monkey(2,name='monkey_object')
  add_observer(m,'baz',get_observer,name='TEST')
  f.baz = 12

  print f.baz
  print 'MONKEY',m.baz
  print 'REMOVE'
  remove_all_observers('TEST','get')
  print m.baz
  del m
  del f
  
  class BaseMeta(type):
    def __new__(cls,name,bases,dct):
      print 'BaseMeta adding method "__call__" to %r' % name
      def call(self):
        return 'my length is %s' % self.length
      dct.setdefault('__call__',call)
      dct.setdefault('name',name)
      return super(BaseMeta,cls).__new__(cls,name,bases,dct)

  class Cheese(object):
    __metaclass__ = make_observable(BaseMeta)

    @observed
    def length(self):
      return getattr(self,'_length',0)
    @length.setter
    def length(self,value):
      self._length = int(value)

  cheese = Cheese()
  cheese.length = 3
  print cheese()

  print '--- Cleanup Time'
  remove_all_observers('TEST')
  print len(_observed_classes)
  dynamic = type('DynamicMonkey',(Monkey,),{})
  del cheese
  del Cheese
  del dynamic
  del Monkey
  del foobar
  gc.collect()
  assert len(_observed_objects) == 0, 'dangling object references exist'
  assert len(_observed_classes) == 0, 'dangling class references exist'

# vi: :set sts=2 sw=2 ai et tw=0:
