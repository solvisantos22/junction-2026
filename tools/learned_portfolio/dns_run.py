"""Optional process-local DNS workaround; preserves TLS hostname verification.

Use only when the host resolver is unavailable. No OS network settings change.
Queries public names through 1.1.1.1 with macOS dig, then launches the usual runner.
"""

import ipaddress
import runpy
import socket
import subprocess
import sys
import time


def install_resolver():
    original=socket.getaddrinfo
    cache={}

    def resolve(host,port,family=0,type=0,proto=0,flags=0):
        name=host.decode() if isinstance(host,bytes) else host
        try:
            ipaddress.ip_address(name)
            return original(host,port,family,type,proto,flags)
        except (ValueError,TypeError):
            pass
        if not name or name=='localhost':return original(host,port,family,type,proto,flags)
        record='AAAA' if family==socket.AF_INET6 else 'A'
        key=(name,record)
        cached=cache.get(key)
        if cached is None or time.monotonic()-cached[0]>60:
            result=subprocess.run(['/usr/bin/dig','+short','+time=3','+tries=1','@1.1.1.1',name,record],
                                  capture_output=True,text=True,timeout=8,check=True)
            addresses=[]
            for line in result.stdout.splitlines():
                try:addresses.append(str(ipaddress.ip_address(line.strip())))
                except ValueError:pass
            if not addresses:raise socket.gaierror(socket.EAI_NONAME,'Public DNS lookup returned no addresses')
            cache[key]=(time.monotonic(),addresses)
        addresses=cache[key][1]
        return [item for address in addresses for item in original(address,port,family,type,proto,flags)]

    socket.getaddrinfo=resolve


if __name__=='__main__':
    install_resolver()
    if sys.argv[1:]==['apps']:
        sys.argv=['modal','app','list','--json']
        runpy.run_module('modal',run_name='__main__')
    else:
        runpy.run_module('tools.learned_portfolio.run',run_name='__main__')
