#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""长安链积分应用 · 后端服务（Flask）

通过调用 cmc 命令行工具与链交互，对外提供 HTTP 接口。
不改动合约；账户使用可读名字（admin / alice / bob），
权限由签名证书决定：org1 client1 是合约部署者（管理员），org2 client1 是普通用户。
"""

import base64
import json
import os
import re
import subprocess
import time

from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
FRONT_DIR = os.path.join(ROOT_DIR, 'frontend')

CMC_DIR = os.environ.get('CMC_DIR', '/home/kinich/chainmaker-go/tools/cmc')
CONTRACT_NAME = os.environ.get('CONTRACT_NAME', 'jifen_aadjjpf')
CHAIN_ID = 'chain1'

# 两个签名身份。account 是该身份在应用里预置的账户名，普通用户不预置。
IDENTITIES = {
    'admin': {
        'label': '管理员',
        'account': 'admin',
        'conf': './testdata/sdk_config.yml',
        'org': 'wx-org1.chainmaker.org',
        'desc': '组织1 client1（合约部署者），拥有铸造权限',
    },
    'user': {
        'label': '普通用户',
        'account': None,
        'conf': './testdata/sdk_config_org2.yml',
        'org': 'wx-org2.chainmaker.org',
        'desc': '组织2 client1，普通调用者，无铸造权限',
    },
}

# 合约返回的错误 → 中文提示
ERROR_HINTS = {
    'Insufficient balance': '余额不足',
    'Only admin can mint tokens': '权限不足：只有管理员可以铸造积分',
    'Missing account parameter': '参数缺失：请填写账户',
    'Missing amount parameter': '参数缺失：请填写数量',
    'Missing to parameter': '参数缺失：请填写收款账户',
    'Missing from parameter': '参数缺失：转出账户未指定',
}

ACCOUNT_RE = re.compile(r'^[A-Za-z0-9_]{1,32}$')

app = Flask(__name__, static_folder=FRONT_DIR, static_url_path='')
app.json.ensure_ascii = False

_cache = {}
CACHE_TTL = 3.0
_current = {'identity': 'admin'}


# ---------------------------------------------------------------- 链交互


def run_cmc(identity, method, params=None, timeout=60):
    """执行一次 cmc 合约调用，返回结构化结果。"""
    conf = IDENTITIES[identity]['conf']
    cmd = [
        os.path.join(CMC_DIR, 'cmc'),
        'client', 'contract', 'user', 'invoke',
        '--contract-name=' + CONTRACT_NAME,
        '--method=' + method,
        '--sdk-conf-path=' + conf,
        '--sync-result=true',
        '--timeout=%d' % timeout,
    ]
    if params is not None:
        cmd.append('--params=' + json.dumps(params, ensure_ascii=False))

    started = time.time()
    try:
        proc = subprocess.run(cmd, cwd=CMC_DIR, capture_output=True, text=True,
                              timeout=timeout + 10)
    except subprocess.TimeoutExpired:
        return {'ok': False, 'error': '调用链超时，请稍后重试', 'raw_message': 'timeout'}

    stdout = proc.stdout.strip()
    start = stdout.find('{')
    payload = {}
    if start >= 0:
        try:
            payload = json.loads(stdout[start:])
        except json.JSONDecodeError:
            payload = {}

    cr = payload.get('contract_result') or {}
    raw = cr.get('result')
    try:
        value = base64.b64decode(raw).decode('utf-8', 'ignore') if raw else ''
    except Exception:
        value = ''

    message = cr.get('message', '') or ''
    ok = message == 'Success'
    if not ok and not message:
        tail = (proc.stderr or stdout or '命令执行失败').strip().splitlines()
        message = tail[-1][:200] if tail else '命令执行失败'

    return {
        'ok': ok,
        'error': None if ok else ERROR_HINTS.get(message, message),
        'raw_message': message,
        'value': value,
        'tx_id': payload.get('tx_id', ''),
        'block_height': payload.get('tx_block_height', 0),
        'timestamp': payload.get('tx_timestamp', 0),
        'gas': cr.get('gas_used', 0),
        'elapsed_ms': int((time.time() - started) * 1000),
    }


def query_cached(identity, method, params=None, ttl=CACHE_TTL):
    """只读查询走短时缓存，避免每次请求都起一个 cmc 进程。"""
    key = (identity, method, json.dumps(params, sort_keys=True, ensure_ascii=False))
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    res = run_cmc(identity, method, params)
    _cache[key] = (now, res)
    return res


def invalidate_cache():
    _cache.clear()


def receipt(res):
    return {
        'tx_id': res['tx_id'],
        'block_height': res['block_height'],
        'timestamp': res['timestamp'],
        'gas': res['gas'],
        'elapsed_ms': res['elapsed_ms'],
    }


# ---------------------------------------------------------------- 参数校验


def parse_amount(raw):
    """金额必须是正整数，返回 (值, 错误信息)。"""
    if raw is None or str(raw).strip() == '':
        return None, '参数缺失：请填写积分数量'
    text = str(raw).strip()
    if not text.isdigit():
        return None, '参数非法：积分数量必须是正整数'
    value = int(text)
    if value <= 0:
        return None, '参数非法：积分数量必须大于 0'
    if value > 100000000:
        return None, '参数非法：单次数量过大'
    return value, None


def parse_account(raw):
    if raw is None or str(raw).strip() == '':
        return None, '参数缺失：请填写账户'
    text = str(raw).strip()
    if not ACCOUNT_RE.match(text):
        return None, '参数非法：账户只能由字母、数字、下划线组成，最长 32 位'
    return text, None


# ---------------------------------------------------------------- 接口


@app.route('/')
def index():
    return send_from_directory(FRONT_DIR, 'index.html')


@app.route('/api/identity', methods=['GET', 'POST'])
def identity_api():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        target = data.get('identity')
        if target not in IDENTITIES:
            return jsonify({'success': False, 'error': '未知身份'}), 400
        _current['identity'] = target
        invalidate_cache()

    current = _current['identity']
    return jsonify({
        'success': True,
        'data': {
            'current': current,
            'list': [
                {
                    'id': key,
                    'label': item['label'],
                    'account': item['account'],
                    'org': item['org'],
                    'desc': item['desc'],
                }
                for key, item in IDENTITIES.items()
            ],
        },
    })


@app.route('/api/info', methods=['GET'])
def info_api():
    ident = _current['identity']
    fields = {}
    for method in ('Name', 'Symbol', 'Decimals', 'TotalSupply'):
        res = query_cached(ident, method)
        fields[method] = res['value'] if res['ok'] else '获取失败'

    return jsonify({
        'success': True,
        'data': {
            'contract': CONTRACT_NAME,
            'chain': CHAIN_ID,
            'name': fields['Name'],
            'symbol': fields['Symbol'],
            'decimals': fields['Decimals'],
            'totalSupply': fields['TotalSupply'],
        },
    })


@app.route('/api/balance', methods=['POST'])
def balance_api():
    data = request.get_json(silent=True) or {}
    account, err = parse_account(data.get('account'))
    if err:
        return jsonify({'success': False, 'error': err}), 400

    res = query_cached(_current['identity'], 'BalanceOf', {'account': account})
    if not res['ok']:
        return jsonify({'success': False, 'error': res['error']}), 502

    balance = res['value'] if res['value'] != '' else '0'
    return jsonify({
        'success': True,
        'data': {'account': account, 'balance': balance},
    })


@app.route('/api/transfer', methods=['POST'])
def transfer_api():
    data = request.get_json(silent=True) or {}
    to, err = parse_account(data.get('to'))
    if err:
        return jsonify({'success': False, 'error': err}), 400
    amount, err = parse_amount(data.get('amount'))
    if err:
        return jsonify({'success': False, 'error': err}), 400

    ident = _current['identity']
    # 管理员身份固定从 admin 转出；普通用户身份不预置账户，由用户显式填写
    default_from = IDENTITIES[ident]['account']
    sender, err = parse_account(data.get('from') or default_from)
    if err:
        return jsonify({'success': False, 'error': err}), 400
    if default_from and sender != default_from:
        return jsonify({'success': False, 'error': '转出账户必须与当前身份绑定账户一致'}), 400
    if sender == to:
        return jsonify({'success': False, 'error': '不能给自己转账'}), 400

    res = run_cmc(ident, 'Transfer', {'from': sender, 'to': to, 'amount': str(amount)})
    invalidate_cache()
    if not res['ok']:
        return jsonify({'success': False, 'error': res['error'], 'raw': res['raw_message']}), 502

    return jsonify({
        'success': True,
        'data': {
            'from': sender,
            'to': to,
            'amount': amount,
            'receipt': receipt(res),
        },
    })


@app.route('/api/mint', methods=['POST'])
def mint_api():
    data = request.get_json(silent=True) or {}
    account, err = parse_account(data.get('account'))
    if err:
        return jsonify({'success': False, 'error': err}), 400
    amount, err = parse_amount(data.get('amount'))
    if err:
        return jsonify({'success': False, 'error': err}), 400

    ident = _current['identity']
    res = run_cmc(ident, 'Mint', {'account': account, 'amount': str(amount)})
    invalidate_cache()
    if not res['ok']:
        return jsonify({'success': False, 'error': res['error'], 'raw': res['raw_message']}), 502

    return jsonify({
        'success': True,
        'data': {'account': account, 'amount': amount, 'receipt': receipt(res)},
    })


@app.route('/api/tx/<tx_id>', methods=['GET'])
def tx_api(tx_id):
    cmd = [
        os.path.join(CMC_DIR, 'cmc'), 'query', 'tx', tx_id,
        '--chain-id=' + CHAIN_ID,
        '--sdk-conf-path=' + IDENTITIES[_current['identity']]['conf'],
    ]
    try:
        proc = subprocess.run(cmd, cwd=CMC_DIR, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'error': '查询超时'}), 504

    text = proc.stdout.strip()
    start = text.find('{')
    if start < 0:
        return jsonify({'success': False, 'error': '未查询到该交易'}), 404
    try:
        payload = json.loads(text[start:])
    except json.JSONDecodeError:
        return jsonify({'success': False, 'error': '交易数据解析失败'}), 500

    sender = payload.get('sender', {}).get('signer', {})
    return jsonify({
        'success': True,
        'data': {
            'tx_id': tx_id,
            'block_height': payload.get('tx_block_height', 0),
            'timestamp': payload.get('tx_timestamp', 0),
            'org_id': sender.get('org_id', ''),
            'message': payload.get('contract_result', {}).get('message', ''),
        },
    })


@app.errorhandler(404)
def not_found(_):
    return jsonify({'success': False, 'error': '接口不存在'}), 404


if __name__ == '__main__':
    print('cmc 目录: %s' % CMC_DIR)
    print('合约: %s  链: %s' % (CONTRACT_NAME, CHAIN_ID))
    app.run(host='0.0.0.0', port=5000, debug=False)
