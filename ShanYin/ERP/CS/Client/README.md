# 闪饮 ERP 前端 (React + Tailwind + shadcn/ui)

## 技术栈

- React 18 + TypeScript
- Vite 5
- Tailwind CSS 3
- shadcn/ui (Radix UI)
- React Router 6
- TanStack Query (React Query)
- Zustand

## 开发

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build
```

## 环境变量

创建 `.env` 文件：

```env
VITE_API_URL=http://localhost:8000
VITE_API_KEY=your-api-key
```

## 项目结构

```
src/
├── api/              # API 客户端
├── components/
│   ├── ui/          # shadcn/ui 组件
│   └── layout/      # 布局组件
├── pages/           # 页面组件
│   ├── Dashboard/   # 运行看板
│   ├── Entry/       # 信息录入
│   └── Finance/     # 财务管理
├── lib/             # 工具函数
└── App.tsx          # 应用入口
```

## 页面清单

- [x] Dashboard - 运行看板（统计卡片、银行账户）
- [x] Entry - 信息录入（客户、点位、供应商、SKU）
- [x] Finance - 财务管理（账户、调拨、凭证、科目）
- [ ] VC - 虚拟合同
- [ ] Logistics - 物流管理
- [ ] CashFlow - 资金流管理
- [ ] Business - 业务管理
- [ ] SupplyChain - 供应链
- [ ] Inventory - 库存看板
- [ ] Rules - 时间规则
