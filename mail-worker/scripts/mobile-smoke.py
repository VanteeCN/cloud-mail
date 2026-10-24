#!/usr/bin/env python3
"""Only exercise the isolated Wrangler listener; never touches an Internet mailbox."""
import json
from pathlib import Path
import secrets
import subprocess
from urllib.request import Request, urlopen
from urllib.error import HTTPError

BASE = 'http://127.0.0.1:18787/api'
ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.wrangler/mobile-local/fixture.json'

def request(path, body=None, token='', method=None):
    headers = {'Content-Type': 'application/json', 'Accept-Language': 'zh'}
    if token:
        headers['Authorization'] = token
    req = Request(BASE + path, data=None if body is None else json.dumps(body).encode(), headers=headers, method=method or ('POST' if body is not None else 'GET'))
    try:
        response = urlopen(req, timeout=30)
    except HTTPError as failure:
        response = failure
    raw = response.read().decode()
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        return {'code': response.status, 'data': raw}
    return result

def success(path, body=None, token='', method=None):
    result = request(path, body, token, method)
    assert result['code'] == 200, f"{path}: {result.get('code')} {result.get('message', '')}"
    return result.get('data')

init = request('/init/local-mobile-tests-never-production')
assert init.get('data') == 'success', 'Local database initialization failed'
if STATE.exists():
    accounts = json.loads(STATE.read_text())
else:
    accounts = {'admin': {'email': 'admin@example.test', 'password': secrets.token_urlsafe(15)},
                'reader': {'email': 'reader@example.test', 'password': secrets.token_urlsafe(15)}}
    for account in accounts.values():
        success('/register', account)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(accounts))

admin = success('/login', accounts['admin'])['token']
reader = success('/login', accounts['reader'])['token']
admin_profile = success('/my/loginUserInfo', token=admin)
reader_profile = success('/my/loginUserInfo', token=reader)
assert admin_profile['permKeys'] == ['*']
for path in ('/analysis/echarts?timeZone=Asia%2FShanghai', '/user/list?num=1&size=20', '/allEmail/list?size=20&full=0', '/role/list'):
    assert request(path, token=reader)['code'] == 403, 'Ordinary user accessed an admin API'

subprocess.run([str(ROOT / 'node_modules/.bin/wrangler.cmd'), 'd1', 'execute', 'mobile-test-mail', '--local',
    '--config', 'wrangler-mobile-local.toml', '--persist-to', '.wrangler/mobile-local', '--command',
    "UPDATE setting SET send=0; UPDATE role SET send_type='internal' WHERE is_default=1"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
assert request('/init/local-mobile-tests-never-production').get('data') == 'success'
form = {'accountId': admin_profile['account']['accountId'], 'name': '本地联调', 'receiveEmail': [accounts['reader']['email']],
        'text': '这是一封隔离的本地联调邮件，不会投递到互联网。', 'content': '<p>本地邮件正文</p><script>bad()</script>',
        'subject': '移动端联调 · 权限与收件箱', 'sendType': 'send', 'manyType': 'together', 'attachments': []}
sent = success('/email/send', form, admin)
assert isinstance(sent, list) and sent
inbox = success('/email/list?accountId=' + str(reader_profile['account']['accountId']) + '&allReceive=1&size=20&full=0&type=0', token=reader)
assert inbox['list'], 'Internal message did not arrive'
received_id = inbox['list'][0]['emailId']
assert 'content' not in inbox['list'][0], 'Summary leaks the full message body'
assert success('/email/detail?emailId=' + str(received_id), token=reader)['emailId'] == received_id
assert request('/email/detail?emailId=' + str(received_id), token=admin)['code'] == 404, 'Detail allowed another user\'s mail'
assert success('/allEmail/detail?emailId=' + str(received_id), token=admin)['emailId'] == received_id
assert request('/allEmail/detail?emailId=' + str(received_id), token=reader)['code'] == 403
success('/star/add', {'emailId': received_id}, reader)
assert any(row['emailId'] == received_id for row in success('/star/list?size=20&full=0', token=reader)['list'])
success('/email/read', {'emailIds': [received_id]}, reader, 'PUT')
assert success('/email/detail?emailId=' + str(received_id), token=reader)['unread'] == 1
users = success('/user/list?num=1&size=20', token=admin)
assert all('password' not in user and 'salt' not in user for user in users['list']), 'User list exposes password data'
success('/analysis/echarts?timeZone=Asia%2FShanghai', token=admin)
roles = success('/role/list', token=admin)
assert roles and success('/role/tree', token=admin)
new_role_name = 'local-' + secrets.token_hex(3)
role_form = {'name': new_role_name, 'key': new_role_name, 'description': 'isolated mobile management regression',
             'permIds': reader_profile['role'].get('permIds', []), 'banEmail': [], 'availDomain': ['example.test'],
             'sendType': 'internal', 'sendCount': 10, 'accountCount': 3, 'sort': 10}
success('/role/add', role_form, admin)
created_role = next(role for role in success('/role/list', token=admin) if role['name'] == new_role_name)
created_role['description'] = 'edited by local regression'
success('/role/set', created_role, admin, 'PUT')
temporary_email = 'temporary-' + secrets.token_hex(4) + '@example.test'
temporary_password = secrets.token_urlsafe(15)
success('/user/add', {'email': temporary_email, 'password': temporary_password, 'type': created_role['roleId']}, admin)
temporary_user = success('/user/list?num=1&size=1&email=' + temporary_email, token=admin)['list'][0]
temporary_id = temporary_user['userId']
assert success('/user/list?num=1&size=1&userId=' + str(temporary_id), token=admin)['list'][0]['email'] == temporary_email
success('/user/setStatus', {'userId': temporary_id, 'status': 1}, admin, 'PUT')
assert request('/login', {'email': temporary_email, 'password': temporary_password})['code'] != 200
success('/user/setStatus', {'userId': temporary_id, 'status': 0}, admin, 'PUT')
temporary_session = success('/login', {'email': temporary_email, 'password': temporary_password})['token']
next_password = secrets.token_urlsafe(15)
success('/user/setPwd', {'userId': temporary_id, 'password': next_password}, admin, 'PUT')
assert request('/my/loginUserInfo', token=temporary_session)['code'] == 401
assert request('/login', {'email': temporary_email, 'password': temporary_password})['code'] != 200
assert success('/login', {'email': temporary_email, 'password': next_password})['token']
success('/user/setType', {'userId': temporary_id, 'type': reader_profile['type']}, admin, 'PUT')
success('/user/resetSendCount', {'userId': temporary_id}, admin, 'PUT')
success('/role/delete?roleId=' + str(created_role['roleId']), token=admin, method='DELETE')
success('/user/delete?userIds=' + str(temporary_id), token=admin, method='DELETE')
assert not success('/user/list?num=1&size=1&userId=' + str(temporary_id), token=admin)['list']
second_reader = success('/login', accounts['reader'])['token']
success('/logout', token=reader, method='DELETE')
assert request('/my/loginUserInfo', token=reader)['code'] == 401
assert request('/my/loginUserInfo', token=second_reader)['code'] == 200
print(json.dumps({'real_local_worker': True, 'd1_kv': True, 'admin_permissions': True,
    'ordinary_user_boundaries': True, 'internal_send_and_receive': True, 'exact_detail_ownership': True,
    'star_and_read': True, 'safe_user_fields': True, 'analytics_and_roles': True, 'role_crud': True,
    'user_create_status_role_delete': True, 'logout_other_device_preserved': True}, indent=2))
