# 私人 VPS 流量监控

通过 VPS 本地统计服务记录网卡上传和下载流量，并在 Surge 信息面板中显示：

- 本月上传、下载和合计流量
- 套餐剩余流量与使用百分比
- 下次重置时间
- VPS 运行时长

统计接口只监听 VPS 的 `127.0.0.1:18080`，Surge 通过指定的 AnyTLS
节点读取，不需要开放额外公网端口。

## VPS 安装

套餐为每月 1000GB、每月 12 日重置时，使用：

```bash
RESET_DAY=12 TOTAL_GB=1000 bash <(curl -fsSL https://raw.githubusercontent.com/succichang/Private-VPS-Traffic/main/install-private-vps-traffic-agent.sh)
```

## Surge 模组

```text
https://raw.githubusercontent.com/succichang/Private-VPS-Traffic/main/Private-VPS-Traffic.sgmodule
```

模组参数 `POLICY` 必须与 Surge `[Proxy]` 中的 AnyTLS 节点名称一致。
默认名称为：

```text
Private-VPS-AnyTLS
```

详细说明参见 [Private-VPS-Traffic-使用说明.md](Private-VPS-Traffic-使用说明.md)。

## 说明

- 流量从安装统计服务后开始计算，不能追溯此前用量。
- VPS 重启后会继续累计当前账期流量。
- 本地统计与服务商计费可能存在少量差异，以服务商后台为准。
- 仓库不应保存 VPS IP、AnyTLS 密码、SSH 密码或证书私钥。
