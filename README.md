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

## bash ##

Function library I've built over the ages. To use simply add he following to
your ~/.bash_profile:

    if [ -f ~/.bash_functions ]; then
        . ~/.bash_functions
    fi
    
    uname=$(uname -s | tr A-Z a-z)
    if [ -f ~/".bash_functions_$uname" ]; then
        . ~/".bash_functions_$uname"
    fi
    unset uname

