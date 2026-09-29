# 安全取证 — `getthefile.duckdns.org` 访问事件（2026-09-28 15:58:09）

> 触发方：IT 助手告警「设备 `v_wffanwan-pcd4` 上 `c:\nvm4w\nodejs\node.exe`（PID 6764）访问已拉黑域名/IP `getthefile.duckdns.org` / `192.169.69.25`」。
> 本文件为本地取证结论，可直接用于向 IT 回复。

## 一、结论（一句话）

**不是 AI Agent / OBM 题包流水线访问的。** 是**浏览器（Microsoft Edge）人工打开了一个该域名的链接**，而该浏览器的流量经代理扩展 `Proxy SwitchyOmega` 转发到了本机的 **whistle 调试代理**；whistle 以 `node.exe` 身份发起出站连接，因此 EDR 把连接归到了 `node.exe` PID 6764。

## 二、证据链

### 1. 被告警的进程 PID 6764 = whistle（不是我的工具链）

```
ExecutablePath = C:\nvm4w\nodejs\node.exe
CreationDate   = 2026-09-28 09:49:06  （早在告警前 6 小时就已启动）
CommandLine    = node ... node_modules\whistle\node_modules\starting\lib\bootstrap.js
                 run ...\whistle\index.js --data {...whistle 2.10.2...}
```

- whistle 是 **HTTP/HTTPS/WebSocket 调试代理**（`wproxy.org`，作者 avenwu），前端开发常用的抓包/转发工具。
- 其 `clientId` 里带 `V_WFFANWAN-PCD4`，与告警设备名 `v_wffanwan-pcd4` **吻合**。
- **监听 `0.0.0.0:8899`**（全网卡）；当前有大量 `[::1]:8899 ESTABLISHED` 连接，即本机客户端在用它。
- whistle 自身规则（`.whistle/rules/properties`）**只做内网→本机映射**（`*.woa.com` / `*.gcloud*.tencent.com` → `127.0.0.1:<port>`），**不含**任何 duckdns 相关配置。→ 不是 whistle 主动外联。

### 2. 浏览器侧确实打开了该域名（决定性证据）

Microsoft Edge 历史库（`.../Edge/User Data/Default/History`）：

| 时间 | URL | 次数 |
|---|---|---|
| **2026-09-28 15:59:11** | `http://getthefile.duckdns.org/` | 2 |
| **2026-09-28 15:59:11** | `https://getthefile.duckdns.org/` | 1 |

同窗口的浏览轨迹（人工浏览特征明显）：

```
15:56:14 chat.deepseek.com
15:56:54 cn.bing.com / www.bing.com
15:57:01 www.deepl.com
15:58:03 zhuanlan.zhihu.com
15:59:11 getthefile.duckdns.org   ← 告警目标
15:59:46 link.zhihu.com
15:59:47 xiecoding.cn
15:59:52 pan.quark.cn             ← 夸克网盘
16:00:10 github.com
```

**形态判断**：从知乎/外链点开 → 落到一个「取文件」页面 → 随后跳到夸克网盘。典型的**他人分享的文件下载链接**。
（告警时间 15:58:09 与历史记录的 15:59:11 相差约 1 分钟，属同一次访问的前后阶段：先建连被拦、随后页面导航被记录。）

### 3. 为什么 EDR 看到的是 `node.exe` 而不是 `msedge.exe`

Edge 装了代理切换扩展 **`Proxy SwitchyOmega 3 (ZeroOmega)`**（扩展 ID `dmaldhchmoafliphkijbfhaomcgglmgd`）。
其存储配置里写着：

```json
"fallbackProxy":{"host":"localhost","port":8899,"scheme":"http"},"name":"proxy"
```

→ 该配置把浏览器流量指向 **`localhost:8899` = whistle**。
链路：**Edge → SwitchyOmega → whistle(127.0.0.1:8899) → 出站解析/连接 `getthefile.duckdns.org`**。
出站连接以 whistle 的进程身份（`node.exe` PID 6764）出现，**这正是 EDR 的告警内容**。

（补充：系统级代理当前为关闭状态 —— WinINET `ProxyEnable=0`，残留 `ProxyServer=127.0.0.1:7897`；WinHTTP 为「直接访问」。所以走的是**扩展级**代理，非系统代理。）

## 三、排除 AI Agent / OBM 流水线的证据

1. **全盘检索**：`.workbuddy`、`Desktop\OBM`、`nvm4w`、npm 目录中，除**本次排查命令自身**外，`duckdns` / `getthefile` / `192.169.69.25` **零引用**。
2. **我的工具链从不使用 whistle**：本会话只调用 bash / python / wsl / docker / lark-cli；`lark-cli` 走的是飞书域名，且其运行**不经过** whistle（shell 环境无 `*_PROXY` 变量）。
3. **15:58:09 我在做什么**：会话时间线显示该时刻正在执行 **WSL 内离线 Docker 验证**（`docker build/run --network=none`），不产生对外连接；WSL 侧 `/etc/environment` 无代理、`/etc/docker/daemon.json` 只配了 daocloud/aliyun registry mirror。
4. **访问形态不符**：该域名的两次命中都在 Edge 历史里，且嵌在一段连续的人工浏览轨迹中。

## 四、域名风险评估

- `duckdns.org` 本身是**合法的免费动态 DNS 服务**，但其**子域被大量滥用**：Malwarebytes 明确将其子域列为钓鱼拦截对象；多家安全厂商与国内网信部门通报过 `*.duckdns.org` 作为 **Mirai/MooBot 僵尸网络、RemCos 后门、HTML Smuggling 载荷投递**的 C2/下载地址（如 Duri 活动即用 duckdns 托管 HTML Smuggling 页面）。
- 本次未在公开 IoC 名单中检索到 `getthefile.duckdns.org` 这一具体子域，但「取文件」语义 + 已被拉黑 + 从社交/外链跳转而来，**风险特征高度吻合文件投递类恶意链接**。
- **本次拦截生效**（EDR 已阻断），未发生实际通信。

## 五、建议

1. **不要再尝试打开该链接**；如是知乎/评论区的分享链接，视为不可信来源。
2. **确认是否已从该域下载过文件**：本次 Edge 下载记录中**未发现**来自该域的下载（已扫描最近 200 条），但若曾用其它方式（其它浏览器/下载器）取过文件，请删除且不要执行。
3. **收紧 whistle 暴露面**：whistle 监听 `0.0.0.0:8899` 且防火墙对部分网段放行了 8899，存在被当作**开放代理**中转的风险。建议改为仅监听 `127.0.0.1`（启动加 `-H 127.0.0.1`），或在防火墙层禁止 8899 对非本机开放。
4. 若需复查同类事件：可核对 Edge 历史 + SwitchyOmega 当前生效规则 + whistle 是否处于代理链路中（`netstat -ano | findstr 8899`）。

> 取证方式：全部为只读检查（进程枚举、注册表读取、浏览器历史库副本查询、扩展配置读取），未修改系统或浏览器数据。
