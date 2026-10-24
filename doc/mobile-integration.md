# 移动客户端配套补丁（本地验证）

日期：2026-10-24。基于 `20e5977a8a4f08cbf14e5e0dbd1cdfe4223b907f`，本地分支
`codex/temp-mail-mobile-api`；移动端在 `E:/code/mobile_app/uniapp_template` 的 `temp_mail`。

补丁不改生产 bindings、变量和原网页布局，不新增数据库结构，也不将管理员 PUBLIC_KEY 提供给移动端。
移动端使用各用户的正常邮箱/密码与原始 JWT，复用现有权限键及资源归属。

## 变更

1. `login-service.logout` 等待异步 Token，未找到当前 Token 时不移除其他会话，保留有界 TTL，
   无剩余设备时删除会话记录。
2. 用户列表显式选择需要返回的列，不返回密码摘要、salt；增加受原 user:query 保护的 userId 精确筛选。
3. `/api/email/detail?emailId=` 仅可读取本人的未删除邮件，验证邮箱归属；
   `/api/allEmail/detail?emailId=` 受 all-email:query 控制，不能以普通详情接口跨用户读取。
4. `/api/mobile/capabilities` 仅返回协议能力标志，帮助旧部署兼容，绝不返回密钥。
5. 增加完全隔离的 Wrangler 本地配置、会话回归测试与真实 D1/KV/R2 HTTP 联调脚本。

## 安全本地运行

```powershell
cd E:\code\cloud-mail\mail-worker
pnpm run dev:mobile
```

保持该终端运行，另一个终端执行：

```powershell
python scripts/mobile-smoke.py
pnpm run test:mobile
```

只监听 `127.0.0.1:18787`，配置中的资源 ID 为本地占位，数据保存在忽略的
`.wrangler/mobile-local`。测试邮箱为 example.test，随机密码保存在忽略的 fixture.json，
脚本从不调用生产域名，也不会向互联网发送测试邮件。没有默认生产账号或固定可登录密码。

HTTP 回归覆盖普通用户拒绝四项管理 API、管理员统计、用户列表字段、角色增改删、用户创建/禁用/启用/
改身份/重置密码/计数/删除、站内发收信、精确详情归属、星标/已读和保留其他设备的退出。
移动 H5 另行实际验证附件、草稿、角色入口与普通用户管理路由拦截。

## 发布前

`wrangler deploy --dry-run` 已验证本地打包，但没有发布。遵守现有
[安全更新与回滚](安全更新与回滚.md)，先备份并审核，再安排生产发布。
此仓库非生产分支构建也可能连接生产 D1/KV；不要直接推送分支作为隔离测试。
不要部署 `wrangler-mobile-local.toml`，它只用于本机模拟资源。

KV 最终一致性、个人改密码/注销的再次认证以及附件公开链接属于现有服务边界；本补丁不宣称替换了
整套会话、附件授权或完成了生产安全审计。移动端不集成系统设置与注册密钥管理，不影响网页版继续使用。
