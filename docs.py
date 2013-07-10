#!/usr/bin/env python
'''A simple tool to dump the markdown (hopefully) from a python package/module into a directorie's
README.md file.
'''

DIRECTORIES = ['observer']

import sys,os,os.path,importlib,glob
from contextlib import contextmanager,closing

@contextmanager
def directory(dir):
  wd = os.getcwd()
  absdir = os.path.abspath(dir)
  os.chdir(dir)
  sys.path.insert(0,absdir)
  try:
    yield
  finally:
    os.chdir(wd)
    sys.path.remove(absdir)

def sort_symbol(a,b):
  if a == b:
    return 0
  _a = a.startswith('_')
  __a = a.startswith('__')
  _b = b.startswith('_')
  __b = b.startswith('__')
  if __a and not __b:
    return 1
  elif __b:
    return -1
  elif _a and not _b:
    return 1
  elif _b:
    return -1
  return cmp(a,b)

def get_exports(module):
  exports = dict()
  for sym,ob in module.__dict__.items():
    doc = getattr(ob,'__doc__')
    if sym.startswith('__') and not sym.endswith('__'):
      continue
    if sym.startswith('_') and not doc:
      continue
    exports[sym] = ob
  return exports

def dump_docs(dir,doc='README.md',modules=None):
  output = []
  with directory(dir):
    module_files = dict()
    if modules is None:
      module_files.update((os.path.splitext(m)[0],m) for m in glob.glob('*.py'))
      modules = module_files.keys()
    else:
      modules_files = dict((m,m) for m in modules)

    for i,module in enumerate(modules):
      print 'generating docs for %s' % os.path.join(dir,module_files[module])
      if i > 0:
        output.append('-----')
      if len(modules) > 1:
        output.append('****%s****' % module)
        output.append('=' * (len(module)+8))

      m = importlib.import_module(module)
      if hasattr(m,'__all__'):
        exports = dict(filter(lambda kv:kv[1],((n,getattr(m,n,None)) for n in m.__all__)))
      else:
        exports = get_exports(m)

      if getattr(m,'__doc__',None):
        output.extend(m.__doc__.splitlines())
      for symbol in sorted(exports.keys(),sort_symbol):
        ob = exports[symbol]
        if getattr(ob,'__doc__',None):
          output.append('**%s**' % symbol)
          output.append('=' * (len(symbol)+4))
          output.append('*(%s)*' % ob)
          output.extend(ob.__doc__.splitlines())
          output.append('')
        else:
          output.append('**%s**: %s' % (symbol,ob))
      exports.clear()

    with file(doc,'w') as f:
      f.write('\n'.join(output))
    del output[::]

if __name__ == '__main__':
  os.chdir(os.path.abspath(os.path.dirname(sys.argv[0])))
  for dir in DIRECTORIES: dump_docs(dir)

