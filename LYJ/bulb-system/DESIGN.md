# 资产管理系统设计文档

## 1. 概述

### 1.1 项目背景

公司资产管理系统，针对投影仪灯泡进行管理。会服人员负责维护投影仪并更换灯泡，备用灯泡在各办公区会服处。资产管理员负责统计公司整体资产库存，与供应商对接补充库存。

### 1.2 核心流程

```
供应商供货 → 会服入库确认 → 会服取用灯泡更换投影仪 → 报备记录
                                         ↓
                              库存不足 → 跨区调拨 → 无 → 紧急供货
```

### 1.3 系统架构

| 维度 | 选择 |
|------|------|
| 应用类型 | PWA（渐进式Web应用） |
| 前端 | React + TailwindCSS |
| 后端 | Node.js + SQLite |
| 部署环境 | 云主机（2CPU/2GB/40GB SSD） |
| 主要使用场景 | 手机为主，PC为辅 |

---

## 2. 角色权限

### 2.1 角色定义

| 角色 | 说明 |
|------|------|
| admin | 超级管理员，具有所有权限，维护系统 |
| 资产管理员 | 查看数据获取信息 |
| 会服 | 维护会议室及设施，取用库存，管理本办公区库存，接收供应商发来的资产 |
| 供应商 | 在系统中录入供货信息 |

### 2.2 权限矩阵

| 功能 | admin | 资产管理员 | 会服 | 供应商 |
|------|:-----:|:----------:|:----:|:------:|
| 系统配置、用户管理 | ✅ | - | - | - |
| 批量导入数据（Excel） | ✅ | ✅ | - | - |
| 查看全局库存 | ✅ | ✅ | ✅ | - |
| 查看本办公区库存 | ✅ | ✅ | ✅ | - |
| 维护会议室/投影仪 | ✅ | - | ✅(本区) | - |
| 记录灯泡更换 | ✅ | - | ✅ | - |
| 确认入库 | ✅ | - | ✅ | - |
| 录入供货信息 | - | - | - | ✅ |
| 查看供货记录 | ✅ | ✅ | ✅ | - |
| 查看报表 | ✅ | ✅ | - | - |

### 2.3 会服权限范围

- 只能操作**本办公区**的会议室、投影仪、库存
- 可以查看**全局**办公区库存（用于协调调拨）
- 更换记录中 `from_office_id` 可选择其他办公区（记录调拨来源）

---

## 3. 数据模型

### 3.1 ER 图

```
Offices (办公区)
    │
    ├── MeetingRooms (会议室)
    │       │
    │       └── Projectors (投影仪)
    │
    └── Inventory (库存)
            │
            └── Skus (SKU)

Users (用户)
    ├── office_id → Offices (会服人员所属)
    └── supplier_id → Suppliers (供应商用户关联)

Suppliers (供应商)
    │
    └── Shipments (发货记录)
            └── recipient_id → Users (收货人)

Replacements (更换记录)
    ├── projector_id → Projectors
    ├── sku_id → Skus
    ├── from_office_id → Offices (灯泡来源)
    └── operator_id → Users
```

### 3.2 数据表 DDL

```sql
-- 用户（统一身份）
CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL, -- admin/asset_manager/facility/supplier
  real_name TEXT,
  phone TEXT,
  email TEXT,
  office_id INTEGER,   -- 会服人员所属办公区
  supplier_id INTEGER, -- 供应商用户关联
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 办公区
CREATE TABLE offices (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  location TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 会议室
CREATE TABLE meeting_rooms (
  id INTEGER PRIMARY KEY,
  office_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  floor TEXT,
  capacity_normal INTEGER,  -- 正常容纳人数
  capacity_max INTEGER,    -- 最大容纳人数
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (office_id) REFERENCES offices(id)
);

-- SKU（统一管理灯泡、投影仪等资产）
CREATE TABLE skus (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT NOT NULL,         -- bulb/projector
  specs TEXT,                  -- JSON: 扩展参数
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 投影仪
CREATE TABLE projectors (
  id INTEGER PRIMARY KEY,
  asset_code TEXT UNIQUE NOT NULL, -- 6位数字资产编码
  meeting_room_id INTEGER,
  sku_id INTEGER NOT NULL,         -- 投影仪型号关联到 sku
  bulb_sku_ids TEXT,               -- JSON: 可能适配的灯泡型号列表
  status TEXT DEFAULT 'normal',    -- normal/warning/offline
  notes TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (meeting_room_id) REFERENCES meeting_rooms(id),
  FOREIGN KEY (sku_id) REFERENCES skus(id)
);

-- 供应商
CREATE TABLE suppliers (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  contact TEXT,
  phone TEXT,
  email TEXT,
  address TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 库存（办公区 × SKU）
CREATE TABLE inventory (
  office_id INTEGER,
  sku_id INTEGER,
  quantity INTEGER DEFAULT 0,
  min_stock INTEGER,  -- 可为空，不设警戒
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (office_id, sku_id),
  FOREIGN KEY (office_id) REFERENCES offices(id),
  FOREIGN KEY (sku_id) REFERENCES skus(id)
);

-- 更换记录
CREATE TABLE replacements (
  id INTEGER PRIMARY KEY,
  projector_id INTEGER NOT NULL,
  sku_id INTEGER NOT NULL,          -- 灯泡型号
  from_office_id INTEGER NOT NULL, -- 灯泡来源办公区
  operator_id INTEGER NOT NULL,
  replaced_at DATETIME NOT NULL,
  notes TEXT,                       -- 详细备注
  photos TEXT,                      -- JSON: [{filename, caption}]
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (projector_id) REFERENCES projectors(id),
  FOREIGN KEY (sku_id) REFERENCES skus(id),
  FOREIGN KEY (from_office_id) REFERENCES offices(id),
  FOREIGN KEY (operator_id) REFERENCES users(id)
);

-- 发货记录
CREATE TABLE shipments (
  id INTEGER PRIMARY KEY,
  supplier_id INTEGER NOT NULL,
  office_id INTEGER NOT NULL,
  recipient_id INTEGER,
  tracking_number TEXT,
  carrier TEXT,
  items TEXT NOT NULL,               -- JSON: [{sku_id, quantity}]
  status TEXT DEFAULT 'pending',    -- pending/delivered
  storage_at DATETIME,              -- 入库时间（会服确认）
  notes TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
  FOREIGN KEY (office_id) REFERENCES offices(id),
  FOREIGN KEY (recipient_id) REFERENCES users(id)
);
```

### 3.3 照片存储

```
/uploads/replacements/
  └── {year}/{month}/{date}/
      └── replacement_{替换记录ID}_{序号}_{时间戳}.jpg
```

- 单次更换最多上传 **5 张**照片
- 文件名格式：`replacement_{id}_{seq}_{timestamp}.jpg`
- 数据库只存路径信息 `{filename, caption}`

---

## 4. API 设计

### 4.1 认证
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/auth/login | 登录 |
| POST | /api/auth/logout | 登出 |
| GET | /api/auth/me | 当前用户信息 |

### 4.2 办公区 Offices
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | /api/offices | 列表 | admin/资产管理员/会服(本区) |
| GET | /api/offices/:id | 详情 | admin/资产管理员/会服(本区) |
| POST | /api/offices | 创建 | admin |
| PUT | /api/offices/:id | 更新 | admin |
| DELETE | /api/offices/:id | 删除 | admin |
| POST | /api/offices/import | Excel 导入 | admin/资产管理员 |

### 4.3 会议室 Meeting Rooms
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | /api/meeting-rooms | 列表 | 会服(本区) |
| GET | /api/meeting-rooms/:id | 详情 | 会服(本区) |
| POST | /api/meeting-rooms | 创建 | admin/会服 |
| PUT | /api/meeting-rooms/:id | 更新 | admin/会服 |
| DELETE | /api/meeting-rooms/:id | 删除 | admin |
| POST | /api/meeting-rooms/import | Excel 导入 | admin/资产管理员 |

### 4.4 投影仪 Projectors
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | /api/projectors | 列表 | 会服(本区)/admin |
| GET | /api/projectors/:id | 详情 | 会服(本区)/admin |
| POST | /api/projectors | 创建 | admin/会服 |
| PUT | /api/projectors/:id | 更新 | admin/会服 |
| DELETE | /api/projectors/:id | 删除 | admin |
| POST | /api/projectors/import | Excel 导入 | admin/资产管理员 |
| PUT | /api/projectors/:id/status | 更新状态 | admin/会服(本区) |

### 4.5 SKU
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | /api/skus | 列表 | 全部 |
| GET | /api/skus/:id | 详情 | 全部 |
| POST | /api/skus | 创建 | admin |
| PUT | /api/skus/:id | 更新 | admin |
| DELETE | /api/skus/:id | 删除 | admin |
| POST | /api/skus/import | Excel 导入 | admin/资产管理员 |

### 4.6 供应商 Suppliers
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | /api/suppliers | 列表 | 全部 |
| GET | /api/suppliers/:id | 详情 | 全部 |
| POST | /api/suppliers | 创建 | admin |
| PUT | /api/suppliers/:id | 更新 | admin |
| DELETE | /api/suppliers/:id | 删除 | admin |

### 4.7 库存 Inventory
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | /api/inventory | 列表（全局/本办公区） | 全部 |
| GET | /api/inventory/alerts | 警戒提醒列表 | 全部 |
| PUT | /api/inventory | 更新库存 | admin |
| POST | /api/inventory/import | Excel 导入 | admin |

### 4.8 更换记录 Replacements
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | /api/replacements | 列表 | admin/资产管理员/会服 |
| GET | /api/replacements/:id | 详情 | admin/资产管理员/会服 |
| POST | /api/replacements | 创建 | 会服 |
| POST | /api/replacements/:id/photos | 上传照片 | 会服 |

### 4.9 发货记录 Shipments
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | /api/shipments | 列表 | 全部 |
| GET | /api/shipments/:id | 详情 | 全部 |
| POST | /api/shipments | 创建 | 供应商 |
| PUT | /api/shipments/:id | 更新 | 供应商 |
| PUT | /api/shipments/:id/tracking | 录入物流 | 供应商 |
| POST | /api/shipments/:id/deliver | 确认入库 | 会服 |
| GET | /api/shipments/supplier/:supplier_id | 供应商查看自己的发货 | 供应商 |

### 4.10 用户 Users
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | /api/users | 列表 | admin |
| GET | /api/users/:id | 详情 | admin |
| POST | /api/users | 创建 | admin |
| PUT | /api/users/:id | 更新 | admin |
| DELETE | /api/users/:id | 删除 | admin |

### 4.11 报表 Reports
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | /api/reports/inventory | 库存汇总报表 | admin/资产管理员 |
| GET | /api/reports/consumption | 消耗趋势报表 | admin/资产管理员 |
| GET | /api/reports/cost | 成本分析报表 | admin/资产管理员 |
| GET | /api/reports/projector-status | 投影仪状况报表 | admin/资产管理员 |
| GET | /api/reports/transfers | 调拨记录报表 | admin/资产管理员 |

### 4.12 分页与筛选

**分页：**
```json
GET /api/offices?page=1&page_size=20

{
  "data": [...],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 100,
    "total_pages": 5
  }
}
```

**筛选示例：**
```
GET /api/inventory?office_id=1&sku_type=bulb
GET /api/replacements?from_office_id=1&start_date=2024-01-01
```

---

## 5. 前端页面结构

### 5.1 UI 设计规范

#### 配色方案
| 用途 | 色值 |
|------|------|
| 主色 | #3B82F6 (蓝色) |
| 成功 | #10B981 (绿色) |
| 警告 | #F59E0B (橙色) |
| 危险 | #EF4444 (红色) |
| 背景 | #FFFFFF |
| 边框 | #E5E7EB |
| 文字主色 | #111827 |
| 文字次色 | #6B7280 |

#### 圆角与间距
- 卡片圆角：12px
- 按钮圆角：8px
- 输入框圆角：8px
- 内边距：16px / 24px
- 卡片间距：16px

#### 表单控件
```
输入框：
┌─────────────────────────┐
│ 输入内容                 │
└─────────────────────────┘
边框: 1px solid #E5E7EB
圆角: 8px
聚焦: 边框变 #3B82F6

下拉框：
┌─────────────────────────┐
│ 选择内容             ▼ │
└─────────────────────────┘

日期选择器（参考 React DatePicker）：
┌─────────────────────────┐
│ 📅 2024-01-15           │
└─────────────────────────┘
```

#### 按钮
```
主按钮：[ 确认操作 ]
背景: #3B82F6, 文字: #FFFFFF, 圆角: 8px

次按钮：[ 取消操作 ]
背景: #FFFFFF, 边框: 1px solid #E5E7EB, 文字: #374151

危险按钮：[ 删除 ]
背景: #EF4444, 文字: #FFFFFF
```

#### 卡片
```
┌───────────────────────────┐
│  标题                      │
│  ────────────────────────  │
│  内容内容内容               │
│                           │
└───────────────────────────┘
背景: #FFFFFF
边框: 1px solid #E5E7EB
圆角: 12px
阴影: 0 1px 3px rgba(0,0,0,0.1)
```

#### 列表
```
┌───────────────────────────┐
│ 状态  │ 名称      │ 操作  │
├───────────────────────────┤
│  ●    │ 望京SOHO │ [查看] │
│  ●    │ 银河SOHO │ [查看] │
└───────────────────────────┘
表头背景: #F9FAFB
行边框: 1px solid #E5E7EB
悬停行背景: #F3F4F6
```

#### 标签页（Tabs）
```
┌────────┐ ┌────────┐ ┌────────┐
│ 库存  │ │ 历史  │ │ 设置  │
└────────┘ └────────┘ └────────┘
选中下边框: 2px solid #3B82F6
选中文字: #3B82F6
未选中文字: #6B7280
```

### 5.3 移动端适配

- 底部 Tab 导航（手机端主要导航方式）
- 卡片单列布局
- 表单垂直排列
- 触摸友好的按钮尺寸（最小 44px）

### 5.2 角色首页

#### 会服 Dashboard
```
┌─────────────────────────────────────┐
│  🏢 望京SOHO-3层 会服中心            │
├─────────────────────────────────────┤
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐   │
│  │扫描│ │报备│ │入库│ │库存│   │
│  │投影│ │更换│ │确认│ │查看│   │
│  └─────┘ └─────┘ └─────┘ └─────┘   │
├─────────────────────────────────────┤
│  ⚠️ 库存提醒                         │
│  · 3层会议室 灯泡库存不足（1个）     │
├─────────────────────────────────────┤
│  📋 最近操作                         │
│  · 2024-01-15 投影仪A区-001 换灯泡   │
│  · 2024-01-14 投影仪A区-002 换灯泡   │
└─────────────────────────────────────┘
```

#### 资产管理员 Dashboard
```
┌─────────────────────────────────────┐
│  📊 资产管理工作台                   │
├─────────────────────────────────────┤
│  ┌────────┐ ┌────────┐ ┌────────┐   │
│  │全局库存│ │待入库  │ │供货记录│   │
│  │ 汇总   │ │发货(3) │ │        │   │
│  └────────┘ └────────┘ └────────┘   │
├─────────────────────────────────────┤
│  ⚠️ 全部警戒提醒                     │
│  · 望京SOHO-3层 某型号库存不足       │
│  · 4层会议室 投影仪离线              │
├─────────────────────────────────────┤
│  📈 快捷报表                         │
│  · 月度消耗趋势 · 成本分析           │
└─────────────────────────────────────┘
```

#### 供应商 Dashboard
```
┌─────────────────────────────────────┐
│  🚚 供应商工作台          [退出]    │
├─────────────────────────────────────┤
│  ┌─────────────────────────────────┐ │
│  │     [+ 发起供货]                │ │
│  └─────────────────────────────────┘ │
├─────────────────────────────────────┤
│  📦 待处理发货 (2)                   │
│  ┌─────────────────────────────────┐ │
│  │ #PO-2024-001                    │ │
│  │ 发往：望京SOHO-3层              │ │
│  │ [填写快递信息]                  │ │
│  └─────────────────────────────────┘ │
├─────────────────────────────────────┤
│  📋 已完成供货记录                   │
└─────────────────────────────────────┘
```

### 5.2 页面清单

#### 公共页面
| 页面 | 路径 | 说明 |
|------|------|------|
| 登录 | `/login` | |

#### 会服页面
| 页面 | 路径 | 说明 |
|------|------|------|
| 首页 | `/facility` | Dashboard |
| 扫码 | `/facility/scan` | 扫描投影仪二维码 |
| 更换报备 | `/facility/replacements/new` | 填写更换表单 |
| 更换记录 | `/facility/replacements` | 历史记录 |
| 本区库存 | `/facility/inventory` | 本办公区库存 |
| 全局库存 | `/facility/inventory/global` | 全局库存（协调用） |
| 确认入库 | `/facility/shipments` | 确认收货 |
| 投影仪列表 | `/facility/projectors` | 本区投影仪 |
| 投影仪详情 | `/facility/projectors/:id` | |

#### 资产管理员页面
| 页面 | 路径 | 说明 |
|------|------|------|
| 首页 | `/asset` | Dashboard |
| 全局库存 | `/asset/inventory` | |
| 库存警戒 | `/asset/inventory/alerts` | |
| 更换记录 | `/asset/replacements` | |
| 供货记录 | `/asset/shipments` | |
| 报表中心 | `/asset/reports` | |
| 报表-库存 | `/asset/reports/inventory` | |
| 报表-消耗 | `/asset/reports/consumption` | |
| 报表-成本 | `/asset/reports/cost` | |
| 投影仪状况 | `/asset/reports/projectors` | |
| 调拨记录 | `/asset/reports/transfers` | |

#### 供应商页面
| 页面 | 路径 | 说明 |
|------|------|------|
| 首页 | `/supplier` | Dashboard |
| 发起供货 | `/supplier/shipments/new` | |
| 待处理发货 | `/supplier/shipments/pending` | |
| 已完成发货 | `/supplier/shipments/completed` | |
| 编辑发货 | `/supplier/shipments/:id` | 填写快递信息 |

#### Admin 页面
| 页面 | 路径 | 说明 |
|------|------|------|
| 首页 | `/admin` | Dashboard |
| 用户管理 | `/admin/users` | |
| 办公区管理 | `/admin/offices` | |
| 会议室管理 | `/admin/meeting-rooms` | |
| 投影仪管理 | `/admin/projectors` | |
| SKU管理 | `/admin/skus` | |
| 供应商管理 | `/admin/suppliers` | |
| 数据导入 | `/admin/import` | |
| 系统设置 | `/admin/settings` | |

---

## 6. Excel 导入模板

### 6.1 模板总览

| 模板名 | 用途 |
|--------|------|
| offices.xlsx | 办公区 |
| meeting_rooms.xlsx | 会议室 |
| skus.xlsx | SKU（灯泡/投影仪） |
| projectors.xlsx | 投影仪 |
| suppliers.xlsx | 供应商 |
| users.xlsx | 用户 |
| inventory.xlsx | 库存 |
| shipments.xlsx | 发货记录 |

### 6.2 办公区 offices.xlsx

| 列名 | 说明 | 示例 |
|------|------|------|
| name | 名称 | 望京SOHO-3层 |
| location | 位置 | 北京市朝阳区望京街道 |

### 6.3 会议室 meeting_rooms.xlsx

| 列名 | 说明 | 示例 |
|------|------|------|
| office_name | 所属办公区名称 | 望京SOHO-3层 |
| name | 会议室名称 | 301会议室 |
| floor | 楼层 | 3 |
| capacity_normal | 正常容纳人数 | 10 |
| capacity_max | 最大容纳人数 | 15 |

### 6.4 SKU skus.xlsx

| 列名 | 说明 | 示例 |
|------|------|------|
| name | 型号名称 | EPSON ELPLP76 |
| type | 类型 | bulb / projector |
| specs | 规格参数(JSON) | {"wattage":"280W","lifespan":"2000h"} |

### 6.5 投影仪 projectors.xlsx

| 列名 | 说明 | 示例 |
|------|------|------|
| asset_code | 资产编码(6位) | 100001 |
| meeting_room | 所属会议室名称 | 301会议室 |
| office_name | 所属办公区名称 | 望京SOHO-3层 |
| sku_name | 投影仪SKU名称 | EPSON EB-955WH |
| bulb_sku_names | 适配灯泡SKU列表(JSON) | ["ELPLP76","ELPPL78"] |
| status | 状态 | normal / warning / offline |
| notes | 备注 | |

### 6.6 供应商 suppliers.xlsx

| 列名 | 说明 | 示例 |
|------|------|------|
| name | 供应商名称 | 北京市办公设备公司 |
| contact | 联系人 | 张三 |
| phone | 电话 | 13800138000 |
| email | 邮箱 | zhangsan@company.com |
| address | 地址 | 北京市朝阳区xxx |

### 6.7 用户 users.xlsx

| 列名 | 说明 | 示例 |
|------|------|------|
| username | 用户名 | facility001 |
| password | 密码(明文导入后加密) | 123456 |
| role | 角色 | admin / asset_manager / facility / supplier |
| real_name | 姓名 | 李四 |
| phone | 手机 | 13800138001 |
| email | 邮箱 | lisi@company.com |
| office_name | 所属办公区名称(会服用) | 望京SOHO-3层 |
| supplier_name | 供应商名称(供应商用户) | 北京市办公设备公司 |

### 6.8 库存 inventory.xlsx

| 列名 | 说明 | 示例 |
|------|------|------|
| office_name | 办公区名称 | 望京SOHO-3层 |
| sku_name | SKU名称 | EPSON ELPLP76 |
| quantity | 数量 | 5 |
| min_stock | 警戒线(可空) | 2 |

### 6.9 发货记录 shipments.xlsx

| 列名 | 说明 | 示例 |
|------|------|------|
| supplier_name | 供应商名称 | 北京市办公设备公司 |
| office_name | 收货办公区名称 | 望京SOHO-3层 |
| recipient_username | 收货人用户名 | facility001 |
| carrier | 快递公司 | 顺丰 |
| tracking_number | 快递单号 | SF1234567890 |
| items | 发货明细(JSON) | [{"sku_name":"ELPLP76","quantity":10}] |
| notes | 备注 | |

### 6.10 导入规则

| 规则 | 说明 |
|------|------|
| 名称匹配 | 导入时通过 name 匹配已有数据，实现增量更新 |
| 唯一性 | asset_code、username 全局唯一 |
| 外键关联 | 导入顺序有依赖，建议按依赖顺序导入 |
| 错误处理 | 整行错误跳过，生成错误日志供下载 |

---

## 7. 业务规则

### 7.1 更换记录流程

1. 会服扫描投影仪资产编码（或手动选择）
2. 选择灯泡来源办公区（可能是本区或跨区调拨）
3. 填写更换备注，上传现场照片（最多5张）
4. 提交后自动记录操作人和时间

### 7.2 入库确认流程

1. 供应商录入发货信息（快递单号、发货明细）
2. 会服收到实物后，在系统中确认入库
3. 确认后库存自动增加对应 SKU 数量
4. 发货记录状态变更为 delivered

### 7.3 库存警戒

- 每个办公区可设置库存警戒线（可选）
- 库存低于警戒线时，在 Dashboard 显示提醒
- 资产管理员可查看全部警戒提醒

### 7.4 资产编码规则

- 投影仪资产编码为 **6 位数字**
- 全局唯一，不可重复

---

## 8. 报表维度

| 报表 | 内容 |
|------|------|
| 库存汇总 | 各办公区、各型号当前库存 |
| 消耗趋势 | 按月/季度统计各型号消耗数量 |
| 成本分析 | 按供应商、按办公区的耗材成本 |
| 投影仪状况 | 各投影仪更换频率、状态分布 |
| 调拨记录 | 跨办公区调拨明细 |

---

## 9. 部署

### 9.1 环境要求

| 项目 | 要求 |
|------|------|
| CPU | 2 核 |
| 内存 | 2 GB |
| 磁盘 | 40 GB SSD |
| 操作系统 | Linux |

### 9.2 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React + TailwindCSS (PWA) |
| 后端 | Node.js |
| 数据库 | SQLite |
| Web服务器 | Nginx |

### 9.3 目录结构

```
/app
├── uploads/           # 照片存储
├── data/              # SQLite 数据库
├── dist/              # 前端构建产物
├── package.json
└── server.js          # Node.js 服务端
```
