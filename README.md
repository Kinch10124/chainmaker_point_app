# chainmaker_point_app

基于长安链 v2.3.4 的校园积分应用 —— 长安链开源训练营实训课程 · 实验十一《基于长安链的积分应用》大作业。

## 项目名称

长安链积分通证应用（ChainMaker Point Token App）

## 主要功能

| 功能 | 说明 |
| --- | --- |
| 合约信息查询 | 读取链上通证名称、符号、小数位、总供应量 |
| 账户余额查询 | 按账户名查询链上余额，只读，不产生交易 |
| 积分转账 | 从当前身份绑定账户向目标账户转账，返回交易凭证 |
| 管理员铸造 | 管理员身份发放积分，同时增加总供应量 |
| 身份切换 | 管理员 / 普通用户两种链上身份，用不同证书签名 |
| 交易凭证 | 每笔交易返回 txid、区块高度、上链时间、Gas 消耗 |
| 异常场景复现 | 一键触发权限不足、余额不足、参数缺失、参数非法四类失败 |
| 角色隔离 | 普通用户看不到铸造与调试入口；越权调用由链上合约拒绝 |

## 目录结构

```
chainmaker_point_app/
├── contract/            Go 智能合约（SimpleContract 积分合约）
│   └── main.go
├── backend/             后端服务（Python + Flask）
│   ├── app.py
│   └── requirements.txt
├── frontend/            前端页面（原生 HTML + CSS + JavaScript）
│   └── index.html
├── scripts/
│   └── start.sh         一键启动脚本
└── README.md
```

## 运行环境

| 组件 | 版本 / 说明 |
| --- | --- |
| 操作系统 | Ubuntu 22.04（虚拟机，2 核 4 GB 以上） |
| 长安链 | chainmaker v2.3.4，四节点单链 `chain1`，RPC 端口 12301 |
| 合约运行环境 | DOCKER_GO，依赖镜像 `chainmakerofficial/chainmaker-vm-engine:v2.3.4` |
| 链交互工具 | cmc（随 chainmaker-go 提供的命令行客户端） |
| 后端 | Python 3.12+，Flask 3.x |
| 前端 | 原生 HTML / CSS / JavaScript，无框架无构建 |
| 浏览器 | Chrome / Edge / Firefox等|

## 部署与运行方法

### 1. 启动区块链

```bash
cd ~/chainmaker-go/scripts
sudo ./cluster_quick_start.sh normal
```

确认四个节点就绪：日志中出现 `all necessary peers connected`，且 `sudo netstat -lptn | grep 1230` 能看到 12301~12304 四个 RPC 端口。

### 2. 部署积分合约

合约源码见 `contract/main.go`，通过 SmartIDE 编译得到 `jifen_aadjjpf.7z` 后部署：

```bash
cd ~/chainmaker-go/tools/cmc
./cmc client contract user create \
  --contract-name=jifen_aadjjpf \
  --runtime-type=DOCKER_GO \
  --byte-code-path=/home/kinich/jifen_aadjjpf.7z \
  --version=1.0 \
  --sdk-conf-path=./testdata/sdk_config.yml \
  --admin-key-file-paths=./testdata/crypto-config/wx-org1.chainmaker.org/user/admin1/admin1.tls.key,./testdata/crypto-config/wx-org2.chainmaker.org/user/admin1/admin1.tls.key,./testdata/crypto-config/wx-org3.chainmaker.org/user/admin1/admin1.tls.key,./testdata/crypto-config/wx-org4.chainmaker.org/user/admin1/admin1.tls.key \
  --admin-crt-file-paths=./testdata/crypto-config/wx-org1.chainmaker.org/user/admin1/admin1.tls.crt,./testdata/crypto-config/wx-org2.chainmaker.org/user/admin1/admin1.tls.crt,./testdata/crypto-config/wx-org3.chainmaker.org/user/admin1/admin1.tls.crt,./testdata/crypto-config/wx-org4.chainmaker.org/user/admin1/admin1.tls.crt \
  --sync-result=true \
  --params="{}" \
  --timeout=60
```

### 3. 准备两个签名身份

后端用两份 SDK 配置区分身份：

- `sdk_config.yml`：组织1 的 client1 证书，即合约部署者，**管理员身份**
- `sdk_config_org2.yml`：组织2 的 client1 证书，**普通用户身份**

生成第二份配置：

```bash
cd ~/chainmaker-go/tools/cmc
cp testdata/sdk_config.yml testdata/sdk_config_org2.yml
sed -i 's/wx-org1/wx-org2/g' testdata/sdk_config_org2.yml
```

### 4. 启动后端

```bash
sudo apt install -y python3-venv        # 首次运行需要
cd ~/chainmaker_point_app
python3 -m venv venv
./venv/bin/pip install -r backend/requirements.txt
./venv/bin/python backend/app.py
```

也可以直接用脚本：`bash scripts/start.sh`

### 5. 打开前端

浏览器访问 `http://<虚拟机IP>:5000/`。页面由后端同源提供，不要直接双击打开 index.html。

## 使用说明

1. 右上角切换「管理员 / 普通用户」身份，切换后所有请求使用对应的证书签名
2. 账户名为自定义字符串（字母、数字、下划线，最长 32 位，区分大小写），如 `admin`、`alice`、`bob`
3. 先在「铸造」页给账户发放积分，再在「转账」页进行转账
4. 每笔成功交易下方显示交易凭证，可与 `cmc query tx <txid>` 的结果对照

## 设计说明

### 为什么不修改合约

合约沿用实验十一手册附录的 `SimpleContract`，未做任何改动。应用层通过以下方式补足工程性：

- **转出方不可伪造**：合约的 `Transfer` 接受前端传入 `from`，后端一律忽略该参数，强制使用当前签名身份绑定的账户，杜绝冒名转出
- **参数前置校验**：账户格式、金额正整数、必填项在后端拦截，不产生无效交易
- **双层权限**：前端按角色隐藏入口，链上合约再校验签名者身份，绕过前端也无法越权

### 关于初始发行量

合约初始化时把 1,000,000 积分记在部署者地址名下，该地址与应用中的业务账户不同，应用未使用该账户。业务积分由管理员通过「铸造」按需发放，总供应量与全部余额之和始终一致。

## 团队分工

| 成员 | 负责内容 |
| --- | --- |
| 王子达 | 合约编写与部署、后端接口、前端页面、联调测试、实验报告 |

## 常见问题

| 现象 | 原因与处理 |
| --- | --- |
| 页面按钮点了没反应 | 后端未启动，确认 `backend/app.py` 正在运行 |
| 提示 `read user crt file failed` | cmc 的工作目录不对，必须在 `chainmaker-go/tools/cmc` 下执行 |
| 提示证书不匹配 / 无权限 | `tools/cmc/testdata/crypto-config` 与当前链的证书不一致，需从 `build/crypto-config` 重新同步 |
| `sdk.log permission denied` | 之前用 `sudo` 运行过 cmc 留下的 root 日志，`sudo rm -f sdk.log.*` 清理即可 |
| 跨域或接口 404 | 请通过后端地址访问页面，而不是直接打开 HTML 文件 |
