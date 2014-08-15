GDB FastRPC pretty printers
===========
This work is based on http://sourceware.org/gdb/wiki/STLSupport. If you
register fastrpc pretty printer in your ~/.gdbinit via this commands:

```
python
import sys
sys.path.insert(0, '/home/burlog/.gdb/gdb-python-printers/')
from fastrpc.printers import register_fastrpc_printers
register_fastrpc_printers(None)
end
```

And consequently turn on pretty printers via this command:

```
set print pretty on
```

You will see fastrpc structures in more readable format:

```
(gdb) > print string_map
$3 = std::map with 5 elements = {
    ["a"] = "A",
    ["b"] = "B",
    ["c"] = "C",
    ["d"] = "D",
    ["e"] = "E"
}
```
