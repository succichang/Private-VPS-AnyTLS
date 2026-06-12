# 私人 VPS 流量面板

该面板不读取服务商账户，也不需要商家 API。VPS 上的统计服务持续记录
默认网卡的收发流量，Surge 通过现有 AnyTLS 节点访问仅监听于
`127.0.0.1:18080` 的接口。

## 特点

- 统计服务不开放公网端口。
- GitHub 仓库不保存 VPS IP、登录密码或 AnyTLS 密码。
- 统计数据在 VPS 重启后继续累计。
- 默认统计上传与下载总和。
- 可按照套餐账单日自动重置。

本地统计可能与商家计费存在少量差异，应以服务商控制面板为最终依据。

## VPS 安装

先确认套餐每月流量和账单重置日，然后在 VPS 上执行：

```bash
RESET_DAY=12 TOTAL_GB=1000 bash <(curl -fsSL https://raw.githubusercontent.com/succichang/Private-VPS-Traffic/main/install-private-vps-traffic-agent.sh)
```

示例中的含义：

- `RESET_DAY=12`：每月 12 日 UTC 重置。
- `TOTAL_GB=1000`：每月总流量为 1000GB。

如果套餐是 500GB，将 `TOTAL_GB` 改为 `500`。

## Surge 安装

在 Surge iOS 的“安装新模组”中输入：

```text
https://raw.githubusercontent.com/succichang/Private-VPS-Traffic/main/Private-VPS-Traffic.sgmodule
```

模组参数 `POLICY` 必须与 `[Proxy]` 中的 AnyTLS 节点名称完全一致，默认值是：

```text
Private-VPS-AnyTLS
```

## 检查

在 VPS 上检查服务：

```bash
systemctl status private-vps-traffic --no-pager
curl http://127.0.0.1:18080/status
```

统计服务正常时，第二条命令会返回 JSON 数据。

## 限制

- 面板统计从安装服务后开始，不追溯安装前的流量。
- VPS 断电前最多约 30 秒的流量可能来不及写入磁盘。
- 面板必须通过指定 AnyTLS 策略访问，节点停机时无法刷新。
- 信息面板主要显示在 Surge iOS；Surge Mac 可编辑和同步模组。
