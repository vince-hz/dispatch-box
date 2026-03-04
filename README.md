# dispatch-box

用于管理机场订阅、静态梯子与 `sing-box` 聚合 outbounds 的轻量面板。

## 功能

- 订阅管理：
  - 保存原始订阅 URL
  - 支持自定义 `User-Agent`
  - 支持重命名前缀、全局 replace map、全局 filter
  - 支持单条/批量拉取并解析订阅
  - 将拉取结果缓存为可直接写入 `sing-box` 的 outbounds
- 静态梯子管理：
  - 不通过订阅拉取，直接粘贴单个 outbound 的 JSON
  - 支持启用/禁用、编辑、删除
  - 与订阅节点一起参与最终 outbounds 合并
- Outbounds 管理（聚合类型）：
  - 面板仅展示和维护聚合 outbound（`selector` / `url-test(urltest)` / `direct`）
  - 支持 `includeAllNodes`，自动并入订阅节点 + 静态梯子节点
- 生成下载：
  - `/downloads/subscriptions.txt`（订阅原始地址清单）
  - `/downloads/subscription-outbounds.json`（订阅解析后的 sing-box outbounds）
  - `/downloads/singbox-overlay.json`（`data/base_config.json` + 动态 outbounds 合并后的完整配置）
- `sing-box` 静态检测：
  - 一键执行 `sing-box check -c <generated-config>` 检测当前聚合配置是否合法

## 订阅解析支持

当前内置解析：

- `ss://`
- `trojan://`
- `vmess://`
- `vless://`
- `hysteria2://` / `hy2://`

如果某些节点行无法识别，会记录在拉取结果的 `warnings` 中。

## 快速启动

```bash
make run
```

打开：`http://127.0.0.1:18080`

说明：
- `make run` 会自动检查 `python3`、创建 `.venv`，并在首次启动或 `requirements.txt` 更新后自动安装依赖。
- 如需只准备环境不启动服务，可运行 `make setup`。

## 环境变量

- `DISPATCH_BOX_DOWNLOAD_TOKEN`：设置后，下载接口需带 `?token=...`
- `SINGBOX_BIN`：可选，自定义 `sing-box` 可执行文件路径（默认：`sing-box`）

## API 摘要

- `GET /api/subscriptions`
- `POST /api/subscriptions`
- `PUT /api/subscriptions/{id}`
- `DELETE /api/subscriptions/{id}`
- `POST /api/subscriptions/{id}/refresh`
- `POST /api/subscriptions/refresh?enabled_only=true|false`
- `GET /api/subscriptions/rename-map`
- `PUT /api/subscriptions/rename-map`
- `GET /api/subscriptions/filter`
- `PUT /api/subscriptions/filter`
- `GET /api/outbounds`
- `POST /api/outbounds`
- `PUT /api/outbounds/{id}`
- `DELETE /api/outbounds/{id}`
- `GET /api/static-ladders`
- `POST /api/static-ladders`
- `PUT /api/static-ladders/{id}`
- `DELETE /api/static-ladders/{id}`
- `GET /api/config/preview`
- `POST /api/singbox/check`
- `GET /api/download-links`

## 注意

- 面板只负责订阅、静态梯子、聚合 outbounds。
- 分流规则、`rule_set`、DNS、实验配置等请直接写在 `data/base_config.json`。
- `/downloads/singbox-overlay.json` 会读取 `data/base_config.json`，并将最终 `outbounds` 覆盖写入。
- 覆盖顺序为：订阅节点 -> 静态梯子 -> 已启用聚合 outbounds（同 tag 后者覆盖前者）。
- 机场订阅数据独立存储于 `data/provider.json`。
- 若 `data/base_config.json` 不存在，启动时会自动创建默认文件。
