# Pretty-printers for fastrpc. Based on svn://gcc.gnu.org/svn/gcc/trunk/libstdc++-v3/python.

# Copyright (C) 2008, 2009, 2010, 2011 Free Software Foundation, Inc.

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import gdb
import itertools
from datetime import datetime
import re

# Try to use the new-style pretty-printing if available.
_use_gdb_pp = True
try:
    import gdb.printing
except ImportError:
    _use_gdb_pp = False

def dynamic_type(value):
    # new gdb (7.3) should bring dynamic_type member
    if hasattr(value, "dynamic_type"): return value.dynamic_type

    # we try recognize type from vtable
    dtor = str(value['_vptr.Value_t'].dereference())
    # 0x000000000040434f <FRPC::String_t::~String_t()> to FRPC::String_t
    typename = dtor[dtor.find('<') + 1:dtor.rfind(':') - 1].strip()
    return gdb.lookup_type(typename)
#enddef

class FRPCNullPrinter:
    "Print a null FRPC value"

    def __init__ (self, typename, val):
        pass

    def to_string (self):
        return ""

class FRPCPrimitiveValuePrinter:
    "Print a primitive FRPC value"

    def __init__ (self, typename, val):
        self.val = val.cast (gdb.lookup_type (typename))

    def to_string (self):
        return self.val['value']

class FRPCDateTimePrinter:
    "Print a datetime FRPC value"

    def __init__ (self, typename, val):
        self.val = val.cast (gdb.lookup_type (typename))

    def to_string (self):
        return "%s %s" % (datetime(self.val["year"],
                                     self.val["month"],
                                     self.val["day"],
                                     self.val["hour"],
                                     self.val["minute"],
                                     self.val["sec"]).isoformat(' '),
                            self.val["timeZone"])

class FRPCArrayPrinter:
    "Print a FRPC::Array_t"

    class _iterator:
        def __init__ (self, start, finish):
            self.item = start
            self.finish = finish
            self.count = 0

        def __iter__(self):
            return self

        def next(self):
            count = self.count
            self.count = self.count + 1
            if self.item == self.finish:
                raise StopIteration
            elt = self.item.dereference().dereference()
            self.item = self.item + 1
            return ('[%d]' % count, elt.cast(dynamic_type(elt)))

    def __init__ (self, typename, val):
        self.val = val.cast (gdb.lookup_type (typename))
        self.typename = typename

    def children (self):
        val = self.val['arrayData']
        start = val['_M_impl']['_M_start']
        finish = val['_M_impl']['_M_finish']
        return self._iterator (start, finish)

    def to_string (self):
        val = self.val['arrayData']
        start = val['_M_impl']['_M_start']
        finish = val['_M_impl']['_M_finish']
        end = val['_M_impl']['_M_end_of_storage']
        return ('(%s of length %d, capacity %d)'
                % (self.typename, int (finish - start), int (end - start)))

class FRPCStructIterator:
    def __init__(self, rbtree):
        self.size = rbtree['_M_t']['_M_impl']['_M_node_count']
        self.node = rbtree['_M_t']['_M_impl']['_M_header']['_M_left']
        self.count = 0

    def __iter__(self):
        return self

    def __len__(self):
        return int (self.size)

    def next(self):
        if self.count == self.size:
            raise StopIteration
        result = self.node
        self.count = self.count + 1
        if self.count < self.size:
            # Compute the next node.
            node = self.node
            if node.dereference()['_M_right']:
                node = node.dereference()['_M_right']
                while node.dereference()['_M_left']:
                    node = node.dereference()['_M_left']
            else:
                parent = node.dereference()['_M_parent']
                while node == parent.dereference()['_M_right']:
                    node = parent
                    parent = parent.dereference()['_M_parent']
                if node.dereference()['_M_right'] != parent:
                    node = parent
            self.node = node
        return result

class FRPCStructPrinter:
    "Print a FRPC::Struct_t"

    class _iter:
        def __init__(self, rbiter, type):
            self.rbiter = rbiter
            self.count = 0
            self.type = type

        def __iter__(self):
            return self

        def next(self):
            if self.count % 2 == 0:
                n = self.rbiter.next()
                n = n.cast(self.type).dereference()['_M_value_field']
                self.pair = n
                item = n['first']
            else:
                item = self.pair['second'].dereference()
                item = item.cast(dynamic_type(item))
            result = ('[%d]' % self.count, item)
            self.count = self.count + 1
            return result

    def __init__ (self, typename, val):
        self.val = val.cast (gdb.lookup_type (typename))['structData']
        self.typename = typename

    def to_string (self):
        return '%s with %d elements' % (self.typename,
                                        len (FRPCStructIterator (self.val)))

    def children (self):
        keytype = self.val.type.template_argument(0).const()
        valuetype = self.val.type.template_argument(1)
        nodetype = gdb.lookup_type('std::_Rb_tree_node< std::pair< %s, %s > >' % (keytype, valuetype))
        nodetype = nodetype.pointer()
        return self._iter (FRPCStructIterator (self.val), nodetype)

    def display_hint (self):
        return 'map'

class FRPCPoolPrinter:
    "Print a FRPC::Pool_t"

    class _iterator:
        def __init__ (self, start, finish):
            self.item = start
            self.finish = finish
            self.count = 0

        def __iter__(self):
            return self

        def next(self):
            count = self.count
            self.count = self.count + 1
            if self.item == self.finish:
                raise StopIteration
            elt = self.item.dereference().dereference()
            self.item = self.item + 1
            return ('[%d](%s)' % (count, elt.address),
                    elt.cast(dynamic_type(elt)))

    def __init__ (self, typename, val):
        self.val = val.cast (gdb.lookup_type (typename))
        self.typename = typename

    def children (self):
        val = self.val['pointerStorage']
        start = val['_M_impl']['_M_start']
        finish = val['_M_impl']['_M_finish']
        return self._iterator (start, finish)

    def to_string (self):
        val = self.val['pointerStorage']
        start = val['_M_impl']['_M_start']
        finish = val['_M_impl']['_M_finish']
        end = val['_M_impl']['_M_end_of_storage']
        return ('(%s of length %d, capacity %d)'
                % (self.typename, int (finish - start), int (end - start)))

# A "regular expression" printer which conforms to the
# "SubPrettyPrinter" protocol from gdb.printing.
class RxPrinter(object):
    def __init__(self, name, function):
        super(RxPrinter, self).__init__()
        self.name = name
        self.function = function
        self.enabled = True

    def invoke(self, value):
        if not self.enabled:
            return None
        return self.function(self.name, value)

# A pretty-printer that conforms to the "PrettyPrinter" protocol from
# gdb.printing.  It can also be used directly as an old-style printer.
class Printer(object):
    def __init__(self, name):
        super(Printer, self).__init__()
        self.name = name
        self.subprinters = []
        self.lookup = {}
        self.enabled = True
        #self.compiled_rx = re.compile('^([a-zA-Z0-9_:]+)<.*>$')

    def add(self, name, function):
        printer = RxPrinter(name, function)
        self.subprinters.append(printer)
        self.lookup[name] = printer

    @staticmethod
    def get_basic_type(type):
        # If it points to a reference, get the reference.
        if type.code == gdb.TYPE_CODE_REF:
            type = type.target ()

        # Get the unqualified type, stripped of typedefs.
        type = type.unqualified ().strip_typedefs ()

        return type.tag

    def __call__(self, val):
        typename = self.get_basic_type(val.type)
        if not typename:
            return None

        if typename in self.lookup:
            return self.lookup[typename].invoke(val)

        # Cannot find a pretty printer.  Return None.
        return None

fastrpc_printer = None

def register_fastrpc_printers (obj):
    "Register fastrpc pretty-printers with objfile Obj."

    global _use_gdb_pp
    global fastrpc_printer

    if _use_gdb_pp:
        gdb.printing.register_pretty_printer(obj, fastrpc_printer)
    else:
        if obj is None:
            obj = gdb
        obj.pretty_printers.append(fastrpc_printer)

def build_fastrpc_dictionary ():
    global fastrpc_printer

    fastrpc_printer = Printer("fastrpc")

    # libstdc++ objects requiring pretty-printing.
    fastrpc_printer.add('FRPC::Int_t', FRPCPrimitiveValuePrinter)
    fastrpc_printer.add('FRPC::String_t', FRPCPrimitiveValuePrinter)
    fastrpc_printer.add('FRPC::Bool_t', FRPCPrimitiveValuePrinter)
    fastrpc_printer.add('FRPC::Double_t', FRPCPrimitiveValuePrinter)
    fastrpc_printer.add('FRPC::Binary_t', FRPCPrimitiveValuePrinter)
    fastrpc_printer.add('FRPC::DateTime_t', FRPCDateTimePrinter)
    fastrpc_printer.add('FRPC::Null_t', FRPCNullPrinter)
    fastrpc_printer.add('FRPC::Struct_t', FRPCStructPrinter)
    fastrpc_printer.add('FRPC::Array_t', FRPCArrayPrinter)
    fastrpc_printer.add('FRPC::Pool_t', FRPCPoolPrinter)

build_fastrpc_dictionary ()

