'''Context manager timer -- based on threading.Timer
'''
from __future__ import with_statement

__all__ = ('TimerExpired','timed')
import thread,threading
from time import time as _time

class TimerExpired(Exception):
  '''Raised when code running under timer() has expired, a single value, the number of elapsed
  seconds is available in the 'elapsed' attribute.
  '''
  def __init__(self,elapsed):
    Exception.__init__(self,elapsed)
    self.elapsed = elapsed

class _TimerContext(object):
  '''Creates a time context, all code bound to the context run complete without the given
  interval (float seconds) otherwise TimerExpired is raised.
  '''
  def __init__(self,interval):
    super(_TimerContext,self).__init__()
    self._interval = interval
    self._main_thread = None
    self._start = None
    self._stop = None
    self.__abort = False
    self.__timer = threading.Timer(interval,self._expire)

  @property
  def elapsed(self):
    '''Returns the number of seconds elapsed since the time context was entered.
    '''
    return _time() - self._start

  @property
  def remaining(self):
    '''Returns the number of seconds remaining untl the time context will expire and
    TimerExpired will be raised.

    Remaining may be 0 for a very short while before the interrupt exception is
    delivered to the main thread and the stack unwinds.
    '''
    return max(0.0,self._interval - (_time() - self._start))

  def __enter__(self):
    self._main_thread = tuple(threading.enumerate())[0]

    if not isinstance(self._main_thread,threading._MainThread):
      raise RuntimeError,"cannot use the 'timed' context except in the main thread (this appears not to be the main thread)"
    self._start = _time()
    self.__timer.setDaemon(True)
    self.__timer.start()
    return self

  def __exit__(self,exc_type,exc_value,tb):
    abort = self.__abort
    main = self._main_thread
    if self.__timer.is_alive():
      self.__timer.cancel()
    self._main_thread = None
    self.__timer = None
    self._stop = _time()
    if abort:
      raise TimerExpired(self._stop - self._start)

  def _expire(self):
    if self._start and not self._stop:
      # still running, abort the main thread with a KeyboardInterrupt that will get ignored by the
      # context's __exit__ handler.
      self.__abort = True
      thread.interrupt_main()

def timed(interval,*args,**kwargs):
  return _TimerContext(interval,*args,**kwargs)
timed.__doc__ = _TimerContext.__doc__

if __name__ == '__main__':
  print 'testing, should not run for longer than 0.5 seconds'
  try:
    with timed(0.5) as timer:
      step = 0.5
      while True:
        if round(timer.remaining,1) < step:
          step = round(timer.remaining,1)
          print 'remaining',step
  except TimerExpired, e:
    print 'Timer expired, elapsed',e.elapsed

