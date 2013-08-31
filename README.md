resusable-code
==============

This is a compilation of various recipies and patterns, mostly in python because that's what I happen to use most, which
I have assembled in one place.

The various modules, packages and the like are not intended to interopate in any clean way at all -- merely to be of
potential reuse *somewhere*.

## timer.py ##

A quick little context manager I wrote for python 2.6+; *to use*:

    import timer
    try:
      with timer.timed(nseconds):
        # ... code ...

    except timer.TimerExpired, e:
      print 'execution expired after %s seconds' % e.elapsed
