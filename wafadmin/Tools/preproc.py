#! /usr/bin/env python
# encoding: utf-8
# Thomas Nagy, 2006 (ita)

"""Waf preprocessor for finding dependencies
  because of the includes system, it is necessary to do the preprocessing in at least two steps:
  - filter the comments and output the preprocessing lines
  - interpret the preprocessing lines, jumping on the headers during the process

  In the preprocessing line step, the following actions are performed:
  - substitute the code in the functions and the defines (and use the # and ## operators)
  - reduce the expression obtained (apply the arithmetic and boolean rules)

TODO: varargs
"""

import re, sys, os, string, types
if __name__ == '__main__':
	sys.path = ['.', '..'] + sys.path
import Params
from Params import debug, error, warning
import traceback

class PreprocError(Exception):
	pass

g_findall = 1
'search harder for project includes'

use_trigraphs = 0
'apply the trigraph rules first'

strict_quotes = 0
"Keep <> for system includes (do not search for those includes)"

g_optrans = {
'not':'!',
'and':'&&',
'bitand':'&',
'and_eq':'&=',
'or':'||',
'bitor':'|',
'or_eq':'|=',
'xor':'^',
'xor_eq':'^=',
'compl':'~',
}
"these ops are for c++, to reset, set an empty dict"

# ignore #warning and #error
reg_define = re.compile(\
	'^[ \t]*(#|%:)[ \t]*(ifdef|ifndef|if|else|elif|endif|include|import|define|undef|pragma)[ \t]*(.*)\r*$',
	re.IGNORECASE | re.MULTILINE)
re_mac = re.compile("^[a-zA-Z_]\w*")
re_fun = re.compile('^[a-zA-Z_][a-zA-Z0-9_]*[(]')
re_pragma_once = re.compile('^\s*once\s*', re.IGNORECASE)
reg_nl = re.compile('\\\\\r*\n', re.MULTILINE)
reg_cpp = re.compile(\
	r"""(/\*[^*]*\*+([^/*][^*]*\*+)*/)|//[^\n]*|("(\\.|[^"\\])*"|'(\\.|[^'\\])*'|.[^/"'\\]*)""",
	re.MULTILINE)
trig_def = [('??'+a, b) for a, b in zip("=-/!'()<>", r'#~\|^[]{}')]

NUM   = 'i'
OP    = 'O'
IDENT = 'T'
STR   = 's'
CHAR  = 'c'

tok_types = [NUM, STR, IDENT, OP]
exp_types = [
	r"""0[xX](?P<hex>[a-fA-F0-9]+)(?P<qual1>[uUlL]*)|L*?'(?P<char>(\\.|[^\\'])+)'|(?P<n1>\d+)[Ee](?P<exp0>[+-]*?\d+)(?P<float0>[fFlL]*)|(?P<n2>\d*\.\d+)([Ee](?P<exp1>[+-]*?\d+))?(?P<float1>[fFlL]*)|(?P<n4>\d+\.\d*)([Ee](?P<exp2>[+-]*?\d+))?(?P<float2>[fFlL]*)|(?P<oct>0*)(?P<n0>\d+)(?P<qual2>[uUlL]*)""",
	r'L?"([^"\\]|\\.)*"',
	r'[a-zA-Z_]\w*',
	r'%:%:|<<=|>>=|\.\.\.|<<|<%|<:|<=|>>|>=|\+\+|\+=|--|->|-=|\*=|/=|%:|%=|%>|==|&&|&=|\|\||\|=|\^=|:>|!=|##|[\(\)\{\}\[\]<>\?\|\^\*\+&=:!#;,%/\-\?\~\.]',
]
reg_clexer = re.compile('|'.join(["(?P<%s>%s)" % (name, part) for name, part in zip(tok_types, exp_types)]), re.M)

accepted  = 'a'
ignored   = 'i'
undefined = 'u'
skipped   = 's'

def repl(m):
	s = m.group(1)
	if s is not None: return ' '
	s = m.group(3)
	if s is None: return ''
	return s

def filter_comments(filename):
	# return a list of tuples : keyword, line
	f = open(filename, "r")
	code = f.read()
	f.close()
	if use_trigraphs:
		for (a, b) in trig_def: code = code.split(a).join(b)
	code = reg_nl.sub('', code)
	code = reg_cpp.sub(repl, code)
	return [(m.group(2), m.group(3)) for m in re.finditer(reg_define, code)]

prec = {}
# op -> number, needed for such expressions:   #if 1 && 2 != 0
ops = ['. * / %', '+ -', '<< >>', '< <= >= >', '== !=', '& | ^', '&& ||', ',']
for x in range(len(ops)):
	syms = ops[x]
	for u in syms.split():
		prec[u] = x

def reduce_nums(val_1, val_2, val_op):
	#print val_1, val_2, val_op
	# pass two values, return a value

	# now perform the operation, make certain a and b are numeric
	try:    a = 0 + val_1
	except: a = int(val_1)
	try:    b = 0 + val_2
	except: b = int(val_2)

	d = val_op
	if d == '%':  c = a%b
	elif d=='+':  c = a+b
	elif d=='-':  c = a-b
	elif d=='*':  c = a*b
	elif d=='/':  c = a/b
	elif d=='|':  c = a|b
	elif d=='||': c = int(a or b)
	elif d=='&':  c = a&b
	elif d=='&&': c = int(a and b)
	elif d=='==': c = int(a == b)
	elif d=='!=': c = int(a != b)
	elif d=='<=': c = int(a <= b)
	elif d=='<':  c = int(a < b)
	elif d=='>':  c = int(a > b)
	elif d=='>=': c = int(a >= b)
	elif d=='^':  c = int(a^b)
	elif d=='<<': c = a<<b
	elif d=='>>': c = a>>b
	else: c = 0
	return c

def get_expr(lst, defs, ban):

	if not lst: return ([], [], [])

	(p, v) = lst[0]
	if p == NUM:
		return (p, v, lst[1:])

	elif p == STR:
		try:
			(p2, v2) = lst[1]
			if p2 == STR: return (p, v+v2, lst[2:])
		except IndexError: pass

		return (p, v, lst[1:])

	elif p == OP:
		if v in ['+', '-', '~', '!']:
			(p2, v2, lst2) = get_expr(lst[1:], defs, ban)
			if p2 != NUM: raise PreprocError, "num expected %s" % str(lst)
			if v == '+': return (p2, v2, lst2)

			# TODO other cases are be complicated
			return (p2, v2, lst2)

		elif v == '#':
			(p2, v2, lst2) = get_expr(lst[1:], defs, ban)
			if p2 != IDENT: raise PreprocError, "ident expected %s" % str(lst)
			return get_expr([(STR, v2)]+lst2, defs, ban)

		elif v == '(':
			count_par = 0
			i = 0
			for _, v in lst:
				if v == ')':
					count_par -= 1
					if count_par == 0: break
				elif v == '(': count_par += 1
				i += 1
			else:
				raise PreprocError, "rparen expected %s" % str(lst)

			ret = process_tokens(lst[1:i], defs, ban)
			if len(ret) == 1:
				(p, v) = ret[0]
				return (p, v, lst[i+1:])
			else:
				#return (None, lst1, lst[i+1:])
				raise PreprocError, "cannot reduce %s" % str(lst)

	elif p == IDENT:
		if len(lst)>1:
			(p2, v2) = lst[1]
			if v2 == "##":
				# token pasting, reevaluate the identifier obtained
				(p3, v3) = lst[2]
				if p3 != IDENT and p3 != NUM and p3 != OP:
					raise PreprocError, "%s: ident expected after '##'" % str(lst)
				return get_expr([(p, v+v3)]+lst[3:], defs, ban)

		if v.lower() == 'defined':
			(p2, v2) = lst[1]
			off = 2
			if v2 == '(':
				(p3, v3) = lst[2]
				if p3 != IDENT: raise PreprocError, 'expected an identifier after a "defined("'
				(p2, v2) = lst[3]
				if v2 != ')': raise PreprocError, 'expected a ")" after a "defined(x"'
				off = 4
			elif p2 != IDENT:
				raise PreprocError, 'expected a "(" or an identifier after a defined'

			x = 0
			if v2 in defs: x = 1
			#return get_expr([(NUM, x)] + lst[off:], defs, ban)
			return (NUM, x, lst[off:])

		elif not v in defs:
			return (p, v, lst[1:])

		# tokenize on demand
		if type(defs[v]) is types.StringType:
			v, k = extract_macro(defs[v])
			defs[v] = k
		macro_def = defs[v]

		if not macro_def[0]:
			# simple macro, substitute, and reevaluate
			lst = macro_def[1] + lst[1:]
			return get_expr(lst, defs, ban)
		else:
			# collect the arguments for the funcall
			params = []
			i = 1
			p2, v2 = lst[i]
			if p2 != OP or v2 != '(': raise PreprocError, "invalid function call '%s'" % v

			one_param = []
			count_paren = 0
			try:
				while 1:
					i += 1
					p2, v2 = lst[i]

					if p2 == OP and count_paren == 0:
						if v2 == '(':
							one_param.append((p2, v2))
							count_paren += 1
						elif v2 == ')':
							if one_param: params.append(one_param)
							lst = lst[i+1:]
							break
						elif v2 == ',':
							if not one_param: raise PreprocError, "empty param in funcall %s" % p
							params.append(one_param)
							one_param = []
						else:
							one_param.append((p2, v2))
					else:
						one_param.append((p2, v2))
						if   v2 == '(': count_paren += 1
						elif v2 == ')': count_paren -= 1

			except IndexError, e:
				#raise PreprocError, 'invalid function call %s: missing ")"' % p
				raise

			# substitute the arguments within the define expression
			accu = []
			table = macro_def[0]
			for p, v in macro_def[1]:
				if p == IDENT and v in table: accu += params[table[v]]
				else: accu.append((p, v))

			return get_expr(accu + lst, defs, ban)

def process_tokens(lst, defs, ban):
	accu = []
	while lst:
		p, v, nlst = get_expr(lst, defs, ban)
		if p == NUM:
			if not nlst: return [(p, v)] # finished

			op1, ov1 = nlst[0]
			if op1 != OP:
				raise PreprocError, "op expected %s" % str(lst)

			if ov1 == '?':
				i = 0
				count_par = 0
				for _, k in nlst:
					if   k == ')': count_par -= 1
					elif k == '(': count_par += 1
					elif k == ':' and count_par == 0: break
					i += 1
				else: raise PreprocError, "ending ':' expected %s" % str(lst)

				if reduce_nums(v, 0, '+'): lst = nlst[1:i]
				else: lst = nlst[i+1:]
				continue

			elif ov1 == ',':
				lst = nlst[1:]
				continue

			p2, v2, nlst = get_expr(nlst[1:], defs, ban)
			if p2 != NUM: raise PreprocError, "num expected after op %s" % str(lst)
			if nlst:
				# op precedence
				op3, ov3 = nlst[0]
				if prec[ov3] < prec[ov1]:
					#print "ov3", ov3, ov1
					# as needed
					p4, v4, nlst2 = get_expr(nlst[1:], defs, ban)
					v5 = reduce_nums(v2, v4, ov3)
					lst = [(p, v), (op1, ov1), (NUM, v5)] + nlst2
					continue

			# no op precedence or empty list, reduce the first tokens
			lst = [(NUM, reduce_nums(v, v2, ov1))] + nlst
			continue

		elif p == STR:
			if nlst: raise PreprocError, "sequence must terminate with a string %s" % str(nlst)
			return [(p, v)]

		return (None, None, [])

def eval_macro(lst, adefs):
	# look at the result, and try to return a 0/1 result
	ret = process_tokens(lst, adefs, [])
	if len(ret) != 1:
		raise IndexError, "error!!!"

	p, v = ret[0]
	return int(v) != 0

def try_exists(node, list):
	lst = []+list
	while lst:
		name = lst.pop(0)
		# it is not a build node, else we would already got it
		path = os.path.join(node.abspath(), name)
		try: os.stat(path)
		except OSError:
			#traceback.print_exc()
			return None
		node = node.find_dir_lst([name])
	return node

class cparse(object):
	def __init__(self, nodepaths=None, strpaths=None, defines=None):
		#self.lines = txt.split('\n')
		self.lines = []

		if defines is None:
			self.defs  = {}
		else:
			self.defs  = dict(defines) # make a copy
		self.state = []

		self.env   = None # needed for the variant when searching for files

		# include paths
		if strpaths is None:
			self.strpaths = []
		else:
			self.strpaths = strpaths
		self.pathcontents = {}

		self.deps  = []
		self.deps_paths = []

		if nodepaths is None:
			self.m_nodepaths = []
		else:
			self.m_nodepaths = nodepaths
		self.m_nodes = []
		self.m_names = []

		# dynamic cache
		try:
			self.parse_cache = Params.g_build.parse_cache
		except AttributeError:
			Params.g_build.parse_cache = {}
			self.parse_cache = Params.g_build.parse_cache

	def tryfind(self, filename):
		global g_findall
		if self.m_nodepaths:
			found = 0
			for n in self.m_nodepaths:
				found = n.find_source(filename, create=0)
				if found:
					break
			# second pass for unreachable folders
			if not found and g_findall:
				lst = filename.split('/')
				if len(lst)>1:
					lst=lst[:-1] # take the folders only
					try: cache = Params.g_build.preproc_cache
					except AttributeError:
						cache = {}
						setattr(Params.g_build, 'preproc_cache', cache)
					key = hash( (str(self.m_nodepaths), str(lst)) )
					if not cache.get(key, None):
						cache[key] = 1
						for n in self.m_nodepaths:
							node = try_exists(n, lst)
							if node:
								found = n.find_source(filename, create=0)
								if found: break
			if found:
				self.m_nodes.append(found)
				# Qt
				if filename[-4:] != '.moc': self.addlines(found.abspath(self.env))
			if not found:
				if not filename in self.m_names:
					self.m_names.append(filename)
		else:
			found = 0
			for p in self.strpaths:
				if not p in self.pathcontents.keys():
					self.pathcontents[p] = os.listdir(p)
				if filename in self.pathcontents[p]:
					#print "file %s found in path %s" % (filename, p)
					np = os.path.join(p, filename)
					# screw Qt two times
					if filename[-4:] != '.moc': self.addlines(np)
					self.deps_paths.append(np)
					found = 1
			if not found:
				pass
				#error("could not find %s " % filename)

	def addlines(self, filepath):
		pc = self.parse_cache
		debug("reading file %r" % filepath, 'preproc')
		if filepath in pc.keys():
			self.lines = pc[filepath] + self.lines
			return

		try:
			lines = filter_comments(filepath)
			pc[filepath] = lines # memorize the lines filtered
			self.lines = lines + self.lines
		except IOError:
			raise PreprocError, "could not read the file %s" % filepath
		except Exception:
			if Params.g_verbose > 0:
				warning("parsing %s failed" % filepath)
				traceback.print_exc()

	def start(self, node, env):
		debug("scanning %s (in %s)" % (node.m_name, node.m_parent.m_name), 'preproc')

		self.env = env
		variant = node.variant(env)

		self.addlines(node.abspath(env))
		if env['DEFLINES']:
			self.lines = [('define', x) for x in env['DEFLINES']] + self.lines

		while self.lines:
			# TODO we can skip evaluating conditions (#if) only when we are
			# certain they contain no define, undef or include
			(type, line) = self.lines.pop(0)
			try:
				self.process_line(type, line)
			except Exception, ex:
				if Params.g_verbose:
					warning("line parsing failed (%s): %s" % (str(ex), line))
					traceback.print_exc()

	# debug only
	def start_local(self, filename):
		self.addlines(filename)
		#print self.lines
		while self.lines:
			(type, line) = self.lines.pop(0)
			try:
				self.process_line(type, line)
			except Exception, ex:
				if Params.g_verbose:
					warning("line parsing failed (%s): %s" % (str(ex), line))
					traceback.print_exc()
				raise
	def isok(self):
		if not self.state: return 1
		if self.state[0] in [skipped, ignored]: return None
		return 1

	def process_line(self, token, line):

		debug("line is %s - %s state is %s" % (token, line, self.state), 'preproc')

		# make certain we define the state if we are about to enter in an if block
		if token in ['ifdef', 'ifndef', 'if']:
			self.state = [undefined] + self.state

		# skip lines when in a dead 'if' branch, wait for the endif
		if not token in ['else', 'elif', 'endif']:
			if not self.isok():
				#print "return in process line"
				return

		def get_name(line):
			ret = tokenize(line)
			for (x, y) in ret:
				if x == IDENT: return y
			return ''

		if token == 'if':
			ret = eval_macro(tokenize(line), self.defs)
			if ret: self.state[0] = accepted
			else: self.state[0] = ignored
		elif token == 'ifdef':
			name = get_name(line)
			if name in self.defs.keys(): self.state[0] = accepted
			else: self.state[0] = ignored
		elif token == 'ifndef':
			name = get_name(line)
			if name in self.defs.keys(): self.state[0] = ignored
			else: self.state[0] = accepted
		elif token == 'include' or token == 'import':
			(type, inc) = extract_include(line, self.defs)
			debug("include found %s    (%s) " % (inc, type), 'preproc')
			if type == '"' or not strict_quotes:
				if not inc in self.deps:
					self.deps.append(inc)
				# allow double inclusion
				self.tryfind(inc)
		elif token == 'elif':
			if self.state[0] == accepted:
				self.state[0] = skipped
			elif self.state[0] == ignored:
				if eval_macro(tokenize(line), self.defs):
					self.state[0] = accepted
		elif token == 'else':
			if self.state[0] == accepted: self.state[0] = skipped
			elif self.state[0] == ignored: self.state[0] = accepted
		elif token == 'endif':
			self.state.pop(0)
		elif token == 'define':
			match = re_mac.search(line)
			if match:
				name = match.group(0)
				debug("define %s   %s" % (name, line), 'preproc')
				self.defs[name] = line
			else:
				raise PreprocError, "invalid define line %s" % line
		elif token == 'undef':
			name = get_name(line)
			if name and name in self.defs:
				self.defs.__delitem__(name)
				#print "undef %s" % name
		elif token == 'pragma':
			if re_pragma_once.search(line.lower()):
				pass
				#print "found a pragma once"

def extract_macro(txt):
	t = tokenize(txt)
	if re_fun.search(txt):
		p, name = t[0]

		p, v = t[1]
		if p != OP: raise PreprocError, "expected open parenthesis"

		i = 1
		pindex = 0
		params = {}
		wantident = 1

		while 1:
			i += 1
			p, v = t[i]

			if wantident:
				if p == IDENT:
					params[v] = pindex
					pindex += 1
				elif v == '...':
					pass
				else:
					raise PreprocError, "expected ident"
			else:
				if v == ',':
					pass
				elif v == ')':
					break
				elif v == '...':
					raise PreprocError, "not implemented"
			wantident = not wantident

		return (name, [params, t[i+1:]])
	else:
		(p, v) = t[0]
		return (v, [[], t[1:]])

re_include = re.compile('^\s*(<(.*)>|"(.*)")\s*')
def extract_include(txt, defs):
	def replace_v(m):
		return m.group(1)

	if re_include.search(txt):
		t = re_include.sub(replace_v, txt)
		return (t[0], t[1:-1])

	# perform preprocessing and look at the result, it must match an include
	tokens = tokenize(txt)
	p, v = tokens[0]
	if v == '<':
		txt = "".join([y for (x, y) in ret])
	elif p == STR:
		txt = '"%s"' % val
	else:
		tokens = process_tokens(tokens, defs, [])
		p, v = tokens[0]
		if p != STR:
			raise PreprocError, "could not parse includes %s" % str(tokens)
		txt = '"%s"' % v

	# TODO eliminate this regexp
	if re_include.search(txt):
		t = re_include.sub(replace_v, txt)
		return (t[0], t[1:-1])

	# if we come here, parsing failed
	raise PreprocError, "include parsing failed %s" % txt

def parse_char(txt):
	# TODO way too complicated!
	try:
		if not txt: raise PreprocError
		if txt[0] != '\\': return ord(txt)
		c = txt[1]
		if c in "ntbrf\\'": return ord(eval('"\\%s"' % c)) # FIXME eval is slow and  ugly
		elif c == 'x':
			if len(txt) == 4 and txt[3] in string.hexdigits: return int(txt[2:], 16)
			return int(txt[2:], 16)
		elif c.isdigit():
			for i in 3, 2, 1:
				if len(txt) > i and txt[1:1+i].isdigit():
					return (1+i, int(txt[1:1+i], 8))
		else:
			raise PreprocError
	except:
		raise PreprocError, "could not parse char literal '%s'" % v

def tokenize(s):
	ret = []
	for match in reg_clexer.finditer(s):
		m = match.group
		for name in tok_types:
			v = m(name)
			if v:
				if name == IDENT:
					try: v = g_optrans[v]; name = OP
					except KeyError:
						# c++ specific
						if v.lower() == "true":
							v = 1
							name = NUM
						elif v.lower() == "false":
							v = 0
							name = NUM
				elif name == NUM:
					if m('oct'): v = int(v, 8)
					elif m('hex'): v = int(m('hex'), 16)
					elif m('n0'): v = m('n0')
					else:
						v = m('char')
						if v: v = parse_char(v)
						else: v = m('n2') or m('n4')
# till i manage to understand what it does exactly (ita)
#					#if v[0] == 'L': v = v[1:]
#					r = parse_literal(v[1:-1])
#					if r[0]+2 != len(v):
#						raise PreprocError, "could not parse char literal %s" % v
#					v = r[1]
				elif name == OP:
					if v == '%:': v='#'
					elif v == '%:%:': v='##'

				ret.append((name, v))
				break
	return ret

# quick test #
if __name__ == "__main__":
	Params.g_verbose = 2
	Params.g_zones = ['preproc']
	class dum:
		def __init__(self):
			self.parse_cache = {}
	Params.g_build = dum()

	try: arg = sys.argv[1]
	except: arg = "file.c"

	paths = ['.']
	f = open(arg, "r"); txt = f.read(); f.close()

	m1   = [[], [(NUM, 1), (OP, '+'), (NUM, 2)]]
	fun1 = [[(IDENT, 'x'), (IDENT, 'y')], [(IDENT, 'x'), (OP, '##'), (IDENT, 'y')]]
	fun2 = [[(IDENT, 'x'), (IDENT, 'y')], [(IDENT, 'x'), (OP, '*'), (IDENT, 'y')]]

	def test(x):
		y = process_tokens(tokenize(x), {'m1':m1, 'fun1':fun1, 'fun2':fun2}, [])
		#print x, y

	test("0&&2<3")
	test("(5>1)*6")
	test("1+2+((3+4)+5)+6==(6*7)/2==1*-1*-1")
	test("1,2,3*9,9")
	test("1?77:88")
	test("0?77:88")
	test("1?1,(0?5:9):3,4")
	test("defined inex")
	test("defined(inex)")
	try: test("inex")
	except: print "inex is not defined"
	test("m1*3")
	test("7*m1*3")
	test("fun1(m,1)")
	test("fun2(2, fun1(m, 1))")
	#test("foo##.##h")

	gruik = cparse(strpaths = paths)
	gruik.start_local(arg)
	print "we have found the following dependencies"
	print gruik.deps
	print gruik.deps_paths

	#f = open(arg, "r")
	#txt = f.read()
	#f.close()
	#print tokenize(txt)

