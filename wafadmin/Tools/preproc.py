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
"""

import re, sys, os, string
sys.path = ['.', '..'] + sys.path
import Params
from Params import debug, error, warning
import traceback

class PreprocError(Exception):
	pass

# ignore #warning and #error
reg_define = re.compile('^\s*(#|%:)\s*(ifdef|ifndef|if|else|elif|endif|include|import|define|undef|pragma)\s*(.*)\r*$', re.MULTILINE)
reg_pragma_once = re.compile('^\s*once\s*')
reg_nl = re.compile('\\\\\r*\n', re.MULTILINE)
reg_cpp = re.compile(r"""(/\*[^*]*\*+([^/*][^*]*\*+)*/)|//[^\n]*|("(\\.|[^"\\])*"|'(\\.|[^'\\])*'|.[^/"'\\]*)""", re.MULTILINE)
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

	code = reg_nl.sub('', code)
	code = reg_cpp.sub(repl, code)

	return [(m.group(2), m.group(3)) for m in re.finditer(reg_define, code)]

strict_quotes = 0
"Keep <> for system includes (do not search for those includes)"

alpha = string.letters + '_' + string.digits

accepted  = 'a'
ignored   = 'i'
undefined = 'u'
skipped   = 's'

num = 'i' # number
op = '@' # operator
ident = 'T' # identifier
stri = 's' # string
chr = 'c' # char

# TODO handle the trigraphs too
trigs = {
'=' : '#',
'-' : '~',
'/' : '\\',
'!' : '|',
'\'': '^',
'(' : '[',
')' : ']',
'<' : '{',
'>' : '}',
}

puncs = []
puncs.append('< > + - * / % = & | ^ . : ! # [ ] ( ) { } ~ ? ; ,'.split())
puncs.append('<< <% <: <= >> >= ++ += -- -> -= *= /= %: %= %> == && &= || |= ^= :> != ##'.split())
puncs.append('<<= >>= ...'.split())
puncs.append('%:%: '.split())

# Here is the small grammar we try to follow:
# result := top
# top    := expr | expr op top
# expr   := val | ( top ) | !expr | -expr
# The following rule should be taken into account:
# val    := num | num . num | num "e" num

def get_expr(tokens):
	if len(tokens) == 0: return (None, None, tokens)
	lst = []+tokens
	(tok, val) = lst.pop(0)
	if tok == num:
		return (tok, val, lst)
	elif tok == op:
		if val == '!':
			(tok2, val2, lst2) = get_expr(lst)
			v = int(val2)
			if v == 0: v = 1
			else:      v = 0
			return (num, v, lst2)
		elif val == '-':
			(tok2, val2, lst2) = get_expr(lst)
			v = - int(val2)
			return (num, v, lst2)
		elif val == '(':
			count_par = 0
			accu = []
			while 1:
				(tok, val) = lst.pop(0)
				if tok == op:
					if val == ')':
						if count_par == 0:
							break
						else:
							count_par -= 1
					elif val == '(':
						count_par += 1
				accu.append( (tok, val) )
			(tok_tmp, val_tmp, lst_tmp) = get_top(accu)
			# TODO raise an exception if the expression could not be reduced properly
			#if lst_tmp: raise ...
			return (tok_tmp, val_tmp, lst)
	else:
		pass
		#print "could not get an expression from ", tokens

	return (None, None, tokens)

def get_top(tokens):
	if len(tokens) == 0: return (None, tokens)
	lst = []+tokens

	(tok_1, val_1, nlst) = get_expr(lst)
	if tok_1 == None: return (None, None, tokens) # we cannot reduce the list of tokens

	#print "tok 1 is ", tok_1

	if len(nlst) == 0: return (tok_1, val_1, nlst)
	(tok_op, val_op) = nlst.pop(0)
	(tok_2, val_2, nlst) = get_top(nlst)

	# TODO: what if users are really mad and use in #if blocks
	# floating-point arithmetic ???
	# strings ???

	# now perform the operation
	a = int(val_1)
	b = int(val_2)
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
	elif d=='<=': c = int(a <= b)
	elif d=='<':  c = int(a < b)
	elif d=='>':  c = int(a > b)
	elif d=='>=': c = int(a >= b)
	elif d=='^':  c = int(a^b)
	elif d=='<<': c = a<<b
	elif d=='>>': c = a>>b

	# now make the operation and return...
	return (num, c, nlst)

def reduce(tokens):
	if not tokens: return (stri, '')
	if len(tokens) == 1: return tokens

	lst = []+tokens

	#print "lst is %s (len %d)  [%s]" % (str(tokens), len(tokens), " ".join([str(x[1]) for x in tokens]))
	#print "\n\n\n"

	(tok, val, lst) = get_top(lst)
	if tok == None: return tokens
	#print "eval returned token", tok

	#print "in reduce, returning ", tokens
	return [(tok, val)]

def eval_fun(name, params, defs, ban=[]):

	fun_def = defs[name]
	fun_code = []+fun_def[1]
	fun_args = fun_def[0]

	# a map  x->1st param, y->2nd param, etc
	param_index = {}
	i = 0
	for u in fun_args:
		param_index[u[1]] = i
		i += 1

	# substitute the arguments within the define expression
	accu = []
	while fun_code:
		(tok, val) = fun_code.pop(0)
		if tok == op:
			if val == '#':
				# the next token is one of the args
				(tok_next, val_next) = fun_code.pop(0)
				tokens = params[param_index[val_next]]
				# macro parameter evaluation is postponed
				ret = eval_tokens(tokens, defs, ban+[name])
				ret = (stri, "".join([y for (x,y) in ret]))
				accu.append(ret)

			elif val == '##':
				# the next token is an identifier (token pasting)
				(tok_next, val_next) = fun_code.pop(0)
				(tok_back, val_back) = accu[-1]
				accu = accu[:-1]
				new_token = (ident, val_back+val_next)
				accu.append(new_token)
				# FIXME this supposes that "a##b(foo)" evaluates as "ab(foo)"
			else:
				accu.append((tok, val))

		elif tok == ident:
			if val in param_index:
				code = params[param_index[val]]
				accu += eval_tokens(code, defs, ban+[name])
			else:
				accu.append((tok, val))
		else:
			accu.append((tok, val))

	ret = eval_tokens(accu, defs, ban+[name])
	return ret

def eval_tokens(lst, adefs, ban=[]):
	#print "lst is ", lst
	lst = []+lst # lists are mutable

	#print "\n\n\n\n"
	#print "---eval---> ", lst
	#print "-------- eval macro --------"
	#for x in adefs:
	#	print x, "\t\t", adefs[x]
	#print "------ end eval macro ------"
	#print "the huge lst is ", lst

	# substitute the defines (functions and simple macros)
	accu = []
	while lst:
		(tok, val) = lst.pop(0)

		if tok == ident and val in adefs: # TODO the defined() and sizeof() cases
			# the identifier is a macro
			name = val

			fun_def = adefs[val]
			fun_args=[]
			if fun_def: fun_args = fun_def[0]
			if fun_args == None:
				# simple macro
				# make the substitution, TODO make certain to disallow recursion
				lst = fun_def[1] + lst
			else:
				# function call, collect the arguments
				params = []
				tmp = []
				(tok, val) = lst.pop(0)
				if tok != op or val != '(': raise ParseError, "invalid function call "+name
				count_paren = 0
				while 1:
					(tok, val) = lst.pop(0)
					# stop condition
					if count_paren == 0 and tok == op:
						if val == ')':
							if tmp: params.append(tmp)
							break
						elif val == ',':
							if not tmp: raise ParseError, "invalid function call "+name
							params.append(tmp)
							tmp = []
							continue

					# all other cases we just append the tokens to tmp
					tmp.append((tok, val))

					# but watch out for the matching parenthesis
					if tok == op:
						if val == '(':
							count_paren += 1
						elif val == ')':
							count_paren -= 1

				accu += eval_fun(name, params, adefs)
		else:
			accu.append((tok, val))

	# now reduce the expressions if possible, like 1+1->2, no more evaluation should take place
	accu = reduce(accu)
	return accu

def eval_macro(lst, adefs):
	# look at the result, and try to return a 0/1 result
	ret = eval_tokens(lst, adefs, [])

	if len(ret) == 0:
		debug("could not evaluate %s to true or false (empty list)" % str(ret), 'preproc')
		return False
	if len(ret) > 1:
		debug("could not evaluate %s to true or false (could not reduce the expression)" % str(ret), 'preproc')
		return False
	if len(ret) == 1:
		(tok, val) = ret[0]
		if tok == num:
			r = int(val)
			return r != 0
		elif tok == ident:
			if val.lower() == 'true': return True
			elif val.lower() == 'false': return False
			else: "could not evaluate %s to true or false (not a boolean)" % str(lst)
		else:
			debug("could not evaluate %s to true or false (not a number/boolean)" % str(lst), 'preproc')
	return ret

class cparse:
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
		if self.m_nodepaths:
			found = 0
			for n in self.m_nodepaths:
				found = n.find_source(filename, create=0)
				if found:
					self.m_nodes.append(found)
					# screw Qt
					if filename[-4:] != '.moc': self.addlines(found.abspath(self.env))
					break
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
				if x == ident: return y
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
			(type, inc) = tokenize_include(line, self.defs)
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
			(name, val) = tokenize_define(line)
			debug("define %s   %s" % (name, str(val)), 'preproc')
			self.defs[name] = val
		elif token == 'undef':
			name = get_name(line)
			if name and name in self.defs:
				self.defs.__delitem__(name)
				#print "undef %s" % name
		elif token == 'pragma':
			if reg_pragma_once.search(line.lower()):
				print "found a pragma once"

re_function = re.compile('^[a-zA-Z_][a-zA-Z0-9_]*[(]')
def tokenize_define(txt):
	t = tokenize(txt)
	if re_function.search(txt):
		# this means we have a function
		params = []
		(tok, val) = t.pop(0)
		name = val

		(tok, val) = t.pop(0)
		if tok != op: raise PreprocError, "expected open parenthesis"
		while 1:
			(tok, val) = t.pop(0)

			if tok == op and val == ')':
				break
			if tok != ident and (tok != op and val != '...'):
				raise PreprocError, "expected ident"

			(tok2, val2) = t.pop(0)
			if tok2 == op and val2 == '...':
				params.append((ident, val+val2)) # to get the varargs "z..."
			elif tok2 == op and val2 == ')':
				if tok == ident:
					params.append((tok, val))
				else:
					params.append((ident, val))
				break
			elif tok2 == op and val2 == ',':
				params.append((tok, val))
			else:
				raise PreprocError, "unexpected token "+str((tok2, val2))

		return (name, [params, t])
	else:
		(tok, val) = t.pop(0)
		return (val, [None, t])

re_include = re.compile('^\s*(<(.*)>|"(.*)")\s*')
def tokenize_include(txt, defs):
	def replace_v(m):
		return m.group(1)

	if re_include.search(txt):
		t = re_include.sub(replace_v, txt)
		return (t[0], t[1:-1])

	# perform preprocessing and look at the result, it must match an include
	tokens = tokenize(txt)
	ret = eval_tokens(tokens, defs)
	(tok, val) = ret[0]
	if len(ret) == 1 and tok == stri:
		# a string token, quote it
		txt = '"%s"' % val
	elif tok == op:
		# a list of tokens, such as <,iostream,.,h,>, concatenate
		txt = "".join(y for (x,y) in ret)
		# TODO if we discard whitespaces, we could test for val == "<"
	else:
		raise PreprocError, "could not parse %s" % str(ret)

	if re_include.search(txt):
		t = re_include.sub(replace_v, txt)
		return (t[0], t[1:-1])

	# if we come here, parsing failed
	raise PreprocError, "include parsing failed %s" % txt

def tokenize(txt):
	i = 0
	max = len(txt)

	abuf = []
	while i<max:
		#print abuf
		#print "---------------------------------"

		c = txt[i]

		#print "look ", c, '   ->', i

		if c == ' ' or c == '\t':
			i += 1
			# white space
			continue
		elif c == '"':
			# string
			i += 1
			c=''
			buf = []
			while i<max:
				p = c
				c = txt[i]
				i += 1
				if c == '"':
					cnt = 0
					while 1:
						#print "cntcnt = ", str(cnt), txt[i-2-cnt]
						if txt[i-2-cnt] == '\\': cnt+=1
						else: break
					#print "cnt is ", str(cnt)
					if (cnt%2)==0: break
					else: buf.append(c)
				else:
					buf.append(c)
			abuf.append((stri, ''.join(buf)))
			i += 1
		elif c == '\'':
			# char
			buf = []
			i += 1
			c = txt[i]
			i += 1
			buf.append(c)
			# skip one more character if there is a backslash '\''
			if c == '\\':
				c = txt[i]
				i += 1
				buf.append(c)
			c = txt[i]
			i += 1
			if c != '\'': error("uh-oh, invalid character"+str(c)) # TODO special chars
			abuf.append((chr, ''.join(buf)))

			i += 1

		elif c in string.digits:
			# number
			buf =[]
			while 1:
				c = txt[i]
				if c in string.digits: # TODO floats
					buf.append(c)
					i += 1
					if c >= max: break
				else:
					break
			abuf.append((num, ''.join(buf)))
		elif c in alpha:
			# identifier (except for the boolean operators 'and', 'or' and 'not')
			buf = []
			while 1:
				c = txt[i]
				if c in alpha:
					buf.append(c)
					i += 1
					if i>= max: break
				else:
					break
			name = ''.join(buf).lower()
			if name == 'not':
				abuf.append((op, '!'))
			elif name == 'or':
				abuf.append((op, '||'))
			elif name == 'and':
				abuf.append((op, '&&'))
			else:
				abuf.append((ident, ''.join(buf)))
		else:
			for x in [3, 2, 1, 0]:
				if i < max - x:
					s = txt[i:i+x+1]
					if s in puncs[x]:
						break
			else:
				raise PreprocError, "unknown op %s" % txt[i-1:]
			abuf.append((op, s))
			i += x+1
	return abuf

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
	gruik = cparse(strpaths = paths)
	gruik.start_local(arg)
	print "we have found the following dependencies"
	print gruik.deps
	print gruik.deps_paths

