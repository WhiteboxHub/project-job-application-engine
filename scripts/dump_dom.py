import json
import urllib.request

try:
    response = urllib.request.urlopen('http://127.0.0.1:9222/json')
    tabs = json.loads(response.read())
    page_ws_url = None
    for tab in tabs:
        if tab.get('type') == 'page' and 'kforce.com' in tab.get('url', ''):
            page_ws_url = tab.get('webSocketDebuggerUrl')
            break
    
    if page_ws_url:
        import websocket
        ws = websocket.create_connection(page_ws_url)
        # Get document
        ws.send(json.dumps({"id": 1, "method": "DOM.getDocument"}))
        doc_res = json.loads(ws.recv())
        root_node_id = doc_res['result']['root']['nodeId']
        # Get outer HTML
        ws.send(json.dumps({"id": 2, "method": "DOM.getOuterHTML", "params": {"nodeId": root_node_id}}))
        html_res = json.loads(ws.recv())
        with open('kforce_dom.html', 'w') as f:
            f.write(html_res['result']['outerHTML'])
        print("DOM dumped to kforce_dom.html")
    else:
        print("Could not find KForce page")
except Exception as e:
    print(f"Error: {e}")
