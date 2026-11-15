from lightlag_client import connect
with connect('http://lightlag:8000/mcp') as t:
    w=t.map()
    print('keys',w.keys())
    print('lander',w.get('lander'), 'targets',w.get('targets'))
    print('telemetry',t.telemetry_log())
