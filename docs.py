#!/usr/bin/env python
'''A simple tool to dump the markdown (hopefully) from a python package/module into a directorie's
README.md file.
'''

DIRECTORIES = ['observer']

import sys,re,os,os.path,inspect,types,importlib,glob
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

def doc_strip(doc,indent):
  lines = [l.rstrip() for l in doc.splitlines()]
  # first line may not be indented.
  min_indent = 0
  for l in lines:
    if l and l[0].isspace():
      i = len(l) - len(l.lstrip())
      if i and (min_indent == 0 or i < min_indent):
        min_indent = i

  for i,l in enumerate(lines):
    if l:
      length = len(l) - len(l.lstrip())
      if length < min_indent:
        lines[i] = indent + l.strip()
      else:
        lines[i] = indent + l[min_indent:]
        #l = (' ' * min_indent) + l.strip()
      #elif length > min_indent:
      #  l = l[min_indent:]
      #lines[i] = indent + l[min_indent:]

  return lines

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

def format_sym(sym):
  return sym.replace('_',r'''\_''')

def describe(ob,indent=''):
  if inspect.ismethod(ob):
    return indent+format_sym(ob.__name__)
  elif inspect.isfunction(ob):
    return indent+'function '+format_sym(ob.func_name)
  elif inspect.ismodule(ob):
    return indent+'module '+format_sym(ob.__name__)
  elif inspect.isclass(ob):
    return indent+'Class '+format_sym(ob.__name__)
  elif isinstance(ob,basestring):
    return indent+repr(ob)
  return indent+'<Instance of Class %s>' % format_sym(type(ob).__name__)

def describe_short(ob,indent=''):
  if inspect.ismethod(ob):
    return indent+'method'
  elif inspect.isfunction(ob):
    return indent+'function'
  elif inspect.ismodule(ob):
    return indent+'module'
  elif inspect.isclass(ob):
    return indent+'class'
  elif isinstance(ob,basestring):
    return indent+'string'
  elif ob is True or ob is False:
    return indent+str(ob)
  elif isinstance(ob,int):
    return indent+'integer'
  return indent+'object'

def describe_class(cls,output,level=1):
  argdesc = []
  indent = ' ' * (2*level)
  start = len(output)
  for sym in sorted(dir(cls),sort_symbol):
    attr = getattr(cls,sym,None)
    if attr is None: continue
    doc = getattr(attr,'__doc__',None)
    if sym.startswith('_') and not doc and sym != '__init__':
      continue
    elif sym not in cls.__dict__ and sym != '__init__':
      continue
    elif sym in ('__doc__','__module__','__name__','__weakref__'):
      continue
    del argdesc[::]
    if inspect.ismethod(attr) or inspect.isfunction(attr):
      args,vargs,varkw,defaults = inspect.getargspec(attr)
      defaults = list(defaults or ())
      argdesc.extend(args)
      i = len(argdesc)-1
      while defaults:
        argdesc[i] += ('=%r' % defaults.pop(-1))
        i -= 1

      if vargs:
        argdesc.append('*'+vargs)
      if varkw:
        argdesc.append('**'+argdesc)
    if argdesc:
      if len(indent) < 4:
        output.append(indent+'*%s*(%s):' % (format_sym(sym),','.join(argdesc)))
      else:
        output.append(indent+'%s(%s): ' % (sym,','.join(argdesc)))
    else:
      if len(indent) < 4:
        output.append(indent+'*%s* = %s' % (format_sym(sym),describe(attr)))
      else:
        output.append(indent+'%s(%s): ' % (sym,','.join(argdesc)))
    if doc:
      output.extend(doc_strip(doc,indent))
  return len(output) - start

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
        output.extend(l.rstrip() for l in m.__doc__.splitlines())
      for symbol in sorted(exports.keys(),sort_symbol):
        ob = exports[symbol]
        if getattr(ob,'__doc__',None):
          output.append('%s' % format_sym(symbol))
          output.append('=' * len(symbol))
          output.append('(*%s*)' % describe_short(ob))
          output.extend(doc_strip(ob.__doc__,''))
          if output[-1]:
            output.append('')
        else:
          output.append('%s: %s' % (format_sym(symbol),ob))
        if inspect.isclass(ob):
          if describe_class(ob,output,1):
            output.append('')
      exports.clear()

    with file(doc,'w') as f:
      f.write('\n'.join(output))
    del output[::]

if __name__ == '__main__':
  os.chdir(os.path.abspath(os.path.dirname(sys.argv[0])))
  for d in DIRECTORIES: dump_docs(d)

