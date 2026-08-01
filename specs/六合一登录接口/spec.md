# JJC-20260801-007 · SDD 契约（spec）

> **Feature**: 实现用户登录接口（含异常处理）— 六合一端到端验证任务
> **Created**: 2026-08-01 | **Status**: Draft → 补齐后重评
> **Language**: chinese

---

## Purpose（为什么做）

为系统提供一个**健壮的用户登录接口**：支持账号密码验证，成功返回会话凭据，失败返回明确错误码。作为六合一闭环端到端验证的真实开发载体，同时补齐登录能力的核心缺口。

---

## Outputs（交付物）

1. **登录接口**：`POST /api/auth/login`，接收 `{username, password}`，成功返回 `{token, user}`，失败返回标准错误结构
2. **异常处理**：覆盖密码错误、用户不存在、输入非法、服务端异常等场景，返回结构化错误码
3. **单元测试**：至少覆盖正常登录 + 4 类异常场景
4. **SDD 契约**：本 spec（六合一门禁要求）

---

## Acceptance Criteria（可验证 pass/fail）

- **AC-001**: `POST /api/auth/login` 存在，接收 `{username, password}` JSON，返回 `200 + {token, user}`（pass：curl 调用返回 200 且含 token / fail：404 或缺字段）
- **AC-002**: 密码错误 → 返回 `401 + {code:"INVALID_PASSWORD"}`（pass：错误码匹配 / fail：返回 200 或错误码不符）
- **AC-003**: 用户不存在 → 返回 `404 + {code:"USER_NOT_FOUND"}`（pass：错误码匹配 / fail：行为不符）
- **AC-004**: username 或 password 缺失/为空 → 返回 `400 + {code:"INVALID_INPUT"}`（pass：错误码匹配 / fail：不校验）
- **AC-005**: 服务端异常（如密码 hash 失败）→ 返回 `500 + {code:"INTERNAL_ERROR"}`，且不泄露内部堆栈（pass：500 且响应体无 traceback / fail：5xx 泄露堆栈）
- **AC-006**: 单元测试 ≥5 用例覆盖 AC-001~AC-005（pass：`pytest` 全绿 / fail：缺用例或红）
- **AC-007**: 全程可观测：flow_log 记录推进轨迹，spec_status 更新（pass：有留痕 / fail：无记录）

---

## Boundaries（不做什么）

- ❌ 不做用户注册/改密/登出（仅登录接口）
- ❌ 不做密码明文存储改造（沿用现有存储，仅验证逻辑）
- ❌ 不做前端登录页（纯后端接口）
- ❌ 不引入新框架（沿用现有 HTTP 框架）

---

## Dependencies（前置依赖）

| 依赖 | 状态 | 说明 |
|------|------|------|
| HTTP 框架（server.py 所在后端） | ✅ 已有 | 复用现有路由机制 |
| 用户数据存储 | ✅ 已有 | 读取现有用户表/文件 |
| 密码哈希工具 | ✅ 已有或标准库 | 现有 bcrypt/hashlib |
| 测试框架 pytest | ✅ 可用 | 新增测试文件 |

---

## Edge Cases（异常场景）

- **EC-001**: username/password 非法类型（非字符串）→ 400 INVALID_INPUT
- **EC-002**: 密码包含特殊字符 → 正常校验不误判
- **EC-003**: 数据库/存储读取失败 → 500 INTERNAL_ERROR 且不泄露
- **EC-004**: 并发登录同一账号 → 幂等，无副作用
- **EC-005**: 已登录用户重复登录 → 返回新 token（幂等设计）

---

## Success Criteria

- **SC-001**: 登录接口通过全部 5 个 AC 测试
- **SC-002**: 六合一门禁验证通过：spec 补齐后重评 ≥98%

---

## Assumptions

- 后端为 Python 应用（server.py 存在），用 Flask/FastAPI 或现有框架
- 用户数据已有存储层，登录只需读取校验
- 此为六合一流程验证任务，会经历门禁拦截 → 补齐 → 重评全链路

---

*军师（guihua）产出 · 补齐门禁短板 D2/D3/D4/D6 · 待重评*
