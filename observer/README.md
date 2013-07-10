Implementation of an 'observer protocol' for python.

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

See **register_observer** for the observer (client) side of things.
Observable
==========
(*class*)
See the observer module documentation.

  **make\_observable(cls,othermeta)**:
  Creates a new metaclass that can used to automatically subclass an existing metaclass
  and thus allow *some* existing metaclass semantics to work while still making classes and
  object observer compatible.

  Note that there is no gaurantee this will operate as expected, it depends on what the subclassed
  metaclasses actually do.

  Usage:

      import observer

      class Foo(object):
        __metaclass__ = observer.make_observable(other_metaclass)

        ...

  **\_\_init\_\_(cls,name,bases,dct)**:

add\_observer
============
(*function*)
Register a function, method or any python callable to be called when a specific
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

make\_observable
===============
(*method*)
Creates a new metaclass that can used to automatically subclass an existing metaclass
and thus allow *some* existing metaclass semantics to work while still making classes and
object observer compatible.

Note that there is no gaurantee this will operate as expected, it depends on what the subclassed
metaclasses actually do.

Usage:

    import observer

    class Foo(object):
      __metaclass__ = observer.make_observable(other_metaclass)

      ...

observed
========
(*class*)
Creates an observable property. These act just like normal properties, including
being usable for both getting (singular usage) and optionally setting and deleting
but they notify any registered observers when get, set or delete happens.

  **deleter(self,func)**:
  **setter(self,func)**:
  **\_\_init\_\_(self,fget=None,fset=None,fdel=None,doc=None)**:

remove\_all\_observers
====================
(*function*)
Removes all observers registered under `name` (the name keyword argument to
*add_observer()*.  Anonymous observers (those registered without a name) cannot
be removed.

To remove only observer of a specific type, pass _get_,_set_, or _del_ in the type
keyword argument. If `type` is _ALL_ (the default), then all types will be removed.
