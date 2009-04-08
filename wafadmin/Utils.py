#!/usr/bin/env python
# encoding: utf-8
# Thomas Nagy, 2005 (ita)

"""
Utilities, the stable ones are the following:

* h_file: compute a unique value for a file (hash), it uses
  the module fnv if it is installed (see waf/utils/fnv & http://code.google.com/p/waf/wiki/FAQ)
  else, md5 (see the python docs)

  For large projects (projects with more than 15000 files) it is possible to use
  a hashing based on the path and the size (may give broken cache results)

	import stat
	def h_file(filename):
		st = os.stat(filename)
		if stat.S_ISDIR(st[stat.ST_MODE]): raise IOError('not a file')
		m = Utils.md5()
		m.update(str(st.st_mtime))
		m.update(str(st.st_size))
		m.update(filename)
		return m.digest()

	To replace the function in your project, use something like this:
	import Utils
	Utils.h_file = h_file

* h_list
* h_fun
* get_term_cols
* ordered_dict

"""

import os, sys, imp, string, errno, traceback, inspect, re, shutil

try: from UserDict import UserDict
except ImportError: from collections import UserDict
if sys.hexversion >= 0x2060000:
	import subprocess as pproc
else:
	import pproc
import Logs
from Constants import *

is_win32 = sys.platform == 'win32'

try:
	# defaultdict in python 2.5
	from collections import defaultdict as DefaultDict
except ImportError:
	class DefaultDict(dict):
		def __init__(self, default_factory):
			super(DefaultDict, self).__init__()
			self.default_factory = default_factory
		def __getitem__(self, key):
			try:
				return super(DefaultDict, self).__getitem__(key)
			except KeyError:
				value = self.default_factory()
				self[key] = value
				return value

class WafError(Exception):
	def __init__(self, *args):
		self.args = args
		self.stack = traceback.extract_stack()
		Exception.__init__(self, *args)
	def __str__(self):
		return str(len(self.args) == 1 and self.args[0] or self.args)

class WscriptError(WafError):
	def __init__(self, message, wscript_file=None):
		if wscript_file:
			self.wscript_file = wscript_file
			self.wscript_line = None
		else:
			(self.wscript_file, self.wscript_line) = self.locate_error()

		msg_file_line = ''
		if self.wscript_file:
			msg_file_line = "%s:" % self.wscript_file
			if self.wscript_line:
				msg_file_line += "%s:" % self.wscript_line
		err_message = "%s error: %s" % (msg_file_line, message)
		WafError.__init__(self, err_message)

	def locate_error(self):
		stack = traceback.extract_stack()
		stack.reverse()
		for frame in stack:
			file_name = os.path.basename(frame[0])
			is_wscript = (file_name == WSCRIPT_FILE or file_name == WSCRIPT_BUILD_FILE)
			if is_wscript:
				return (frame[0], frame[1])
		return (None, None)

indicator = is_win32 and '\x1b[A\x1b[K%s%s%s\r' or '\x1b[K%s%s%s\r'

try:
	from fnv import new as md5
	import Constants
	Constants.SIG_NIL = 'signofnv'

	def h_file(filename):
		m = md5()
		try:
			m.hfile(filename)
			x = m.digest()
			if x is None: raise OSError("not a file")
			return x
		except SystemError:
			raise OSError("not a file" + filename)

except ImportError:
	try:
		from hashlib import md5
	except ImportError:
		from md5 import md5

	def h_file(filename):
		f = open(filename, 'rb')
		m = md5()
		readBytes = 100000
		while (filename):
			filename = f.read(100000)
			m.update(filename)
		f.close()
		return m.digest()

class ordered_dict(UserDict):
	def __init__(self, dict = None):
		self.allkeys = []
		UserDict.__init__(self, dict)

	def __delitem__(self, key):
		self.allkeys.remove(key)
		UserDict.__delitem__(self, key)

	def __setitem__(self, key, item):
		if key not in self.allkeys: self.allkeys.append(key)
		UserDict.__setitem__(self, key, item)

def exec_command(s, **kw):
	if 'log' in kw:
		kw['stdout'] = kw['stderr'] = kw['log']
		del(kw['log'])
	kw['shell'] = isinstance(s, str)

	try:
		proc = pproc.Popen(s, **kw)
		return proc.wait()
	except WindowsError:
		return -1

if is_win32:
	old_log = exec_command
	def exec_command(s, **kw):
		# TODO very long command-lines are unlikely to be used in the configuration
		if len(s) < 2000: return old_log(s, **kw)

		if 'log' in kw:
			kw['stdout'] = kw['stderr'] = kw['log']
			del(kw['log'])
		kw['shell'] = isinstance(s, str)

		startupinfo = pproc.STARTUPINFO()
		startupinfo.dwFlags |= pproc.STARTF_USESHOWWINDOW
		kw['startupinfo'] = startupinfo
		proc = pproc.Popen(s, **kw)
		return proc.wait()

listdir = os.listdir
if is_win32:
	def listdir_win32(s):
		if re.match('^[A-Za-z]:$', s):
			# os.path.isdir fails if s contains only the drive name... (x:)
			s += os.sep
		if not os.path.isdir(s):
			e = OSError()
			e.errno = errno.ENOENT
			raise e
		return os.listdir(s)
	listdir = listdir_win32

def waf_version(mini = 0x010000, maxi = 0x100000):
	"Halts if the waf version is wrong"
	ver = HEXVERSION
	try: min_val = mini + 0
	except TypeError: min_val = int(mini.replace('.', '0'), 16)

	if min_val > ver:
		Logs.error("waf version should be at least %s (%s found)" % (mini, ver))
		sys.exit(0)

	try: max_val = maxi + 0
	except TypeError: max_val = int(maxi.replace('.', '0'), 16)

	if max_val < ver:
		Logs.error("waf version should be at most %s (%s found)" % (maxi, ver))
		sys.exit(0)

def python_24_guard():
	if sys.hexversion<0x20400f0:
		raise ImportError("Waf requires Python >= 2.3 but the raw source requires Python 2.4")

def ex_stack():
	exc_type, exc_value, tb = sys.exc_info()
	exc_lines = traceback.format_exception(exc_type, exc_value, tb)
	return ''.join(exc_lines)

def to_list(sth):
	if isinstance(sth, str):
		return sth.split()
	else:
		return sth

g_loaded_modules = {}
"index modules by absolute path"

g_module=None
"the main module is special"

def load_module(file_path, name=WSCRIPT_FILE):
	"this function requires an absolute path"
	try:
		return g_loaded_modules[file_path]
	except KeyError:
		pass

	module = imp.new_module(name)

	try:
		code = readf(file_path)
	except (IOError, OSError):
		raise WscriptError('The file %s could not be opened!' % file_path)

	module.waf_hash_val = code

	module_dir = os.path.dirname(file_path)
	sys.path.insert(0, module_dir)
	exec(code, module.__dict__)
	sys.path.remove(module_dir)

	g_loaded_modules[file_path] = module

	return module

def set_main_module(file_path):
	"Load custom options, if defined"
	global g_module
	g_module = load_module(file_path, 'wscript_main')
	g_module.root_path = file_path

	# note: to register the module globally, use the following:
	# sys.modules['wscript_main'] = g_module

def to_hashtable(s):
	"used for importing env files"
	tbl = {}
	lst = s.split('\n')
	for line in lst:
		if not line: continue
		mems = line.split('=')
		tbl[mems[0]] = mems[1]
	return tbl

def get_term_cols():
	"console width"
	return 80
try:
	import struct, fcntl, termios
except ImportError:
	pass
else:
	if sys.stderr.isatty() and os.environ['TERM'] != 'dumb':
		def myfun():
			dummy_lines, cols = struct.unpack("HHHH", \
			fcntl.ioctl(sys.stderr.fileno(),termios.TIOCGWINSZ , \
			struct.pack("HHHH", 0, 0, 0, 0)))[:2]
			return cols
		# we actually try the function once to see if it is suitable
		try:
			myfun()
		except IOError:
			pass
		else:
			get_term_cols = myfun

rot_idx = 0
rot_chr = ['\\', '|', '/', '-']
"the rotation character in the progress bar"

def split_path(path):
	if not path: return ['']
	return path.split('/')

if is_win32:
	def split_path(path):
		h,t = os.path.splitunc(path)
		if not h: return __split_dirs(t)
		return [h] + __split_dirs(t)[1:]

	def __split_dirs(path):
		h,t = os.path.split(path)
		if not h: return [t]
		if h == path: return [h.replace('\\', '')]
		if not t: return __split_dirs(h)
		else: return __split_dirs(h) + [t]

def copy_attrs(orig, dest, names, only_if_set=False):
	for a in to_list(names):
		u = getattr(orig, a, ())
		if u or not only_if_set:
			setattr(dest, a, u)

def def_attrs(cls, **kw):
	'''
	set attributes for class.
	@param cls [any class]: the class to update the given attributes in.
	@param kw [dictionary]: dictionary of attributes names and values.

	if the given class hasn't one (or more) of these attributes, add the attribute with its value to the class.
	'''
	for k, v in kw.iteritems():
		if not hasattr(cls, k):
			setattr(cls, k, v)

quote_define_name_table = None
def quote_define_name(path):
	"Converts a string to a constant name, foo/zbr-xpto.h -> FOO_ZBR_XPTO_H"
	global quote_define_name_table
	if not quote_define_name_table:
		invalid_chars = set([chr(x) for x in xrange(256)]) - set(string.digits + string.uppercase)
		quote_define_name_table = string.maketrans(''.join(invalid_chars), '_'*len(invalid_chars))
	return string.translate(string.upper(path), quote_define_name_table)

def quote_whitespace(path):
	return (path.strip().find(' ') > 0 and '"%s"' % path or path).replace('""', '"')

def trimquotes(s):
	if not s: return ''
	s = s.rstrip()
	if s[0] == "'" and s[-1] == "'": return s[1:-1]
	return s

def h_list(lst):
	m = md5()
	m.update(str(lst))
	return m.digest()

def h_fun(fun):
	try:
		return fun.code
	except AttributeError:
		try:
			h = inspect.getsource(fun)
		except IOError:
			h = "nocode"
		try:
			fun.code = h
		except AttributeError:
			pass
		return h

def pprint(col, str, label='', sep=os.linesep):
	"print messages in color"
	sys.stderr.write("%s%s%s %s%s" % (Logs.colors(col), str, Logs.colors.NORMAL, label, sep))

def check_dir(dir):
	"""If a folder doesn't exists, create it."""
	try:
		os.stat(dir)
	except OSError:
		try:
			os.makedirs(dir)
		except OSError, e:
			raise WafError("Cannot create folder '%s' (original error: %s)" % (dir, e))

def cmd_output(cmd, **kw):

	# the following is for backward compatibility
	silent = kw.get('silent', False)
	if silent:
		del(kw['silent'])

	if 'e' in kw:
		tmp = kw['e']
		del(kw['e'])
		kw['env'] = tmp

	kw['shell'] = isinstance(cmd, str)
	kw['stdout'] = pproc.PIPE
	if silent:
		kw['stderr'] = pproc.PIPE

	try:
		p = pproc.Popen(cmd, **kw)
		output = p.communicate()[0]
	except WindowsError, e:
		raise ValueError(str(e))

	if p.returncode:
		if not silent:
			msg = "command execution failed: %s -> %r" % (cmd, str(output))
			raise ValueError(msg)
		output = ''
	return output

reg_subst = re.compile(r"(\\\\)|(\$\$)|\$\{([^}]+)\}")
def subst_vars(expr, params):
	"substitute ${PREFIX}/bin in /usr/local/bin"
	def repl_var(m):
		if m.group(1):
			return '\\'
		if m.group(2):
			return '$'
		try:
			# environments may contain lists
			return params.get_flat(m.group(3))
		except AttributeError:
			return params[m.group(3)]
	return reg_subst.sub(repl_var, expr)

def detect_platform():
	s = sys.platform

	# known POSIX
	for x in 'cygwin linux irix sunos hpux aix darwin'.split():
		# sys.platform may be linux2
		if s.find(x) >= 0:
			return x

	# unknown POSIX
	if os.name in 'posix java os2'.split():
		return os.name

	return s

def load_tool(tool, tooldir=None):
	if tooldir:
		assert isinstance(tooldir, list)
		sys.path = tooldir + sys.path
	try:
		try:
			return __import__(tool)
		except ImportError, e:
			raise WscriptError(e)
	finally:
		if tooldir:
			for d in tooldir:
				sys.path.remove(d)

def readf(fname, m='r'):
	"get the contents of a file, it is not used anywhere for the moment"
	f = None
	try:
		f = open(fname, m)
		txt = f.read()
	finally:
		if f: f.close()
	return txt

def nada(*k, **kw):
	"""A function that does nothing"""
	pass

class Context(object):
	"""A base class for commands to be executed from Waf scripts"""
	def recurse(self, dirs, name=''):
		"""The function for calling scripts from folders, it tries to call wscript + function_name
		and if that file does not exist, it will call the method 'function_name' from a file named wscript
		the dirs can be a list of folders or a string containing space-separated folder paths
		"""
		if not name:
			name = inspect.stack()[1][3]

		if isinstance(dirs, str):
			dirs = to_list(dirs)

		if not getattr(self, 'curdir', None):
			self.curdir = os.getcwd()

		for x in dirs:
			if os.path.isabs(x):
				nexdir = x
			else:
				nexdir = os.path.join(self.curdir, x)

			base = os.path.join(nexdir, WSCRIPT_FILE)

			try:
				txt = readf(base + '_' + name)
			except (OSError, IOError):
				try:
					module = load_module(base)
				except OSError:
					raise WscriptError('No such script %s' % base)

				try:
					f = module.__dict__[name]
				except KeyError:
					raise WscriptError('No function %s defined in %s' % (name, base))

				if getattr(self.__class__, 'pre_recurse', None):
					self.pre_recurse(f, base, nexdir)
				old = self.curdir
				self.curdir = nexdir
				try:
					f(self)
				finally:
					self.curdir = old
				if getattr(self.__class__, 'post_recurse', None):
					self.post_recurse(module, base, nexdir)
			else:
				dc = {'ctx': self}
				if getattr(self.__class__, 'pre_recurse', None):
					dc = self.pre_recurse(txt, base + '_' + name, nexdir)
				old = self.curdir
				self.curdir = nexdir
				try:
					exec (txt, dc)
				finally:
					self.curdir = old
				if getattr(self.__class__, 'post_recurse', None):
					self.post_recurse(txt, base + '_' + name, nexdir)

def jar_regexp(regex):
	if regex.endswith('/'):
		regex += '**'
	regex = (re.escape(regex).replace(r"\*\*\/", ".*")
		.replace(r"\*\*", ".*")
		.replace(r"\*","[^/]*")
		.replace(r"\?","[^/]"))
	if regex.endswith(r'\/.*'):
		regex = regex[:-4] + '([/].*)*'
	regex += '$'
	#print regex
	return re.compile(regex)

if is_win32:
	old = shutil.copy2
	def copy2(src, dst):
		old(src, dst)
		shutil.copystat(src, src)
	setattr(shutil, 'copy2', copy2)

