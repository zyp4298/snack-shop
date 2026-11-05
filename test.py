import requests,json

API = 'xxx'
MODEL = 'xxx'

def ask(msgs):
    r = requests.post(
        API,
        headers={'Authorization':'xxx'},
        json={
            'model':MODEL,
            'message':msgs,
            'max_token':300,
            'temperature':0.3,
        },timeout=30)
    return r.json()#忘了



def run(msgs):
    for i in range(1,6):
        msg = ask(msgs)
        calls = msg.get('tool_calls')

        if not calls:
            return msg['content']

        msgs.append(msg)

        for call in calls:
            name = call['function']['name']
            args = json.loads(call['function']['arguments'])
