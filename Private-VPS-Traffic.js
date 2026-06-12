/*
 * Surge information panel for a private VPS traffic counter.
 * The endpoint is only reachable through the selected AnyTLS policy.
 */

function parseArguments(raw) {
  const result = {};

  String(raw || "")
    .split("&")
    .forEach((item) => {
      const separator = item.indexOf("=");
      if (separator < 0) return;

      const key = item.slice(0, separator).trim();
      const value = item.slice(separator + 1).trim();
      result[key] = value;
    });

  return result;
}

function formatBytes(value) {
  const bytes = Number(value);
  if (!Number.isFinite(bytes) || bytes < 0) return "未知";

  const units = ["B", "KB", "MB", "GB", "TB"];
  let amount = bytes;
  let unitIndex = 0;

  while (amount >= 1024 && unitIndex < units.length - 1) {
    amount /= 1024;
    unitIndex += 1;
  }

  const digits = amount >= 100 || unitIndex === 0 ? 0 : amount >= 10 ? 1 : 2;
  return `${amount.toFixed(digits)} ${units[unitIndex]}`;
}

function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "未知";

  const parts = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(date);
  const values = {};
  parts.forEach((part) => {
    values[part.type] = part.value;
  });
  return `${values.month}-${values.day} ${values.hour}:${values.minute}`;
}

function formatUptime(seconds) {
  const value = Number(seconds);
  if (!Number.isFinite(value) || value < 0) return "未知";

  const days = Math.floor(value / 86400);
  const hours = Math.floor((value % 86400) / 3600);
  const minutes = Math.floor((value % 3600) / 60);

  if (days > 0) return `${days}天 ${hours}小时`;
  if (hours > 0) return `${hours}小时 ${minutes}分钟`;
  return `${minutes}分钟`;
}

function finishWithError(message) {
  $done({
    title: "私人 VPS",
    content: message,
    style: "error",
  });
}

const args = parseArguments(typeof $argument === "undefined" ? "" : $argument);
const policy = args.POLICY || "Private-VPS-AnyTLS";

$httpClient.get(
  {
    url: "http://127.0.0.1:18080/status",
    policy,
    timeout: 8,
    "auto-cookie": false,
  },
  (error, response, body) => {
    if (error) {
      finishWithError(`查询失败：${error}\n请确认策略名称为 ${policy}`);
      return;
    }

    if (!response || response.status !== 200) {
      finishWithError(`统计服务返回 HTTP ${response?.status || "未知"}`);
      return;
    }

    let data;
    try {
      data = JSON.parse(body);
    } catch (_) {
      finishWithError("统计服务返回内容无法解析");
      return;
    }

    if (!data.ok) {
      finishWithError(`统计服务错误：${data.error || "未知错误"}`);
      return;
    }

    const total = Number(data.total_bytes);
    const quota = Number(data.quota_bytes);
    const percentage = Number(data.usage_percent);
    const hasQuota = Number.isFinite(quota) && quota > 0;
    const style =
      hasQuota && percentage >= 90
        ? "error"
        : hasQuota && percentage >= 75
          ? "alert"
          : "good";
    const title = hasQuota
      ? `私人 VPS · ${percentage.toFixed(1)}%`
      : "私人 VPS · 在线";

    const content = [
      `运行：${formatUptime(data.uptime_seconds)}`,
      `下载：${formatBytes(data.rx_bytes)}`,
      `上传：${formatBytes(data.tx_bytes)}`,
      `合计：${formatBytes(total)}`,
    ];

    if (hasQuota) {
      content.push(`剩余：${formatBytes(Math.max(quota - total, 0))}`);
      content.push(`总量：${formatBytes(quota)}`);
    }

    content.push(`重置：${formatDate(data.next_reset)}（北京时间）`);

    $done({
      title,
      content: content.join("\n"),
      style,
    });
  }
);
